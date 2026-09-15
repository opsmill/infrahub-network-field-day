#!/usr/bin/env bash
# Destroy everything, rebuild it with `invoke bootstrap --fresh`, and assert the
# result stage by stage.
#
# This exists because "it worked" and "it is stable" are different claims, and
# only a full teardown distinguishes them. Six runs of this found three bugs
# that were invisible from a running instance, each hiding behind a different
# symptom:
#
#   - a 502 from the hostvar trigger that took the whole chain down, leaving a
#     spine rendered with three of five neighbours from artifacts reporting Ready
#   - the topology generators running twice, the second pass deleting the
#     cabling the first had created: 10, 0 and 4 of 10 spine-leaf links across
#     three identical rebuilds
#   - CoreDNS still starting when Crossplane preflighted it, which only bites
#     when the installs run back to back rather than by hand
#
# None of them failed loudly in a way that pointed at the cause. What catches
# them is asserting the OUTCOME -- BGP sessions established, links present,
# resources delivered -- rather than the exit status of the command that was
# supposed to produce it. Several of the checks below are deliberately about
# state rather than about whether a step reported success:
#
#   - `spine1 underlay sessions` counts established neighbours, because an AVD
#     artifact can be 239 lines, contain `router bgp`, report Ready and still
#     describe a fabric that does not exist.
#   - `configuration artifacts with content` downloads every artifact, because
#     generation is asynchronous and an empty one still reports Ready.
#   - the Vidra checks look at the resources, because `syncState: Succeeded`
#     over an empty set is still Succeeded.
#
# Usage:  scripts/verify_bootstrap.sh [run-label]
# Env:    INFRAHUB_ADDRESS     default http://localhost:8000
#         INFRAHUB_API_TOKEN   default matches docker-compose.override.yml
#         NFD41_LAB_DIR        default: found beside this checkout
#
# Takes about twenty minutes. Exits non-zero with the number of failed checks.
set -uo pipefail

LABEL="${1:-$(date +%H%M%S)}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Locate the sibling lab repository the same way tasks.py does: beside this
# checkout, or beside one of its parents, because `../lab` is wrong from a git
# worktree.
find_lab() {
    if [[ -n "${NFD41_LAB_DIR:-}" ]]; then printf '%s' "$NFD41_LAB_DIR"; return; fi
    local dir="$REPO"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/../lab/nfd41.clab.yml" ]]; then
            (cd "$dir/../lab" && pwd); return
        fi
        dir="$(dirname "$dir")"
    done
    printf '%s' "$REPO/../lab"
}
LAB="$(find_lab)"

export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-http://localhost:8000}"
# The committed development default from docker-compose.override.yml, not a
# secret. Override it for any instance that does not use it.
export INFRAHUB_API_TOKEN="${INFRAHUB_API_TOKEN:-06438eb2-8019-4776-878c-0941b1f1d1ec}"
export COLUMNS=200

LOG="$(mktemp -d -t nfd41-verify-XXXXXX)"
FAILURES=0
started=$(date +%s)

stage() { printf '\n=== [%s] %s (t+%ss) ===\n' "$LABEL" "$1" "$(( $(date +%s) - started ))"; }
pass()  { printf 'PASS  %s\n' "$*"; }
fail()  { printf 'FAIL  %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
check() { if [ "$1" = "$2" ]; then pass "$3 ($1)"; else fail "$3 (got '$1', want '$2')"; fi; }

count() {
    curl -s -X POST "$INFRAHUB_ADDRESS/graphql/main" -H 'Content-Type: application/json' \
        -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -d "{\"query\":\"{ $1 { count } }\"}" \
    | python3 -c "
import json,sys
try: print(list(json.load(sys.stdin)['data'].values())[0]['count'])
except Exception: print(-1)"
}

cd "$REPO" || exit 1
printf 'repository: %s\nlab:        %s\nlogs:       %s\n' "$REPO" "$LAB" "$LOG"

stage "invoke bootstrap --fresh"
uv run invoke bootstrap --fresh >"$LOG/bootstrap.log" 2>&1
check "$?" "0" "invoke bootstrap exit status"

stage "infrahub data"
check "$(count DcimGenericDevice)" "22" "devices"
check "$(count NetworkLink)" "17" "links (server cabling plus the spine-leaf fabric)"
check "$(count AvdStructuredConfigFile)" "7" "structured configs on main"

stage "artifacts"
# Downloaded, not counted: an artifact that exists and reports Ready can still be
# empty, and provisioning one would replace a switch's configuration with nothing.
empty=$(uv run python - <<'PY' 2>/dev/null
import os, httpx
H = {"X-INFRAHUB-KEY": os.environ["INFRAHUB_API_TOKEN"]}
A = os.environ["INFRAHUB_ADDRESS"]
q = "{ CoreArtifact { edges { node { id name { value } } } } }"
r = httpx.post(f"{A}/graphql/main", json={"query": q}, headers=H, timeout=60).json()
names = {"AVD EOS Configuration", "FRR Configuration", "Junos Configuration"}
print(sum(1 for e in r["data"]["CoreArtifact"]["edges"]
          if e["node"]["name"]["value"] in names
          and not httpx.get(f"{A}/api/artifact/{e['node']['id']}", headers=H, timeout=60).text.strip()))
PY
)
check "$empty" "0" "configuration artifacts with content"

stage "lab and devices"
check "$(docker ps -q --filter name=clab-nfd41 | wc -l)" "30" "lab nodes running"
# Cycle 030 made the bootstrap's device step `invoke reconcile --converge`
# rather than `invoke provision`, so the string this used to grep for is gone.
grep -q "Every device is confirmed to match its rendered configuration" "$LOG/bootstrap.log" \
    && pass "reconciler reported convergence" || fail "reconciler did not converge"
# The outcome rather than the log line, and a stronger claim than the old one:
# not "the command said it pushed 14" but "the graph says 14 devices were
# CONFIRMED to match" -- which only a comparison finding no difference writes.
confirmed=$(python3 - <<'PYSTATE'
import httpx, os
A=os.environ["INFRAHUB_ADDRESS"]; H={"X-INFRAHUB-KEY": os.environ["INFRAHUB_API_TOKEN"]}
q='{DeploymentState{edges{node{status{value} last_confirmed_at{value}}}}}'
r=httpx.post(f"{A}/graphql", json={"query": q}, headers=H, timeout=60).json()
print(sum(1 for e in r["data"]["DeploymentState"]["edges"]
          if e["node"]["status"]["value"] == "in_sync"
          and e["node"]["last_confirmed_at"]["value"]))
PYSTATE
)
check "$confirmed" "14" "devices confirmed in_sync in DeploymentState"
# The outcome, not the artifact: a config can look complete and describe a fabric
# that is not there.
check "$(docker exec clab-nfd41-spine1 Cli -p 15 -c 'show ip bgp summary' 2>/dev/null | grep -c Estab)" \
    "5" "spine1 underlay sessions"
check "$(docker exec clab-nfd41-spine1 Cli -p 15 -c 'show bgp evpn summary' 2>/dev/null | grep -c Estab)" \
    "5" "spine1 EVPN sessions"

stage "kubernetes"
export KUBECONFIG="$LAB/k8s/.kubeconfig/kubeconfig.yaml"
check "$(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready')" "3" "k3s nodes Ready"
grep -q "torn down" "$LOG/bootstrap.log" \
    && pass "handover waited for teardown before resyncing" \
    || fail "handover did not report 'torn down'"

for kind_name in "fabricapp nfd41-demo" "fabricpeering nfd41"; do
    set -- $kind_name
    ready=no
    for _ in $(seq 1 30); do
        [ "$(kubectl get "$1" "$2" -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" = "True" ] \
            && { ready=yes; break; }
        sleep 15
    done
    check "$ready" "yes" "$1/$2 delivered by Vidra and Ready"
done

# Two would mean the handover recreated the claim while the first namespace was
# still terminating, which does not resolve on its own.
check "$(kubectl get object --no-headers 2>/dev/null | grep -c 'nfd41-demo.*Namespace')" \
    "1" "exactly one composed Namespace"
for app in nfd41-access nfd41-observability; do
    check "$(kubectl get fabricapp $app -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null)" \
        "True" "lab-owned $app untouched"
done

stage "the cluster is inside the fabric"
check "$(kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers 2>/dev/null | grep -c established)" \
    "2" "Cilium sessions to both k8s leaves"
routes=$(docker exec clab-nfd41-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp' 2>/dev/null \
    | grep -cE '10\.111|10\.112')
[ "$routes" -ge 4 ] && pass "leaf learns the pod CIDRs and LoadBalancer VIPs ($routes)" \
    || fail "leaf learned only $routes cluster routes"

elapsed=$(( $(date +%s) - started ))
printf '\n=== [%s] COMPLETE in %sm%ss — %s failure(s) ===\n' \
    "$LABEL" "$((elapsed / 60))" "$((elapsed % 60))" "$FAILURES"
[ "$FAILURES" -eq 0 ] || printf 'bootstrap log: %s/bootstrap.log\n' "$LOG"
exit "$FAILURES"
