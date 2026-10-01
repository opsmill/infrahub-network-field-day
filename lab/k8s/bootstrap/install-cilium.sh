#!/usr/bin/env bash
# Install Cilium into the k3s cluster and wire it to the EVPN fabric.
#
# Run after `make deploy` has the fabric up and the k3s nodes Ready-but-unready
# (they stay NotReady until a CNI is installed, which is expected).
set -euo pipefail

CILIUM_VERSION="${CILIUM_VERSION:-1.18.6}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KUBECONFIG_PATH="${KUBECONFIG:-$LAB_DIR/k8s/.kubeconfig/kubeconfig.yaml}"

export KUBECONFIG="$KUBECONFIG_PATH"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f "$KUBECONFIG" ]] || die "kubeconfig not found at $KUBECONFIG -- is k8s-node1 up? (docker logs clab-otternet-k8s-node1)"

# k3s writes 127.0.0.1 into the kubeconfig. Point it at the node's MANAGEMENT
# address, not the fabric one: 10.110.0.11 lives inside VRF K8S_PROD and the
# host has no route into it (the switch management interfaces are in VRF MGMT,
# which deliberately does not route to the tenants). k3s was started with
# --tls-san 172.20.41.41 so the served certificate is valid for this address.
# Cilium's own k8sServiceHost stays on the fabric address -- the agents run
# inside the cluster, where that is the right way to reach the API.
say "Pointing kubeconfig at the management API address"
sed -i -E 's|server: https://(127.0.0.1\|10.110.0.11):6443|server: https://172.20.41.41:6443|' "$KUBECONFIG"

say "Waiting for all three k3s nodes to register"
for _ in $(seq 1 60); do
    count=$(kubectl get nodes --no-headers 2>/dev/null | wc -l || echo 0)
    [[ "$count" -ge 3 ]] && break
    sleep 5
done
kubectl get nodes -o wide
[[ "$(kubectl get nodes --no-headers | wc -l)" -ge 3 ]] || die "fewer than 3 nodes registered"

# The BGP cluster config selects on this label, so BGP is opt-in per node.
say "Labelling nodes for BGP participation"
kubectl label nodes --all otternet.lab/bgp=true --overwrite

# MD5 secret matching the leaves' cleartext_password in the AVD vars.
say "Creating the BGP session authentication secret"
kubectl create namespace kube-system --dry-run=client -o yaml | kubectl apply -f -
kubectl -n kube-system create secret generic otternet-bgp-auth \
    --from-literal=password='Otternet-Cilium' \
    --dry-run=client -o yaml | kubectl apply -f -

say "Installing Cilium $CILIUM_VERSION"
helm repo add cilium https://helm.cilium.io/ >/dev/null 2>&1 || true
helm repo update cilium >/dev/null
helm upgrade --install cilium cilium/cilium \
    --version "$CILIUM_VERSION" \
    --namespace kube-system \
    --values "$LAB_DIR/k8s/helm/cilium-values.yaml" \
    --wait --timeout 10m

say "Waiting for Cilium to go ready"
kubectl -n kube-system rollout status daemonset/cilium --timeout=5m
kubectl wait --for=condition=Ready nodes --all --timeout=5m

# This script deliberately stops here.
#
# BGP peering, the advertisements, the LoadBalancer pools, the network policies
# and the applications themselves used to be applied from k8s/manifests/ at this
# point. They are now Crossplane's: see crossplane/ and
# k8s/bootstrap/install-crossplane.sh.
#
# The split is where the bootstrap problem actually is. Cilium is the CNI, so it
# cannot be reconciled by a controller that needs a pod network to run in -- it
# has to be installed imperatively, once, from outside. Everything downstream of
# a working pod network can be declarative, and is.
#
# What that leaves here is the irreducible bootstrap: the CNI, the BGP session
# password, and the node labels that decide which nodes speak BGP at all.

say "Done. Cluster state:"
kubectl get nodes -o wide

cat <<'EOF'

Cilium is up and the nodes are Ready. Nothing is peering with the fabric yet --
the peering is a Crossplane resource.

Next:
  make crossplane     # Crossplane, the platform APIs, the peering and the apps
  make k8s-bgp        # BGP peering state from the Cilium side (after the above)

EOF
