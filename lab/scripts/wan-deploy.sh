#!/usr/bin/env bash
# Push the rendered WAN configs onto the running ISP / customer / branch routers.
#
# The WAN's equivalent of `make avd-deploy`: wan/render.py produces the intended
# config, this makes the devices match it. A candidate REPLACE rather than a
# restart, so a customer being added does not bounce the BGP sessions of the
# customers that were already there -- the commit applies only the net change.
#
# This is the lab's own push, for working on the lab without Infrahub. Once
# Infrahub runs the lab, its reconciler pushes the identical file the same way
# (src/solution_arista_avd/deployment/devices.py, push_srl).
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

    # Hosts have no routing stack; re-running their init script is idempotent.
    if [[ ! -f "$dir/config.cli" ]]; then
        if docker exec "$container" sh /opt/init.sh >/dev/null 2>&1; then
            ok "$node (host addressing)"
            pushed=$((pushed + 1))
        else
            warn "$node addressing did not apply"
            failed=$((failed + 1))
        fi
        continue
    fi

    # SR Linux: delete the three subtrees the file owns and re-set them from it,
    # in ONE private candidate, then commit. That is a replace -- a tenant removed
    # from tenants.yml is removed from the router -- and only the net difference
    # is applied. /system (credentials, gNMI, TLS) is never touched.
    #
    # sr_cli stops at the first error and commits nothing, but leaves its named
    # candidate behind; it is cleared on failure so ten bad runs cannot use up
    # the router's candidate slots.
    candidate="wan-deploy-$$"
    if out=$({
            echo "enter candidate private name $candidate"
            echo "delete / interface *"
            echo "delete / network-instance *"
            echo "delete / routing-policy"
            cat "$dir/config.cli"
            echo "commit now"
        } | docker exec -i "$container" sr_cli 2>&1) && grep -q "All changes have been committed" <<<"$out"; then
        ok "$node"
        pushed=$((pushed + 1))
    else
        docker exec "$container" sr_cli -d "tools system configuration candidate $candidate clear" >/dev/null 2>&1 || true
        warn "$node commit failed:"
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
