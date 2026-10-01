#!/usr/bin/env bash
# Install Crossplane and hand the platform over to it.
#
# Run after install-cilium.sh. The split matters and is not arbitrary: Cilium is
# the CNI, so it has to be installed imperatively -- there is no pod network for
# Crossplane's own pods to run on until it is. Everything after that point is
# declarative:
#
#   install-cilium.sh   the CNI, the BGP auth secret, node labels
#   this script         Crossplane, its providers, the XRDs and Compositions
#   crossplane/         the desired state: peering, and the apps
#
# So Cilium-the-datapath is bootstrapped, and Cilium-the-network-intent -- BGP
# peering, advertisements, VIP pools, network policy -- is reconciled from XRs
# alongside the applications those policies protect.
set -euo pipefail

CROSSPLANE_VERSION="${CROSSPLANE_VERSION:-2.4.0}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KUBECONFIG_PATH="${KUBECONFIG:-$LAB_DIR/k8s/.kubeconfig/kubeconfig.yaml}"

export KUBECONFIG="$KUBECONFIG_PATH"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f "$KUBECONFIG" ]] || die "kubeconfig not found at $KUBECONFIG -- run 'make k8s' first"
kubectl get nodes >/dev/null 2>&1 || die "cannot reach the cluster with $KUBECONFIG"

# Crossplane is the first thing in this lab that needs the cluster to work from
# the *inside*: it resolves package names, pulls OCI artefacts and talks to the
# API server through its ClusterIP. All three were broken here for reasons that
# a north-south demo never touches (see docs/troubleshooting.md), so check them
# before spending five minutes watching packages fail to unpack.
say "Checking in-cluster networking (ClusterIP, DNS, egress)"
kubectl -n kube-system delete pod xp-preflight --ignore-not-found >/dev/null 2>&1 || true
if ! kubectl -n kube-system run xp-preflight --image=busybox:1.36 --restart=Never \
        --command --quiet --rm -i --timeout=120s -- sh -c '
            nc -z -w 5 "${API:-10.112.0.1}" 443 || { echo "FAIL: API ClusterIP unreachable from a pod"; exit 1; }
            nslookup xpkg.crossplane.io. >/dev/null 2>&1 || { echo "FAIL: external DNS does not resolve from a pod"; exit 1; }
            nc -z -w 8 1.1.1.1 443 || { echo "FAIL: no pod egress to the internet"; exit 1; }
            echo PREFLIGHT-OK' 2>/dev/null | grep -q PREFLIGHT-OK; then
    die "in-cluster networking preflight failed -- see docs/troubleshooting.md
     'Crossplane and anything else that runs inside the cluster'"
fi

say "Installing Crossplane $CROSSPLANE_VERSION"
helm repo add crossplane-stable https://charts.crossplane.io/stable >/dev/null 2>&1 || true
helm repo update crossplane-stable >/dev/null
helm upgrade --install crossplane crossplane-stable/crossplane \
    --version "$CROSSPLANE_VERSION" \
    --namespace crossplane-system --create-namespace \
    --wait --timeout 10m

kubectl -n crossplane-system rollout status deployment/crossplane --timeout=5m

# The DeploymentRuntimeConfigs have to exist before the Providers reference them,
# and the RBAC has to exist before the provider pods start reconciling, or the
# first few reconciles fail with forbidden errors and back off.
say "Pinning provider identities and granting them RBAC"
kubectl apply -f "$LAB_DIR/crossplane/providers/01-runtime.yaml"
kubectl apply -f "$LAB_DIR/crossplane/providers/02-rbac.yaml"

say "Installing providers and composition functions"
kubectl apply -f "$LAB_DIR/crossplane/providers/00-packages.yaml"

say "Waiting for packages to become healthy (pulling from xpkg.crossplane.io)"
for pkg in provider-helm provider-kubernetes; do
    kubectl wait "provider.pkg.crossplane.io/$pkg" \
        --for=condition=Healthy --timeout=6m \
        || die "$pkg did not become healthy: kubectl describe provider $pkg"
done
for fn in function-go-templating function-auto-ready; do
    kubectl wait "function.pkg.crossplane.io/$fn" \
        --for=condition=Healthy --timeout=6m \
        || die "$fn did not become healthy: kubectl describe function $fn"
done

# ProviderConfigs come after the providers, because their CRDs ship inside the
# provider packages.
say "Pointing both providers at this cluster"
kubectl apply -f "$LAB_DIR/crossplane/providers/03-provider-configs.yaml"

say "Installing the platform APIs (XRDs and Compositions)"
kubectl apply -f "$LAB_DIR/crossplane/platform/00-xrd-fabric-peering.yaml"
kubectl apply -f "$LAB_DIR/crossplane/platform/01-composition-fabric-peering.yaml"
kubectl apply -f "$LAB_DIR/crossplane/apps/00-xrd-fabric-app.yaml"
kubectl apply -f "$LAB_DIR/crossplane/apps/01-composition-fabric-app.yaml"

# The access broker's API. The FirewallAccess CRD is a plain CRD rather than an
# XRD because a controller of ours reconciles it onto the vSRX -- see
# crossplane/access/00-crd-firewall-access.yaml. It has to exist before the
# AppAccess composition can compose one.
kubectl apply -f "$LAB_DIR/crossplane/access/00-crd-firewall-access.yaml"
kubectl apply -f "$LAB_DIR/crossplane/access/01-xrd-app-access.yaml"
kubectl apply -f "$LAB_DIR/crossplane/access/02-composition-app-access.yaml"
kubectl apply -f "$LAB_DIR/crossplane/access/03-rbac.yaml"

for xrd in fabricpeerings.otternet.lab fabricapps.otternet.lab appaccesses.otternet.lab; do
    kubectl wait "xrd/$xrd" --for=condition=Established --timeout=2m \
        || die "$xrd never established"
done

say "Claiming the fabric peering"
kubectl apply -f "$LAB_DIR/crossplane/platform/10-peering.yaml"
kubectl wait fabricpeering/otternet --for=condition=Ready --timeout=5m \
    || die "FabricPeering did not become ready: kubectl describe fabricpeering otternet"

say "Deploying the applications"
kubectl apply -f "$LAB_DIR/crossplane/apps/10-demo.yaml"
# OTTERNET_SKIP_OBSERVABILITY=1 is set by this repository's `invoke
# cluster`, which delivers its own kube-prometheus-stack (`otternet-metrics`)
# through Vidra. Two releases of that chart in one cluster contend for the same
# CRDs and the second fails `invalid ownership metadata`, so this one must not
# be applied there at all -- deleting it afterwards, as the handover does for
# the others, is too late. Unset, the lab behaves exactly as it always has.
if [[ "${OTTERNET_SKIP_OBSERVABILITY:-0}" != "1" ]]; then
    kubectl apply -f "$LAB_DIR/crossplane/apps/20-observability.yaml"
fi

# The access broker is a FabricApp like any other -- it needs a VIP the branch
# can reach before anybody has been granted anything. Its two images are built
# on this host and imported into the nodes, because there is no registry here.
if docker image inspect otternet/access-portal:local >/dev/null 2>&1 \
   && docker image inspect otternet/fw-controller:local >/dev/null 2>&1; then
    "$LAB_DIR/scripts/access-images.sh"
    kubectl apply -f "$LAB_DIR/crossplane/access/10-access-portal.yaml"
else
    printf '\033[1;33mwarning: access broker images missing -- run: make access-images && make access\033[0m\n'
fi

# The observability stack is a real chart: an operator, a dozen CRDs, and
# Prometheus itself. Give it room.
say "Waiting for the applications (kube-prometheus-stack takes a few minutes)"
kubectl wait fabricapp/otternet-demo --for=condition=Ready --timeout=6m \
    || printf '\033[1;33mwarning: otternet-demo not ready yet\033[0m\n'
if [[ "${OTTERNET_SKIP_OBSERVABILITY:-0}" != "1" ]]; then
    kubectl wait fabricapp/otternet-observability --for=condition=Ready --timeout=12m \
        || printf '\033[1;33mwarning: otternet-observability not ready yet -- kubectl describe fabricapp otternet-observability\033[0m\n'
fi
if kubectl get fabricapp otternet-access >/dev/null 2>&1; then
    kubectl wait fabricapp/otternet-access --for=condition=Ready --timeout=6m \
        || printf '\033[1;33mwarning: otternet-access not ready yet -- kubectl describe fabricapp otternet-access\033[0m\n'
fi

say "Done. Platform state:"
kubectl get fabricpeering,fabricapp
echo
kubectl get ciliumbgpclusterconfig,ciliumbgpadvertisement,ciliumloadbalancerippool
echo
kubectl get svc -A -l otternet.lab/advertise=true

cat <<'EOF'

Next:
  make xp                 # what Crossplane is managing, and whether it is healthy
  make xp-drift           # prove the XR is the source of truth
  make grafana            # the VIP, and how to reach it from the app tenant
  make verify             # end-to-end checks across fabric, security and k8s

EOF
