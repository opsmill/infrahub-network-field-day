#!/usr/bin/env bash
# Raise the host's inotify limits to what the lab needs. Never lowers a value.
#
# Each k3s node, the kubelet and containerd in it, and every pod with a file
# watcher holds inotify instances. Linux allows 128 per user by default; with
# the lab running, root holds about 780. Past the limit, pods fail with "too
# many open files" and host services such as fwupd log "Could not initialize
# inotify".
#
# The cEOS image raises these limits itself: its ceoslab-apply-sysctls sets
# max_user_instances to 62800 and max_user_watches to 25600000 when a switch
# boots, and these settings are host-wide, not per container. This script covers
# the time before the switches have booted, while the k3s nodes are already
# starting, and a deploy with no cEOS node.
#
# `sysctl -w` does not survive a reboot. `invoke lab` and `make deploy` run this
# before every deploy, the same way they recreate the tooling bridge. To make it
# permanent: OTTERNET_PERSIST_LIMITS=1 writes /etc/sysctl.d/99-otternet-lab.conf.
set -euo pipefail

declare -A MINIMUM=(
    [fs.inotify.max_user_instances]=8192
    [fs.inotify.max_user_watches]=1048576
)

persist=()
for key in "${!MINIMUM[@]}"; do
    want="${MINIMUM[$key]}"
    have="$(sysctl -n "$key")"
    if (( have < want )); then
        printf '  raising %s from %s to %s\n' "$key" "$have" "$want"
        sudo sysctl -qw "$key=$want"
    fi
    persist+=("$key = $(( have > want ? have : want ))")
done

if [[ "${OTTERNET_PERSIST_LIMITS:-0}" == "1" ]]; then
    printf '%s\n' "# Written by lab/scripts/host-limits.sh for the OTTERNET lab." "${persist[@]}" \
        | sudo tee /etc/sysctl.d/99-otternet-lab.conf >/dev/null
    printf '  wrote /etc/sysctl.d/99-otternet-lab.conf\n'
fi
