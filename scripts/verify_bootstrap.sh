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
#   - the dashboard check runs every panel's queries THROUGH Grafana, because
#     Prometheus holding the data says nothing about Grafana being able to show
#     it (scripts/check_grafana_panels.py).
#
# Usage:  scripts/verify_bootstrap.sh [run-label]
# Env:    INFRAHUB_ADDRESS     default http://localhost:8000
#         INFRAHUB_API_TOKEN   default matches docker-compose.override.yml
#         OTTERNET_LAB_DIR        default: lab/ in this checkout
#
# Takes about twenty minutes. Exits non-zero with the number of failed checks.
set -uo pipefail

LABEL="${1:-$(date +%H%M%S)}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The lab lives in this repository, under lab/. OTTERNET_LAB_DIR overrides it,
# the same way it does for tasks.py.
find_lab() {
    if [[ -n "${OTTERNET_LAB_DIR:-}" ]]; then printf '%s' "$OTTERNET_LAB_DIR"; return; fi
    printf '%s' "$REPO/lab"
}
LAB="$(find_lab)"

export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-http://localhost:8000}"
# The committed development default from docker-compose.override.yml, not a
# secret. Override it for any instance that does not use it.
export INFRAHUB_API_TOKEN="${INFRAHUB_API_TOKEN:-06438eb2-8019-4776-878c-0941b1f1d1ec}"
export COLUMNS=200

LOG="$(mktemp -d -t otternet-verify-XXXXXX)"
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
names = {"AVD EOS Configuration", "SR Linux Configuration", "Junos Configuration"}
print(sum(1 for e in r["data"]["CoreArtifact"]["edges"]
          if e["node"]["name"]["value"] in names
          and not httpx.get(f"{A}/api/artifact/{e['node']['id']}", headers=H, timeout=60).text.strip()))
PY
)
check "$empty" "0" "configuration artifacts with content"

stage "lab and devices"
# 31 since the tooling cluster: `tool-node1` is a lab node like any other,
# even though nothing in the fabric reaches it. Cycle 034 added six
# frr_exporter sidecars (37); the SR Linux re-platform removed them again,
# because the routers stream their own telemetry over gNMI.
check "$(docker ps -q --filter name=clab-otternet | wc -l)" "31" "lab nodes running"
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
check "$(docker exec clab-otternet-spine1 Cli -p 15 -c 'show ip bgp summary' 2>/dev/null | grep -c Estab)" \
    "5" "spine1 underlay sessions"
check "$(docker exec clab-otternet-spine1 Cli -p 15 -c 'show bgp evpn summary' 2>/dev/null | grep -c Estab)" \
    "5" "spine1 EVPN sessions"

# fw1 was the device "confirmed in_sync" above could be wrong about. vrnetlab's
# init.conf boots it with two cleartext `plain-text-password-value` leaves, and
# `show | compare` never prints their deletion -- so a comparison could confirm
# a firewall nothing had pushed. Ask the running configuration itself: no
# cleartext, and the newest commit is the reconciler's (`admin`), not vrnetlab's
# boot commit (`root via other`). Read-only, both of them; and an unreachable
# CLI reads "unreachable", never as a clean zero.
fw1_cli() {
    printf '%s\nexit\n' "$1" | docker exec -i clab-otternet-fw1 sshpass -p admin@123 \
        ssh -T -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR \
        admin@127.0.0.1 2>/dev/null
}
check "$(fw1_cli 'show configuration | display set | match plain-text-password-value' \
    | awk '/^admin@fw1> show configuration/ {seen = 1} /^set .*plain-text-password-value/ {n++}
           END {print seen ? n + 0 : "unreachable"}')" \
    "0" "fw1 running configuration carries no plain-text-password-value"
check "$(fw1_cli 'show system commit' | sed -n 's/^0 .* by \([^ ]*\) via .*/\1/p')" \
    "admin" "fw1's newest commit is the reconciler's, so the full configuration was applied"

# Every WAN router's BGP, counted against its OWN rendered artifact rather than a
# number written here: each `neighbor <addr>` in a network-instance must be an
# established session in that instance. A missing artifact is a failure, never
# a vacuous 0/0.
for router in isp-pe1 isp-pe2 internet-rtr cust-acme-ce cust-globex-ce branch-rtr; do
    rendered="$LAB/wan/rendered/$router/config.cli"
    want=$(grep -oE '^set / network-instance [^ ]+ protocols bgp neighbor [^ ]+ ' "$rendered" 2>/dev/null \
        | awk '{print $4, $8}' | sort -u)
    got=$(docker exec "clab-otternet-$router" sr_cli -d "show network-instance * protocols bgp neighbor" 2>/dev/null \
        | awk -F'|' 'NF > 7 { gsub(/ /, "", $2); gsub(/ /, "", $3); gsub(/ /, "", $7)
                              if ($7 == "established") print $2, $3 }' | sort -u)
    expected=$(printf '%s' "$want" | grep -c .)
    if [ "$expected" = "0" ]; then
        fail "$router: no BGP neighbours in $rendered to check against"
        continue
    fi
    up=$(comm -12 <(printf '%s\n' "$want") <(printf '%s\n' "$got") | grep -c .)
    check "$up/$expected" "$expected/$expected" "$router BGP sessions established across its network instances"
done

stage "kubernetes"
export KUBECONFIG="$LAB/k8s/.kubeconfig/kubeconfig.yaml"
check "$(kubectl get nodes --no-headers 2>/dev/null | grep -c ' Ready')" "3" "k3s nodes Ready"
grep -q "torn down" "$LOG/bootstrap.log" \
    && pass "handover waited for teardown before resyncing" \
    || fail "handover did not report 'torn down'"

for kind_name in "fabricapp otternet-demo" "fabricpeering otternet" \
                 "fabricapp otternet-metrics" "fabricapp otternet-telemetry"; do
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
check "$(kubectl get object --no-headers 2>/dev/null | grep -c 'otternet-demo.*Namespace')" \
    "1" "exactly one composed Namespace"
# Only the applications Infrahub declares: the demo and, since cycle 034, the
# two observability applications. The lab's installer applies its access broker
# as well and the handover deletes it, so anything beyond these three is a
# workload no proposed change can account for. Counted as well as named: a
# fourth application from somewhere else would pass every absence check.
check "$(kubectl get fabricapp --no-headers 2>/dev/null | wc -l | tr -d ' ')" "3" \
    "exactly three FabricApps, the ones Infrahub models"
# One composed Namespace per application. Two for one application means a claim
# was recreated while its first namespace was still terminating.
for app in otternet-metrics otternet-telemetry; do
    check "$(kubectl get object --no-headers 2>/dev/null | grep -c "$app.*Namespace")" "1" \
        "exactly one composed Namespace for $app"
done
for app in otternet-access otternet-observability; do
    check "$(kubectl get fabricapp $app --no-headers 2>/dev/null | wc -l | tr -d ' ')" "0" \
        "unmodelled $app removed by the handover"
done

stage "the cluster is inside the fabric"
check "$(kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers 2>/dev/null | grep -c established)" \
    "2" "Cilium sessions to both k8s leaves"
# A floor, not an exact count: three pod CIDRs, one per node, and the demo's
# VIP. Grafana's VIP is advertised only from the node running Grafana
# (externalTrafficPolicy Local), so whether a given leaf learns it depends on
# scheduling; the observability stage below asserts it from the branch instead.
routes=$(docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp' 2>/dev/null \
    | grep -cE '10\.111|10\.112')
[ "$routes" -ge 4 ] && pass "leaf learns the pod CIDRs and LoadBalancer VIPs ($routes)" \
    || fail "leaf learned only $routes cluster routes"

stage "the tooling cluster, and signing in"
# A SEPARATE CLUSTER from the one above, with its own kubeconfig, reached
# through the node rather than from the host. It carries the lab's identity
# provider and the portal people request services through, and the bootstrap
# now deploys it -- so a bootstrap that brought up everything except the ability
# to sign in used to pass this script with nothing to say about it.
TOOL=clab-otternet-tool-node1
DESK=clab-otternet-branch-desktop
tk() { docker exec "$TOOL" kubectl -n otternet-tooling "$@" 2>/dev/null; }

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
# `ssl_verify_result=0` is a second claim inside the first: the CA that signed
# the portal's certificate is INSTALLED on this desktop. Dropping to `curl -k`
# here would pass while the user sees a warning. It is necessary, not
# sufficient: curl accepted the old self-signed CA:TRUE certificate too, while
# Firefox refused it (MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY), so the
# check after it asserts what Firefox needs, a server certificate that is not
# itself a CA.
read -r portal verify <<EOF
$(docker exec "$DESK" curl -s -o /dev/null -w '%{http_code} %{ssl_verify_result}' \
    --max-time 10 https://10.90.0.11:32001/ 2>/dev/null)
EOF
check "$portal" "200" "branch desktop reaches the portal over HTTPS"
check "$verify" "0" "portal certificate is trusted on the branch desktop"
check "$(docker exec "$DESK" sh -c 'echo | timeout 10 openssl s_client -connect 10.90.0.11:32001 2>/dev/null | openssl x509 -noout -ext basicConstraints 2>/dev/null' | grep -c 'CA:TRUE')" \
    "0" "portal serves a CA-signed certificate Firefox accepts, not a self-signed CA"
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
cb=$(curl -s -b "$J" -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 15     -d "login=alice@otternet.lab" -d "password=password" "http://10.90.0.11:32556${form}")
curl -s -b "$J" -c "$J" --max-time 20 "http://10.90.0.1:8000/api/oidc/provider1/token?${cb#*\?}"
' 2>/dev/null | grep -c access_token)
check "$signin" "1" "alice signs in to Infrahub through Dex, from the branch desktop"

# EVERY portal user, not just the one the check above happens to create.
#
# That check is a sign-in, and a sign-in PROVISIONS the account -- so it proved
# alice could sign in while creating the very account it then relied on, and was
# structurally unable to notice that nobody else had one. A user with no account
# gets a red run and an orphan branch on their first request.
missing_accounts=$(uv run python scripts/provision_portal_accounts.py --check >/dev/null 2>&1 && echo 0 || echo 1)
check "$missing_accounts" "0" "every portal user has an Infrahub account"

# THE RECONCILER LOOP, not the one-off convergence the bootstrap already did.
# Without it a merge reaches no device, and DeploymentState keeps reporting the
# green it recorded during the bootstrap -- a reading that is identical whether
# the loop is running or was never started.
check "$(docker compose ps --format '{{.Name}}' 2>/dev/null | grep -c deployment-reconciler)" "1" \
    "the deployment reconciler is running"

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

stage "observability"
# Grafana, Prometheus and Telegraf, delivered from Infrahub (cycle 034). Every
# check is about state a person would see, not about a step having run.
km() { kubectl -n otternet-metrics "$@" 2>/dev/null; }
# THROUGH A PORT-FORWARD, NOT `kubectl exec`. The Prometheus image carries no
# wget or curl, so an exec'd query fails before it is sent -- and every check
# below then read -1 against a Prometheus that was answering fine.
km port-forward svc/prometheus-operated 19090:9090 >/dev/null 2>&1 &
prom_pf=$!
for _ in $(seq 1 20); do curl -s -o /dev/null http://127.0.0.1:19090/-/ready && break; sleep 3; done
promql() {
    curl -s --get --max-time 20 http://127.0.0.1:19090/api/v1/query --data-urlencode "query=$1" \
    | python3 -c 'import json,sys
r = json.load(sys.stdin)["data"]["result"]
print(int(float(r[0]["value"][1])) if r else 0)' 2>/dev/null || echo -1
}

# THE GATE HOLDS BEFORE ANYONE ASKS. No grant is seeded, so the branch has no
# route to Grafana's VIP and no firewall permit. If this answers, the request
# alice makes in the demo would be decoration.
docker exec "$DESK" curl -s -o /dev/null --max-time 5 http://10.112.240.81/ 2>/dev/null \
    && fail "Grafana answers the branch with no grant; the request would change nothing" \
    || pass "Grafana does not answer the branch before a grant exists"

# SIGN-IN THROUGH DEX, driven end to end from the host through a port-forward.
# The browser half goes to the issuer; Grafana's own token exchange goes out of
# its pod to the tool node's management address -- so a pass here also proves
# the back channel (research R3), which nothing else exercises.
gsvc=$(km get svc -l app.kubernetes.io/name=grafana -o name | head -1)
km port-forward "$gsvc" 13000:80 >/dev/null 2>&1 &
pf=$!
sleep 4
grafana_role=$(bash -c '
J=$(mktemp)
auth=$(curl -s -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 10 http://127.0.0.1:13000/login/generic_oauth)
case "$auth" in http://10.90.0.11:32556/dex/auth*client_id=grafana*) ;; *) echo "no-redirect"; exit 0;; esac
curl -s -L -b "$J" -c "$J" -o /tmp/grafana-login.html --max-time 15 "$auth"
form=$(grep -oE "action=\"[^\"]*\"" /tmp/grafana-login.html | head -1 | cut -d\" -f2 | sed "s/&amp;/\&/g")
cb=$(curl -s -b "$J" -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 15 \
    -d "login=alice@otternet.lab" -d "password=password" "http://10.90.0.11:32556${form}")
curl -s -b "$J" -c "$J" -o /dev/null --max-time 20 "http://127.0.0.1:13000/login/generic_oauth?${cb#*\?}"
curl -s -b "$J" --max-time 10 http://127.0.0.1:13000/api/user/orgs \
    | python3 -c "import json,sys; print(json.load(sys.stdin)[0][\"role\"])"
' 2>/dev/null)
check "$grafana_role" "Viewer" "alice signs in to Grafana through Dex and lands as Viewer"

# EVERY PANEL OF EVERY OTTERNET DASHBOARD HAS DATA, ASKED THROUGH GRAFANA. This used
# to query Prometheus directly and passed while every panel on the lab read "No
# data": Grafana's Prometheus plugin was not registered, so each `/api/ds/query`
# answered `plugin.notRegistered` while Prometheus held everything. The helper runs
# the datasource health check, then every visible query of every panel in the
# OTTERNET folder through `/api/ds/query`, with the dashboards' own variables, and
# names each panel that returns no data or an error. Its allowlist is the one place
# a query may be empty, with a reason per entry.
#
# RETRIED FOR A BOUNDED WINDOW, because the bootstrap's own last step can empty a
# panel for a minute: the firewall's first full-config push lands moments before
# this stage, and its rate() panels need two SNMP samples after it. Measured: four
# firewall panels empty at the check, all nine full a few minutes later. A panel
# that stays empty for the whole window still fails, with the last listing.
grafana_ok=0
for attempt in 1 2 3 4 5 6; do
    if uv run python scripts/check_grafana_panels.py --url http://127.0.0.1:13000; then
        grafana_ok=1
        break
    fi
    [ "$attempt" -lt 6 ] && { echo "      (attempt $attempt: retrying in 45s while recent pushes settle)"; sleep 45; }
done
if [ "$grafana_ok" = 1 ]; then
    pass "every OTTERNET dashboard panel returns data through Grafana"
else
    fail "an OTTERNET dashboard panel returns no data or an error through Grafana (listed above)"
fi
kill "$pf" 2>/dev/null

# ORGANISATION METRICS, counted against Infrahub itself rather than a number
# written here: one exporter series per DcimGenericDevice in the graph.
want_devices=$(count DcimGenericDevice)
check "$(promql 'count(infrahub_dcimgenericdevice_info)')" "$want_devices" \
    "the organisation dashboard's device series match Infrahub's device count"

# DEVICE TELEMETRY, PER FAMILY, so a family that collects nothing fails by name.
# The expected numbers are the seeded monitoring profiles' reach -- every member
# of each family's group -- and every target Telegraf has came from Infrahub.
for family in "DcimFabricSwitch 7" "DcimDevice 6" "SecurityFirewall 1" "ComputePhysicalServer 3"; do
    set -- $family
    check "$(promql "count(count by (device) ({job=\"telemetry\",kind=\"$1\"}))")" "$2" \
        "telemetry reported by every modelled $1"
done

kill "$prom_pf" 2>/dev/null

elapsed=$(( $(date +%s) - started ))
printf '\n=== [%s] COMPLETE in %sm%ss — %s failure(s) ===\n' \
    "$LABEL" "$((elapsed / 60))" "$((elapsed % 60))" "$FAILURES"
[ "$FAILURES" -eq 0 ] || printf 'bootstrap log: %s/bootstrap.log\n' "$LOG"
exit "$FAILURES"
