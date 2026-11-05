#!/usr/bin/env bash
# Maintainers only: publish the lab images that no public registry carries to
# OpsMill's registry, so that `make images` can pull them on a new machine.
#
#   cEOS            ceos:<version>                -> <registry>/ceos-image:<version>
#   vSRX            vrnetlab/juniper_vsrx:<ver>   -> <registry>/juniper_vsrx:<ver>
#   branch desktop  otternet/branch-desktop:local -> <registry>/otternet-branch-desktop:<commit>
#
# The desktop is rebuilt from the current source first and tagged with the
# commit that last changed lab/configs/branch/desktop, which is the tag
# images.sh asks for.
#
# WHY NOT `docker push`: registry.opsmill.io is behind Cloudflare, which refuses
# any request larger than about 100 MB with "413 Payload Too Large". Docker
# uploads each layer in one request, and the vSRX layer is about 900 MB. regctl
# uploads in chunks, so it is used instead. It reads the login that
# `docker login registry.opsmill.io` stores.
#
# Usage: publish-images.sh [ceos] [vsrx] [desktop]   (all three by default)
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CEOS_VERSION="${CEOS_VERSION:-4.36.0.1F}"
VSRX_VERSION="${VSRX_VERSION:-22.3R1.11}"
REGISTRY="${OTTERNET_IMAGE_REGISTRY:-registry.opsmill.io/external}"
REGISTRY_HOST="${REGISTRY%%/*}"
REGCTL_VERSION="v0.11.7"
REGCTL="${REGCTL:-${XDG_CACHE_HOME:-$HOME/.cache}/otternet/regctl-$REGCTL_VERSION}"
CHUNK=$((50 * 1024 * 1024))

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

if [[ ! -x "$REGCTL" ]]; then
    say "Downloading regctl $REGCTL_VERSION"
    mkdir -p "$(dirname "$REGCTL")"
    curl -sSfL -o "$REGCTL" \
        "https://github.com/regclient/regclient/releases/download/$REGCTL_VERSION/regctl-linux-amd64"
    chmod +x "$REGCTL"
fi
"$REGCTL" registry set "$REGISTRY_HOST" --blob-chunk "$CHUNK" --blob-max "$CHUNK" >/dev/null

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# publish <local image> <registry reference>
publish() {
    local local_name="$1" remote="$2"
    docker image inspect "$local_name" >/dev/null 2>&1 || die "$local_name is not in the local image store"
    say "Publishing $local_name as $remote"
    docker tag "$local_name" "$remote"
    docker save -o "$WORK/image.tar" "$remote"
    "$REGCTL" image import "$remote" "$WORK/image.tar"
    rm -f "$WORK/image.tar"
    "$REGCTL" manifest head "$remote" >/dev/null || die "$remote is not in the registry after the upload"
    printf '  published %s\n' "$remote"
}

targets=("$@")
(( ${#targets[@]} )) || targets=(ceos vsrx desktop)
for target in "${targets[@]}"; do
    case "$target" in
        ceos) publish "ceos:$CEOS_VERSION" "$REGISTRY/ceos-image:$CEOS_VERSION" ;;
        vsrx) publish "vrnetlab/juniper_vsrx:$VSRX_VERSION" "$REGISTRY/juniper_vsrx:$VSRX_VERSION" ;;
        desktop)
            [[ -z "$(git -C "$LAB_DIR" status --porcelain -- configs/branch/desktop)" ]] \
                || die "lab/configs/branch/desktop has uncommitted changes; commit them first so the tag names them"
            tag="$(git -C "$LAB_DIR" log -1 --format=%H -- configs/branch/desktop | cut -c1-7)"
            say "Building the branch desktop from source"
            docker build -q -t otternet/branch-desktop:local "$LAB_DIR/configs/branch/desktop" >/dev/null
            publish otternet/branch-desktop:local "$REGISTRY/otternet-branch-desktop:$tag"
            ;;
        *) die "unknown image '$target' (expected ceos, vsrx or desktop)" ;;
    esac
done
