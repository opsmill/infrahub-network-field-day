# Verifying the lab yourself

Every command here was run against the live lab. Copy-paste them in order; each
one answers a specific question rather than just printing state.

First, point kubectl at the cluster. Use the **absolute** path — a
`$PWD`-relative one silently does the wrong thing if you are not inside `lab/`:

```bash
export KUBECONFIG=/path/to/infrahub/lab/k8s/.kubeconfig/kubeconfig.yaml   # this repository's lab/
```

Sanity-check that it took, because the failure mode here is confusing:

```bash
kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}{"\n"}'
# expect: https://172.20.41.41:6443
```

If you instead see `https://localhost:8443` (or a connection-refused error
naming it), kubectl fell back to a pre-existing `~/.kube/config` from some other
cluster. That happens whenever `KUBECONFIG` is unset *or* points at a path that
does not exist — kubectl does not warn you, it just uses the default file.

Alternatively, skip the environment variable entirely. Every Makefile target
passes the kubeconfig explicitly, so these work from anywhere in `lab/`:

```bash
make k8s-status     # nodes, pods, services, network policies
make k8s-bgp        # Cilium BGP peering and advertised routes
make verify         # every check, pass/fail
```

If you only run one thing, run `make verify` — it runs every check across the
fabric, the security layers, the Crossplane control plane and the datapath, and
prints a pass/fail line for each. Everything below is what it
does, unpacked, so you can watch it rather than trust it.

---

## 1. What is actually deployed

```bash
kubectl -n otternet-demo get deploy,svc,pods -o wide
```

When Infrahub drives the lab, the demo application is the `whoami` Helm chart
that Vidra delivers: one Deployment of three replicas, one per node, behind a
**LoadBalancer** Service named `otternet-demo-<hash>-whoami` holding VIP
`10.112.240.0`. Its Service carries the label `otternet.lab/advertise: "true"`,
which is what gets it a VIP and an advertisement at all; `make verify` finds it
by that label rather than by name.

A lab deployed without Infrahub runs the lab's own claim instead: `frontend`
(3 replicas) on the LoadBalancer and `backend` (2 replicas) with a
**ClusterIP only**. The chart is one tier, so the backend has no Infrahub
equivalent ([§3](#3-the-negative-case) uses another ClusterIP as the control).

## 2. The headline path

A request from the classic app tenant, across the firewall, into a pod:

```bash
docker exec clab-otternet-host-a curl -s http://10.112.240.0/ | grep -E 'Hostname|RemoteAddr'
```

```text
Hostname: otternet-demo-da28581ff356-whoami-df5999546-hn7v6
RemoteAddr: 10.210.0.11:36066
```

Two things worth noticing. `Hostname` tells you which pod answered — repeat the
command and it changes, because the fabric ECMPs the VIP across the nodes
advertising it. `RemoteAddr` is the **original client IP** only when the
Service sets `externalTrafficPolicy: Local`, as the lab's `frontend` does and
Grafana does. The `whoami` chart's Service keeps the default, `Cluster`, so a
request that lands on a node whose chosen pod is elsewhere arrives SNATed to
that node (`RemoteAddr: 10.110.0.x`) and is admitted by the policy's
`remote-node` entity rather than by its CIDR list. That is a known gap in the
delivered demo, not a verification artefact.

```bash
for i in 1 2 3; do docker exec clab-otternet-host-a curl -s http://10.112.240.0/ | grep Hostname; done
```

## 3. The negative case

A ClusterIP is never advertised, so it must never be reachable from the app
tenant. Look the address up, because a ClusterIP is assigned at create time:

```bash
# Infrahub-driven: the demo Service's OWN ClusterIP -- the same pods, admitted by
# the same policy, answering on the VIP above
CIP=$(kubectl -n otternet-demo get svc -l otternet.lab/advertise=true \
        -o jsonpath='{.items[0].spec.clusterIP}')
docker exec clab-otternet-host-a curl -s --max-time 5 "http://$CIP/" \
  && echo "REACHABLE — bad" || echo "unreachable — correct"

# lab-only: the ClusterIP-only backend, on 8080
CIP=$(kubectl -n otternet-demo get svc backend -o jsonpath='{.spec.clusterIP}')
docker exec clab-otternet-host-a curl -s --max-time 5 "http://$CIP:8080/" \
  && echo "REACHABLE — bad" || echo "unreachable — correct"
```

A lab where everything works proves nothing. This is the control.

## 4. Kubernetes routes living in the fabric

The switch learned the pod CIDRs and the service VIP over BGP, from Cilium:

```bash
docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp' \
  | grep -E '10\.111|10\.112'
```

```
 B E      10.111.0.0/24 [20/0]     <- k8s-node1 pod CIDR
 B E      10.111.1.0/24 [20/0]     <- k8s-node3 pod CIDR
 B E      10.111.2.0/24 [20/0]     <- k8s-node2 pod CIDR
 B E      10.112.240.0/32 [20/0]   <- the LoadBalancer VIP
```

And the same sessions from Cilium's side:

```bash
kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers
```

```
Local AS  Peer AS  Peer Address     Session       Uptime   Family         Received  Advertised
65401     65101    10.110.0.2:179   established   5h55m    ipv4/unicast   2         3
65401     65101    10.110.0.3:179   established   5h55m    ipv4/unicast   2         3
```

`Received 2` is the route policy at work: the leaves send a default route and
the node subnet, and nothing else.

## 5. The firewall is doing work

```bash
docker exec clab-otternet-host-a curl -s --max-time 5 telnet://10.110.0.11:22 \
  && echo "SSH reachable — bad" || echo "blocked — correct"

make fw-log    # active sessions, then the RT_FLOW permits and denies
```

The zone policy permits only 80/443 and ICMP between tenants; everything else
falls to the default deny. `show security policies hit-count from-zone app-prod`
in `make fw-console` shows which rule each permitted session matched.

To see the path rather than infer it:

```bash
docker exec clab-otternet-host-a traceroute -n -w1 -m6 10.110.0.11
```

Hop 2 is the border leaf's handoff, hop 3 is the firewall itself.

## 5b. The WAN: customers, isolation, and onboarding

Start with every session in the WAN, from customer edge to the datacentre:

```bash
make wan-bgp
```

Expect five established sessions: `isp-pe1`↔`isp-pe2` (iBGP in AS 65500),
`isp-pe2`↔`border-leaf1` (eBGP into VRF WAN), one eBGP session per customer
CE, and `branch-rtr`↔`border-leaf1` (eBGP into VRF BRANCH).

### A customer consumes a DC service

```bash
docker exec clab-otternet-cust-acme-host curl -sS http://10.112.240.0/ | grep Hostname
# Hostname: otternet-demo-...-whoami-...
```

The demo application, because its pod policy names the WAN customers
(`10.60.0.0/16`). Grafana's does not, so the same request to Grafana stops at
its pod — see [the real application](#the-real-application-on-a-bgp-advertised-vip).

That request crossed the customer LAN, an eBGP session into a VRF on the
provider's edge, two AS hops of provider, an eBGP session into the DC's WAN
VRF, out of the border leaf into the firewall's `wan` zone, back in, across
EVPN to a k8s leaf, and into a pod — and it was allowed by the ISP's route
policy, the DC's route policy, the leaf ACL, the firewall zone policy and the
CiliumNetworkPolicy. Any one of them says no and it stops.

### ...and cannot reach the other customer

This is the check worth dwelling on, because it is pure route policy:

```bash
make wan-customers      # each customer VRF's table on the edge PE
docker exec clab-otternet-cust-acme-ce \
  sr_cli -d "show network-instance default ipv4 route 10.60.20.0/24"
# the table header, and no 10.60.20.0/24 line
```

Both customers' prefixes **are** in the provider's default table — look:

```bash
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance default ipv4 route" | grep 10.60
# 10.60.10.0/24, 10.60.11.0/24 and 10.60.20.0/24, each leaked from its VRF
```

They have to be, or the datacentre could not route back to either. The only
thing stopping each customer from being handed the other's route is the
inter-instance import policy on its VRF:

```bash
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "info flat network-instance CUST_ACME inter-instance-policies"
# import-policy [ RM-ACME-IMPORT ], export-policy [ LEAKABLE ]
```

`RM-ACME-IMPORT` accepts only the shared DC services, acme's cloud subnet and
the default route, each matched on `origin-network-instance default`. To watch
it fail, widen it in `wan/templates/isp-edge.srl.j2`, then `make wan-build &&
make wan-deploy` — the two customers can now route to each other through the
provider, and `make verify` says so.

### Onboarding a customer

```bash
$EDITOR wan/tenants.yml         # copy an entry, change name/id/asn/vrf/lan
$EDITOR otternet.clab.yml            # add its CE + host nodes and two links
make wan-build && git diff wan/rendered/
```

The diff is the point: you see the new VRF, the new sub-interface, the new
eBGP session and the new route-maps before anything is pushed. Then:

```bash
make wan-deploy
```

That commits a full-configuration replace in one confirmed candidate rather than restarting anything, so
the customers who were already connected keep their sessions. Confirm with the uptime column in
`make wan-bgp` — the existing sessions should not have reset.

### The branch is more trusted than a customer, in routing not just policy

```bash
docker exec clab-otternet-branch-rtr \
  sr_cli -d "show network-instance default ipv4 route" | grep -c 10.110  # 1
docker exec clab-otternet-cust-acme-ce \
  sr_cli -d "show network-instance default ipv4 route" | grep -c 10.110  # 0

docker exec clab-otternet-branch-host    ping -c2 10.110.0.11    # works
docker exec clab-otternet-cust-acme-host ping -c2 10.110.0.11    # no route
```

The branch is told a route to the k8s node subnet and permitted to ping it;
a customer is told neither. Neither learns the pod CIDR.

One thing not to test this way: **do not ping a LoadBalancer VIP.** ICMP to a
VIP does not work in this datapath at all — Cilium programs the service's TCP
port, so an echo request lands on a node with no route for it, is forwarded
back out, and returns `Time to live exceeded`. That is unrelated to any policy
and will mislead you.

## 6. Watch policy verdicts live

Hubble is the tool that settles arguments. Make some requests, then read the
verdicts — check every agent, since the request lands wherever ECMP sends it:

```bash
for i in 1 2 3 4; do docker exec clab-otternet-host-a curl -s http://10.112.240.0/ >/dev/null; done

for p in $(kubectl -n kube-system get pods -l k8s-app=cilium -o name | sed 's|pod/||'); do
  kubectl -n kube-system exec $p -- hubble observe --last 50 --to-namespace otternet-demo 2>/dev/null \
    | grep 10.210.0.11 | tail -2
done
```

```
10.210.0.11:54460 -> otternet-demo/frontend-...:8080 to-endpoint FORWARDED
```

Now the denied case. A pod outside the namespace has no business reaching the
frontend:

```bash
kubectl run otternet-debug --image=nicolaka/netshoot:v0.16 --restart=Never --command -- sleep 900
kubectl exec otternet-debug -- curl -sS --max-time 6 http://10.111.0.141:8080/   # times out

for p in $(kubectl -n kube-system get pods -l k8s-app=cilium -o name | sed 's|pod/||'); do
  kubectl -n kube-system exec $p -- hubble observe --last 40 --verdict DROPPED 2>/dev/null | tail -2
done

kubectl delete pod otternet-debug --force --grace-period=0
```

```
default/otternet-debug:45746 <> otternet-demo/frontend-...:8080 policy-verdict:none INGRESS DENIED
default/otternet-debug:45746 <> otternet-demo/frontend-...:8080 Policy denied DROPPED
```

Or use the UI: `make hubble`, then open http://localhost:12000.

## 6b. The platform is declarative, and you can prove it

Everything in the cluster except Cilium itself is composed by Crossplane from
two claims. Start with what exists and what made it:

```bash
make xp
```

Expect two healthy providers, two healthy functions, two established XRDs, one
`FabricPeering`, two `FabricApp`s, and around twenty composed resources — plus
the Cilium BGP and LoadBalancer objects, which are outputs of those claims
rather than things anyone applied.

Trace one Cilium object back to the claim that produced it:

```bash
kubectl get objects.kubernetes.crossplane.io -o custom-columns=\
'MANAGES:.spec.forProvider.manifest.kind,NAME:.spec.forProvider.manifest.metadata.name,FROM-CLAIM:.metadata.ownerReferences[0].name'
```

```
MANAGES                    NAME                     FROM-CLAIM
CiliumBGPAdvertisement     otternet-podcidr            otternet
CiliumBGPClusterConfig     otternet-fabric             otternet
CiliumBGPPeerConfig        otternet-leaf-peer          otternet
CiliumLoadBalancerIPPool   otternet-demo-vips          otternet-demo
CiliumNetworkPolicy        default-deny             otternet-demo
...
```

Nothing in that list was applied by hand. The `FROM-CLAIM` column is the
`FabricPeering` or `FabricApp` each object was composed from.

Now break it the way someone would at 2am, and watch it heal:

```bash
make xp-drift
```

```
==> Current localASN on the CiliumBGPClusterConfig Crossplane owns
65401

==> Hand-editing it to a wrong AS (65999), the way someone would in an incident
  now: 65999

==> Waiting for Crossplane to notice and revert it
  reverted to 65401 after 15s -- the XR, not the CRD, is the source of truth
```

That is the difference from `kubectl apply -f`. Before, a hand-edit to the BGP
config stuck, and the repository silently described a cluster that no longer
existed.

### The real application, on a BGP-advertised VIP

```bash
make grafana
```

Grafana came from the upstream `kube-prometheus-stack` chart — pulled and
installed by `provider-helm`, with no manifests in this repo. Its VIP was
allocated from the pool its own claim defined and advertised into EVPN by the
advertisement its own claim defined.

When Infrahub drives the lab it is `otternet-metrics`, on the pinned VIP
`10.112.240.81`, and its pod policy admits **only the cluster's pod prefix**
until a grant names another source. So it answers from inside the cluster, and
the **other** tenant is dropped at the pod even though the firewall permits the
session (`app-to-k8s-services`):

```bash
docker exec clab-otternet-k8s-node1 wget -qO- http://10.112.240.81/api/health
# {"database":"ok","version":"..."}
docker exec clab-otternet-host-a curl -sS -m5 http://10.112.240.81/api/health
# times out -- Grafana's own allow-ingress, not the firewall
kubectl -n otternet-metrics get cnp allow-ingress -o jsonpath='{.spec.ingress[0].fromCIDR}'
# ["10.111.0.0/16"]
```

`make verify` derives that expectation from fw1's policy and the pod's
CiliumNetworkPolicy and then requires the datapath to agree, so a grant that
adds the app tenant turns the same check into a positive. On the lab-only
`otternet-observability` claim, which admits the app tenant from the start,
the request from `host-a` answers on that application's VIP.

Then confirm the two apps did not collide, which is the failure this design had
to be fixed for:

```bash
kubectl get ciliumloadbalancerippool \
  -o custom-columns='NAME:.metadata.name,BLOCK:.spec.blocks[*].cidr,SELECTOR:.spec.serviceSelector.matchLabels'
```

Each pool is scoped to its own namespace. Without that, both apps select
`otternet.lab/advertise: "true"` cluster-wide and whichever pool LB-IPAM considers
first hands out the address.

And what Grafana is showing you is the datapath that carried you to it:

```bash
make prometheus-forward   # then http://localhost:19090/targets
```

Expect `cilium-agent` (3) and `hubble` (3) among the targets, all up.
`make verify` asks the same question through the API server's service proxy, so
it needs no port-forward:

```bash
kubectl get --raw "/api/v1/namespaces/otternet-metrics/services/http:$(kubectl -n otternet-metrics \
  get svc -l app=kube-prometheus-stack-prometheus -o jsonpath='{.items[0].metadata.name}'):9090/proxy/api/v1/targets"
```

## 5c. Tenants: multi-site, isolated cloud, and internet as a product

The provider-edge use case. Every positive here has a negative worth checking
alongside it, because a flat network passes all the positives.

### One tenant, two kinds of edge

`acme` has two sites. `hq` runs eBGP; `dr` runs no routing protocol at all.
Both are in `CUST_ACME`, so they reach each other with nothing leaked:

```bash
docker exec clab-otternet-cust-acme-host ping -c2 10.60.11.10     # hq -> dr
docker exec clab-otternet-cust-acme-dr-host ping -c2 10.60.10.10  # dr -> hq
```

Confirm the dr site really is static — there is no session for it:

```bash
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance CUST_ACME protocols bgp neighbor"
# one neighbour only: 10.51.10.2 (hq). Nothing for 10.51.11.2.
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance CUST_ACME ipv4 route 10.60.11.0/24"
# route type static, put into the BGP table by BGP-TABLE-CUST_ACME
```

### Isolated cloud instances

```bash
# each tenant reaches its own
docker exec clab-otternet-cust-acme-host   ping -c2 10.220.10.10
docker exec clab-otternet-cust-globex-host ping -c2 10.220.20.10
# the static site gets the same service as the BGP one
docker exec clab-otternet-cust-acme-dr-host ping -c2 10.220.10.10

# and neither reaches the other's -- these MUST fail
docker exec clab-otternet-cust-globex-host ping -c2 -W2 10.220.10.10
docker exec clab-otternet-cust-acme-host   ping -c2 -W2 10.220.20.10
```

Three independent gates make that true, and it is worth seeing each:

```bash
# 1. the fabric: separate VRFs, no route between them
docker exec clab-otternet-border-leaf1 Cli -p 15 -c "show ip route vrf TENANT_ACME"

# 2. the PE: globex's VRF never learns acme's cloud prefix
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance CUST_GLOBEX ipv4 route" | grep 10.220
# only 10.220.20.0/24

# 3. the firewall: the permit names acme's sites, and there is no equivalent
#    rule letting anything else into acme-cloud
make fw-console
  show configuration security policies from-zone wan to-zone acme-cloud | display set
```

### Internet as a product

acme bought it, globex did not:

```bash
docker exec clab-otternet-cust-acme-host    curl -s -o /dev/null -w '%{http_code}\n' http://198.51.100.10/   # 200
docker exec clab-otternet-cust-acme-dr-host curl -s -o /dev/null -w '%{http_code}\n' http://198.51.100.10/   # 200
docker exec clab-otternet-cust-globex-host  curl -s -m5 -o /dev/null -w '%{http_code}\n' http://198.51.100.10/ # fails
```

globex fails at the first hop, not at a firewall — there is simply no default
route in its VRF, and no route back to it on the internet either:

```bash
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance CUST_ACME ipv4 route 0.0.0.0/0"    # present
docker exec clab-otternet-isp-pe1 \
  sr_cli -d "show network-instance CUST_GLOBEX ipv4 route 0.0.0.0/0"  # absent
docker exec clab-otternet-internet-rtr \
  sr_cli -d "show network-instance default protocols bgp routes ipv4 summary" | grep 10.60.
# acme's two site prefixes only; globex is never announced
```

### Onboarding a tenant, or a site

Both are data-model changes. A new site is an entry under a tenant's `sites`
plus its nodes and links; a new tenant additionally needs a VRF in
`avd/group_vars/OTTERNET_FABRIC/10-network-services.yml`, a wire to the firewall,
and a zone and policy in `configs/fw/vsrx/junos.conf`.

```bash
vim wan/tenants.yml
make wan-build && git diff wan/rendered/     # review before pushing
make wan-deploy
```

## 6c. The branch office, and access on request

When Infrahub drives the lab, the portal is **Backstage** in the tooling
cluster, `https://10.90.0.11:32001` (signed by a lab CA the desktop trusts), with Dex beside it on
`http://10.90.0.11:32556`; the branch reaches both through
`branch-to-tooling-portal`, the one standing branch permit that matters. A
request is a `ServiceAppAccess`, reviewed in a proposed change, and merging it
opens the firewall rule, the fabric advertisement and the application's pod
policy together. The handover deleted the lab's own access broker by design, so
`make verify` asserts its absence instead of skipping it.

The rest of this section is that lab-only broker, which runs when the lab is
deployed without Infrahub or with `invoke cluster --no-handover`. There, a
grant is a named policy appended to the `branch` -> `k8s-prod` zone pair, and
`kubectl get firewallaccess` reports exactly where it landed:

```
NAME              SOURCE   DESTINATION     POLICY
access-kanboard   branch   10.112.240.49   branch->k8s-prod/aa-access-kanboard
```

### Get onto the branch desktop

```bash
make guac
# → http://<lab host>:8080/    branch / branch
```

The desktop is `10.70.0.20` on the branch LAN. Guacamole's web front end is on
the management network with its port published; the half that speaks VNC
(`guacd`, `10.70.0.31`) is on the branch LAN, so the session itself crosses the
site network. You can watch it do that on the router port facing the desktop,
which is a bridged member of the LAN mac-vrf (`e1-3` is `ethernet-1/3` in the
container's own namespace):

```bash
docker exec clab-otternet-branch-rtr tcpdump -ni e1-3 tcp port 5901
```

### Prove the door is shut before you knock

From a terminal on the desktop, or equivalently:

```bash
docker exec clab-otternet-branch-desktop curl -k -m5 -o /dev/null -w '%{http_code}\n' \
    https://10.90.0.11:32001/      # 200 — Backstage, branch-to-tooling-portal
docker exec clab-otternet-branch-desktop curl -m5 -o /dev/null -w '%{http_code}\n' \
    http://10.112.240.81/          # times out — Grafana, no grant for it
docker exec clab-otternet-branch-desktop curl -m5 -o /dev/null -w '%{http_code}\n' \
    http://10.112.240.0/           # times out — the demo app, no grant either
```

On the lab-only broker the portal is `http://10.112.240.33/` instead, and
Grafana is that claim's own VIP.

The demo application is the sharper of the two: its pod policy already names
the branch LAN, so the firewall is the only thing refusing it. Grafana is
refused at both. `make verify` prints which gate refused each one.

The branch has a *route* to `10.112.240.0/24` — it is advertised to the branch
by `RM-DC-TO-BRANCH` — so this is the firewall denying the session, not the
fabric failing to route. Confirm which:

```bash
docker exec clab-otternet-branch-rtr \
  sr_cli -d "show network-instance default ipv4 route 10.112.240.81"
make fw-log | grep deny
```

### Request, approve, and watch one object become four things

In the portal, request **Kanboard** and approve it. Or entirely from the CLI,
which is the same object either way:

```bash
kubectl get appaccess
kubectl patch appaccess access-kanboard --type=merge \
    -p '{"spec":{"approved":true,"approvedBy":"netops"}}'
```

Then watch it land:

```bash
watch -n2 make access-status
```

In order, what should appear:

```bash
kubectl get fabricapp otternet-kanboard                 # the app, composed
kubectl -n otternet-kanboard get pods,svc               # running, with a VIP
kubectl get firewallaccess                           # where the policy landed
kubectl -n otternet-kanboard get cnp                    # Cilium naming the branch
```

...and on the firewall itself, the generated rule, above the default deny:

```bash
make fw-console
  show configuration security policies from-zone branch to-zone k8s-prod | display set
  # ...policy aa-access-kanboard match destination-address aa-access-kanboard
  # appended after the hand-written rules, which is correct: the default policy
  # is consulted only once every policy in the pair has been tried
```

Then the desktop reaches it:

```bash
docker exec clab-otternet-branch-desktop curl -m5 -o /dev/null -w '%{http_code}\n' \
    http://10.112.240.49/
```

### The firewall is reconciled, not configured

Delete the generated policy by hand and it comes back inside twenty seconds —
the same property `make xp-drift` demonstrates for the Cilium config:

```bash
make fw-console
  configure
  delete security policies from-zone branch to-zone k8s-prod policy aa-access-kanboard
  commit and-quit
make access-status        # gone
sleep 25
make access-status        # back
```

### Revoking takes the application with it

```bash
kubectl delete appaccess access-kanboard
kubectl get fabricapp,firewallaccess       # both composed resources gone
make access-status                         # no aa-* policies on the box
```

That is the reason the request, the deployment and the firewall rule are one
object rather than three tickets: the delete path cannot half-happen.

## 7. Break it on purpose

The most convincing demo is removing an enforcement layer and watching traffic
stop in a *different, identifiable* place each time.

**Fabric route policy** — widen what the cluster may advertise and watch the
leaf refuse anyway:

```bash
docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c 'show ip bgp neighbors 10.110.0.11 received-routes'
docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp'
```

Offered versus accepted are not the same set — `RM-CILIUM-IN` permits only
`10.111.0.0/16 le 26` and `10.112.0.0/16`.

**Kubernetes policy** — remove it and the 200 becomes a timeout:

```bash
kubectl -n otternet-demo delete cnp allow-ingress
docker exec clab-otternet-host-a curl -s --max-time 6 http://10.112.240.0/   # now fails: default-deny
```

You do not have to restore this one. The policy is composed from the `FabricApp`
claim, so Crossplane notices the deletion and puts it back within about 20
seconds — which is itself worth watching:

```bash
kubectl -n otternet-demo get cnp -w      # allow-ingress reappears
```

To hold it deleted long enough to demo, set `policy.allowFrom: []` in
`crossplane/apps/10-demo.yaml` and `kubectl apply -f` it. That is the point of
the exercise: the way to break the policy is to change the declared intent, not
to delete the object.

**Firewall** — deactivate the rule that carries the headline path and watch it
stop, then put it back:

```bash
make fw-console
  configure private
  deactivate security policies from-zone app-prod to-zone k8s-prod policy app-to-k8s-services
  commit and-quit
```

The VIP now times out from `host-a` while everything else keeps working — the
route is still there, Cilium still permits it, and only the firewall changed its
mind. Restore it:

```bash
make fw-console
  configure private
  activate security policies from-zone app-prod to-zone k8s-prod policy app-to-k8s-services
  commit and-quit
```

`deactivate` rather than `delete` on purpose: it leaves the rule visible in the
config, marked `inactive:`, so the diff between broken and working is one word
rather than a missing block. `rollback 1` undoes the whole thing if you would
rather not retype it.

Note this is the *hand-written* baseline, so nothing puts it back on its own.
Generated grants in the `branch` zone pair behave differently — the access
broker re-asserts those every twenty seconds, which is the point of
[§6c](#6c-the-branch-office-and-access-on-request).

## 8. Re-run everything

```bash
make verify
```

```text
111 passed, 0 failed, 0 skipped
```

That is the full lab as Infrahub drives it. A skip names an optional component
that is not deployed and says which — a WAN customer site, the lab-only access
broker, the tooling cluster — and is never how a check that disagrees with the
design gets out of the way.
