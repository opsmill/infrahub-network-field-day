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

# vtysh on a WAN router. Note the stderr filter: FRR complains about a missing
# /etc/frr/vtysh.conf on every invocation and it means nothing, but it lands in
# the middle of the output being matched.
frr()  { docker exec "clab-otternet-$1" vtysh -c "$2" 2>/dev/null; }

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
    check "vSRX clamps TCP MSS to fit its 9192-byte interface MTU" \
          "9138" jnpr "show configuration security flow | display set"
else
    skp "firewall checks" "fw1 is not running"
fi

# =========================================================== kubernetes =====
hdr "Kubernetes and fabric integration"
if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1 && kubectl get nodes >/dev/null 2>&1; then
    check "all three k3s nodes are Ready" \
          "^3$" bash -c 'kubectl get nodes --no-headers | grep -c " Ready "'
    check "Cilium is running on every node" \
          "3" bash -c 'kubectl -n kube-system get ds cilium -o jsonpath="{.status.numberReady}"'
    check "Cilium BGP sessions to both leaves are established" \
          "established" bash -c 'kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers 2>/dev/null || kubectl get ciliumbgpclusterconfig otternet-fabric -o yaml'
    check "the frontend service has a LoadBalancer VIP from the pool" \
          "10\.112\.240\." bash -c 'kubectl -n otternet-demo get svc frontend -o jsonpath="{.status.loadBalancer.ingress[0].ip}"'
    check "default-deny policy is in force in the demo namespace" \
          "default-deny" bash -c 'kubectl -n otternet-demo get cnp -o name'

    if running k8s-leaf1; then
        check "the leaf learned the pod CIDR over BGP from Cilium" \
              "10\.111\." eos k8s-leaf1 "show ip route vrf K8S_PROD bgp"
        check "the LoadBalancer VIP reached the fabric" \
              "10\.112\.240\." eos k8s-leaf1 "show ip route vrf K8S_PROD bgp"
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
          "10\.50\.255\.2" bash -c 'docker exec clab-otternet-isp-pe1 vtysh -c "show bgp ipv4 unicast summary" 2>/dev/null | grep -E "^10\.50\.255\.2" | grep -v never'
    check "isp-pe2 peers with the DC border leaf" \
          "10\.250\.50\.1" bash -c 'docker exec clab-otternet-isp-pe2 vtysh -c "show bgp ipv4 unicast summary" 2>/dev/null | grep -E "^10\.250\.50\.1" | grep -v never'

    # Every customer's eBGP session, and what it is allowed to learn.
    for c in acme globex; do
        if running "cust-$c-ce"; then
            check "customer $c has an established session to the ISP" \
                  "65500" bash -c "docker exec clab-otternet-cust-$c-ce vtysh -c 'show bgp ipv4 unicast summary' 2>/dev/null | grep -E '^10\.51\.' | grep -v never"
            check "customer $c learned the DC service prefix" \
                  "10\.112\.240\.0/24" frr "cust-$c-ce" "show bgp ipv4 unicast"
        fi
    done

    # THE isolation check. Both customers' prefixes sit in the ISP's default
    # table -- they have to, or the DC could not route back -- so this passing
    # is entirely down to the import route-map on isp-pe1.
    if running cust-acme-ce && running cust-globex-ce; then
        if frr cust-acme-ce "show ip route 10.60.20.0/24" | grep -q "10.60.20.0/24"; then
            bad "customer isolation" "cust-acme has a route to cust-globex's LAN -- the provider is transiting between customers, check RM-DC-SERVICES-ONLY on isp-pe1"
        else
            ok "customer isolation: acme has no route to globex's LAN"
        fi
        if frr cust-globex-ce "show ip route 10.60.10.0/24" | grep -q "10.60.10.0/24"; then
            bad "customer isolation" "cust-globex has a route to cust-acme's LAN"
        else
            ok "customer isolation: globex has no route to acme's LAN"
        fi
        # A customer must not learn DC internals either.
        if frr cust-acme-ce "show ip route 10.111.0.0/16" | grep -q "10.111"; then
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
          "65103" bash -c 'docker exec clab-otternet-branch-rtr vtysh -c "show bgp ipv4 unicast summary" 2>/dev/null | grep -E "^10\.250\.70\.1" | grep -v never'
    check "the branch learned the DC service prefix" \
          "10\.112\.240\.0/24" frr branch-rtr "show bgp ipv4 unicast"
    # The branch must not be reachable from, or able to reach, the WAN.
    if frr branch-rtr "show ip route 10.60.0.0/16" | grep -q "10.60"; then
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
    check "Prometheus is scraping Cilium" \
          "^cilium-agent$" bash -c 'kubectl -n otternet-observability get cm -o name >/dev/null; kubectl get secret -n otternet-observability -o json | python3 -c "
import json,sys,base64,re
for s in json.load(sys.stdin)[\"items\"]:
    for k,v in (s.get(\"data\") or {}).items():
        if k.endswith(\".yaml\") and \"scrape\" in k.lower() or k==\"additional-scrape-configs.yaml\":
            t=base64.b64decode(v).decode()
            m=re.search(r\"job_name: (cilium-agent)\", t)
            if m: print(m.group(1)); raise SystemExit"'
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

if running isp-pe1; then
    # ---- one VRF per tenant, both sites inside it ------------------------
    check "acme's two sites share one VRF on the PE" \
          "10\.60\.11\.0/24" frr isp-pe1 "show ip route vrf CUST_ACME"
    check "the statically routed site is redistributed, not peered" \
          "static" frr isp-pe1 "show ip route vrf CUST_ACME 10.60.11.0/24"
    # acme/dr has no BGP session at all -- if one appears, the site kind in
    # wan/tenants.yml and the rendered config have diverged.
    if frr isp-pe1 "show bgp vrf CUST_ACME ipv4 unicast summary" | grep -q "10.51.11.2"; then
        bad "acme/dr attachment" "there is a BGP session to the dr CE, but that site is kind: static -- re-render with make wan-build"
    else
        ok "acme/dr has no BGP session, as a static site should not"
    fi

    # ---- per-tenant import policy ----------------------------------------
    check "acme's VRF learns acme's cloud subnet" \
          "10\.220\.10\.0/24" frr isp-pe1 "show ip route vrf CUST_ACME"
    if frr isp-pe1 "show ip route vrf CUST_ACME" | grep -q "10.220.20.0/24"; then
        bad "tenant cloud isolation" "acme's VRF has a route to GLOBEX's cloud subnet -- RM-ACME-IMPORT is too wide"
    else
        ok "acme's VRF has no route to globex's cloud"
    fi
    if frr isp-pe1 "show ip route vrf CUST_GLOBEX" | grep -q "10.220.10.0/24"; then
        bad "tenant cloud isolation" "globex's VRF has a route to ACME's cloud subnet -- RM-GLOBEX-IMPORT is too wide"
    else
        ok "globex's VRF has no route to acme's cloud"
    fi
    if frr isp-pe1 "show ip route vrf CUST_GLOBEX" | grep -qE "10\.60\.1[01]\.0/24"; then
        bad "tenant isolation" "globex's VRF has a route to an acme site -- the tenants are leaking into each other"
    else
        ok "globex's VRF has no route to any acme site"
    fi

    # ---- internet as a product -------------------------------------------
    check "acme's VRF has a default route (it bought internet)" \
          "0\.0\.0\.0/0" frr isp-pe1 "show ip route vrf CUST_ACME"
    if frr isp-pe1 "show ip route vrf CUST_GLOBEX 0.0.0.0/0" | grep -qE "^[KCSB>*]|via"; then
        bad "internet product" "globex has a default route in its VRF but did not buy internet access -- check RM-GLOBEX-IMPORT"
    else
        ok "globex has NO default route, because it did not buy internet"
    fi
fi

if running internet-rtr; then
    check "the internet learns acme's prefixes from the provider" \
          "10\.60\.10\.0/24" frr internet-rtr "show bgp ipv4 unicast"
    if frr internet-rtr "show bgp ipv4 unicast" | grep -q "10.60.20.0/24"; then
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
        [[ "$code" == "200" ]] \
            && ok "acme hq reaches the internet (HTTP 200 from 198.51.100.10)" \
            || bad "internet access" "acme bought internet access but got '${code:-nothing}' from 198.51.100.10"
    fi
    if running cust-acme-dr-host; then
        code=$(docker exec clab-otternet-cust-acme-dr-host curl -sS -o /dev/null \
                 -w '%{http_code}' --max-time 8 http://198.51.100.10/ 2>/dev/null)
        [[ "$code" == "200" ]] \
            && ok "acme's static site reaches the internet too" \
            || bad "internet access" "acme/dr got '${code:-nothing}' from the internet; the site kind should make no difference to the product"
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
    # enslaved, guacd cannot open a VNC session to the desktop without the
    # router forwarding between two hosts in the same /24, which mostly works
    # and is not what a branch LAN does.
    ports=$(docker exec clab-otternet-branch-rtr sh -c \
              "ip -o link show | grep -c 'master br-branch'" 2>/dev/null || echo 0)
    if [[ "${ports:-0}" -ge 3 ]]; then
        ok "all $ports branch LAN ports are on br-branch"
    else
        bad "branch LAN bridge" "expected 3 ports on br-branch, found ${ports:-0} -- re-render and push: make wan-build wan-deploy"
    fi
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
    else
        skp "access broker" "not installed -- make access-images && make access"
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
    # crossplane/apps/10-demo.yaml).
    if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1; then
        vip=$(kubectl -n otternet-demo get svc frontend -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [[ -n "$vip" ]]; then
            hits=0
            for _ in $(seq 1 10); do
                docker exec clab-otternet-host-a curl -sS --max-time 6 "http://$vip/" 2>/dev/null | grep -q Hostname && hits=$((hits+1))
            done
            if [[ "$hits" -eq 10 ]]; then
                ok "host-a reaches the LoadBalancer VIP through every enforcement layer (10/10)"
            else
                bad "end-to-end LoadBalancer path" "only $hits/10 requests to http://$vip/ succeeded -- expect all 10"
            fi
        else
            skp "end-to-end LoadBalancer path" "no VIP allocated yet"
        fi
    fi

    # The real application, on its own VIP, reached from the other tenant. This
    # is the same path as the demo workload's but through a chart nobody here
    # wrote: Crossplane pulled it, Cilium allocated and advertised the VIP, and
    # the firewall permitted the session.
    if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1; then
        gvip=$(kubectl -n otternet-observability get svc -l otternet.lab/advertise=true \
                 -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [[ -n "$gvip" ]]; then
            ghits=0
            for _ in $(seq 1 5); do
                code=$(docker exec clab-otternet-host-a curl -sS -o /dev/null \
                         -w '%{http_code}' --max-time 8 "http://$gvip/api/health" 2>/dev/null)
                [[ "$code" == "200" ]] && ghits=$((ghits+1))
            done
            if [[ "$ghits" -eq 5 ]]; then
                ok "host-a reaches Crossplane-deployed Grafana on its advertised VIP $gvip (5/5)"
            else
                bad "Grafana VIP path" "only $ghits/5 requests to http://$gvip/api/health returned 200"
            fi
        else
            skp "Grafana VIP path" "no VIP allocated for the observability app yet"
        fi
    fi

    # ---- the new external paths -------------------------------------------
    # A WAN customer and a branch user consuming a DC service. Same service,
    # two different trust levels, two different firewall zones -- and for the
    # customer, two AS hops of provider in between.
    if [[ -f "$KUBECONFIG" ]] && command -v kubectl >/dev/null 2>&1; then
        gvip=$(kubectl -n otternet-observability get svc -l otternet.lab/advertise=true \
                 -o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}' 2>/dev/null)
        if [[ -z "$gvip" ]]; then
            skp "WAN and branch service access" "no advertised DC service VIP yet"
        else
            # The branch is the exception, and deliberately so on the
            # The branch baseline permits the access portal and nothing else,
            # so reaching Grafana proves somebody granted it rather than
            # proving the datapath works. It is checked separately below.
            sites=(cust-acme-host cust-globex-host)
            for site in "${sites[@]}"; do
                if ! running "$site"; then
                    skp "$site -> DC service" "$site is not running"
                    continue
                fi
                hits=0
                for _ in $(seq 1 5); do
                    code=$(docker exec "clab-otternet-$site" curl -sS -o /dev/null \
                             -w '%{http_code}' --max-time 8 "http://$gvip/api/health" 2>/dev/null)
                    [[ "$code" == "200" ]] && hits=$((hits+1))
                done
                if [[ "$hits" -eq 5 ]]; then
                    ok "$site reaches the DC service VIP $gvip (5/5)"
                else
                    bad "$site -> DC service" "only $hits/5 requests to http://$gvip/api/health returned 200"
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

            # ---- the self-service path, from the branch --------------------
            # Two assertions that only make sense together: the portal is
            # always reachable, and an application nobody has requested is not.
            # If the second one ever passes by accident the demo still *looks*
            # right -- the user clicks Request, waits, and the app was reachable
            # the whole time -- so it is asserted explicitly.
            if running branch-desktop; then
                code=$(docker exec clab-otternet-branch-desktop curl -sS -o /dev/null \
                         -w '%{http_code}' --max-time 10 http://10.112.240.33/ 2>/dev/null)
                if [[ "$code" == "200" ]]; then
                    ok "the branch desktop reaches the access portal with no grant at all"
                else
                    bad "branch -> portal" "http://10.112.240.33/ returned ${code:-nothing} from the desktop; that path is the one standing branch permit (policy 6) and everything else depends on it"
                fi

                granted=$(kubectl get appaccess -o jsonpath='{.items[?(@.spec.app=="grafana")].spec.approved}' 2>/dev/null)
                reach=$(docker exec clab-otternet-branch-desktop curl -sS -o /dev/null \
                          -w '%{http_code}' --max-time 6 "http://$gvip/api/health" 2>/dev/null)
                if [[ "$granted" == "true" ]]; then
                    [[ "$reach" == "200" ]] \
                        && ok "Grafana is reachable from the branch because access was granted" \
                        || bad "granted access" "an approved AppAccess exists for grafana but http://$gvip/ returned ${reach:-nothing} -- make access-status"
                else
                    [[ "$reach" == "200" ]] \
                        && bad "ungranted access" "the branch reached Grafana at $gvip with no approved AppAccess -- the branch baseline is too wide, so every grant is a no-op" \
                        || ok "Grafana is NOT reachable from the branch until access is requested"
                fi
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

    # And a negative: the backend is ClusterIP-only and must NOT be reachable.
    # Look the address up rather than hardcoding it -- a ClusterIP is assigned
    # at create time, so a literal here goes stale the first time the service is
    # recreated and the check then passes because it is probing an address that
    # belongs to nothing.
    beip=$(kubectl -n otternet-demo get svc backend -o jsonpath='{.spec.clusterIP}' 2>/dev/null)
    if [[ -z "$beip" ]]; then
        skp "backend isolation" "backend service not found"
    elif docker exec clab-otternet-host-a curl -sS --max-time 5 "http://$beip:8080/" 2>&1 | grep -q Hostname; then
        bad "backend isolation" "the ClusterIP-only backend ($beip) answered from the app tenant -- it should never be advertised"
    else
        ok "the ClusterIP-only backend ($beip) stays unreachable from the app tenant"
    fi
else
    skp "datapath checks" "workload nodes are not running"
fi

printf '\n\033[1m%d passed, %d failed, %d skipped\033[0m\n\n' "$pass" "$fail" "$skip"
(( fail == 0 ))
