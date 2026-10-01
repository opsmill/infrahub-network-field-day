#!/usr/bin/env bash
# Build the access broker's two images and put them where k3s can find them.
#
# There is no registry in this lab, and the k3s nodes are containers with their
# own containerd -- they cannot see the host's docker images. So each image is
# built here and imported into every node's image store directly. The
# alternative, standing up a registry node and pointing three k3s nodes at it
# over the management network, is more moving parts than the thing it serves.
#
# Both Deployments set imagePullPolicy: IfNotPresent for the same reason. With
# the default policy a `:local` tag would still be treated as present-if-present,
# but stating it means a typo in a tag fails as ErrImageNeverPull rather than as
# a confusing attempt to reach docker.io.
set -euo pipefail

LAB="${OTTERNET_LAB:-otternet}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

IMAGES=(
    "otternet/access-portal:local|$LAB_DIR/k8s/access/portal"
    "otternet/fw-controller:local|$LAB_DIR/k8s/access/fw-controller"
)

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

say "Building the access broker images"
for entry in "${IMAGES[@]}"; do
    tag="${entry%%|*}"; context="${entry##*|}"
    printf '  %s\n' "$tag"
    docker build -q -t "$tag" "$context" >/dev/null || die "build failed: $tag"
done

nodes=$(docker ps --format '{{.Names}}' | grep -E "^clab-$LAB-k8s-node[0-9]+$" | sort || true)
[[ -n "$nodes" ]] || die "no k3s nodes running -- deploy the lab first:
     make deploy"

say "Importing into each k3s node's containerd"
for node in $nodes; do
    for entry in "${IMAGES[@]}"; do
        tag="${entry%%|*}"
        printf '  %-22s <- %s\n' "$node" "$tag"
        # -n k8s.io is the namespace the kubelet looks in; an image imported
        # into the default containerd namespace is present on the node and
        # invisible to Kubernetes, which presents as ErrImageNeverPull with the
        # image sitting right there in `ctr images ls`.
        docker save "$tag" \
            | docker exec -i "$node" ctr -a /run/k3s/containerd/containerd.sock \
                  -n k8s.io images import - >/dev/null \
            || die "import of $tag into $node failed"
    done
done

say "Done. Restart the workloads if they were already running:"
cat <<'HINT'

  kubectl -n otternet-access rollout restart deploy/access-portal deploy/fw-controller

HINT
