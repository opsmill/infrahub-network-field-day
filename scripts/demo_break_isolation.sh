#!/usr/bin/env bash
# Make a proposed-change check FAIL on purpose, then put it back.
#
# WHY. Every validator is green on every proposed change this demo produces, so
# the review step reads as decoration -- the audience never sees it catch
# anything, and "merging is the approval" sounds like a slogan rather than a
# control. This breaks the lab's central claim in the one way the graph can
# express, and lets `wan-service-consistency` say so.
#
# WHAT IT BREAKS. `ServiceL3vpn.circuits` is not a label, it is the routing
# domain: two of a tenant's sites reach each other because both circuits are in
# that list. Adding ANOTHER tenant's circuit joins two tenants directly across
# the provider edge -- the exact east-west path the WAN services claim is
# structurally impossible. Nothing about the rendered configuration looks wrong;
# the check is what notices.
#
# It is done on a branch, in a proposed change, and never merged. `--revert`
# deletes the branch and the change, leaving main untouched throughout.
#
#   scripts/demo_break_isolation.sh            # break it, open the change
#   scripts/demo_break_isolation.sh --revert   # delete the branch and the change
set -euo pipefail

BRANCH="${OTTERNET_DEMO_BREAK_BRANCH:-demo-broken-isolation}"
ADDRESS="${INFRAHUB_ADDRESS:-http://localhost:8000}"
TOKEN="${INFRAHUB_API_TOKEN:?INFRAHUB_API_TOKEN must be set}"

# globex's circuit, added to acme's L3VPN. Resolved by name rather than pinned by
# id, because ids differ on every rebuild of this lab.
VPN_NAME="${OTTERNET_DEMO_VPN:-acme-l3vpn}"
FOREIGN_CIRCUIT="${OTTERNET_DEMO_CIRCUIT:-globex-hq}"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

gql() {  # gql <query> [branch]
    local query="$1" branch="${2:-}" url="$ADDRESS/graphql"
    [ -n "$branch" ] && url="$ADDRESS/graphql/$branch"
    python3 -c '
import json, sys, urllib.request
url, query, token = sys.argv[1], sys.argv[2], sys.argv[3]
body = json.dumps({"query": query}).encode()
request = urllib.request.Request(url, body, {"Content-Type": "application/json", "X-INFRAHUB-KEY": token})
with urllib.request.urlopen(request, timeout=60) as response:
    payload = json.load(response)
if "errors" in payload:
    print(json.dumps(payload["errors"]), file=sys.stderr)
    raise SystemExit(1)
print(json.dumps(payload["data"]))
' "$url" "$query" "$TOKEN"
}

if [ "${1:-}" = "--revert" ]; then
    say "Deleting the proposed change and the branch"
    pc=$(gql "{CoreProposedChange(source_branch__value: \"$BRANCH\"){edges{node{id}}}}" \
        | python3 -c 'import json,sys; e=json.load(sys.stdin)["CoreProposedChange"]["edges"]; print(e[0]["node"]["id"] if e else "")')
    if [ -n "$pc" ]; then
        gql "mutation { CoreProposedChangeDelete(data: {id: \"$pc\"}) { ok } }" >/dev/null
        echo "  proposed change deleted"
    fi
    if gql "{Branch(name: \"$BRANCH\"){name}}" >/dev/null 2>&1; then
        gql "mutation { BranchDelete(data: {name: \"$BRANCH\"}) { ok } }" >/dev/null || true
        echo "  branch deleted"
    fi
    say "main is untouched; nothing was ever merged"
    exit 0
fi

say "Resolving $VPN_NAME and the foreign circuit $FOREIGN_CIRCUIT"
ids=$(gql "{
  ServiceL3vpn(name__value: \"$VPN_NAME\") { edges { node { id tenant { node { name { value } } } } } }
  DcimCircuit(circuit_id__value: \"$FOREIGN_CIRCUIT\") { edges { node { id tenant { node { name { value } } } } } }
}")
vpn_id=$(printf '%s' "$ids" | python3 -c 'import json,sys; print(json.load(sys.stdin)["ServiceL3vpn"]["edges"][0]["node"]["id"])')
vpn_tenant=$(printf '%s' "$ids" | python3 -c 'import json,sys; print(json.load(sys.stdin)["ServiceL3vpn"]["edges"][0]["node"]["tenant"]["node"]["name"]["value"])')
circuit_id=$(printf '%s' "$ids" | python3 -c 'import json,sys; print(json.load(sys.stdin)["DcimCircuit"]["edges"][0]["node"]["id"])')
circuit_owner=$(printf '%s' "$ids" | python3 -c 'import json,sys; print(json.load(sys.stdin)["DcimCircuit"]["edges"][0]["node"]["tenant"]["node"]["name"]["value"])')
[ "$vpn_tenant" = "$circuit_owner" ] && die "$FOREIGN_CIRCUIT already belongs to $vpn_tenant; pick a circuit of another tenant"
echo "  $VPN_NAME belongs to $vpn_tenant; $FOREIGN_CIRCUIT belongs to $circuit_owner"

say "Creating branch $BRANCH"
gql "mutation { BranchCreate(data: {name: \"$BRANCH\", sync_with_git: false}) { ok } }" >/dev/null

say "Adding ${circuit_owner}'s circuit to ${vpn_tenant}'s L3VPN"
# RelationshipAdd rather than an Update, so the existing circuits stay: the point
# is a list that has one too many, not a list that was replaced.
gql "mutation {
  RelationshipAdd(data: {id: \"$vpn_id\", name: \"circuits\", nodes: [{id: \"$circuit_id\"}]}) { ok }
}" "$BRANCH" >/dev/null

say "Opening the proposed change"
pc=$(gql "mutation {
  CoreProposedChangeCreate(data: {
    name: { value: \"Add $FOREIGN_CIRCUIT to $VPN_NAME\" }
    description: { value: \"Deliberately wrong, for the demo: this puts ${circuit_owner}'s circuit into ${vpn_tenant}'s routing domain, which would let the two tenants reach each other directly across the provider edge. wan-service-consistency is expected to fail.\" }
    source_branch: { value: \"$BRANCH\" }
    destination_branch: { value: \"main\" }
  }) { object { id } }
}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["CoreProposedChangeCreate"]["object"]["id"])')

# THE CHECKS MUST BE RE-RUN, and finding that out is worth the extra call.
# Creating a proposed change kicks off its validators immediately, and that first
# pass raced the relationship added a moment earlier: measured 62 checks, all
# green, over data that was already wrong. Asking again produces the failure --
# 67 checks, one red. Without this the demo shows an all-green change and the
# presenter has to explain why the thing they just broke is not reported.
say "Re-running the checks"
gql "mutation { CoreProposedChangeRunCheck(data: {id: \"$pc\", check_type: ALL}) { ok } }" >/dev/null
printf '  waiting for a check to report the breakage'
for _ in $(seq 1 30); do
    failing=$(gql "{CoreCheck{edges{node{conclusion{value}}}}}" "$BRANCH" \
        | python3 -c 'import json,sys; print(sum(1 for e in json.load(sys.stdin)["CoreCheck"]["edges"] if e["node"]["conclusion"]["value"] != "success"))')
    [ "$failing" -gt 0 ] && { printf '\n  %s check(s) failing\n' "$failing"; break; }
    printf '.'
    sleep 10
done

say "Done"
cat <<EOF
  Open:  $ADDRESS/proposed-changes/$pc
  Watch: the Checks tab. 'wan-service-consistency' should FAIL and name both
         tenants, while every other validator stays green -- the configuration
         renders perfectly, which is the point.

  Put it back with:  scripts/demo_break_isolation.sh --revert
EOF
