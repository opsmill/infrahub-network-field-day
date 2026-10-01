#!/usr/bin/env bash
# Push the rendered WAN configs onto the running ISP / customer / branch routers.
#
# The WAN's equivalent of `make avd-deploy`: wan/render.py produces the intended
# config, this makes the devices match it. Reload rather than restart, so a
# customer being added does not bounce the BGP sessions of the customers that
# were already there -- which is the whole reason to have a reload path at all.
set -euo pipefail

LAB="${OTTERNET_LAB:-otternet}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RENDERED="$LAB_DIR/wan/rendered"

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32mok\033[0m    %s\n' "$*"; }
warn() { printf '  \033[1;33mwarn\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

[[ -d "$RENDERED" ]] || die "nothing rendered yet -- run: make wan-build"

say "Pushing WAN configs"
pushed=0 skipped=0 failed=0

for dir in "$RENDERED"/*/; do
    node="$(basename "$dir")"
    container="clab-$LAB-$node"

    if ! docker inspect "$container" >/dev/null 2>&1; then
        warn "$node is not running -- skipped"
        skipped=$((skipped + 1))
        continue
    fi

    # No copying: the topology bind-mounts wan/rendered/<node>/ into the
    # container, and render.py overwrites those files in place, so the node can
    # already see the new config. Trying to `docker cp` onto them fails anyway
    # -- "device or resource busy" -- because they are read-only bind mounts.

    # Hosts have no routing daemon; re-running their init script is idempotent.
    if [[ ! -f "$dir/frr.conf" ]]; then
        if docker exec "$container" sh /opt/init.sh >/dev/null 2>&1; then
            ok "$node (host addressing)"
            pushed=$((pushed + 1))
        else
            warn "$node addressing did not apply"
            failed=$((failed + 1))
        fi
        continue
    fi

    # frr-reload.py computes the difference between the running config and the
    # file and applies only that. `vtysh -f` would MERGE, which quietly leaves
    # a removed customer's VRF and BGP session in place -- so a customer you
    # deleted from tenants.yml would still be connected.
    if out=$(docker exec "$container" /usr/lib/frr/frr-reload.py \
                --reload --stdout /etc/frr/frr.conf 2>&1); then
        ok "$node"
        pushed=$((pushed + 1))
    else
        warn "$node reload failed:"
        printf '%s\n' "$out" | tail -8 | sed 's/^/          /'
        failed=$((failed + 1))
    fi
done

printf '\n  %d pushed, %d skipped, %d failed\n' "$pushed" "$skipped" "$failed"

if (( failed > 0 )); then
    die "some WAN devices did not take their config"
fi

cat <<'EOF'

Next:
  make wan-bgp           # BGP state on every WAN router
  make wan-customers     # what each customer can see -- and cannot
  make verify            # end-to-end, including WAN and branch to DC services

EOF
