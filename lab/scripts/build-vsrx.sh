#!/usr/bin/env bash
# Build a containerlab-runnable vSRX image from a Junos vSRX 3.0 qcow2.
#
# vrnetlab derives the version by stripping `junos-vsrx3-x86-64-` and `.qcow2`
# from the filename, and Juniper's download is already named that way -- so if
# the file is named as Juniper shipped it, the docker tag is right and there is
# nothing to guess.
#
# Juniper does not redistribute the image. Download the vSRX 3.0 evaluation
# qcow2 from https://support.juniper.net/support/downloads/?p=vsrxeval -- a free
# account registered for "Evaluation user access" is enough, you do not need a
# support contract.
set -euo pipefail

SRC="${1:-/images/junos-vsrx3-x86-64-22.3R1.11.qcow2}"
WORKDIR="${OTTERNET_VRNETLAB_DIR:-$HOME/vrnetlab}"
BASE_IMAGE="ghcr.io/srl-labs/vrnetlab-base:0.3.0"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -f "$SRC" ]] || die "vSRX qcow2 not found: $SRC
     Pass the path as the first argument. Download the vSRX 3.0 evaluation
     image from https://support.juniper.net/support/downloads/?p=vsrxeval"
command -v docker >/dev/null || die "docker is required"

BASENAME="$(basename "$SRC")"
VERSION="${BASENAME#junos-vsrx3-x86-64-}"
VERSION="${VERSION%.qcow2}"
# vrnetlab's sanity check fails the build when the version string comes back
# identical to the filename, which is what happens if the name does not match
# the pattern. Catching it here says something useful instead.
[[ "$VERSION" != "$BASENAME" ]] || die "cannot read a version out of '$BASENAME'
     vrnetlab expects the name Juniper ships: junos-vsrx3-x86-64-<version>.qcow2
     e.g. junos-vsrx3-x86-64-22.3R1.11.qcow2"

say "Fetching vrnetlab into $WORKDIR"
if [[ -d "$WORKDIR/.git" ]]; then
    git -C "$WORKDIR" pull --ff-only --quiet || true
else
    git clone --depth 1 https://github.com/hellt/vrnetlab "$WORKDIR"
fi

VSRX_DIR="$WORKDIR/juniper/vsrx"
[[ -d "$VSRX_DIR" ]] || die "$VSRX_DIR missing -- has vrnetlab moved the juniper directory?"

say "Staging $BASENAME"
rm -f "$VSRX_DIR"/junos-vsrx3-*.qcow2 "$VSRX_DIR"/*.qcow2
cp "$SRC" "$VSRX_DIR/$BASENAME"

# The vSRX Makefile hard-codes IMAGE to an ancient 12.1X47 filename rather than
# globbing for whatever is present, so it has to be told which file to use.
say "Pulling the vrnetlab base image"
docker pull -q "$BASE_IMAGE"

say "Building vrnetlab/juniper_vsrx:$VERSION"
make -C "$VSRX_DIR" IMAGE="$BASENAME"

docker image inspect "vrnetlab/juniper_vsrx:$VERSION" >/dev/null 2>&1 \
    || die "build reported success but vrnetlab/juniper_vsrx:$VERSION does not exist"

# A 900 MB qcow2 left in a git clone gets committed by someone, eventually.
rm -f "$VSRX_DIR"/*.qcow2

say "Done"
cat <<HINT

Built: vrnetlab/juniper_vsrx:$VERSION

Deploy with it:
  VSRX_VERSION=$VERSION make deploy

containerlab's startup-config works for this kind: vrnetlab appends
configs/fw/vsrx/junos.conf to its own init.conf and Junos loads the result at
boot, so there is no post-boot config push.
HINT
