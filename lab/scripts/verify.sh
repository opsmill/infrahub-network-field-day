#!/usr/bin/env bash
# End-to-end checks across all three pillars: fabric, security and Kubernetes.
# Every check prints the command it ran, so a failure is something you can go and
# reproduce by hand rather than a bare red cross.
set -uo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-$LAB_DIR/k8s/.kubeconfig/kubeconfig.yaml}"
pass=0; fail=0; skip=0

hdr()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[1;32mPASS\033[0m  %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[1;31mFAIL\033[0m  %s\n\n        %s\n' "$1" "$2"; fail=$((fail+1)); }
skp()  { printf '  \033[1;33mSKIP\033[0m  %s (%s)\n' "$1" "$2"; skip=$((skip+1)); }

# check <name> <expected-regex> <command...>
check() {
    local name="$1" want="$2"; shift 2
    local out
    out=$("$@" 2>&1)
    if grep -qE "$want" <<<"$out"; then ok "$name"; else bad "$name" "\$ $* -> expected /$want/, got: $(head -3 <<<"$out" | tr '\n' ' ')"; fi
}

# -p 15 is required: without it EOS answers "privileged mode required"
# to most show commands and the check fails for the wrong reason.
eos()  { docker exec "clab-otternet-$1" Cli -p 15 -c "$2"; }
node() { docker exec "clab-otternet-$1" sh -c "$2"; }

running() { docker ps --format '{{.Names}}' | grep -qx "clab-otternet-$1"; }

# sr_cli on a WAN router, one command, no candidate. Route lookups are anchored
# with `^<prefix>` below because SR Linux prints the table header -- which names
# the network instance -- even when the prefix is absent.
srl()  { docker exec "clab-otternet-$1" sr_cli -d "$2" 2>/dev/null; }
# A BGP neighbour of $1 in network instance $3 matching $2 that is established.
srl_peer() { srl "$1" "show network-instance ${3:-default} protocols bgp neighbor" | grep -E "$2" | grep established; }

# The lab has one firewall, a Junos vSRX, and the branch baseline permits the
# access portal and nothing else -- so a branch user reaching an arbitrary DC
# service is a policy failure rather than a healthy datapath. Ask the node what
# it is rather than assuming, because a topology edit that swaps the kind would
# otherwise make every firewall check below silently vacuous.
fw_kind=$(docker inspect clab-otternet-fw1 \
            --format '{{ index .Config.Labels "clab-node-kind" }}' 2>/dev/null || echo "")

# Junos over SSH on the management address, from inside the node's own
# container so the host needs no sshpass.
jnpr() {
    docker exec clab-otternet-fw1 sshpass -p "${OTTERNET_VSRX_PASSWORD:-admin@123}" \
        ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -o ConnectTimeout=10 admin@127.0.0.1 "$1" 2>/dev/null
}

kube_ok() {
    [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1 && kubectl get nodes >/dev/null 2>&1
}
ns_exists() { kubectl get ns "$1" >/dev/null 2>&1; }

# The first advertised LoadBalancer Service in namespace $1, as
# "<name> <vip> <clusterIP> <port>". Looked up by the advertisement label rather
# than by name, because the name is not stable across the two ways this lab is
# driven: the lab's own claim calls it `frontend`, the Helm chart Infrahub
# delivers calls it `<release>-whoami`.
advertised_svc() {
    kubectl -n "$1" get svc -l otternet.lab/advertise=true -o json 2>/dev/null | python3 -c '
import json,sys
for s in json.load(sys.stdin)["items"]:
    if s["spec"].get("type") != "LoadBalancer": continue
    ing=(s.get("status",{}).get("loadBalancer",{}).get("ingress") or [{}])[0].get("ip","")
    print(s["metadata"]["name"], ing or "-", s["spec"].get("clusterIP","-"), s["spec"]["ports"][0]["port"]); break'
}

# Does the FabricApp deploying into namespace $1 own the VIP $2? Prints the block.
vip_in_block() {
    kubectl get fabricapp -o json 2>/dev/null | python3 -c '
import json,sys,ipaddress
ns,vip=sys.argv[1],ipaddress.ip_address(sys.argv[2])
for a in json.load(sys.stdin)["items"]:
    if a["spec"].get("namespace")!=ns: continue
    b=(a["spec"].get("expose") or {}).get("vipBlock")
    if b and vip in ipaddress.ip_network(b): print(b)' "$1" "$2"
}

# THE POD GATE: would the CiliumNetworkPolicies in namespace $1 admit source
# address $3 to the pods behind Service $2? Read from the policies themselves
# rather than from the FabricApp, because the lab-only access path adds its own
# policy beside the composed one while the Infrahub path widens the composed
# one -- both end up here. A pod no policy selects is admitted, as Cilium does.
pod_admits() {
    python3 - "$1" "$2" "$3" <<'PY'
import ipaddress, json, subprocess, sys
ns, svc, src = sys.argv[1], sys.argv[2], ipaddress.ip_address(sys.argv[3])
k = lambda *a: json.loads(subprocess.run(["kubectl", "-n", ns, *a, "-o", "json"],
                                         capture_output=True, text=True).stdout or "{}")
sel = k("get", "svc", svc).get("spec", {}).get("selector") or {}
pods = k("get", "pods", "-l", ",".join(f"{a}={b}" for a, b in sel.items())).get("items", [])
labels = pods[0]["metadata"].get("labels", {}) if pods else {}
selected = admitted = False
for p in k("get", "cnp").get("items", []):
    want = p["spec"].get("endpointSelector", {}).get("matchLabels", {})
    if not all(labels.get(a) == b for a, b in want.items()):
        continue
    rules = p["spec"].get("ingress")
    if rules is None:
        continue
    selected = True
    for r in rules:
        cidrs = list(r.get("fromCIDR", [])) + [c.get("cidr") for c in r.get("fromCIDRSet", [])]
        if any(c and src in ipaddress.ip_network(c) for c in cidrs):
            admitted = True
print("admit" if admitted or not selected else "drop")
PY
}

# THE FIREWALL GATE: does fw1's policy, evaluated first-match as Junos does,
# permit source $2 in zone $1 to $3:$4/tcp in zone k8s-prod? Derived from the
# running configuration so that a grant -- which is a new policy, not a change
# to the baseline -- is recognised whatever the grant is called. Reads the
# configuration from $fw_cfg, which load_fw_cfg fills once: every call would
# otherwise be two more SSH sessions to a box whose sessions are not cheap.
fw_cfg=""
load_fw_cfg() {
    [[ -n "$fw_cfg" ]] && return
    fw_cfg=$(jnpr "show configuration security | display set"; jnpr "show configuration applications | display set")
}
fw_permits() {
    python3 -c '
import ipaddress, sys
zone, src, dst, port = sys.argv[1], ipaddress.ip_address(sys.argv[2]), ipaddress.ip_address(sys.argv[3]), int(sys.argv[4])
addr, sets, apps, order, pol = {}, {}, {}, [], {}
builtin = {"junos-http": {80}, "junos-https": {443}}
for line in sys.stdin:
    t = line.split()
    if t[:5] == ["set", "security", "address-book", "global", "address"] and len(t) >= 7:
        try: addr[t[5]] = ipaddress.ip_network(t[6])
        except ValueError: pass
    elif t[:5] == ["set", "security", "address-book", "global", "address-set"] and len(t) >= 8:
        sets.setdefault(t[5], []).append(t[7])
    elif t[:3] == ["set", "applications", "application"] and len(t) >= 6 and t[4] == "destination-port":
        lo, _, hi = t[5].partition("-")
        apps[t[3]] = set(range(int(lo), int(hi or lo) + 1))
    elif t[:3] == ["set", "security", "policies"] and len(t) >= 10 and t[3] == "from-zone" \
            and t[4] == zone and t[6] == "k8s-prod":
        p = pol.setdefault(t[8], {"source-address": [], "destination-address": [], "application": [], "then": None})
        if t[8] not in order: order.append(t[8])
        if t[9] == "match" and len(t) >= 12: p.setdefault(t[10], []).append(t[11])
        elif t[9] == "then" and t[10] in ("permit", "deny", "reject"): p["then"] = t[10]
def has(name, ip, seen=()):
    if name in ("any", "any-ipv4"): return True
    if name in addr: return ip in addr[name]
    return any(has(m, ip, seen + (name,)) for m in sets.get(name, []) if m not in seen)
def serves(name):
    return name == "any" or port in builtin.get(name, apps.get(name, set()))
for n in order:
    p = pol[n]
    if any(has(a, src) for a in p["source-address"]) and any(has(a, dst) for a in p["destination-address"]) \
            and any(serves(a) for a in p["application"]):
        print(("permit " if p["then"] == "permit" else "deny ") + n); break
else:
    print("deny default")' "$1" "$2" "$3" "$4" <<<"$fw_cfg" 2>/dev/null || echo "deny unparsed"
}

# One source host, one destination VIP, and the two independent gates between
# them. The answer is DERIVED from configuration -- the firewall's policy and
# the pods' CiliumNetworkPolicy -- and then the datapath has to agree with it in
# both directions: open-but-unreachable is a broken datapath, and
# closed-but-reachable is a security failure. Nothing here assumes which way
# round the gates are set, so a grant made while the lab is running moves the
# expectation instead of failing the check.
#   gated_reach <label> <src-node> <src-ip> <src-zone> <ns> <svc> <vip> <port> <path>
gated_reach() {
    local label="$1" node="$2" sip="$3" zone="$4" ns="$5" svc="$6" vip="$7" port="$8" path="$9"
    local fw pod code
    fw=$(fw_permits "$zone" "$sip" "$vip" "$port")
    pod=$(pod_admits "$ns" "$svc" "$sip")
    code=$(docker exec "clab-otternet-$node" curl -sS -o /dev/null -w '%{http_code}' \
             --max-time 6 "http://$vip:$port$path" 2>/dev/null)
    local why="firewall: ${fw}; pod policy: ${pod}"
    if [[ "$fw" == permit* && "$pod" == "admit" ]]; then
        [[ "$code" == "200" ]] \
            && ok "$label: reachable, both gates open ($why)" \
            || bad "$label" "both gates are open ($why) but http://$vip:$port$path returned ${code:-nothing} from $node -- the datapath is broken"
    else
        [[ "$code" == "200" ]] \
            && bad "$label" "a gate is closed ($why) yet $node reached http://$vip:$port$path -- the gate is not enforcing" \
            || ok "$label: NOT reachable, as configured ($why)"
    fi
}

# =============================================================== fabric =====
hdr "Fabric underlay and overlay"
if running spine1; then
    # EOS abbreviates the state to "Estab" in summary output.
    check "spine1 has all 5 underlay BGP sessions up" \
          "^5$" bash -c 'docker exec clab-otternet-spine1 Cli -p 15 -c "show ip bgp summary" | grep -c Estab' 
    check "spine1 has all 5 EVPN overlay sessions up" \
          "^5$" bash -c 'docker exec clab-otternet-spine1 Cli -p 15 -c "show bgp evpn summary" | grep -c Estab' 
    check "k8s-leaf1/2 MLAG is Active and config-consistent" \
          "Active" eos k8s-leaf1 "show mlag"
    check "MLAG peer config is consistent" \
          "consistent" eos k8s-leaf1 "show mlag"
    # Deliberately not checking "show vxlan vtep": the MLAG pair shares one VTEP
    # address, and the only other VTEPs carry different VLANs, so zero remote
    # VTEPs is the correct answer. Assert symmetric IRB via type-5 instead.
    check "k8s-leaf1 has the VXLAN VNI for the k8s tenant" \
          "110" eos k8s-leaf1 "show vxlan vni"
    check "k8s-leaf1 learned the firewall handoff as an EVPN type-5 route" \
          "10\.250\.110\.0/30" eos k8s-leaf1 "show ip route vrf K8S_PROD"
    # Vlan110 holds the per-leaf address (10.110.0.2/.3); 10.110.0.1 is the
    # shared VARP gateway and only shows under virtual-router.
    check "k8s-leaf1 has its unique SVI address for BGP peering" \
          "10\.110\.0\.2" eos k8s-leaf1 "show ip interface Vlan110"
    # `show ip virtual-router` prints the shared MAC, not the per-interface
    # addresses -- read them from the interface config instead.
    check "the VARP anycast gateway is configured on Vlan110" \
          "10\.110\.0\.1" eos k8s-leaf1 "show running-config interfaces Vlan110"
    check "border-leaf1 holds both tenant VRFs" \
          "APP_PROD" eos border-leaf1 "show vrf"
else
    skp "fabric checks" "ceOS nodes are not running"
fi

# ============================================================= security =====
hdr "Security enforcement"
if running k8s-leaf1; then
    # cEOS cannot apply an ACL to an SVI, so the tenant source-validation ACL
    # lives outbound on the border leaf's routed handoff instead.
    check "tenant source-validation ACL is applied on the border leaf" \
          "ACL-K8S-ANTISPOOF" eos border-leaf1 "show ip access-lists summary"
    check "BGP route policy toward Cilium is installed" \
          "RM-CILIUM-IN" eos k8s-leaf1 "show route-map RM-CILIUM-IN"
    check "management ACL is bound to the SSH server" \
          "ACL-MGMT-IN" eos k8s-leaf1 "show running-config section management ssh"
    # The fabric must NOT leak between tenants -- that is the firewall's job.
    if eos k8s-leaf1 "show ip route vrf K8S_PROD 10.210.0.0/24" 2>&1 | grep -qE 'via 10\.250\.110\.2|0\.0\.0\.0/0'; then
        ok "app tenant is reachable only via the firewall default route"
    elif eos k8s-leaf1 "show ip route vrf K8S_PROD 10.210.0.0/24" 2>&1 | grep -q "10.210.0.0/24"; then
        bad "tenant isolation" "K8S_PROD has a direct route to 10.210.0.0/24 -- the VRFs are leaking and the firewall is being bypassed"
    else
        ok "no direct route from K8S_PROD to the app tenant"
    fi
else
    skp "fabric security checks" "ceOS nodes are not running"
fi

if running fw1; then
    if [[ "$fw_kind" == "juniper_vsrx" ]]; then
        ok "the firewall is a Junos vSRX"
    else
        bad "firewall kind" "fw1 is running as kind '${fw_kind:-unknown}', not juniper_vsrx -- every firewall check below is written against Junos and would pass or fail for the wrong reason"
    fi

    # No serial-console driver needed: vrnetlab loads configs/fw/vsrx/junos.conf
    # at boot and the box is reachable properly from the start.
    check "vSRX zones are bound to all six handoff interfaces" \
          "ge-0/0/5" jnpr "show configuration security zones | display set"
    check "vSRX policy permits app -> published k8s services" \
          "app-to-k8s-services" jnpr "show configuration security policies | display set"
    check "vSRX default policy is deny-all" \
          "deny-all" jnpr "show configuration security policies | display set"
    check "the branch's only standing permit is the access portal" \
          "branch-to-access-portal" jnpr "show configuration security policies | display set"
    check "vSRX has routes back into both tenants" \
          "10\.250\.210\.1" jnpr "show configuration routing-options | display set"
    # A NAT rule here would translate pod addresses and quietly invalidate
    # every ACL and policy downstream while traffic still flowed.
    if jnpr "show configuration security nat" | grep -qE "pool|rule-set"; then
        bad "vSRX NAT" "a NAT rule set exists -- pod addresses will be translated and the ACL/policy demo becomes meaningless"
    else
        ok "vSRX performs no NAT (pod addresses stay intact on the wire)"
    fi
    # The MTU compromise this platform forces. Without the clamp, large TCP
    # through the firewall stalls in exactly the way the lab warns about.
    # The clamp is sized for the VXLAN fabric BEHIND the firewall, not for its
    # own 9192-byte interface: 9214 - 50 (VXLAN) - 20 (IP) - 20 (TCP) = 9124.
    # The interface-sized 9138 was measured to drop every full-size segment
    # inside the fabric, so matching it here would pass a broken datapath.
    check "vSRX clamps TCP MSS to 9124, sized for the VXLAN fabric behind it" \
          "tcp-mss all-tcp mss 9124$" jnpr "show configuration security flow | display set"
else
    skp "firewall checks" "fw1 is not running"
fi

# =========================================================== kubernetes =====
hdr "Kubernetes and fabric integration"
demo_svc=""; demo_vip=""; demo_cip=""; demo_port=""; metrics_ns=""
if kube_ok; then
    check "all three k3s nodes are Ready" \
          "^3$" bash -c 'kubectl get nodes --no-headers | grep -c " Ready "'
    check "Cilium is running on every node" \
          "3" bash -c 'kubectl -n kube-system get ds cilium -o jsonpath="{.status.numberReady}"'
    check "Cilium BGP sessions to both leaves are established" \
          "established" bash -c 'kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers 2>/dev/null || kubectl get ciliumbgpclusterconfig otternet-fabric -o yaml'
    # The demo application's advertised Service, whichever writer delivered it,
    # and the observability stack's namespace: `otternet-metrics` when Infrahub
    # delivers it, the lab's own `otternet-observability` otherwise. Detected,
    # never assumed, so a lab deployed without Infrahub still verifies.
    read -r demo_svc demo_vip demo_cip demo_port <<<"$(advertised_svc otternet-demo)"
    metrics_ns=""
    for n in otternet-metrics otternet-observability; do
        ns_exists "$n" && { metrics_ns=$n; break; }
    done
    if [[ -n "${demo_svc:-}" && "$demo_vip" != "-" ]]; then
        blk=$(vip_in_block otternet-demo "$demo_vip")
        [[ -n "$blk" ]] \
            && ok "the demo app's Service $demo_svc holds VIP $demo_vip, inside its own block $blk" \
            || bad "demo VIP" "$demo_svc holds $demo_vip, which is outside the otternet-demo FabricApp's vipBlock -- another app's pool handed it out"
    else
        bad "demo VIP" "no advertised LoadBalancer Service with a VIP in otternet-demo -- kubectl -n otternet-demo get svc -l otternet.lab/advertise=true"
    fi
    # externalTrafficPolicy: Local is what lets the pod policy see the client.
    # With the chart default, Cluster, a request landing on a node whose chosen
    # backend is elsewhere is SNATed to that node's address, admitted as
    # `remote-node`, and the source-prefix rule decides nothing for it. The
    # datapath half of this -- whoami reporting host-a's own address -- is
    # checked under "Datapath" below.
    if [[ -n "${demo_svc:-}" ]]; then
        check "the demo app's Service keeps the client address (externalTrafficPolicy Local)" \
              "^Local$" kubectl -n otternet-demo get svc "$demo_svc" -o jsonpath='{.spec.externalTrafficPolicy}'
    fi
    check "default-deny policy is in force in the demo namespace" \
          "default-deny" bash -c 'kubectl -n otternet-demo get cnp -o name'

    if running k8s-leaf1; then
        check "the leaf learned the pod CIDR over BGP from Cilium" \
              "10\.111\." eos k8s-leaf1 "show ip route vrf K8S_PROD bgp"
        check "the demo app's LoadBalancer VIP reached the fabric" \
              "${demo_vip:-10.112.240.}/32" eos k8s-leaf1 "show ip route vrf K8S_PROD bgp"
    fi
else
    skp "kubernetes checks" "cluster not reachable -- run make k8s"
fi

# ================================================================== wan =====
# The ISP, its customers, and the branch office. The interesting checks here
# are the negative ones: a customer must reach the DC's published services and
# must NOT reach the other customer, and the two properties are enforced in
# different places (the DC's firewall, and the ISP's route policy).
hdr "ISP, WAN customers and the branch"
if running isp-pe1 && running isp-pe2; then
    check "the ISP core session between both PEs is established" \
          "10\.50\.255\.2" srl_peer isp-pe1 "10\.50\.255\.2"
    check "isp-pe2 peers with the DC border leaf" \
          "10\.250\.50\.1" srl_peer isp-pe2 "10\.250\.50\.1"

    # Every customer's eBGP session, and what it is allowed to learn.
    for c in acme globex; do
        if running "cust-$c-ce"; then
            check "customer $c has an established session to the ISP" \
                  "65500" srl_peer "cust-$c-ce" "10\.51\."
            check "customer $c learned the DC service prefix" \
                  "10\.112\.240\.0/24" srl "cust-$c-ce" "show network-instance default protocols bgp routes ipv4 summary"
        fi
    done

    # THE isolation check. Both customers' prefixes sit in the ISP's default
    # table -- they have to, or the DC could not route back -- so this passing
    # is entirely down to the import route-map on isp-pe1.
    if running cust-acme-ce && running cust-globex-ce; then
        if srl cust-acme-ce "show network-instance default ipv4 route 10.60.20.0/24" | grep -q "^10.60.20.0/24"; then
            bad "customer isolation" "cust-acme has a route to cust-globex's LAN -- the provider is transiting between customers, check RM-ACME-IMPORT and RM-GLOBEX-IMPORT on isp-pe1"
        else
            ok "customer isolation: acme has no route to globex's LAN"
        fi
        if srl cust-globex-ce "show network-instance default ipv4 route 10.60.10.0/24" | grep -q "^10.60.10.0/24"; then
            bad "customer isolation" "cust-globex has a route to cust-acme's LAN"
        else
            ok "customer isolation: globex has no route to acme's LAN"
        fi
        # A customer must not learn DC internals either.
        if srl cust-acme-ce "show network-instance default ipv4 route 10.111.0.0/16" | grep -q "^10.111"; then
            bad "DC internals leaked" "a WAN customer learned the pod CIDR -- check RM-DC-TO-EXTERNAL on border-leaf1"
        else
            ok "a WAN customer never learns the DC pod CIDR"
        fi
    fi
else
    skp "ISP checks" "the ISP routers are not running"
fi

if running border-leaf1; then
    check "border-leaf1 holds the WAN and BRANCH VRFs" \
          "BRANCH" eos border-leaf1 "show vrf"
    check "the WAN VRF learned both customer prefixes over eBGP" \
          "10\.60\.20\.0/24" eos border-leaf1 "show ip route vrf WAN bgp"
    check "the BRANCH VRF learned the branch LAN over eBGP" \
          "10\.70\.0\.0/24" eos border-leaf1 "show ip route vrf BRANCH bgp"
    # Neither external VRF may have a route into a tenant: the only way in is
    # out through the firewall and back.
    if eos border-leaf1 "show ip route vrf WAN 10.111.0.0/16" 2>&1 | grep -q "10.111.0.0/16"; then
        bad "WAN isolation" "VRF WAN has a route to the pod CIDR -- an external network can bypass the firewall"
    else
        ok "VRF WAN has no route into the k8s tenant (only via the firewall)"
    fi
    check "the WAN route policy that bounds the ISP is installed" \
          "RM-WAN-IN" eos border-leaf1 "show route-map RM-WAN-IN"
    check "the branch source-validation ACL is applied" \
          "ACL-FROM-BRANCH" eos border-leaf1 "show ip access-lists summary"
fi

if running branch-rtr; then
    check "the branch router peers with the border leaf directly" \
          "65103" srl_peer branch-rtr "10\.250\.70\.1"
    check "the branch learned the DC service prefix" \
          "10\.112\.240\.0/24" srl branch-rtr "show network-instance default protocols bgp routes ipv4 summary"
    # The branch must not be reachable from, or able to reach, the WAN.
    if srl branch-rtr "show network-instance default ipv4 route 10.60.0.0/16" | grep -q "^10.60"; then
        bad "branch isolation" "the branch has a route to WAN customer space"
    else
        ok "the branch has no route to WAN customer space"
    fi
fi

# =========================================================== crossplane =====
# The platform is only as declarative as its controllers are healthy. A broken
# provider does not break what is already running -- it stops new intent from
# being applied and stops drift from being corrected, which is a silent failure
# and worth an explicit check.
hdr "Crossplane control plane"
if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1 && kubectl get providers >/dev/null 2>&1; then
    check "both providers are installed and healthy" \
          "^2$" bash -c 'kubectl get providers -o json | python3 -c "
import json,sys
n=0
for p in json.load(sys.stdin)[\"items\"]:
    c={x[\"type\"]:x[\"status\"] for x in p.get(\"status\",{}).get(\"conditions\",[])}
    if c.get(\"Installed\")==\"True\" and c.get(\"Healthy\")==\"True\": n+=1
print(n)"'
    check "both composition functions are healthy" \
          "^2$" bash -c 'kubectl get functions -o json | python3 -c "
import json,sys
n=0
for p in json.load(sys.stdin)[\"items\"]:
    c={x[\"type\"]:x[\"status\"] for x in p.get(\"status\",{}).get(\"conditions\",[])}
    if c.get(\"Healthy\")==\"True\": n+=1
print(n)"'
    # Every otternet.lab XRD, not a fixed count of them: the lab grew a third API
    # (AppAccess) and a hard-coded 2 turns that into a failure that says
    # nothing about what is actually wrong.
    check "every platform API is established" \
          "^$" bash -c 'kubectl get xrd -o json | python3 -c "
import json,sys
for x in json.load(sys.stdin)[\"items\"]:
    if x[\"metadata\"][\"name\"].endswith(\"otternet.lab\"):
        c={i[\"type\"]:i[\"status\"] for i in x.get(\"status\",{}).get(\"conditions\",[])}
        if c.get(\"Established\")!=\"True\": print(x[\"metadata\"][\"name\"])"'
    check "the FabricPeering claim is synced and ready" \
          "True True" bash -c 'kubectl get fabricpeering otternet -o jsonpath="{range .status.conditions[*]}{.status} {end}" | tr -s " "'
    check "every FabricApp is ready" \
          "^$" bash -c 'kubectl get fabricapp -o json | python3 -c "
import json,sys
for a in json.load(sys.stdin)[\"items\"]:
    c={x[\"type\"]:x[\"status\"] for x in a.get(\"status\",{}).get(\"conditions\",[])}
    if c.get(\"Ready\")!=\"True\": print(a[\"metadata\"][\"name\"])"'
    check "every composed resource is synced" \
          "^$" bash -c 'kubectl get objects.kubernetes.crossplane.io,releases.helm.crossplane.io -o json | python3 -c "
import json,sys
for o in json.load(sys.stdin)[\"items\"]:
    c={x[\"type\"]:x[\"status\"] for x in o.get(\"status\",{}).get(\"conditions\",[])}
    if c.get(\"Synced\")!=\"True\": print(o[\"kind\"], o[\"metadata\"][\"name\"])"'

    # The Cilium config that used to be hand-applied is now composed. Check it
    # exists AND that Crossplane owns it, because an orphaned CRD left behind by
    # a deleted Object looks identical until something tries to change it.
    check "the BGP peering Cilium runs on is owned by Crossplane" \
          "otternet-fabric" bash -c 'kubectl get objects.kubernetes.crossplane.io -o json | python3 -c "
import json,sys
for o in json.load(sys.stdin)[\"items\"]:
    m=o[\"spec\"][\"forProvider\"][\"manifest\"]
    if m[\"kind\"]==\"CiliumBGPClusterConfig\": print(m[\"metadata\"][\"name\"])"'
    # Named pools with no namespace in their selector match services
    # cluster-wide, so two apps hand each other addresses. Print the offenders
    # rather than counting the good ones -- an approved access request creates
    # another pool while the lab is running.
    check "every VIP pool is scoped to its own namespace" \
          "^$" bash -c 'kubectl get ciliumloadbalancerippool -o json | python3 -c "
import json,sys
for p in json.load(sys.stdin)[\"items\"]:
    sel=p[\"spec\"].get(\"serviceSelector\",{}).get(\"matchLabels\",{})
    if \"io.kubernetes.service.namespace\" not in sel: print(p[\"metadata\"][\"name\"])"'

    # The real chart, actually deployed by provider-helm.
    check "kube-prometheus-stack is deployed as a Helm release" \
          "deployed" bash -c 'kubectl get releases.helm.crossplane.io -o jsonpath="{.items[*].status.atProvider.state}"'
    # Ask Prometheus itself, through the API server's service proxy, rather than
    # grepping its configuration: a job that is configured and never scraped
    # successfully is exactly what a dashboard full of "No data" looks like.
    if [[ -n "$metrics_ns" ]]; then
        prom=$(kubectl -n "$metrics_ns" get svc -l app=kube-prometheus-stack-prometheus \
                 -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
        check "Prometheus in $metrics_ns is scraping Cilium on every node" \
              "^cilium-agent up=[1-9][0-9]* down=0$" bash -c "kubectl get --raw '/api/v1/namespaces/$metrics_ns/services/http:$prom:9090/proxy/api/v1/targets?state=active' | python3 -c '
import json,sys
t=[x for x in json.load(sys.stdin)[\"data\"][\"activeTargets\"] if x[\"labels\"].get(\"job\")==\"cilium-agent\"]
up=sum(x[\"health\"]==\"up\" for x in t)
print(\"cilium-agent up=%d down=%d\" % (up, len(t)-up))'"
    else
        bad "Prometheus" "neither otternet-metrics (Infrahub's) nor otternet-observability (the lab's) exists -- the observability stack is not deployed"
    fi
else
    skp "crossplane checks" "Crossplane not installed -- run make crossplane"
fi

# ================================================================ tenants ===
# The provider-edge use case: a tenant with two sites attached two different
# ways, isolated cloud instances in the datacentre, and internet access as a
# product one tenant buys and the other does not.
#
# Almost every check here has a matching negative. "acme reaches acme's cloud"
# is worth very little on its own -- it is only interesting alongside "globex
# does not", because a flat network passes the first and fails the second.
hdr "Tenants: multi-site, isolated cloud, internet as a product"

# Internet access is the builder demonstration's capability: the seeded baseline does not sell it, and
# the merged capability does (acme's import policy gains statement 30, the default route). Ask the
# provider edge which it is, so the checks below hold the lab to the state it is in -- the baseline must
# have no internet for anyone, and a lab with the capability must give it to acme alone.
internet_sold=false
if running isp-pe1 && srl isp-pe1 "info from running /routing-policy policy RM-ACME-IMPORT statement 30" | grep -q "PL-DEFAULT"; then
    internet_sold=true
fi
if $internet_sold; then
    printf '  (internet access is deployed: acme has bought it)\n'
else
    printf '  (internet access is not deployed: the baseline, before the builder capability is merged)\n'
fi

if running isp-pe1; then
    # ---- one VRF per tenant, both sites inside it ------------------------
    check "acme's two sites share one VRF on the PE" \
          "10\.60\.11\.0/24" srl isp-pe1 "show network-instance CUST_ACME ipv4 route"
    check "the statically routed site is redistributed, not peered" \
          "static" srl isp-pe1 "show network-instance CUST_ACME ipv4 route 10.60.11.0/24"
    # acme/dr has no BGP session at all -- if one appears, the site kind in
    # wan/tenants.yml and the rendered config have diverged.
    if srl isp-pe1 "show network-instance CUST_ACME protocols bgp neighbor" | grep -q "10.51.11.2"; then
        bad "acme/dr attachment" "there is a BGP session to the dr CE, but that site is kind: static -- re-render with make wan-build"
    else
        ok "acme/dr has no BGP session, as a static site should not"
    fi

    # ---- per-tenant import policy ----------------------------------------
    check "acme's VRF learns acme's cloud subnet" \
          "10\.220\.10\.0/24" srl isp-pe1 "show network-instance CUST_ACME ipv4 route"
    if srl isp-pe1 "show network-instance CUST_ACME ipv4 route" | grep -q "10.220.20.0/24"; then
        bad "tenant cloud isolation" "acme's VRF has a route to GLOBEX's cloud subnet -- RM-ACME-IMPORT is too wide"
    else
        ok "acme's VRF has no route to globex's cloud"
    fi
    if srl isp-pe1 "show network-instance CUST_GLOBEX ipv4 route" | grep -q "10.220.10.0/24"; then
        bad "tenant cloud isolation" "globex's VRF has a route to ACME's cloud subnet -- RM-GLOBEX-IMPORT is too wide"
    else
        ok "globex's VRF has no route to acme's cloud"
    fi
    if srl isp-pe1 "show network-instance CUST_GLOBEX ipv4 route" | grep -qE "10\.60\.1[01]\.0/24"; then
        bad "tenant isolation" "globex's VRF has a route to an acme site -- the tenants are leaking into each other"
    else
        ok "globex's VRF has no route to any acme site"
    fi

    # ---- internet as a product -------------------------------------------
    if $internet_sold; then
        check "acme's VRF has a default route (it bought internet)" \
              "0\.0\.0\.0/0" srl isp-pe1 "show network-instance CUST_ACME ipv4 route"
    elif srl isp-pe1 "show network-instance CUST_ACME ipv4 route 0.0.0.0/0" | grep -q "^0\.0\.0\.0/0"; then
        bad "internet product" "acme has a default route but internet access is not deployed -- the baseline sells it to no one"
    else
        ok "acme has NO default route, because internet access is not deployed in the baseline"
    fi
    if srl isp-pe1 "show network-instance CUST_GLOBEX ipv4 route 0.0.0.0/0" | grep -q "^0\.0\.0\.0/0"; then
        bad "internet product" "globex has a default route in its VRF but did not buy internet access -- check RM-GLOBEX-IMPORT"
    else
        ok "globex has NO default route, because it did not buy internet"
    fi
fi

if running internet-rtr; then
    if $internet_sold; then
        check "the internet learns acme's prefixes from the provider" \
              "10\.60\.10\.0/24" srl internet-rtr "show network-instance default protocols bgp routes ipv4 summary"
    else
        skp "the internet learns acme's prefixes from the provider" "internet access is not deployed"
    fi
    if srl internet-rtr "show network-instance default protocols bgp routes ipv4 summary" | grep -q "10.60.20.0/24"; then
        bad "internet announcement" "globex's prefix is in the internet's table -- RM-INTERNET-OUT on isp-pe2 is announcing a tenant that did not buy transit"
    else
        ok "globex's prefix is NOT announced to the internet"
    fi
fi

# ---- the fabric side: a VRF per tenant, with no route between them --------
if running border-leaf1; then
    check "the tenant cloud VRFs exist on the border leaf" \
          "TENANT_GLOBEX" eos border-leaf1 "show vrf"
    if eos border-leaf1 "show ip route vrf TENANT_ACME 10.220.20.0/24" | grep -q "10.220.20"; then
        bad "tenant VRF isolation" "TENANT_ACME has a route to globex's cloud subnet -- the VRFs are leaking in the fabric"
    else
        ok "TENANT_ACME has no route into globex's cloud"
    fi
fi
if running app-leaf1; then
    # The SVI must be connected *inside the tenant VRF*, not merely present:
    # a cloud host with a gateway in the wrong VRF is exactly the failure the
    # APP_LEAFS tag filter caused during development.
    check "acme's cloud SVI is connected inside TENANT_ACME" \
          "directly connected, Vlan310" eos app-leaf1 "show ip route vrf TENANT_ACME 10.220.10.0/24"
fi

# ---- the firewall side ----------------------------------------------------
if running fw1 && [[ "$fw_kind" == "juniper_vsrx" ]]; then
    check "a firewall zone exists per tenant cloud" \
          "globex-cloud" jnpr "show configuration security zones | display set"
    check "acme's sites are permitted into acme's cloud" \
          "acme-sites-to-acme-cloud" jnpr "show configuration security policies | display set"
    # The absence of a permit IS the isolation, so assert the absence.
    if jnpr "show configuration security policies | display set" \
         | grep -qE "to-zone globex-cloud .*(acme|source-address any)"; then
        bad "tenant zone policy" "something other than globex's own sites is permitted into globex-cloud"
    else
        ok "nothing but globex's sites is permitted into globex-cloud"
    fi
fi

# ---- and the datapath, which is the only thing that really settles it -----
if running cust-acme-host && running cust-acme-dr-host; then
    check "acme hq reaches acme dr: two sites, two attachment kinds, one tenant" \
          "bytes from" node cust-acme-host "ping -c2 -W3 10.60.11.10"
fi

if running acme-cloud1 && running cust-acme-host; then
    check "acme hq reaches acme's cloud instance through the firewall" \
          "bytes from" node cust-acme-host "ping -c2 -W3 10.220.10.10"
fi
if running acme-cloud1 && running cust-acme-dr-host; then
    # The static site too -- the whole point of the tenant model is that both
    # sites get the same service.
    check "acme dr reaches acme's cloud instance as well" \
          "bytes from" node cust-acme-dr-host "ping -c2 -W3 10.220.10.10"
fi
if running globex-cloud1 && running cust-globex-host; then
    check "globex reaches its own cloud instance" \
          "bytes from" node cust-globex-host "ping -c2 -W3 10.220.20.10"
fi

# The negatives. These are the checks that would still pass on a flat network
# if they were written the other way round, so they are written as failures.
if running acme-cloud1 && running cust-globex-host; then
    if docker exec clab-otternet-cust-globex-host ping -c2 -W2 10.220.10.10 >/dev/null 2>&1; then
        bad "tenant cloud isolation" "globex reached ACME's cloud instance -- a tenant can see another tenant's compute"
    else
        ok "globex cannot reach acme's cloud instance"
    fi
fi
if running globex-cloud1 && running cust-acme-host; then
    if docker exec clab-otternet-cust-acme-host ping -c2 -W2 10.220.20.10 >/dev/null 2>&1; then
        bad "tenant cloud isolation" "acme reached GLOBEX's cloud instance -- a tenant can see another tenant's compute"
    else
        ok "acme cannot reach globex's cloud instance"
    fi
fi

# ---- internet reachability, and its absence -------------------------------
if running internet-host; then
    if running cust-acme-host; then
        code=$(docker exec clab-otternet-cust-acme-host curl -sS -o /dev/null \
                 -w '%{http_code}' --max-time 8 http://198.51.100.10/ 2>/dev/null)
        if $internet_sold; then
            [[ "$code" == "200" ]] \
                && ok "acme hq reaches the internet (HTTP 200 from 198.51.100.10)" \
                || bad "internet access" "acme bought internet access but got '${code:-nothing}' from 198.51.100.10"
        else
            [[ "$code" == "200" ]] \
                && bad "internet access" "acme reached the internet although it is not deployed in the baseline" \
                || ok "acme hq cannot reach the internet, as in the baseline"
        fi
    fi
    if running cust-acme-dr-host; then
        code=$(docker exec clab-otternet-cust-acme-dr-host curl -sS -o /dev/null \
                 -w '%{http_code}' --max-time 8 http://198.51.100.10/ 2>/dev/null)
        if $internet_sold; then
            [[ "$code" == "200" ]] \
                && ok "acme's static site reaches the internet too" \
                || bad "internet access" "acme/dr got '${code:-nothing}' from the internet; the site kind should make no difference to the product"
        else
            [[ "$code" == "200" ]] \
                && bad "internet access" "acme/dr reached the internet although it is not deployed in the baseline" \
                || ok "acme's static site cannot reach the internet, as in the baseline"
        fi
    fi
    if running cust-globex-host; then
        code=$(docker exec clab-otternet-cust-globex-host curl -sS -o /dev/null \
                 -w '%{http_code}' --max-time 6 http://198.51.100.10/ 2>/dev/null)
        [[ "$code" == "200" ]] \
            && bad "internet product" "globex reached the internet without buying it -- a default route is leaking into CUST_GLOBEX" \
            || ok "globex cannot reach the internet, having not bought it"
    fi
fi

# ============================================ branch office and access ======
# The branch site is no longer one test host: it is a switched LAN with a
# workstation on it, a VNC gateway, and a self-service path into the DC. These
# checks are about that path existing and being *closed by default* -- the
# grant itself is exercised in the datapath section below.
hdr "Branch office and self-service access"

if running branch-rtr; then
    # One switched segment, not three point-to-point links. If the ports are not
    # bridged, guacd cannot open a VNC session to the desktop without the
    # router forwarding between two hosts in the same /24, which mostly works
    # and is not what a branch LAN does.
    #
    # branch-rtr is SR Linux, so the LAN is a mac-vrf (`lan`) with the three
    # access subinterfaces bridged into it and irb0.0 as the routed gateway in
    # `default` -- not a Linux bridge, which SR Linux never creates. The Type
    # line is reset per interface because irb0.0 prints none.
    ports=$(srl branch-rtr "show network-instance lan interfaces" | awk '
        /^Interface/ {t=""} /^Type/ {t=$3}
        /^Oper state/ { if (t=="bridged" && $4=="up") n++ }
        END {print n+0}')
    if [[ "${ports:-0}" -ge 3 ]]; then
        ok "all $ports branch LAN ports are bridged and up in mac-vrf lan"
    else
        bad "branch LAN bridge" "expected 3 bridged subinterfaces up in mac-vrf lan, found ${ports:-0} -- docker exec clab-otternet-branch-rtr sr_cli -d 'show network-instance lan interfaces'"
    fi
    check "the branch LAN gateway 10.70.0.1 is on irb0.0, routed in default" \
          "default \(default\)" bash -c "docker exec clab-otternet-branch-rtr sr_cli -d 'show interface irb0' 2>/dev/null | grep -A12 'irb0.0 is up' | grep -B10 '10\.70\.0\.1/24'"
fi

if running branch-desktop; then
    check "the branch desktop holds its LAN address" \
          "10\.70\.0\.20" node branch-desktop "ip -4 -o addr show eth1"
    check "the branch desktop is serving VNC" \
          "5901" node branch-desktop "ss -ltn"
    check "an XFCE session is actually running on the desktop" \
          "xfce4-session" node branch-desktop "ps -eo comm"
else
    skp "branch desktop" "branch-desktop is not running"
fi

if running branch-guacd && running branch-desktop; then
    # guacd reaching the desktop is the whole reason it sits on the branch LAN.
    # busybox nc, because the guacd image has no bash and therefore no
    # /dev/tcp. Reading the banner proves the VNC server answered rather than
    # only that something is listening.
    banner=$(docker exec clab-otternet-branch-guacd sh -c \
               'timeout 5 nc 10.70.0.20 5901 < /dev/null | head -c 3' 2>/dev/null)
    if [[ "$banner" == "RFB" ]]; then
        ok "guacd reaches the desktop's VNC server across the branch LAN"
    else
        bad "guacd -> desktop" "expected an RFB banner from 10.70.0.20:5901, got '${banner:-nothing}' -- check the br-branch ports and the desktop's session"
    fi
fi

if running branch-guac; then
    # The front end is published on the lab host, which is how a human gets in.
    # The bare path, not /guacamole/. WEBAPP_CONTEXT=ROOT makes Tomcat serve it
    # at /, and asserting that here is the point: the default context 404s on
    # the obvious URL, which is what anyone forwarding port 8080 will try.
    code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
             http://127.0.0.1:8080/ 2>/dev/null)
    if [[ "$code" == "200" ]]; then
        ok "Guacamole answers on the lab host at :8080/ (root context)"
    else
        bad "Guacamole web" "http://127.0.0.1:8080/ returned ${code:-nothing}; a 404 here means WEBAPP_CONTEXT=ROOT is missing from the branch-guac node and it is only serving /guacamole/"
    fi
    # File-based auth, so a token means the user-mapping.xml was actually read.
    if curl -sS --max-time 10 -X POST -d 'username=branch&password=branch' \
         http://127.0.0.1:8080/api/tokens 2>/dev/null | grep -q authToken; then
        ok "Guacamole authenticates branch/branch from user-mapping.xml"
    else
        bad "Guacamole auth" "branch/branch was rejected -- is configs/branch/guacamole mounted at /etc/guacamole?"
    fi
fi

# What a branch user actually clicks: every Firefox bookmark and every desktop
# launcher, probed FROM the desktop, so through branch-rtr and fw1 like a real
# click. READ-ONLY: it reads two files out of the container and makes requests.
#
# The list is parsed from the policies the desktop is RUNNING, not from a list
# kept here, so a bookmark added to firefox-policies.json is checked without
# anyone editing this script. The label is the contract: a title containing
# "(locked)" says "needs a grant first", so that bookmark may time out, must
# name a live LoadBalancer VIP, and may answer only where the firewall permits
# the branch. Any other bookmark must answer, grant or no grant.
if running branch-desktop; then
    desk_pol=$(docker exec clab-otternet-branch-desktop cat /etc/firefox/policies/policies.json 2>/dev/null)
    repo_pol="$LAB_DIR/configs/branch/desktop/firefox-policies.json"
    if [[ -z "$desk_pol" ]]; then
        bad "desktop Firefox policies" "the desktop has no /etc/firefox/policies/policies.json -- rebuild it: make desktop-image"
    elif python3 -c 'import json,sys; sys.exit(json.load(open(sys.argv[1])) != json.loads(sys.stdin.read()))' \
            "$repo_pol" <<<"$desk_pol" 2>/dev/null; then
        ok "the desktop runs the committed Firefox policies"
    else
        bad "desktop Firefox policies" "the running desktop's policies differ from configs/branch/desktop/firefox-policies.json, so its image is stale; the probes below check what users see now -- make desktop-image, or docker cp the file into /etc/firefox/policies/policies.json and restart Firefox"
    fi

    # The portal's certificate, two ways. Firefox cannot trust a server
    # certificate that is itself a CA (MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY),
    # whatever is installed, and the CA installed on the desktop must be the one
    # that signed what is served -- a regenerated secret without a re-run of
    # the desktop step leaves the old CA behind.
    if running tool-node1; then
        served=$(docker exec clab-otternet-branch-desktop sh -c \
                   'echo | timeout 10 openssl s_client -connect 10.90.0.11:32001 2>/dev/null | openssl x509 -noout -ext basicConstraints 2>/dev/null')
        if grep -q "CA:TRUE" <<<"$served"; then
            bad "portal certificate" "the portal serves a self-signed CA certificate, which Firefox refuses as a server certificate whatever the desktop trusts -- re-run 'uv run invoke tooling', which replaces it with a CA-signed one"
        elif [[ -n "$served" ]]; then
            ok "the portal serves a CA-signed certificate (not itself a CA)"
        fi
        code=$(docker exec clab-otternet-branch-desktop curl -sS -o /dev/null -w '%{http_code}' --max-time 10 \
                 --cacert /usr/local/share/ca-certificates/otternet-portal.crt https://10.90.0.11:32001/ 2>/dev/null)
        if [[ "$code" == "200" ]]; then
            ok "the CA installed on the desktop verifies the portal's certificate"
        else
            bad "portal trust on the desktop" "curl --cacert /usr/local/share/ca-certificates/otternet-portal.crt https://10.90.0.11:32001/ returned ${code:-nothing} from the desktop -- re-run 'uv run invoke tooling' to reinstall the CA, then restart Firefox"
        fi
    fi

    if [[ -n "$desk_pol" ]]; then
        lb_vips=""
        kube_ok && lb_vips=$(kubectl get svc -A -o jsonpath='{range .items[?(@.spec.type=="LoadBalancer")]}{.status.loadBalancer.ingress[0].ip}{"\n"}{end}' 2>/dev/null)
        fw_ready=""
        if running fw1 && [[ "$fw_kind" == "juniper_vsrx" ]]; then load_fw_cfg; fw_ready=1; fi
        launchers=$(docker exec clab-otternet-branch-desktop sh -c \
                      'grep -H "^Exec=" /home/*/Desktop/*.desktop' 2>/dev/null)
        # kind <TAB> label <TAB> url <TAB> host <TAB> port
        while IFS=$'\t' read -r kind label url host port; do
            [[ -z "$url" ]] && continue
            what="$kind '$label' ($url)"
            if [[ "$url" == file://* ]]; then
                if docker exec clab-otternet-branch-desktop test -f "${url#file://}"; then
                    ok "$what: the page it opens is on the desktop"
                else
                    bad "$what" "${url#file://} does not exist on the desktop -- the image is missing it"
                fi
                continue
            fi
            code=$(docker exec clab-otternet-branch-desktop curl -sk -o /dev/null -w '%{http_code}' \
                     --max-time 8 "$url" 2>/dev/null)
            answered=""; [[ "$code" =~ ^(2|3)[0-9][0-9]$|^401$ ]] && answered=1
            if [[ "$label" != *"(locked)"* ]]; then
                [[ -n "$answered" ]] \
                    && ok "$what: open, answers $code" \
                    || bad "$what" "answered ${code:-nothing} from the desktop, and nothing in its label says it needs a grant -- fix the path, label it (locked), or remove it"
                continue
            fi
            # A bookmark may name the VIP by its DNS name; resolve it on the desktop,
            # which is also what a click does, so a name the zone lacks fails here.
            if [[ "$host" =~ ^[0-9.]+$ ]]; then
                vip="$host"
            else
                vip=$(docker exec clab-otternet-branch-desktop getent ahostsv4 "$host" 2>/dev/null | awk 'NR==1{print $1}')
                if [[ -z "$vip" ]]; then
                    bad "$what" "$host does not resolve from the desktop -- the application has no name in the lab's DNS zone yet (see docs/docs/developer-guide/dns-service.md)"
                    continue
                fi
            fi
            if [[ -n "$lb_vips" ]] && ! grep -qxF "$vip" <<<"$lb_vips"; then
                bad "$what" "$host ($vip) is not the address of any LoadBalancer Service in the cluster -- the bookmark names a stale VIP (kubectl get svc -A | grep LoadBalancer)"
                continue
            fi
            fw="unknown"; [[ -n "$fw_ready" ]] && fw=$(fw_permits branch 10.70.0.20 "$vip" "$port")
            if [[ -z "$answered" ]]; then
                ok "$what: locked, as labelled -- no answer without a grant (firewall: $fw)"
            elif [[ "$fw" == permit* || "$fw" == "unknown" ]]; then
                ok "$what: answers $code -- a grant exists (firewall: $fw)"
            else
                bad "$what" "labelled (locked) but answered $code from the desktop while the firewall says '$fw' -- the gate is not enforcing, or the branch baseline is too wide"
            fi
        done < <(python3 -c '
import json, sys
from urllib.parse import urlsplit
def row(kind, label, url):
    u = urlsplit(url)
    port = u.port or (443 if u.scheme == "https" else 80)
    print("\t".join([kind, label, url, u.hostname or "", str(port)]))
pol, launchers = json.loads(sys.argv[1]), sys.argv[2]
for b in pol.get("policies", {}).get("Bookmarks", []):
    row("bookmark", b.get("Title", ""), b.get("URL", ""))
for line in launchers.splitlines():
    path, _, exe = line.partition(":Exec=")
    urls = [w for w in exe.split() if "://" in w]
    if urls: row("launcher", path.rsplit("/", 1)[-1], urls[0])
' "$desk_pol" "$launchers" 2>/dev/null)
    fi
fi

if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1 \
   && kubectl get nodes >/dev/null 2>&1; then
    check "the AppAccess platform API is established" \
          "True" kubectl get xrd appaccesses.otternet.lab -o jsonpath='{.status.conditions[?(@.type=="Established")].status}'
    if kubectl get crd firewallaccesses.otternet.lab >/dev/null 2>&1; then
        ok "the FirewallAccess CRD is installed"
    else
        bad "FirewallAccess CRD" "not installed -- run: make access"
    fi

    if kubectl -n otternet-access get deploy access-portal >/dev/null 2>&1; then
        ready=$(kubectl -n otternet-access get deploy access-portal \
                  -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
        [[ "${ready:-0}" -ge 1 ]] \
            && ok "the access portal is running" \
            || bad "access portal" "no ready replica -- kubectl -n otternet-access describe deploy access-portal"

        pvip=$(kubectl -n otternet-access get svc access-portal \
                 -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [[ "$pvip" == "10.112.240.33" ]]; then
            ok "the portal holds its pinned VIP $pvip"
        else
            bad "portal VIP" "expected the pinned 10.112.240.33, got '${pvip:-none}' -- the desktop's Firefox homepage and the firewall's baseline rule both name that address"
        fi

        ready=$(kubectl -n otternet-access get deploy fw-controller \
                  -o jsonpath='{.status.readyReplicas}' 2>/dev/null)
        [[ "${ready:-0}" -ge 1 ]] \
            && ok "the firewall access controller is running" \
            || bad "fw-controller" "no ready replica -- kubectl -n otternet-access describe deploy fw-controller"

        # A controller that cannot log in reconciles forever and says so only in
        # its log; nothing else in the cluster goes red.
        if kubectl -n otternet-access logs deploy/fw-controller --tail=40 2>/dev/null \
             | grep -qE "reconcile failed|Authentication failed"; then
            bad "fw-controller health" "the controller is logging reconcile failures -- kubectl -n otternet-access logs deploy/fw-controller"
        else
            ok "the access controller is reconciling without errors"
        fi
    elif ns_exists vidra-system; then
        # Infrahub drives this lab. `invoke cluster`'s handover deletes the
        # lab's access broker ON PURPOSE -- nothing in Infrahub models it, and
        # a workload no service object declares is state no proposed change can
        # explain. Requests come from Infrahub's portal (Backstage, in the
        # tooling cluster) and a grant is a `ServiceAppAccess`, so absence is
        # the asserted state here, not a gap to skip over. `--no-handover`
        # keeps the broker, and then the branch above runs instead.
        ok "the lab's access broker is absent by design: the handover removed it and Infrahub's portal replaces it"
    else
        skp "access broker" "optional in a lab-only deployment and not installed -- make access-images && make access"
    fi
fi

# ======================================================== datapath ==========
hdr "Datapath"
if running host-a && running k8s-node1; then
    check "host-a reaches its anycast gateway" \
          "bytes from" node host-a "ping -c2 -W2 10.210.0.1"
    check "k8s-node1 reaches its anycast gateway" \
          "bytes from" node k8s-node1 "ping -c2 -W2 10.110.0.1"
    check "host-a reaches the k8s tenant through the firewall" \
          "bytes from" node host-a "ping -c3 -W3 10.110.0.11"

    # The headline path: app tenant -> firewall -> EVPN -> Cilium LoadBalancer
    # VIP -> pod, crossing the leaf ACL, the firewall zone policy and the
    # CiliumNetworkPolicy. Ten consecutive requests, because a partial pass here
    # means per-backend asymmetry (see the externalTrafficPolicy note in
    # crossplane/apps/10-demo.yaml). The demo app is the one every external
    # source is admitted to at the pod, so it is the one that proves the
    # datapath; Grafana is the one that proves the gates, further down.
    if kube_ok; then
        if [[ -n "$demo_vip" && "$demo_vip" != "-" ]]; then
            hits=0
            for _ in $(seq 1 10); do
                docker exec clab-otternet-host-a curl -sS --max-time 6 "http://$demo_vip:$demo_port/" 2>/dev/null | grep -q Hostname && hits=$((hits+1))
            done
            if [[ "$hits" -eq 10 ]]; then
                ok "host-a reaches the demo app's LoadBalancer VIP $demo_vip through every enforcement layer (10/10)"
            else
                bad "end-to-end LoadBalancer path" "only $hits/10 requests to http://$demo_vip:$demo_port/ succeeded -- expect all 10"
            fi

            # Reachable is not enough: the pod must see WHO is asking, or its
            # CiliumNetworkPolicy admits the request as `remote-node` rather than
            # on host-a's prefix. whoami echoes the peer address it saw, so every
            # one of ten requests must report host-a's own 10.210.0.11 -- a
            # 10.110.0.x here is a node SNAT, the externalTrafficPolicy Cluster
            # symptom, and it only shows on the requests that crossed a node.
            seen=$(for _ in $(seq 1 10); do
                       docker exec clab-otternet-host-a curl -sS --max-time 6 "http://$demo_vip:$demo_port/" 2>/dev/null \
                           | sed -n 's/^RemoteAddr: \(.*\):[0-9]*$/\1/p'
                   done | sort | uniq -c | awk '{printf "%s%s x%s", sep, $2, $1; sep=", "}')
            if [[ "$seen" == "10.210.0.11 x10" ]]; then
                ok "the demo app sees host-a's real address 10.210.0.11 on every request (10/10), not a node SNAT"
            else
                bad "client address at the pod" "whoami reported RemoteAddr '${seen:-nothing}' for 10 requests from host-a -- expect '10.210.0.11 x10'; a 10.110.0.x is a node SNAT (kubectl -n otternet-demo get svc ${demo_svc:-} -o jsonpath='{.spec.externalTrafficPolicy}')"
            fi
        else
            bad "end-to-end LoadBalancer path" "the demo app has no advertised VIP -- kubectl -n otternet-demo get svc -l otternet.lab/advertise=true"
        fi
    fi

    # The real application, a chart nobody here wrote: Crossplane pulled it,
    # Cilium allocated and advertised the VIP, the firewall permits the session
    # -- and then Grafana's own pod policy decides. Infrahub seeds it to admit
    # the cluster's pod prefix only, so a source outside the cluster is dropped
    # AT THE POD until a grant names it. The positive is therefore taken from a
    # k8s node, which the composed policy admits as `host`/`remote-node`; the
    # cross-tenant request is the negative, and is derived from the policy
    # rather than assumed, so the lab-only claim (which admits the app tenant
    # outright) still reads as a positive there.
    gsvc=""; gvip="-"; gport=80
    if kube_ok && [[ -n "$metrics_ns" ]]; then
        read -r gsvc gvip _ gport <<<"$(advertised_svc "$metrics_ns")"
    fi
    if [[ -z "$gsvc" || "$gvip" == "-" ]]; then
        bad "Grafana VIP" "no advertised LoadBalancer Service with a VIP in ${metrics_ns:-the observability namespace} -- kubectl -n ${metrics_ns:-otternet-metrics} get svc -l otternet.lab/advertise=true"
    else
        blk=$(vip_in_block "$metrics_ns" "$gvip")
        [[ -n "$blk" ]] \
            && ok "Grafana's Service holds VIP $gvip, inside its own block $blk" \
            || bad "Grafana VIP" "$gvip is outside the $metrics_ns FabricApp's vipBlock"
        if running k8s-leaf1; then
            check "Grafana's VIP is advertised into the fabric" \
                  "${gvip}/32" eos k8s-leaf1 "show ip route vrf K8S_PROD bgp"
        fi
        # busybox wget, because the k3s node image has no curl.
        check "Grafana answers on its VIP $gvip from inside the cluster" \
              '"database": *"ok"' node k8s-node1 "wget -q -T 8 -O - http://$gvip:$gport/api/health"
        if running fw1 && [[ "$fw_kind" == "juniper_vsrx" ]]; then
            load_fw_cfg
            gated_reach "host-a -> Grafana (app tenant)" host-a 10.210.0.11 app-prod \
                        "$metrics_ns" "$gsvc" "$gvip" "$gport" /api/health
        fi
    fi

    # ---- the new external paths -------------------------------------------
    # A WAN customer and a branch user consuming a DC service. Same service,
    # two different trust levels, two different firewall zones -- and for the
    # customer, two AS hops of provider in between. The demo app, because it is
    # the service whose pod policy names both external sources.
    if [[ -z "$demo_vip" || "$demo_vip" == "-" ]]; then
        bad "WAN and branch service access" "no advertised demo VIP to test against"
    else
        # The branch is the exception, and deliberately so: its baseline
        # permits the self-service portal and nothing else, so reaching an
        # application proves somebody granted it rather than proving the
        # datapath works. It is checked separately below.
        sites=(cust-acme-host cust-globex-host)
        for site in "${sites[@]}"; do
            if ! running "$site"; then
                skp "$site -> DC service" "optional WAN customer site $site is not running"
                continue
            fi
            hits=0
            for _ in $(seq 1 5); do
                code=$(docker exec "clab-otternet-$site" curl -sS -o /dev/null \
                         -w '%{http_code}' --max-time 8 "http://$demo_vip:$demo_port/" 2>/dev/null)
                [[ "$code" == "200" ]] && hits=$((hits+1))
            done
            if [[ "$hits" -eq 5 ]]; then
                ok "$site reaches the DC service VIP $demo_vip (5/5)"
            else
                bad "$site -> DC service" "only $hits/5 requests to http://$demo_vip:$demo_port/ returned 200"
            fi
        done

        # The trust difference, tested against a k8s NODE rather than the
        # VIP. Do not be tempted to ping the VIP to prove this: ICMP to a
        # LoadBalancer VIP does not work in this datapath at all -- Cilium
        # only programs the service's TCP port, so the echo request lands
        # on a node with no route for it, gets forwarded back out, and
        # comes back as "Time to live exceeded". That failure is unrelated
        # to policy and would make this check pass or fail for the wrong
        # reason.
        #
        # The branch is told a route to 10.110.0.0/24 and permitted ICMP to
        # it; a WAN customer is told neither.
        if running branch-host; then
            check "the branch may ping a k8s node, because it is our own network" \
                  "bytes from" node branch-host "ping -c2 -W2 10.110.0.11"
        fi
        if running cust-acme-host; then
            if docker exec clab-otternet-cust-acme-host ping -c2 -W2 10.110.0.11 >/dev/null 2>&1; then
                bad "WAN customer reach" "a WAN customer reached a k8s node -- it should be told no route to 10.110.0.0/24 and be denied by the wan zone policy"
            else
                ok "a WAN customer cannot reach a k8s node (no route, and no policy)"
            fi
        fi
    fi

    # ---- the self-service path, from the branch ----------------------------
    # Two assertions that only make sense together: the portal is always
    # reachable, and an application nobody has requested is not. If the second
    # one ever passes by accident the demo still *looks* right -- the user
    # clicks Request, waits, and the app was reachable the whole time -- so it
    # is asserted explicitly.
    if running branch-desktop; then
        if kube_ok && ns_exists otternet-access; then
            # The lab's own broker, on its pinned VIP (lab-only, or --no-handover).
            code=$(docker exec clab-otternet-branch-desktop curl -sS -o /dev/null \
                     -w '%{http_code}' --max-time 10 http://10.112.240.33/ 2>/dev/null)
            if [[ "$code" == "200" ]]; then
                ok "the branch desktop reaches the lab's access portal with no grant at all"
            else
                bad "branch -> portal" "http://10.112.240.33/ returned ${code:-nothing} from the desktop; that path is the one standing branch permit and everything else depends on it"
            fi
        elif running tool-node1; then
            # Infrahub's portal: Backstage and Dex in the tooling cluster,
            # reached the hard way -- branch -> border-leaf1 -> fw1, zone
            # `tooling`, policy branch-to-tooling-portal. HTTPS with a
            # self-signed certificate, hence -k; Dex is plain HTTP.
            code=$(docker exec clab-otternet-branch-desktop curl -sSk -o /dev/null \
                     -w '%{http_code}' --max-time 10 https://10.90.0.11:32001/ 2>/dev/null)
            if [[ "$code" == "200" ]]; then
                ok "the branch desktop reaches the service portal (Backstage, 10.90.0.11:32001) with no grant at all"
            else
                bad "branch -> portal" "https://10.90.0.11:32001/ returned ${code:-nothing} from the desktop; branch-to-tooling-portal is the one standing branch permit and every request depends on it"
            fi
            check "the branch desktop reaches the lab's one OIDC issuer (Dex, 10.90.0.11:32556)" \
                  '"issuer": *"http://10\.90\.0\.11:32556/dex"' \
                  node branch-desktop "curl -sS --max-time 10 http://10.90.0.11:32556/dex/.well-known/openid-configuration"
        else
            skp "branch -> portal" "no portal deployed: neither the lab's access broker (make access) nor the tooling cluster (tool-node1) is running"
        fi

        # Both applications, from the desktop, against both gates. Grafana is
        # the grant demonstration: closed at the firewall AND at its pod until
        # a ServiceAppAccess (or, lab-only, an AppAccess) opens both. The demo
        # app's pod policy already names the branch, so it isolates the
        # firewall: if the branch reached it with no permit, the branch
        # baseline would be too wide and every grant a no-op.
        if running fw1 && [[ "$fw_kind" == "juniper_vsrx" ]] && kube_ok; then
            load_fw_cfg
            if [[ -n "$gsvc" && "$gvip" != "-" ]]; then
                gated_reach "branch desktop -> Grafana (only after a grant)" branch-desktop 10.70.0.20 branch \
                            "$metrics_ns" "$gsvc" "$gvip" "$gport" /api/health
            fi
            if [[ -n "$demo_vip" && "$demo_vip" != "-" ]]; then
                gated_reach "branch desktop -> demo app (only after a grant)" branch-desktop 10.70.0.20 branch \
                            otternet-demo "$demo_svc" "$demo_vip" "$demo_port" /
            fi
        fi
    fi

    # A customer must not reach the classic app tenant at all.
    if running cust-acme-host; then
        if docker exec clab-otternet-cust-acme-host curl -sS --max-time 5 http://10.210.0.11/ 2>&1 | grep -q .; then
            bad "WAN to app tenant" "a WAN customer reached the app tenant -- deny-wan->app is not working"
        else
            ok "a WAN customer cannot reach the classic app tenant"
        fi
    fi

    # And a negative: a ClusterIP is never advertised, so it must NOT be
    # reachable from outside the cluster. The lab's own claim has a
    # ClusterIP-only `backend` for this; the chart Infrahub delivers is one
    # tier (cycle 033), so its control is the advertised Service's OWN
    # ClusterIP: the same pods, admitted by the same policy, answering on the
    # VIP above -- so a failure here can only be the address not being routed.
    # Look the address up rather than hardcoding it -- a ClusterIP is assigned
    # at create time, so a literal here goes stale the first time the service
    # is recreated and the check then passes because it is probing an address
    # that belongs to nothing.
    beip=$(kubectl -n otternet-demo get svc backend -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
    beport=8080; bename="ClusterIP-only backend"
    if [[ -z "$beip" && -n "$demo_cip" && "$demo_cip" != "-" ]]; then
        beip=$demo_cip; beport=$demo_port; bename="demo app's own ClusterIP"
    fi
    if [[ -z "$beip" ]]; then
        bad "ClusterIP isolation" "neither a backend Service nor the demo Service was found in otternet-demo"
    elif docker exec clab-otternet-host-a curl -sS --max-time 5 "http://$beip:$beport/" 2>&1 | grep -q Hostname; then
        bad "ClusterIP isolation" "the $bename ($beip) answered from the app tenant -- it should never be advertised"
    else
        ok "the $bename ($beip) stays unreachable from the app tenant"
    fi
else
    skp "datapath checks" "workload nodes are not running"
fi

printf '\n\033[1m%d passed, %d failed, %d skipped\033[0m\n\n' "$pass" "$fail" "$skip"
(( fail == 0 ))
