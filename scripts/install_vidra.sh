#!/usr/bin/env bash
# Install the Vidra operator and point it at this Infrahub.
#
# Vidra closes the last gap in the chain: Infrahub renders the Crossplane
# manifests, and this operator applies them to the cluster when their checksum
# moves. Because the syncs are pinned to `main`, the trigger is a MERGE -- work
# on a feature branch regenerates that branch's artifacts and they go nowhere.
#
# Everything committed lives in vidra/. The one thing that is not committed is
# the credential, which is created here from the environment.
#
# ORDER IS LOAD-BEARING. The operator reads its ConfigMap once, at startup
# (InitConfigWithClient), so the namespace, the ConfigMap, the Secret and the
# CRD shim all have to exist BEFORE the chart is installed. Install the chart
# first and the operator keeps its own defaults -- including queryName
# "ArtifactIDs", which this repository does not register, giving
# `query failed with status 404 Not Found` on every sync.
#
# Usage:  scripts/install_vidra.sh
# Env:    KUBECONFIG              defaults to the lab's kubeconfig
#         INFRAHUB_USERNAME       defaults to admin
#         INFRAHUB_PASSWORD       defaults to infrahub
#         INFRAHUB_CLUSTER_URL    how the CLUSTER reaches Infrahub; must match
#                                 the infrahubAPIURL in vidra/infrahub-syncs.yaml
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LAB_KUBECONFIG="${LAB_KUBECONFIG:-$REPO_DIR/../lab/k8s/.kubeconfig/kubeconfig.yaml}"
export KUBECONFIG="${KUBECONFIG:-$LAB_KUBECONFIG}"

INFRAHUB_USERNAME="${INFRAHUB_USERNAME:-admin}"
INFRAHUB_PASSWORD="${INFRAHUB_PASSWORD:-infrahub}"
INFRAHUB_CLUSTER_URL="${INFRAHUB_CLUSTER_URL:-http://172.20.41.1:8000}"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32mok\033[0m    %s\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f "$KUBECONFIG" ]] || die "kubeconfig not found at $KUBECONFIG -- is the cluster up? (invoke cluster)"
kubectl get nodes >/dev/null 2>&1 || die "cannot reach the cluster with $KUBECONFIG"

# The label value the operator matches on is the BARE HOST -- no scheme, no
# port. It derives it by splitting the API URL on ":" and trimming "//", which
# it has to do because a colon is not a legal character in a label value. Get
# this wrong and the operator reports "no secret found with InfrahubAPIURL",
# having looked right past a Secret that is otherwise perfect.
API_HOST="$(printf '%s' "$INFRAHUB_CLUSTER_URL" | sed -E 's#^[a-z]+://##; s#:[0-9]+$##')"

# Guard the single most silent misconfiguration there is: a sync whose
# infrahubAPIURL does not match the Secret's label matches no Secret, and a sync
# that cannot authenticate looks a lot like one with nothing to do.
if ! grep -q "$INFRAHUB_CLUSTER_URL" "$REPO_DIR/vidra/infrahub-syncs.yaml"; then
    die "INFRAHUB_CLUSTER_URL ($INFRAHUB_CLUSTER_URL) does not appear in vidra/infrahub-syncs.yaml.
     The Secret's label is derived from this URL, and the operator selects the
     Secret by that label, so the two must agree. Fix one or the other."
fi

say "Checking the cluster can reach Infrahub at $INFRAHUB_CLUSTER_URL"
# From a pod's point of view Infrahub is on the management gateway, not
# localhost: inside a node, localhost is the node. The check runs in the
# cluster rather than on this host for exactly that reason.
if kubectl -n kube-system delete pod vidra-preflight --ignore-not-found >/dev/null 2>&1; then :; fi
if kubectl -n kube-system run vidra-preflight --image=busybox:1.36 --restart=Never \
        --command --timeout=120s --attach --rm -- \
        wget -q -O /dev/null --timeout=10 "$INFRAHUB_CLUSTER_URL/api/config" >/dev/null 2>&1; then
    ok "a pod can reach Infrahub"
else
    die "a pod cannot reach Infrahub at $INFRAHUB_CLUSTER_URL.
     The operator authenticates over this URL, so it will fail the same way.
     Check that Infrahub publishes 8000 on the containerlab management bridge."
fi

say "Creating the namespace"
kubectl create namespace vidra-system --dry-run=client -o yaml | kubectl apply -f -

say "Applying the operator configuration"
# Found by its `app: vidra` label, not by name or namespace.
kubectl apply -f "$REPO_DIR/vidra/vidra-config.yaml"

say "Creating the Infrahub credential"
# A USERNAME AND PASSWORD, not an API token: the operator exchanges them at
# POST /api/auth/login. An INFRAHUB_API_TOKEN-shaped Secret does not
# authenticate, and the failure is not obviously a credential problem.
kubectl -n vidra-system create secret generic infrahub-credentials \
    --from-literal=username="$INFRAHUB_USERNAME" \
    --from-literal=password="$INFRAHUB_PASSWORD" \
    --dry-run=client -o yaml | kubectl apply -f -
kubectl -n vidra-system label secret infrahub-credentials "infrahub-api-url=$API_HOST" --overwrite
ok "labelled infrahub-api-url=$API_HOST"

# Secrets are selected by label across the whole cluster, newest first, so a
# second matching Secret is a hazard rather than a fallback.
matches="$(kubectl get secrets -A -l "infrahub-api-url=$API_HOST" --no-headers 2>/dev/null | wc -l)"
[[ "$matches" -le 1 ]] || printf '\033[1;33m  warn  %s Secrets carry this label; the operator takes the newest\033[0m\n' "$matches"

say "Registering the InfrahubWriteBack CRD shim"
# Load-bearing. The pinned image runs a third controller for a kind the upstream
# 0.0.6 chart does not install; its informer cannot build a cache for a kind the
# API server does not know, so the manager exits after about two minutes and the
# pod crash-loops. Delivery still appears to work, because each restart
# re-reconciles everything -- which is what makes it worth stating plainly.
kubectl apply -f "$REPO_DIR/vidra/writeback-crd-shim.yaml"

say "Installing the operator"
helm repo add vidra https://infrahub-operator.github.io/vidra >/dev/null 2>&1 || true
helm repo update vidra >/dev/null
helm upgrade --install vidra vidra/vidra-operator \
    --namespace vidra-system \
    --values "$REPO_DIR/vidra/helm-values.yaml" \
    --wait --timeout 5m

say "Waiting for the operator to be ready"
kubectl -n vidra-system rollout status deploy/vidra-vidra-operator-controller-manager --timeout=5m

# The ConfigMap is read at startup. It was applied before the chart above, so
# this is belt and braces -- but a re-run of this script against an operator
# that booted with a stale ConfigMap would otherwise leave it stale.
say "Restarting the operator so it reads the current configuration"
kubectl -n vidra-system rollout restart deploy/vidra-vidra-operator-controller-manager
kubectl -n vidra-system rollout status deploy/vidra-vidra-operator-controller-manager --timeout=5m

say "Declaring the syncs"
kubectl apply -f "$REPO_DIR/vidra/infrahub-syncs.yaml"

say "Done. Watch delivery with:"
printf '  kubectl get infrahubsync -o custom-columns=NAME:.metadata.name,STATE:.status.syncState,LAST:.status.lastSyncTime,ERROR:.status.lastError\n'
printf '  kubectl get vidraresource -o custom-columns=NAME:.metadata.name,STATE:.status.DeployState\n\n'
printf '\033[1;33mNote: syncState Succeeded over an EMPTY set is still Succeeded.\033[0m\n'
printf '  Check the VidraResource, not just the sync -- an artefactName that does not\n'
printf '  match .infrahub.yml exactly returns no artifacts and reports success.\n'
