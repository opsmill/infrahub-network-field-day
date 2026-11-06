#!/usr/bin/env bash
# Make sure the three lab images that no public registry carries exist locally:
# the Arista cEOS image, the Junos vSRX image and the branch desktop image.
#
# For each image, in order, the first source that works wins:
#
#   1. the image is already in the local Docker image store;
#   2. it is pulled from OpsMill's registry and tagged with the local name the
#      topology uses, so nothing else in the lab has to know where it came from;
#   3. it is built from the raw vendor file in $OTTERNET_IMAGES_DIR (cEOS tar,
#      vSRX qcow2) or from the source in this repository (desktop);
#   4. before step 3, a missing raw vendor file is downloaded from the OpsMill
#      Google Drive folder with rclone, when an rclone remote for Drive is set up.
#
# Usage: images.sh [--check]
#   --check   only report what is missing; pull and build nothing. Exits 1 when
#             an image is missing.
#
# Settings (environment):
#   OTTERNET_CEOS_IMAGE     local cEOS image name       (ceos:4.36.0.1F)
#   OTTERNET_VSRX_IMAGE     local vSRX image name       (vrnetlab/juniper_vsrx:22.3R1.11)
#   OTTERNET_DESKTOP_IMAGE  local desktop image name    (otternet/branch-desktop:local)
#   OTTERNET_IMAGE_REGISTRY registry to pull from       (registry.opsmill.io/external)
#                           set it to "" to never pull
#   OTTERNET_IMAGES_DIR     where raw vendor files live (/images)
#   OTTERNET_GDRIVE_REMOTE  rclone remote for Drive     (gdrive)
#   OTTERNET_GDRIVE_FOLDER  Drive folder ID             (the OpsMill "Images" folder)
set -uo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECK_ONLY=0
[[ "${1:-}" == "--check" ]] && CHECK_ONLY=1

CEOS_VERSION="${CEOS_VERSION:-4.36.0.1F}"
VSRX_VERSION="${VSRX_VERSION:-22.3R1.11}"
CEOS_IMAGE="${OTTERNET_CEOS_IMAGE:-ceos:$CEOS_VERSION}"
VSRX_IMAGE="${OTTERNET_VSRX_IMAGE:-vrnetlab/juniper_vsrx:$VSRX_VERSION}"
DESKTOP_IMAGE="${OTTERNET_DESKTOP_IMAGE:-otternet/branch-desktop:local}"
REGISTRY="${OTTERNET_IMAGE_REGISTRY-registry.opsmill.io/external}"
IMAGES_DIR="${OTTERNET_IMAGES_DIR:-/images}"
GDRIVE_REMOTE="${OTTERNET_GDRIVE_REMOTE:-gdrive}"
GDRIVE_FOLDER="${OTTERNET_GDRIVE_FOLDER:-1FISplMk6UxB2hmuG4PuEZcSlNkXrynVr}"
GDRIVE_URL="https://drive.google.com/drive/folders/$GDRIVE_FOLDER"

CEOS_FILE="cEOS-lab-$CEOS_VERSION.tar"
VSRX_FILE="junos-vsrx3-x86-64-$VSRX_VERSION.qcow2"

# The desktop image in the registry is tagged with the commit that last changed
# its source, so a change to the desktop is never served by an older image: the
# new tag is not in the registry yet, the pull fails, and the image is built.
DESKTOP_SOURCE="$LAB_DIR/configs/branch/desktop"
DESKTOP_TAG="$(git -C "$LAB_DIR" log -1 --format=%H -- configs/branch/desktop 2>/dev/null | cut -c1-7)"
DESKTOP_LABEL="org.opsmill.otternet.desktop-source"

rc=0
say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32mok\033[0m    %s\n' "$*"; }
info() { printf '  ..    %s\n' "$*"; }
bad()  { printf '  \033[1;31mFAIL\033[0m  %s\n' "$*"; rc=1; }

present() { docker image inspect "$1" >/dev/null 2>&1; }

# pull <registry reference> <local name>
pull() {
    local remote="$1" local_name="$2"
    [[ -n "$REGISTRY" ]] || return 1
    info "pulling $remote"
    docker pull -q "$remote" >/dev/null 2>&1 || { info "not available from $remote"; return 1; }
    docker tag "$remote" "$local_name"
}

# fetch_raw <file name>: make sure $IMAGES_DIR/<file> exists, downloading it from
# Google Drive when it does not and rclone has a Drive remote.
fetch_raw() {
    local file="$1"
    [[ -f "$IMAGES_DIR/$file" ]] && return 0
    if ! command -v rclone >/dev/null 2>&1 || ! rclone listremotes 2>/dev/null | grep -qx "$GDRIVE_REMOTE:"; then
        info "$IMAGES_DIR/$file is missing, and there is no rclone remote '$GDRIVE_REMOTE' to download it with"
        return 1
    fi
    if [[ ! -w "$IMAGES_DIR" ]]; then
        info "$IMAGES_DIR is not writable; create it first: sudo install -d -o \"\$USER\" $IMAGES_DIR"
        return 1
    fi
    info "downloading $file from Google Drive ($GDRIVE_REMOTE:)"
    rclone copy "$GDRIVE_REMOTE:" "$IMAGES_DIR" --drive-root-folder-id "$GDRIVE_FOLDER" \
        --include "/$file" --stats-one-line --stats 30s
    [[ -f "$IMAGES_DIR/$file" ]]
}

ensure_ceos() {
    if present "$CEOS_IMAGE"; then ok "cEOS $CEOS_IMAGE"; return; fi
    if (( CHECK_ONLY )); then bad "cEOS $CEOS_IMAGE missing -- run: make -C lab images"; return; fi
    say "cEOS image $CEOS_IMAGE"
    # The registry copy was made with `docker import` of the same tar, so it is
    # the same filesystem layer under a different name.
    if pull "$REGISTRY/ceos-image:$CEOS_VERSION" "$CEOS_IMAGE"; then ok "cEOS $CEOS_IMAGE"; return; fi
    if fetch_raw "$CEOS_FILE"; then
        info "importing $IMAGES_DIR/$CEOS_FILE"
        docker import "$IMAGES_DIR/$CEOS_FILE" "$CEOS_IMAGE" >/dev/null && { ok "cEOS $CEOS_IMAGE"; return; }
    fi
    bad "cEOS $CEOS_IMAGE could not be pulled or imported.
     Get $CEOS_FILE from the OpsMill Drive folder ($GDRIVE_URL)
     or from arista.com (free account), put it in $IMAGES_DIR, and run this again."
}

ensure_vsrx() {
    if present "$VSRX_IMAGE"; then ok "vSRX $VSRX_IMAGE"; return; fi
    if (( CHECK_ONLY )); then bad "vSRX $VSRX_IMAGE missing -- run: make -C lab images"; return; fi
    say "vSRX image $VSRX_IMAGE"
    if pull "$REGISTRY/juniper_vsrx:$VSRX_VERSION" "$VSRX_IMAGE"; then ok "vSRX $VSRX_IMAGE"; return; fi
    if fetch_raw "$VSRX_FILE"; then
        # build-vsrx.sh always names its image vrnetlab/juniper_vsrx:<version>.
        if "$LAB_DIR/scripts/build-vsrx.sh" "$IMAGES_DIR/$VSRX_FILE" \
            && docker tag "vrnetlab/juniper_vsrx:$VSRX_VERSION" "$VSRX_IMAGE"; then
            ok "vSRX $VSRX_IMAGE"; return
        fi
    fi
    bad "vSRX $VSRX_IMAGE could not be pulled or built.
     Get $VSRX_FILE from the OpsMill Drive folder ($GDRIVE_URL)
     or Juniper's free evaluation download
     (https://support.juniper.net/support/downloads/?p=vsrxeval),
     put it in $IMAGES_DIR, and run this again."
}

# Whether the local desktop image was made from the current source: built here
# with the source label, or pulled from the registry under the current tag.
# A name given in OTTERNET_DESKTOP_IMAGE is trusted as it is.
desktop_current() {
    [[ -n "${OTTERNET_DESKTOP_IMAGE:-}" || -z "$DESKTOP_TAG" ]] && return 0
    local id label
    id="$(docker image inspect -f '{{.Id}}' "$DESKTOP_IMAGE" 2>/dev/null)" || return 1
    label="$(docker image inspect -f "{{index .Config.Labels \"$DESKTOP_LABEL\"}}" "$DESKTOP_IMAGE" 2>/dev/null)"
    [[ "$label" == "$DESKTOP_TAG" ]] && return 0
    [[ "$id" == "$(docker image inspect -f '{{.Id}}' "$REGISTRY/otternet-branch-desktop:$DESKTOP_TAG" 2>/dev/null)" ]]
}

ensure_desktop() {
    if present "$DESKTOP_IMAGE"; then
        if desktop_current; then ok "branch desktop $DESKTOP_IMAGE"; return; fi
        if (( CHECK_ONLY )); then
            bad "branch desktop $DESKTOP_IMAGE is older than its source (commit $DESKTOP_TAG) -- run: make -C lab images"
            return
        fi
        info "$DESKTOP_IMAGE was not made from the current source (commit $DESKTOP_TAG); replacing it"
    elif (( CHECK_ONLY )); then
        bad "branch desktop $DESKTOP_IMAGE missing -- run: make -C lab images"; return
    fi
    say "Branch desktop image $DESKTOP_IMAGE"
    if [[ -n "$DESKTOP_TAG" ]] && pull "$REGISTRY/otternet-branch-desktop:$DESKTOP_TAG" "$DESKTOP_IMAGE"; then
        ok "branch desktop $DESKTOP_IMAGE"; return
    fi
    info "building from $DESKTOP_SOURCE"
    if docker build -q --label "$DESKTOP_LABEL=$DESKTOP_TAG" -t "$DESKTOP_IMAGE" "$DESKTOP_SOURCE" >/dev/null; then
        ok "branch desktop $DESKTOP_IMAGE"; return
    fi
    bad "branch desktop $DESKTOP_IMAGE could not be pulled or built"
}

command -v docker >/dev/null 2>&1 || { printf 'ERROR: docker is required\n' >&2; exit 1; }

printf '\n\033[1mOTTERNET lab images\033[0m\n'
ensure_ceos
ensure_vsrx
ensure_desktop
exit "$rc"
