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

NODE="${OTTERNET_TOOLING_NODE:-clab-otternet-tool-node1}"
NAMESPACE="${OTTERNET_TOOLING_NAMESPACE:-otternet-tooling}"
IMAGE="${OTTERNET_BACKSTAGE_IMAGE:-otternet/backstage:local}"
PORTAL_IP="${OTTERNET_PORTAL_IP:-10.90.0.11}"
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
# `NODE_EXTRA_CA_CERTS` on the deployment is what closes that, pointed at the
# CA below.
#
# WHY TWO CERTIFICATES, a throwaway CA and a server certificate it signs,
# rather than one self-signed certificate: Firefox cannot be made to trust a
# self-signed server certificate at all. Marked `CA:TRUE` (as this script
# used to), Firefox trusts it as an authority and then refuses it as a server
# with MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY; without that, it is not
# an authority and nothing can install it as one. So the branch desktop showed
# a certificate warning on every fresh profile, whatever its policies said, and
# the "trusted" desktop was in fact one somebody had clicked through. Measured
# with the desktop image: the CA-signed pair loads with no warning, and Node
# accepts it through NODE_EXTRA_CA_CERTS=ca.crt (UNABLE_TO_VERIFY_LEAF_SIGNATURE
# without). The CA's key is never stored, so nothing else can ever be signed.
#
# A secret from before this change has no `ca.crt`, and is replaced: the
# restart below picks the new pair up, and the desktop step trusts the new CA.
# --------------------------------------------------------------------------
kf apply -f - < "$HERE/tooling/00-namespace.yaml" >/dev/null

if k -n "$NAMESPACE" get secret backstage-tls -o jsonpath='{.data.ca\.crt}' 2>/dev/null | grep -q .; then
    log "backstage-tls already present"
else
    if k -n "$NAMESPACE" get secret backstage-tls >/dev/null 2>&1; then
        log "backstage-tls is a self-signed certificate Firefox cannot trust -- replacing it"
        k -n "$NAMESPACE" delete secret backstage-tls >/dev/null
    fi
    log "generating a lab CA and a server certificate for $PORTAL_IP"
    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$WORK/ca.key" -out "$WORK/ca.crt" \
        -subj "/CN=OTTERNET lab CA" \
        -addext "basicConstraints=critical,CA:TRUE,pathlen:0" \
        -addext "keyUsage=critical,keyCertSign,cRLSign" \
        2>/dev/null
    openssl req -newkey rsa:2048 -nodes \
        -keyout "$WORK/tls.key" -out "$WORK/tls.csr" \
        -subj "/CN=otternet-portal" 2>/dev/null
    # 825 days: the longest validity browsers accept for a server certificate
    # from a private CA.
    printf '%s\n' \
        "subjectAltName=IP:${PORTAL_IP},IP:127.0.0.1,DNS:localhost" \
        "basicConstraints=critical,CA:FALSE" \
        "keyUsage=critical,digitalSignature,keyEncipherment" \
        "extendedKeyUsage=serverAuth" > "$WORK/leaf.ext"
    openssl x509 -req -in "$WORK/tls.csr" -CA "$WORK/ca.crt" -CAkey "$WORK/ca.key" \
        -CAcreateserial -days 825 -extfile "$WORK/leaf.ext" \
        -out "$WORK/tls.crt" 2>/dev/null
    # Copied onto the node rather than piped: kubectl reads three files here,
    # and `docker exec -i` gives one stdin.
    docker cp "$WORK/tls.crt" "$NODE:/tmp/tls.crt"
    docker cp "$WORK/tls.key" "$NODE:/tmp/tls.key"
    docker cp "$WORK/ca.crt" "$NODE:/tmp/ca.crt"
    k -n "$NAMESPACE" create secret generic backstage-tls \
        --from-file=tls.crt=/tmp/tls.crt --from-file=tls.key=/tmp/tls.key \
        --from-file=ca.crt=/tmp/ca.crt >/dev/null
    docker exec "$NODE" rm -f /tmp/tls.crt /tmp/tls.key /tmp/ca.crt
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
# have to click through. What is installed is the CA, not the server
# certificate, at the one path Firefox's `Certificates.Install` policy names in
# lab/configs/branch/desktop/firefox-policies.json. Firefox does not read the
# system store on Linux (`ImportEnterpriseRoots` is a Windows and macOS
# feature); update-ca-certificates is for curl and everything else on the box.
#
# Firefox imports the file when it STARTS. A Firefox already open when this
# runs keeps warning until it is closed and opened again.
# --------------------------------------------------------------------------
DESKTOP="${OTTERNET_BRANCH_DESKTOP:-clab-otternet-branch-desktop}"
if docker inspect "$DESKTOP" >/dev/null 2>&1; then
    k -n "$NAMESPACE" get secret backstage-tls -o jsonpath='{.data.ca\.crt}' \
        | base64 -d > "$WORK/portal-ca.crt"
    docker cp "$WORK/portal-ca.crt" "$DESKTOP:/usr/local/share/ca-certificates/otternet-portal.crt"
    docker exec "$DESKTOP" update-ca-certificates >/dev/null 2>&1
    log "portal CA trusted on $DESKTOP (an open Firefox must be restarted to pick it up)"
else
    log "$DESKTOP not running -- skipping certificate trust"
fi

log "ready: portal https://${PORTAL_IP}:32001, identity http://${PORTAL_IP}:32556/dex"
