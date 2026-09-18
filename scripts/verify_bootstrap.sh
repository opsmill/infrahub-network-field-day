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
# 31 since the tooling cluster: `tool-node1` is a lab node like any other,
# even though nothing in the fabric reaches it.
check "$(docker ps -q --filter name=clab-nfd41 | wc -l)" "31" "lab nodes running"
# Cycle 030 made the bootstrap's device step `invoke reconcile --converge`
# rather than `invoke provision`, so the string this used to grep for is gone.
grep -q "Every device is confirmed to match its rendered configuration" "$LOG/bootstrap.log" \
    && pass "reconciler reported convergence" || fail "reconciler did not converge"
# The outcome rather than the log line, and a stronger claim than the old one:
# not "the command said it pushed 14" but "the graph says 14 devices were
# CONFIRMED to match" -- which only a comparison finding no difference writes.
confirmed=$(uv run python - <<'PYSTATE'
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
# Only the applications Infrahub declares. The lab's installer applies its own
# two as well and the handover deletes them, so anything left here is a workload
# no proposed change can account for. Counted as well as named: a third
# application from somewhere else would pass the two absence checks.
check "$(kubectl get fabricapp --no-headers 2>/dev/null | wc -l | tr -d ' ')" "1" \
    "exactly one FabricApp, the one Infrahub models"
for app in nfd41-access nfd41-observability; do
    check "$(kubectl get fabricapp $app --no-headers 2>/dev/null | wc -l | tr -d ' ')" "0" \
        "unmodelled $app removed by the handover"
done

stage "the cluster is inside the fabric"
check "$(kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers 2>/dev/null | grep -c established)" \
    "2" "Cilium sessions to both k8s leaves"
# Four is now the exact set rather than a floor with slack in it: three pod
# CIDRs, one per node, and the one VIP of the one application Infrahub models.
# It used to carry the lab's two applications as well, so a missing VIP passed.
routes=$(docker exec clab-nfd41-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp' 2>/dev/null \
    | grep -cE '10\.111|10\.112')
[ "$routes" -ge 4 ] && pass "leaf learns the pod CIDRs and LoadBalancer VIPs ($routes)" \
    || fail "leaf learned only $routes cluster routes"

stage "the tooling cluster, and signing in"
# A SEPARATE CLUSTER from the one above, with its own kubeconfig, reached
# through the node rather than from the host. It carries the lab's identity
# provider and the portal people request services through, and the bootstrap
# now deploys it -- so a bootstrap that brought up everything except the ability
# to sign in used to pass this script with nothing to say about it.
TOOL=clab-nfd41-tool-node1
DESK=clab-nfd41-branch-desktop
tk() { docker exec "$TOOL" kubectl -n nfd41-tooling "$@" 2>/dev/null; }

for deploy in dex backstage; do
    check "$(tk get deploy "$deploy" -o jsonpath='{.status.availableReplicas}')" "1" \
        "$deploy available in the tooling cluster"
done

# THE ISSUER, not just a 200. An issuer that disagrees with the address it is
# served on fails at token validation rather than at connect, which is a much
# worse error to debug -- and it is the single string Infrahub, Backstage and
# every browser have to agree on.
check "$(docker exec "$DESK" curl -s --max-time 10 \
    http://10.90.0.11:32556/dex/.well-known/openid-configuration 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["issuer"])' 2>/dev/null)" \
    "http://10.90.0.11:32556/dex" "Dex publishes the issuer everyone is configured with"

# FROM THE BRANCH DESKTOP, which is the whole point. Every one of these passed
# from the host while being broken for the only audience that uses them, and
# that is how the two-Dex detour started.
#
# `ssl_verify_result=0` is a second claim inside the first: the portal's
# self-signed certificate is INSTALLED on this desktop, so a real browser gets
# no warning. Dropping to `curl -k` here would pass while the user sees one.
read -r portal verify <<EOF
$(docker exec "$DESK" curl -s -o /dev/null -w '%{http_code} %{ssl_verify_result}' \
    --max-time 10 https://10.90.0.11:32001/ 2>/dev/null)
EOF
check "$portal" "200" "branch desktop reaches the portal over HTTPS"
check "$verify" "0" "portal certificate is trusted on the branch desktop"
check "$(docker exec "$DESK" curl -s -o /dev/null -w '%{http_code}' --max-time 10 \
    http://10.90.0.1:8000/api/config 2>/dev/null)" "200" \
    "branch desktop reaches Infrahub (firewall rule AND return route)"

# The policy is a permit-list, not an any/any that happens to work. If ICMP gets
# through, everything above passes for the wrong reason.
docker exec "$DESK" ping -c1 -W3 10.90.0.11 >/dev/null 2>&1 \
    && fail "ICMP into the tooling zone is permitted; the policy is too broad" \
    || pass "ICMP into the tooling zone is denied"

# THE ONLY CHECK THAT MEANS "a user can sign in". Everything above can pass
# with sign-in broken: a reachable IdP, a reachable relying party, and a
# redirect URI neither of them agrees on. This drives the whole flow --
# authorize, Dex login as alice, then the code exchange -- and asserts Infrahub
# minted its own token at the end of it.
signin=$(docker exec "$DESK" bash -c '
J=$(mktemp)
auth=$(curl -s -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 10     "http://10.90.0.1:8000/api/oidc/provider1/authorize")
curl -s -L -b "$J" -c "$J" -o /tmp/login.html --max-time 15 "$auth"
form=$(grep -oE "action=\"[^\"]*\"" /tmp/login.html | head -1 | cut -d\" -f2 | sed "s/&amp;/\&/g")
cb=$(curl -s -b "$J" -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 15     -d "login=alice@nfd41.lab" -d "password=password" "http://10.90.0.11:32556${form}")
curl -s -b "$J" -c "$J" --max-time 20 "http://10.90.0.1:8000/api/oidc/provider1/token?${cb#*\?}"
' 2>/dev/null | grep -c access_token)
check "$signin" "1" "alice signs in to Infrahub through Dex, from the branch desktop"

# WHAT THE PORTAL ACTUALLY OFFERS, not merely that it answers.
#
# Every check above passes against a portal whose catalogue is EMPTY: it serves
# its bundle, signs a user in, and has nothing for them to ask for. That is not
# hypothetical -- three of the nine service kinds were missing for a whole
# session because Infrahub's json_schema endpoint 500s on a List attribute, and
# the only trace was a warning in the backend log.
#
# THE EXPECTED NUMBER COMES FROM INFRAHUB, not from the portal's config, and
# that is the point: the claim is "every service kind can be requested", which
# is a statement about the two agreeing. Counting the portal's own configuration
# would let a kind be missing from both and still pass -- and it undercounts
# anyway, because the provider DISCOVERS kinds under a configured generic.
# `ServiceFabricPeering` is in no `kinds` list and has a template.
want_templates=$(uv run python - <<'PYWANT'
import json, os, httpx
r = httpx.get(
    f"{os.environ['INFRAHUB_ADDRESS']}/api/schema",
    headers={"X-INFRAHUB-KEY": os.environ["INFRAHUB_API_TOKEN"]},
    timeout=60,
)
print(sum(1 for n in r.json()["nodes"]
          if "ServiceGeneric" in (n.get("inherit_from") or [])))
PYWANT
)
docker cp scripts/portal/portal_signin.sh "$DESK:/tmp/portal_signin.sh" >/dev/null 2>&1
docker exec "$DESK" chmod +x /tmp/portal_signin.sh 2>/dev/null
got_templates=$(docker exec "$DESK" sh -c '
T=$(/tmp/portal_signin.sh)
[ -n "$T" ] || exit 1
curl -s -H "Authorization: Bearer $T" --max-time 25 \
  "https://10.90.0.11:32001/api/catalog/entities?filter=kind=template,metadata.tags=generated" \
  | python3 -c "import json,sys; print(len(json.load(sys.stdin)))"' 2>/dev/null)
check "${got_templates:-0}" "$want_templates" "request templates in the portal catalogue"

# ... AND THAT ONE CAN ACTUALLY BE SUBMITTED.
#
# A template being ingested says nothing about whether the mutation inside it is
# one Infrahub will accept, and every defect found in this path was of exactly
# that shape: a status value the schema does not have, a List attribute dropped,
# an hfid of the wrong length. All of them left the catalogue looking healthy.
#
# The mutation is taken OUT OF THE RENDERED TEMPLATE rather than written here --
# a copy would pass while the portal shipped something else, which is the failure
# being guarded against. It runs on a branch that is deleted afterwards, so a
# verification run leaves no grant behind and never reaches a device.
if docker exec "$DESK" sh -c '
T=$(/tmp/portal_signin.sh)
[ -n "$T" ] || exit 1
curl -s -H "Authorization: Bearer $T" --max-time 25 \
  "https://10.90.0.11:32001/api/catalog/entities/by-name/template/default/app-access-request"' \
  2>/dev/null | uv run python scripts/portal/portal_request_check.py; then
    pass "a request can be submitted through the portal's own create mutation"
else
    fail "the portal's create mutation is not one Infrahub accepts"
fi

elapsed=$(( $(date +%s) - started ))
printf '\n=== [%s] COMPLETE in %sm%ss — %s failure(s) ===\n' \
    "$LABEL" "$((elapsed / 60))" "$((elapsed % 60))" "$FAILURES"
[ "$FAILURES" -eq 0 ] || printf 'bootstrap log: %s/bootstrap.log\n' "$LOG"
exit "$FAILURES"
