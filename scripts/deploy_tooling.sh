#!/usr/bin/env bash
# Deploy the tooling cluster's contents: Dex, and the Backstage service portal.
#
# The tooling cluster is the one piece of this lab that is NOT delivered by
# Infrahub, and cannot be. It carries the identity provider Infrahub logs users
# in against and the portal people request services through, so anything that
# waited on an Infrahub merge to exist would have to exist before it could be
# merged. See lab/scripts/tooling-bridge.sh for the other half of that argument.
#
# Idempotent. Safe to re-run; it is how the manifests are rolled out after an
# edit, and how the image is refreshed after a rebuild.
set -euo pipefail

NODE="${NFD41_TOOLING_NODE:-clab-nfd41-tool-node1}"
NAMESPACE="${NFD41_TOOLING_NAMESPACE:-nfd41-tooling}"
IMAGE="${NFD41_BACKSTAGE_IMAGE:-nfd41/backstage:local}"
PORTAL_IP="${NFD41_PORTAL_IP:-10.90.0.11}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

log() { echo "[tooling] $*"; }
k() { docker exec "$NODE" kubectl "$@"; }
kf() { docker exec -i "$NODE" kubectl "$@"; }

if ! docker inspect "$NODE" >/dev/null 2>&1; then
    echo "[tooling] $NODE is not running -- deploy the lab first" >&2
    exit 1
fi

# --------------------------------------------------------------------------
# 1. The portal's TLS certificate.
#
# WHY THERE IS A CERTIFICATE AT ALL, since nothing here is secret: the frontend
# calls `crypto.randomUUID`, which the browser populates only in a SECURE
# CONTEXT. Served over plain HTTP at a bare IP the portal signs a user in and
# then dies with `globalThis.crypto.randomUUID is not a function` -- a failure
# that names a missing function rather than a missing protocol. `localhost` is
# a secure context by exception, which is why this is invisible from the host.
#
# WHY IT IS GENERATED HERE rather than by Backstage itself, which can do this:
# its generated certificate lives in the container's filesystem, so it is a new
# certificate on every pod restart -- and the branch user has to accept a new
# browser exception each time. This one lives in a Secret and survives.
#
# WHY NODE HAS TO TRUST IT: Backstage's sign-in resolver calls its own catalog
# back through `https://localhost:7007`. Node rejects the self-signed
# certificate, and the error surfaces inside the OIDC popup as a `FetchError`
# against a catalog URL, which reads as a broken catalog rather than as TLS.
# `NODE_EXTRA_CA_CERTS` on the deployment is what closes that, and it needs a
# certificate that is the same file on disk as the one being served.
# --------------------------------------------------------------------------
kf apply -f - < "$HERE/tooling/00-namespace.yaml" >/dev/null

if k -n "$NAMESPACE" get secret backstage-tls >/dev/null 2>&1; then
    log "backstage-tls already present"
else
    log "generating a self-signed certificate for $PORTAL_IP"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$WORK/tls.key" -out "$WORK/tls.crt" \
        -subj "/CN=nfd41-portal" \
        -addext "subjectAltName=IP:${PORTAL_IP},IP:127.0.0.1,DNS:localhost" \
        -addext "basicConstraints=critical,CA:TRUE" \
        2>/dev/null
    # Copied onto the node rather than piped: kubectl reads two files here, and
    # `docker exec -i` gives one stdin.
    docker cp "$WORK/tls.crt" "$NODE:/tmp/tls.crt"
    docker cp "$WORK/tls.key" "$NODE:/tmp/tls.key"
    k -n "$NAMESPACE" create secret generic backstage-tls \
        --from-file=tls.crt=/tmp/tls.crt --from-file=tls.key=/tmp/tls.key >/dev/null
    docker exec "$NODE" rm -f /tmp/tls.crt /tmp/tls.key
    log "backstage-tls created"
fi

# --------------------------------------------------------------------------
# 2. The portal image.
#
# There is no registry in this lab, and the node's containerd cannot see the
# host's docker images, so the image is carried across by hand. Skipped when the
# node already holds the same digest, because the copy is ~200MB.
# --------------------------------------------------------------------------
if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
    echo "[tooling] $IMAGE is not built -- run 'docker compose --profile build-only build backstage'" >&2
    exit 1
fi

want="$(docker image inspect "$IMAGE" --format '{{.Id}}')"
have="$(docker exec "$NODE" ctr -n k8s.io images ls "name==docker.io/${IMAGE}" -q 2>/dev/null || true)"
if [ -n "$have" ] && docker exec "$NODE" ctr -n k8s.io images ls "name==docker.io/${IMAGE}" 2>/dev/null | grep -q "$(echo "$want" | cut -d: -f2 | head -c 12)"; then
    log "$IMAGE already on $NODE"
else
    # STREAMED, not staged. Writing the tar out and then `docker cp`ing it put
    # two full copies of a ~200MB image through disk and page cache, on a host
    # that is also running the lab -- and the deploy was killed for memory
    # rather than failing, which reads as an infrastructure hiccup. `ctr import`
    # reads a tar on stdin, so neither copy is needed.
    #
    # `set -o pipefail` is on via `set -euo`, so a failure in `docker save`
    # still fails the script rather than being masked by a happy `ctr`.
    log "importing $IMAGE into $NODE"
    docker save "$IMAGE" | docker exec -i "$NODE" ctr -n k8s.io images import - >/dev/null
fi

# --------------------------------------------------------------------------
# 3. The manifests, then a restart.
#
# `rollout restart` rather than relying on apply: the image tag never changes,
# so a reimported image is invisible to the Deployment, and a ConfigMap change
# does not restart the pods that read it as environment.
# --------------------------------------------------------------------------
for manifest in "$HERE"/tooling/*.yaml; do
    log "applying $(basename "$manifest")"
    kf apply -f - < "$manifest" >/dev/null
done

# DEX FIRST, AND FULLY, BEFORE BACKSTAGE IS TOUCHED. Restarting both at once
# raced them, and Backstage lost: its OIDC authenticator calls `Issuer.discover`
# ONCE at startup and keeps the promise, so a single boot-time ECONNREFUSED is
# cached for the life of the process. Dex then comes up, is reachable from
# everywhere, and every sign-in still fails with
#
#   Request failed with status 500 connect ECONNREFUSED 10.90.0.11:32556
#
# forever -- a permanent failure caused by a few seconds of startup ordering,
# and one that looks like a network fault because the address in the message is
# reachable by the time anyone tests it. Recovery is a Backstage restart, which
# is exactly what makes it hard to attribute: the fix for the symptom is also
# the thing that hides the cause.
#
# `rollout status` on Dex is the right gate rather than a sleep, because Dex's
# readiness probe is a GET of `/dex/.well-known/openid-configuration` -- the very
# document Backstage is about to fetch. Ready means discovery is being served.
k -n "$NAMESPACE" rollout restart deploy/dex >/dev/null
k -n "$NAMESPACE" rollout status deploy/dex --timeout=180s
k -n "$NAMESPACE" rollout restart deploy/backstage >/dev/null
k -n "$NAMESPACE" rollout status deploy/backstage --timeout=300s

# --------------------------------------------------------------------------
# 4. Trust the portal's certificate on the branch desktop.
#
# BEST EFFORT, and skipped silently when the desktop is not running: the portal
# works without this, it just greets the user with a certificate warning they
# have to click through. Firefox reads the system trust store only because
# `security.enterprise_roots.enabled` is set in
# lab/configs/branch/desktop/firefox-policies.json -- installing the certificate
# without that preference changes nothing, and setting the preference without
# installing the certificate changes nothing either.
# --------------------------------------------------------------------------
DESKTOP="${NFD41_BRANCH_DESKTOP:-clab-nfd41-branch-desktop}"
if docker inspect "$DESKTOP" >/dev/null 2>&1; then
    k -n "$NAMESPACE" get secret backstage-tls -o jsonpath='{.data.tls\.crt}' \
        | base64 -d > "$WORK/portal.crt"
    docker cp "$WORK/portal.crt" "$DESKTOP:/usr/local/share/ca-certificates/nfd41-portal.crt"
    docker exec "$DESKTOP" update-ca-certificates >/dev/null 2>&1
    log "portal certificate trusted on $DESKTOP"
else
    log "$DESKTOP not running -- skipping certificate trust"
fi

log "ready: portal https://${PORTAL_IP}:32001, identity http://${PORTAL_IP}:32556/dex"
