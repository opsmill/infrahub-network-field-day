# OTTERNET Lab — EVPN fabric, AVD automation, security and Kubernetes

A containerlab topology that puts four things on one wire and makes them
interact, rather than demoing them side by side:

- **AVD** builds the entire Arista EVPN/VXLAN fabric from a data model. No
  device config is written by hand.
- **Security** is enforced at three independent layers — leaf ACLs, a
  zone-based firewall the tenants must traverse, and Cilium network policy —
  which have to *agree* before traffic flows.
- **Kubernetes** is a first-class fabric participant: Cilium peers BGP with the
  leaves and its pod CIDR and LoadBalancer VIPs are redistributed into EVPN.
- **Crossplane** owns everything above the CNI. The BGP peering, the
  advertisements, the LoadBalancer pools, the network policies *and* the
  applications are all composed from two custom APIs and reconciled
  continuously — so a hand-edit to the fabric-facing Cilium config is reverted
  rather than silently kept.

The interesting part is the seam. A pod is reachable from a bare-metal host in
another tenant only if the AVD-generated route policy accepts the advertisement,
the firewall zone policy permits the session, *and* the Cilium policy allows the
request. Break any one and you can watch exactly where it stops.

The second interesting part is that both ends are now declarative in the same
way. AVD renders the fabric from a data model; Crossplane renders the cluster's
side of the same contract from an XR. Deploying a real application — the lab
ships `kube-prometheus-stack` from the upstream chart — allocates its VIP,
advertises it into EVPN and writes its network policy from one object.

The third is the provider edge. The ISP carries **tenants**, not customers: a
tenant is one VRF and one policy, a site is one attachment circuit, and acme
has two sites attached two different ways — one running eBGP, one with no
routing protocol at all — that reach each other because they share a VRF.
Each tenant also has isolated cloud instances in the datacentre, in a VRF of
their own, reachable only by that tenant and only through a firewall zone. And
internet access is a product: acme bought it, globex did not, and the entire
difference is one route-map clause.

The fourth is what that buys you at the edge. The branch office has a real
desktop on it, reachable in a browser through Guacamole, and a user sitting at
that desktop can request an application they cannot currently reach. One
approval later the app is deployed if it was not running, its VIP is advertised
into EVPN, its Cilium policy names the branch, and a policy appears on the
firewall above its default deny — all composed from a single `AppAccess`
object, and all removed again when it is deleted. See
[docs/design.md](docs/design.md#requesting-access-to-an-app).

---

## Topology

The datacentre, and the two things outside it that consume its services.

```text
        WAN CUSTOMERS                 ISP  AS 65500
  ┌──────────────────┐         ┌──────────────────────┐
  │ acme    AS 65010 ├─ CE ────┤ isp-pe1 ──── isp-pe2 │
  │ 10.60.10.0/24    │         │ VRF per       default│
  ├──────────────────┤         │ customer      VRF    │
  │ globex  AS 65020 ├─ CE ────┤                      │
  │ 10.60.20.0/24    │         └───────────┬──────────┘
  └──────────────────┘                     │ 10.250.50.0/30
                                           │ eBGP, VRF WAN
                    ┌──────────┐        ┌──┴───────┐
                    │  spine1  │        │  spine2  │      AS 65100
                    └────┬─────┘        └────┬─────┘
         ┌───────┬───────┼──────┬───────┬────┴──┬───────┐
         │       │       │      │       │       │       │
    ┌────┴───┐┌──┴─────┐│ ┌────┴───┐┌──┴─────┐ │  ┌────┴───────┐
    │k8s-leaf1││k8s-leaf2│ │app-leaf1││app-leaf2│ │border-leaf1│◄── branch-rtr
    │  AS 65101 (MLAG)  │ │  AS 65102 (MLAG)  │ │   AS 65103   │    AS 65030
    └──┬──────┘└─┬────┬─┘ └───┬─────┘└────┬───┘ └─┬──┬──┬──┬───┘    10.70.0.0/24
       │         │    │       │           │       │  │  │  │        private circuit
   k8s-node1 node2  node3   host-a     host-b   Et10 11 14 15
   └──── VLAN 110, VRF K8S_PROD ───┘  └ VLAN 210 ┘ │  │  │  │
        10.110.0.0/24                 VRF APP_PROD │  │  │  │
                                      10.210.0.0/24│  │  │  │
                                          ┌─────────┴──┴──┴──┴─────────┐
                                          │            fw1             │
                                          │ zone k8s-prod  zone wan    │
                                          │ zone app-prod  zone branch │
                                          └────────────────────────────┘
```

The provider edge carries **tenants**, not customers — a tenant may have
several sites, attached in different ways, and they share one VRF:

```text
  TENANT acme  (VRF CUST_ACME, buys internet)
   site hq  10.60.10.0/24  eBGP AS 65010 ─┐
                                          ├─ isp-pe1 ── isp-pe2 ─┬─ border-leaf1
   site dr  10.60.11.0/24  static route ──┘   VRF per tenant     │
                                                                 └─ internet-rtr
  TENANT globex (VRF CUST_GLOBEX, no internet)                      AS 64500
   site hq  10.60.20.0/24  eBGP AS 65020 ─── isp-pe1                198.51.100.0/24

  ...and in the datacentre, one isolated VRF of cloud instances per tenant:

   VRF TENANT_ACME    10.220.10.0/24  acme-cloud1     app-leaf1  ─┐ one wire
   VRF TENANT_GLOBEX  10.220.20.0/24  globex-cloud1   app-leaf2  ─┘ per tenant
                                                                    to fw1
```

hq and dr reach each other because they share a VRF, not because anything was
leaked. acme reaches `10.220.10.0/24` and the internet; globex reaches neither.

The branch office behind `branch-rtr` is a switched LAN, not a single host:

```text
   BRANCH OFFICE  10.70.0.0/24                     ┌──────────────────────┐
  ┌────────────────────────────────────┐           │  your browser        │
  │  branch-host      .10   multitool  │           │  host port 8080      │
  │  branch-desktop   .20   XFCE + VNC │◄─ VNC ─┐  └──────────┬───────────┘
  │  branch-guacd     .31   guacd      │────────┘             │ mgmt net
  └───────────┬────────────────────────┘                 branch-guac
              │ mac-vrf lan, ethernet-1/2-4 + irb0     (web front end,
        branch-rtr  AS 65030                            no LAN interface)
              │ private circuit, VRF BRANCH
        border-leaf1 ──► fw1 zone branch ──► zone k8s-prod
                          baseline: the access portal, and ping.
                          everything else is granted on request.
```

Four firewall zones, and every one of them is reached the same way: routed out
of the border leaf into a zone and back in again. There is no path between any
two of these networks that does not cross `fw1`, which is why adding a customer
or a site adds a zone rather than an exception.

| Plane | Addressing |
|---|---|
| Management | `172.20.41.0/24` (switches `.11`–`.25`, fw `.31`, k8s `.41`–`.43`, hosts `.51`–`.52`, ISP `.61`–`.62`, tenant sites `.71`–`.76`, branch `.81`–`.85`, internet `.91`–`.92`, tenant cloud `.93`–`.94`) |
| Loopback0 / router-id | `10.41.0.0/24` (spines `.1`–`.2`, leaves `.11`–`.15`) |
| VTEP Loopback1 | `10.41.1.0/24` |
| Spine↔leaf P2P | `10.41.255.0/24` |
| K8s nodes | `10.110.0.0/24`, anycast GW `.1`, leaf SVIs `.2`/`.3` |
| K8s pods / services | `10.111.0.0/16` / `10.112.0.0/16`, LB VIPs `10.112.240.0/24` |
| LB VIP blocks | demo `…240.0/28`, observability `…240.16/28`, access portal `…240.32/28` (pinned `.33`), requested apps `…240.48/28` up |
| App hosts | `10.210.0.0/24`, anycast GW `.1` |
| ISP loopbacks / core | `10.50.0.0/24` / `10.50.255.0/30` |
| Site CE↔PE | `10.51.<n>.0/30` (acme/hq `10`, acme/dr `11`, globex/hq `20`) |
| Tenant site LANs | `10.60.<n>.0/24`, same numbering |
| Tenant cloud subnets | `10.220.<tenant id>.0/24` (acme `10`, globex `20`) |
| Tenant cloud handoffs | `10.250.<tenant id>.0/30` to the firewall |
| The internet | AS 64500, peering `10.52.0.0/30`, host network `198.51.100.0/24` |
| Branch LAN | `10.70.0.0/24` on mac-vrf `lan`, gateway `.1` on `irb0`, host `.10`, desktop `.20`, guacd `.31`, router loopback `10.70.255.1` |
| Firewall handoffs | `10.250.110.0/30` k8s, `10.250.210.0/30` app, `10.250.150.0/30` wan, `10.250.170.0/30` branch |
| External handoffs | `10.250.50.0/30` (ISP↔DC), `10.250.70.0/30` (branch↔DC) |

---

## Prerequisites

**Required, and you must supply it yourself:** the ceOS image. Arista requires a
(free) account.

```bash
# download cEOS-lab-4.36.0.1F.tar from arista.com, then:
docker import cEOS-lab-4.36.0.1F.tar ceos:4.36.0.1F
```

4.32.0F or newer is not optional on a modern host: older ceOS builds require
cgroups v1, and this box is cgroups v2. `make preflight` checks this.

Everything else is either already here or pulled automatically, including
Nokia SR Linux (`ghcr.io/nokia/srlinux:26.7.2`) for the ISP, customer and
branch routers, and the Guacamole images for the branch gateway.

The VM firewall needs an image its vendor does not redistribute, built locally
from a qcow2 in `/images`:

```bash
make fw-image                # vrnetlab/juniper_vsrx:22.3R1.11
```

No support contract is needed: Juniper's vSRX 3.0 evaluation image is available
to any free account registered for "Evaluation user access" at
<https://support.juniper.net/support/downloads/?p=vsrxeval>.

### Toolchain

```bash
make setup
```

This builds a self-contained virtualenv. It does **not** use the system Python
or Ansible, deliberately: AVD 6.x supports ansible-core 2.16–2.20 and this host
runs 2.21 on Python 3.14, which AVD refuses. `make setup` pins Python 3.12 and
`ansible-core==2.20.9`, with `pyavd[ansible]==6.4.0`, inside `lab/.venv`.

---

## Quick start

```bash
make setup           # AVD toolchain (once)
make avd-build       # render the whole fabric offline — no images, no lab
make preflight       # check this host can run it
make deploy          # bring up the lab (fabric + WAN + branch) and push config
make k8s             # Cilium — the CNI only
make crossplane      # Crossplane, the platform APIs, BGP peering, apps, access broker
make verify          # end-to-end checks
make guac            # how to open the branch desktop in a browser
```

```bash
make guac            # → http://<host>:8080/   branch / branch
make access-status   # requests, grants, and the policies on the box
```

`make k8s` and `make crossplane` are separate on purpose, and the split is where
the real bootstrap problem is. Cilium is the CNI, so it has to be installed
imperatively — there is no pod network for a controller to run in until it
exists. Everything downstream of a working pod network is declarative and lives
in `crossplane/`.

`make avd-build` is worth running first and often: it renders every device
config with no lab running at all, so you can review a data-model change in
seconds rather than minutes. It is also the thing to put in CI.

---

## Deployments

Two sizes of the same lab, both with the same firewall. They are environment
overrides on the single `otternet.clab.yml`, not separate topology files, so there
is no second copy to drift out of sync; `deploy-lite` uses containerlab's
`--node-filter` and trims per-switch memory.

| Target | Fabric | RAM |
|---|---|---|
| `make deploy` | 7 switches, both pods | ~37 GB |
| `make deploy-lite` | 5 switches, k8s pod + border | ~30 GB |

Both include the ISP, its two customers, and the branch office in full — router,
desktop and Guacamole gateway. The six WAN routers are SR Linux and the hosts
are multitool containers. SR Linux is not small -- about 2 GB per router, set by
`OTTERNET_SRL_MEMORY` -- so the WAN now costs about as much as three more ceOS
nodes; the branch is there because the access demo lives on it.

**Both need CPU virtualization.** The firewall is a VM, and there is no
container-firewall fallback, so a host without `vmx`/`svm` cannot run this lab
at all. `make preflight` checks before anything is torn down.

If something else on the host is using memory (the Infrahub stack, for instance,
holds about 14 GB), use the lite deployment. You can also skip the heaviest
application — the peering and the demo workload are independent of it:

```bash
make crossplane                                    # everything
kubectl delete fabricapp otternet-observability       # frees ~2 GB
```

### The firewall

A Junos **vSRX 3.0** VM, run by vrnetlab, with four security zones matching the
four handoffs from the border leaf. The policy is in
`configs/fw/vsrx/junos.conf`: address book, zones, one-per-intent permit rules,
explicit named denies where a drop is worth logging, and `default-policy
deny-all` behind them.

```text
ge-0/0/0  10.250.110.2/30  <-> border-leaf1 Et10   zone k8s-prod
ge-0/0/1  10.250.210.2/30  <-> border-leaf1 Et11   zone app-prod
ge-0/0/2  10.250.150.2/30  <-> border-leaf1 Et14   zone wan
ge-0/0/3  10.250.170.2/30  <-> border-leaf1 Et15   zone branch
fxp0                           containerlab management
```

Three things about it are worth knowing:

- **`startup-config` genuinely works.** vrnetlab appends `junos.conf` to its own
  `init.conf` and Junos loads the result at boot, so the box comes up already
  carrying its zones and policy — no post-boot push step. Note *appends*: the
  file must not restate what `init.conf` already sets up (`fxp0`, the admin
  user, the `mgmt_junos` instance, SSH, NETCONF).
- **No object-count licence limit.** Junos licenses throughput tiers and feature
  bundles, not how many policies you may write, so the access broker can grant
  as many as anyone asks for.
- **vSRX caps interface MTU at 9192**, an IP MTU of 9178 against the fabric's
  9214. The config clamps TCP MSS to 9124 to compensate; see
  [docs/design.md](docs/design.md#living-with-vsrx).

Building it — Juniper does not redistribute the image, but no support contract
is needed either. A free account registered for "Evaluation user access" can
download the vSRX 3.0 evaluation qcow2 from
<https://support.juniper.net/support/downloads/?p=vsrxeval>; drop it in
`/images` and:

```bash
make fw-image                # vrnetlab/juniper_vsrx:22.3R1.11
make preflight               # will this host run it?
make deploy
```

## What to actually demo

These are the standalone lab's demos, run after `make deploy` and `make crossplane`.
When the lab is driven from Infrahub (`uv run invoke bootstrap` in the repository root),
`invoke cluster` removes the lab's access broker and observability stack, and a branch
user asks through the Backstage portal instead; the script for that is the
[demo runbook](../docs/docs/demo-runbook.md).

**A branch user asks for an application, and gets it.** This is the headline
demo of the branch site.

```bash
make guac              # → http://<host>:8080/   branch / branch
```

That drops you onto a real XFCE desktop at `10.70.0.20`, on the branch LAN,
behind the branch's private circuit. Firefox opens on the Backstage service
portal; its **Access Portal (DC)** bookmark is the lab's own access portal — the
one datacentre service the branch is permitted to reach without asking.

Before you click anything, prove the door is shut. From the desktop's terminal:

```bash
curl -m5 http://10.112.240.16/    # Grafana — hangs, then fails. No policy.
curl -m5 http://10.112.240.33/    # the portal — answers. Policy 6, and only that.
```

Now request **Kanboard** in the portal. It is not running: nothing is deployed,
no VIP is allocated, no rule exists. Approve it (the portal's Approve button, or
`kubectl patch appaccess access-kanboard --type=merge -p '{"spec":{"approved":true}}'`)
and watch all of it happen from one object:

```bash
make access-status     # request → grant → the policy on the firewall
kubectl get appaccess,fabricapp,firewallaccess
```

Within a minute the portal shows a link and the desktop's browser reaches it.
What actually happened, in order: Crossplane composed a `FabricApp`, which
created the namespace, the Deployment, the LoadBalancer Service, a VIP pool, a
BGP advertisement and a default-deny `CiliumNetworkPolicy` naming the branch
LAN; it composed a `FirewallAccess`; the controller wrote an address object, an
application object and a policy, all named `aa-access-kanboard`, and moved that
policy above the default deny.

Then take it away:

```bash
kubectl delete appaccess access-kanboard
make access-status     # the policy, the address object and the app are all gone
```

**The firewall is reconciled, not configured.** Delete a generated policy by
hand and watch it come back — the same story `make xp-drift` tells for Cilium:

```bash
make fw-console
  configure
  delete security policies from-zone branch to-zone k8s-prod policy aa-access-kanboard
  commit and-quit
# wait 20s
make access-status
```

**AVD drives everything.** Change `avd/group_vars/` and rebuild:

```bash
vim avd/group_vars/OTTERNET_FABRIC/10-network-services.yml   # add a VLAN, a VRF
make avd-build && git diff --stat avd/intended/            # see the blast radius
make avd-deploy                                            # push it
```

**Tenant isolation is real.** `K8S_PROD` and `APP_PROD` share a fabric but not a
route. The only path between them leaves the border leaf and comes back:

```bash
make ssh-border-leaf1
  show ip route vrf K8S_PROD          # default route points at the firewall
make fw-log                           # watch sessions being permitted and denied
```

**The fabric polices what Kubernetes claims.** `RM-CILIUM-IN` accepts only
`10.111.0.0/16 le 26` and `10.112.0.0/16`. Widen the Cilium advertisement to
something greedy and watch the leaf refuse it:

```bash
kubectl edit ciliumbgpadvertisement otternet-fabric-advertisements
make ssh-k8s-leaf1
  show ip bgp neighbors 10.110.0.11 received-routes   # offered
  show ip route vrf K8S_PROD bgp                      # accepted — not the same set
```

**Three enforcement points, one intent.** A request from `host-a` to the
frontend VIP must clear the leaf ACL, the vSRX zone policy *and* the Cilium L7
policy. Remove any one and it stops in a different, identifiable place:

```bash
docker exec -it clab-otternet-host-a curl -sS --max-time 5 http://10.112.240.1/
make hubble          # http://localhost:12000 — see the L7 verdict
```

**A WAN customer consumes a DC service across somebody else's network.** Two
customers hang off an ISP in its own AS, each in its own VRF, and both reach
the datacentre's published service VIP:

```bash
make wan-bgp                     # every session, ISP to CE to border leaf
docker exec clab-otternet-cust-acme-host curl -sS http://10.112.240.16/api/health
```

**...and cannot reach each other.** This is the sharpest thing in the WAN,
because it is a route-policy property and nothing else. Both customers'
prefixes are in the ISP's default table — they have to be, or the DC could not
route back — so the only reason acme cannot see globex is the inter-instance
import policy on `isp-pe1`:

```bash
make wan-customers                                    # each VRF's table
docker exec clab-otternet-cust-acme-ce \
  sr_cli -d "show network-instance default ipv4 route 10.60.20.0/24"
# the table header, and no 10.60.20.0/24 line
```

Widen `RM-ACME-IMPORT` in `wan/templates/isp-edge.srl.j2` to accept anything
from the default instance, re-render, re-deploy, and the two customers can
suddenly route to each other through the provider.

**Onboarding a customer is a diff, not a procedure.** Add an entry to
`wan/tenants.yml`, add its two nodes and two links to the topology, then:

```bash
make wan-build && git diff wan/rendered/     # see exactly what will change
make wan-deploy                              # commit, no session bounced
```

**Three independent parties each bound what a customer may do.** The ISP bounds
what the customer may announce and learn, the DC bounds what it will accept
from the ISP and advertise back, and the firewall bounds the sessions. A WAN
customer never even learns a route to the pod CIDR or the node subnet, so
reaching them is not something the firewall has to refuse:

```bash
docker exec clab-otternet-cust-acme-ce \
  sr_cli -d "show network-instance default ipv4 route" | grep -c 10.111  # 0
docker exec clab-otternet-branch-rtr \
  sr_cli -d "show network-instance default ipv4 route" | grep -c 10.110  # 1
```

That asymmetry is the branch office being a different trust level from a
paying customer, expressed in routing rather than only in policy: the branch
is told a route to the node subnet and permitted to ping it, and a customer is
told neither.

**One object deploys a real app onto the fabric.** A `FabricApp` claim is an
application *plus* its place in the network — namespace, Helm release, VIP pool,
BGP advertisement and network policy:

```bash
kubectl get fabricapp
make grafana                          # the VIP, and how to reach it
docker exec clab-otternet-host-a curl -sS http://10.112.240.16/api/health
```

Grafana is `kube-prometheus-stack` from the upstream chart — nothing in this
repo describes its Deployments. It is reachable from the *other* tenant, across
the firewall and over EVPN, and its Prometheus scrapes Cilium and Hubble, so
what it is showing you is the state of the datapath that carried you to it.

**The declared intent wins, and you can watch it win.** The Cilium BGP config is
composed from an XR, so editing it by hand is a temporary condition:

```bash
make xp                               # everything Crossplane owns
make xp-drift                         # break the local AS by hand, watch it heal
```

```text
==> Hand-editing it to a wrong AS (65999), the way someone would in an incident
  now: 65999
==> Waiting for Crossplane to notice and revert it
  reverted to 65401 after 15s -- the XR, not the CRD, is the source of truth
```

That is the part `kubectl apply -f` could not do. Before, the hand-edit stuck
and the repository quietly described a cluster that no longer existed.

**Pod IPs are on the wire.** Masquerading is off and routing is native, so the
leaves see pod addresses, not node addresses. That is what makes the ACLs and
firewall policies meaningful rather than decorative.

---

## Layout

```text
lab/
├── otternet.clab.yml              topology — one file, env-driven profiles
├── Makefile                    every workflow; `make help`
├── avd/
│   ├── inventory.yml
│   ├── group_vars/
│   │   ├── OTTERNET_FABRIC/       fabric, tenants, security, endpoints
│   │   ├── OTTERNET_SPINES.yml
│   │   └── OTTERNET_L3LEAFS.yml
│   ├── playbooks/              build (offline) / deploy (eAPI) / validate (ANTA)
│   └── intended/               generated — configs and documentation
├── wan/                        the ISP, its customers and the branch office
│   ├── tenants.yml           the data model — edit this to onboard a customer
│   ├── templates/              Jinja2 for SR Linux configs and host init scripts
│   ├── render.py               model -> wan/rendered/ (offline, no lab needed)
│   └── rendered/               generated — one directory per WAN device
├── configs/
│   ├── fw/vsrx/            Junos zones and policy, loaded at boot by
│   │                       vrnetlab as a startup-config
│   └── branch/
│       ├── desktop/            the branch workstation image — XFCE, Xvnc, Firefox
│       └── guacamole/          file-based auth and guacd wiring, no database
├── k8s/
│   ├── helm/cilium-values.yaml
│   ├── bootstrap/              k3s entrypoint, Cilium and Crossplane installers
│   └── access/
│       ├── portal/             the self-service portal (stdlib Python, one file)
│       └── fw-controller/      reconciles FirewallAccess onto Junos over SSH
├── crossplane/
│   ├── providers/              packages, pinned identities, RBAC, ProviderConfigs
│   ├── platform/               FabricPeering  — XRD, Composition, and the one claim
│   ├── apps/                   FabricApp      — XRD, Composition, and two apps
│   └── access/                 AppAccess      — XRD, Composition, the FirewallAccess
│                               CRD, RBAC, and the portal's own FabricApp
├── scripts/                    setup, preflight, verify, access image build/import
└── docs/                       design notes and troubleshooting
```

There is no `k8s/manifests/` any more. The BGP objects, the network policies and
the demo workload that used to live there are composed from
`crossplane/platform/10-peering.yaml` and `crossplane/apps/*.yaml`.

### The platform APIs

| Kind | Scope | Produces |
|---|---|---|
| `FabricPeering` | one per cluster | `CiliumBGPClusterConfig`, `CiliumBGPPeerConfig`, and the cluster-wide PodCIDR `CiliumBGPAdvertisement` |
| `FabricApp` | one per application | namespace, Helm release and/or raw manifests, `CiliumLoadBalancerIPPool`, per-app `CiliumBGPAdvertisement`, and a default-deny `CiliumNetworkPolicy` set |
| `AppAccess` | one per request | a `FabricApp` if the app is not running, and a `FirewallAccess` — so approving a request deploys the app *and* opens the firewall, and deleting it closes both |
| `FirewallAccess` | one per grant | a Junos address-book entry, application object and security policy, appended to the relevant zone pair by `k8s/access/fw-controller` |

`FirewallAccess` is a plain CRD rather than an XRD: there is no Crossplane
provider for Junos worth depending on, so a small controller of ours reconciles it onto the box
and reports back on the object's `Ready` condition.

`FabricApp` bundles those because they are not separable in practice: a Service
with no pool never gets a VIP, a VIP with no advertisement is unreachable
off-cluster, and an advertisement with no policy exposes the app to the whole
app tenant. Each of those is a working cluster and a broken application, and
each fails differently enough to be its own debugging session. See
`docs/design.md` for the longer argument.

---

## Verified state

Deployed and validated on this host with ceOS 4.36.0.1F, Junos 22.3R1.11,
SR Linux 26.7.2 and Cilium 1.18.6. On the lab as Infrahub drives it — built by
`invoke bootstrap`, applications delivered by Vidra, the handover done —
`make verify` reports **111 passed, 0 failed, 0 skipped**, covering the list
below. Each skip the script can still print names an optional component that is
not deployed (a WAN customer site, the lab-only access broker, the tooling
cluster); none is reachable on a full build. A lab deployed without Infrahub, or
with `invoke cluster --no-handover`, is detected rather than assumed: the script
looks for `otternet-metrics` or `otternet-observability`, and for the lab's own
access broker, and checks whichever is there.

- 5/5 underlay BGP and 5/5 EVPN overlay sessions, MLAG Active and consistent
- symmetric IRB: the firewall handoff learned as an EVPN type-5 route
- tenant isolation: no direct route between `K8S_PROD` and `APP_PROD`
- Cilium BGP established to both leaves with MD5 auth, all three pod CIDRs and
  the LoadBalancer VIP installed in the fabric's VRF table
- the headline path, ten times out of ten: `host-a` -> firewall -> EVPN ->
  the demo application's LoadBalancer VIP -> pod, through the leaf ACL, the
  firewall zone policy and the CiliumNetworkPolicy, with the VIP checked to lie
  inside that application's own block
- negatives that must fail: a ClusterIP unreachable from the app tenant (the
  lab's `backend`, or, for the one-tier chart Infrahub delivers, the demo
  Service's own ClusterIP while its VIP answers), SSH to a k8s node dropped by
  the firewall, and an out-of-namespace pod denied by Cilium with a Hubble
  verdict
- the Crossplane control plane: both providers and both composition functions
  healthy, both XRDs established, every claim ready, every composed resource
  synced, and the `CiliumBGPClusterConfig` Cilium is actually running confirmed
  to be one of them rather than an orphan
- `kube-prometheus-stack` installed by `provider-helm` as a real release, with
  Prometheus reporting every `cilium-agent` target up (asked through its own
  API, not read from its configuration), and Grafana answering on its
  BGP-advertised VIP from inside the cluster — and dropped at its pod from the
  app tenant even though the firewall permits that session, because
  `otternet-metrics` admits only the pod prefix until a grant names a source
- the WAN: every BGP session from CE through both ISP PEs to the border leaf,
  both customers learning the DC service prefix and **neither learning the
  other's LAN**, and no customer learning the pod CIDR
- both customer hosts reaching the demo application's VIP five times out of
  five, across two AS hops of provider
- the trust asymmetry: the branch may ping a k8s node, a WAN customer has no
  route to one and is denied by policy, and neither can reach the app tenant
- the tenant model: acme's two sites reach each other across one VRF with
  nothing leaked, the statically routed site gets exactly the same service as
  the eBGP one, and neither tenant's VRF learns the other's cloud subnet
- tenant cloud isolation, asserted in both directions: each tenant reaches its
  own instances through its own firewall zone, and **cannot** reach the other's
  — a flat network passes the positives and fails these
- internet as a product: both of acme's sites get HTTP 200 from the internet,
  globex has no default route and cannot, and globex's prefixes are never
  announced to AS 64500 so nothing out there has a route back to it
- the branch office as a site: a LAN of three devices bridged in SR Linux
  mac-vrf `lan`, with `irb0.0` as its gateway, an XFCE
  session serving VNC, guacd reaching that session across the LAN and returning
  its RFB banner, and Guacamole authenticating from `user-mapping.xml` with no
  database behind it
- access closed by default: the branch desktop reaches the portal (Backstage
  and Dex in the tooling cluster, or the lab's broker where it is installed)
  with no grant at all, and **cannot** reach Grafana or the demo application
  until a grant exists. The expectation is derived from fw1's policy and the
  pods' CiliumNetworkPolicy and the datapath must agree with it either way, so
  a grant made while the lab runs moves the expectation instead of failing the
  check. The demo application's pod policy already names the branch, which
  isolates the firewall gate; Grafana's isolates both
- the firewall: it really is a vSRX, four zones bound to their handoffs, a
  deny-all default policy, routes back into both tenants, no NAT anywhere, and
  the TCP MSS clamp of 9124, sized for the VXLAN fabric behind it
  (9214 − 50 − 20 − 20) rather than for its own 9192-byte interface

Exercised by hand, end to end from the branch desktop's browser:

- request and approve **Kanboard**, which is not running: `FabricApp` composed,
  namespace created, pod scheduled, VIP `10.112.240.49` allocated and advertised
  into EVPN, `CiliumNetworkPolicy` written naming the branch LAN, and policy
  `aa-access-kanboard` appended to the `branch`→`k8s-prod` zone pair with its
  address-book entry and application object. Reachable from the desktop about
  15 seconds after approval.
- delete the generated policy on the firewall by hand: traffic stops, and the
  controller puts it back within one reconcile (~10 s)
- `kubectl delete appaccess access-kanboard`: the application, its namespace and
  every object the grant created on the firewall all go, and the desktop can no
  longer reach the VIP

## Notes and gotchas

Things that cost time to work out, recorded so they do not cost it twice.

**MTU: containerlab gives workload veths 9500, AVD configures EOS at 9214.**
Leave it and TCP negotiates a ~9460 byte MSS whose frames the leaf silently
drops. This is the single most expensive bug in this lab to diagnose, because
ping succeeds (it fragments), k3s agents show ESTABLISHED sessions to the API
server, and the only real symptom is that Send-Q never drains and the cluster
never converges. Every workload interface is now pinned to 9214.

**Cilium needs `/sys/fs/bpf` to be a *shared* mount inside the k3s container.**
k3d does this for you; a plain containerlab node does not. Without it every
cilium pod dies in `CreateContainerError` with `path "/sys/fs/bpf" is mounted on
"/sys" but it is not a shared mount`. Handled in the k3s entrypoint.

**Point Cilium's CNI paths at the containerd defaults, not the k3s ones.**
With flannel disabled, the containerd config k3s generates here has no
`[plugins."io.containerd.grpc.v1.cri".cni]` section, so containerd falls back to
`/etc/cni/net.d` and `/opt/cni/bin`. Since the kubelet learns CNI readiness from
containerd over CRI, using the k3s paths yields a perfectly valid conflist that
nothing reads, and every node sits NotReady on `cni plugin not initialized`.

**`kubeProxyReplacement: true` is required for LoadBalancer VIPs.** Cilium only
programs LB-IPAM VIPs into a datapath it owns. With it off, the VIP is allocated
and advertised over BGP -- the fabric even installs the /32 -- but no node ever
answers and connections just time out. k3s runs with `--disable-kube-proxy` to
match -- **on the server only**, because it is a server flag and `k3s agent`
rejects it (see below).

**`externalTrafficPolicy: Local` on any service you write CIDR policy against.**
With the default, a request landing on a node whose backend is elsewhere gets
SNATed to that node's address, so CiliumNetworkPolicy sees `remote-node` instead
of the client. Policies then fail for most requests and work for a minority,
which reads as flakiness rather than a config error.

**L7 HTTP policy does not work on ingress from an external CIDR here.** Hubble
shows `policy-verdict:L3-L4 INGRESS ALLOWED` then `to-proxy FORWARDED (SYN)`,
after which the SYN is retransmitted and Envoy never completes the handshake --
the client sees a timeout, not a 403. The cross-tenant policy is therefore
L3/L4; L7 is demonstrated on the in-cluster frontend-to-backend path.

**Reach the cluster API on the management address, not the fabric one.**
`10.110.0.11` lives in VRF `K8S_PROD` and the host has no route into it, because
the switch management interfaces sit in VRF `MGMT` which deliberately does not
route to tenants. k3s carries a `--tls-san` for the management address.

**cEOS rejects `ip access-group` on a VLAN interface, and uRPF on an SVI.** Both
return "not supported on this hardware platform" and fail the whole config
replace. The tenant source-validation ACL therefore sits outbound on the border
leaf's routed handoff. On real hardware, move it to the access edge.

**cEOS also rejects `storm-control`.** Same failure mode. It is commented out of
the `WORKLOAD_EDGE` port profile with a note to restore it for physical kit.

**Never invent a password hash.** An `sha512_password` that is not actually a
hash of the password you think it is applies cleanly and then locks eAPI out of
every switch it reached. Generate with `openssl passwd -6`. Relatedly,
`management_security.password.minimum_length` is deliberately unset: it rejects
`username x secret 0 <short>` at the CLI, which is exactly the command needed to
recover from that situation.

**`tcpdump` does not exist in the `rancher/k3s` image,** and neither does a
shell in `traefik/whoami`. Captures from those containers fail silently and
produce empty files that look like "no traffic arrived". Use `hubble observe` or
`cilium-dbg monitor` instead -- Hubble is what finally pinpointed both policy
bugs above.

**EOS prints `Estab`, not `Established`,** in BGP summary output, and most show
commands need `Cli -p 15` via `docker exec` or they answer "privileged mode
required". Both cost a round of false failures in `verify.sh`.

**`eos_designs` silently ignores unknown keys.** Its schema sets
`allow_other_keys: true`, so an `eos_cli_config_gen` key placed in
`group_vars` renders *nothing* and reports no error — security config that looks
present and does not exist. Anything that is not a native `eos_designs` key
carries the `custom_structured_configuration_` prefix on purpose. Verify with
`grep` against `avd/intended/configs/`, never by eye.

**`ipv4_acls` only renders where an *interface* references it.** A name
reference from `ssh_settings.vrfs[].ipv4_acl` does not count, so an ACL used
only for the management plane must be raw structured config. Putting it in
`ipv4_acls` produced an SSH server on all seven switches pointing at an
access-list that was defined on none of them.

**BGP passwords are `cleartext_password`, not `password`.** EOS type-7 BGP
ciphertext is keyed by peer-group name or neighbour address, so a hash copied
between peers fails authentication silently. AVD encrypts cleartext with the
right key per peer.

**AVD 6.x is not AVD 5.x.** `design.type` is gone, `tenants` became
`network_services`, `local_users` moved under `aaa_settings`, and static routes
use `prefix`/`next_hop` instead of `destination_address_prefix`/`gateway`. The
validator names the replacement for every stale key — run `make avd-build` and
read it.

**k3s must not start before its fabric link exists.** containerlab creates the
container first and wires veths a moment later. If k3s starts early, kubelet and
Cilium bind to the management address and the fabric never learns a usable next
hop. `k8s/bootstrap/k3s-entrypoint.sh` waits for `eth1`, addresses it, then
execs k3s.

**`sudo -E` is refused on this host,** which would silently drop every `OTTERNET_*`
override and deploy the default profile. The Makefile names the variables via
`--preserve-env=` instead.

**The k8s leaves need unique SVI addresses.** Cilium peers with `10.110.0.2` and
`10.110.0.3`; the shared `10.110.0.1` is a VARP gateway only. Peering to an
anycast address across an MLAG pair is ambiguous.

**The firewall denies by default.** Traffic *to* the firewall (ping, SSH on a data
interface) needs `host-inbound-traffic` on the zone, which is already set for
ping. Add services there if you need more.

**Cilium's socket-LB hooks attach to the wrong cgroup here, and it breaks every
ClusterIP in the cluster.** With `cgroup.autoMount` left on, the agent mounts a
fresh cgroup2 whose root — in this nested containerlab/k3s/pod arrangement — is
the cilium-agent's *own* leaf cgroup. The `connect4` programs are then attached
to a cgroup containing one process, so no other pod's `connect()` passes through
them and ClusterIP translation never happens for anything. It hides for a very
long time, because a north-south demo never touches a ClusterIP: pods reach node
addresses fine and LoadBalancer VIPs work from outside, while in-cluster DNS
never resolves and `nc -z 10.112.0.1 443` from any pod times out. The first
thing that notices is a controller that needs the API server, which then fails
with `dial tcp 10.112.0.1:443: i/o timeout` and looks like RBAC or a policy bug.
Fixed with `cgroup.autoMount.enabled: false` and `cgroup.hostRoot:
/sys/fs/cgroup`.

**Changing that value is not enough — the pinned bpf_links keep the old
attachment.** Cilium pins the socket-LB programs as bpf_links under
`/sys/fs/bpf/cilium/socketlb/links/cgroup/`, and `bpf_link_update` swaps the
*program* but never the cgroup a link is bound to. So the agent restarts, logs
`Updated link for program` for all nine of them, and remains attached to the
wrong cgroup. Delete the pinned links on each node and restart the DaemonSet.

**A Cilium values change lands in the ConfigMap and does not roll the pods.**
`helm upgrade` updated `cilium-config`, the DaemonSet pod spec was unchanged, so
nothing restarted and the running agents kept the old setting — for as long as
you like. Cilium does notice, and says so where nobody is looking:
`config-drift-checker ... key=enable-host-legacy-routing actual=false
expectedValue=true`. Always `rollout restart ds/cilium` after a values change,
and confirm with `cilium-dbg config -a` rather than by reading the ConfigMap
back.

**Pods have no internet egress, and they need it.** Masquerading is off so the
fabric sees real pod IPs, which is the entire basis of the ACL and firewall
demo. But Crossplane resolves package names and pulls charts and OCI artefacts
*from inside pods*. Image pulls are not affected — containerd runs in the k3s
container's netns — so this only surfaces when an in-cluster controller needs
something off-cluster. One iptables rule per node, in the k3s entrypoint:
`-s 10.111.0.0/16 ! -d 10.0.0.0/8 -o eth0 -j MASQUERADE`. The exclusion is
load-bearing: everything in `10.0.0.0/8` is untouched, so pod IPs still appear
on the wire exactly as before, and only genuinely internet-bound traffic on the
management interface is SNATed.

**eBPF host routing bypasses netfilter, so that rule never matches.** The
packet leaving a pod is redirected straight to the egress device in BPF and
never enters the host's upper stack — the MASQUERADE counter sits at zero, and
`cilium monitor` shows no drop because nothing is dropping it. A capture in the
node's netns is what finally showed it: the node was ARPing for `1.1.1.1` out
`eth1`, the *fabric* interface, instead of using its default route on `eth0`.
`bpf.hostLegacyRouting: true` puts pod egress back on the netfilter path. Cilium
still masquerades nothing.

**k3s rewrites resolv.conf to 8.8.8.8, and CoreDNS cannot reach 127.0.0.11.**
Docker gives the container `nameserver 127.0.0.11`, its embedded resolver, which
listens in the *node's* netns — so CoreDNS, running with `dnsPolicy: Default`
and inheriting that file, forwards every external query to a loopback address
inside its own pod. Cluster-internal names resolve (CoreDNS answers those
itself) and external ones fail with `server misbehaving`, so DNS is only half
broken. k3s compounds it: seeing a loopback nameserver, it substitutes `8.8.8.8`
into the resolv.conf it generates for kubelet, which is not reachable from a pod
either. The entrypoint now rewrites resolv.conf with the real upstream — which
Docker helpfully records in an `# ExtServers:` comment in the same file — before
k3s starts.

**`busybox nslookup` without a trailing dot is not a DNS test.** With
`ndots:5` and a five-entry search list, `nslookup kubernetes.default` from a
busybox pod can fail while DNS is working perfectly. This cost a round of
diagnosis: the datapath trace showed the query being answered and the reply
delivered while the command still reported a timeout. Use a FQDN with the
trailing dot, or `nslookup kubernetes.default.svc.cluster.local`.

**A `CiliumLoadBalancerIPPool`'s `serviceSelector` matches cluster-wide.** So
does a `CiliumBGPAdvertisement`'s. Two apps that both select
`otternet.lab/advertise: "true"` — the obvious label, and the one this lab already
documented — match each other's Services, and whichever pool LB-IPAM considers
first hands out the address. Per-app VIP blocks are meaningless without pinning
`io.kubernetes.service.namespace` into the selector. Caught the obvious way: the
observability app was given `10.112.240.16/28` and Grafana came up on
`10.112.240.1`, out of the demo app's block.

**Applying an XRD and a claim that uses a new field in the same `kubectl apply`
silently drops the field.** The API server may still be serving the previous
generated CRD schema when the claim lands, so the unknown field is pruned. The
claim is accepted, Crossplane reports `SYNCED=True`, and the resource that field
was supposed to produce simply is not created. Nothing warns you — read the
field back with `kubectl get <claim> -o jsonpath='{.spec...}'` and re-apply the
claim on its own.

**Crossplane 2 removed `mode: Resources` from Compositions.** Every Composition
is a function pipeline now. `function-patch-and-transform` is the direct
translation of the old style but can only patch a fixed, pre-declared resource
list, which does not work when the resource count depends on the claim — one
`Object` per manifest, one BGP peer per leaf, a policy per rule requested.
`function-go-templating` is the right tool for that shape.

**A provider's ServiceAccount is named after the package revision.** So
`provider-kubernetes-d1ed189e04fc` becomes something else the moment the pinned
version is bumped, and any `ClusterRoleBinding` written against the old name
stops applying — the provider then fails with `forbidden` on a deploy that
changed nothing but a version tag. A `DeploymentRuntimeConfig` pins the name.

**Do not delete a Helm chart's hook Job to make it retry.** Deleting a failed
`admission-create` cert job leaves the release stuck in `failed` with
`failed pre-install: resource Job/... status: NotFound` — the hook it is waiting
on no longer exists and Helm cannot recover. Delete the Crossplane `Release`
instead and let `provider-helm` install it again from the composition.

**Anything Crossplane manages reverts within about 20 seconds.** That is the
point, and it makes live debugging confusing if you have forgotten. To
experiment on a Cilium CRD by hand, delete its `Object` first — or better, edit
the XR.

**`--disable-kube-proxy` is a `k3s server` flag and `k3s agent` refuses to
start with it.** Passing it to an agent gives
`FATA flag provided but not defined: -disable-kube-proxy` and an immediate
exit. `k3s server --help` lists it, `k3s agent --help` does not; kube-proxy is
disabled cluster-wide from the server. This sat latent in the topology for a
while because the *running* containers had been created before the flag was
added to the agent lines — `docker inspect` shows a container's creation-time
command, so the lab kept working and the topology on disk was already broken.
The next `--reconfigure` recreated the agents with the current command and two
of the three k8s nodes never came back.

**A docker restart destroys the links containerlab wired in, permanently.**
containerlab pushes each veth into the node's network namespace from the
outside, after the container is running. A restart builds a *new* network
sandbox, the veth is not in it, and containerlab is long finished and will not
add it again. Since these nodes run with `--restart=always`, anything that
exits PID 1 costs the node its fabric interface for good — and the only
recovery is redeploying the lab (or hand-building the veth pair with
`ip link add ... netns`).

The two failure modes compound, and the result is very misleading: an agent
that cannot start loops, and after the first restart the symptom is no longer
"k3s rejected a flag" but "two of three nodes have no `eth1` at all" while the
switches are perfectly healthy. That reads as a containerlab wiring bug. The
tell is `docker inspect <node> --format '{{.RestartCount}}'` being non-zero,
and the real error being several restarts back in `docker logs`.

`k3s-entrypoint.sh` mitigates it by waiting up to 600s for the link
(configurable, and logging progress, because giving up is unrecoverable) —
which is also the window in which the veth pair can be rebuilt by hand, see
`docs/troubleshooting.md`.

**The obvious fix for that — supervising k3s so PID 1 survives a crash — breaks
the cluster, and `exec` is load-bearing.** On cgroups v2, k3s applies its own
nesting workaround before starting kubelet: it moves the existing processes
into a child cgroup and enables the controllers in the subtree, because cgroup
v2 forbids a cgroup holding both processes and domain controllers. k3s only
does that when it finds itself running as **PID 1**. Wrap it in a supervisor
and it is PID 2, skips the nesting, and kubelet dies with

```text
Failed to start ContainerManager
cannot enter cgroupv2 "/sys/fs/cgroup/kubepods" with domain controllers
-- it is in an invalid state
```

which reads as a broken host, not as a wrapper you added. (The tell that the
workaround has run is `cat /proc/1/cgroup` showing `0::/init` rather than
`0::/`.) A wrapper would have to do the nesting itself, the way k3d's
entrypoint does. So the entrypoint ends in `exec /bin/k3s` and should stay that
way.

**In a `.ONESHELL` Makefile, a `cd` in one variable leaks into the rest of the
recipe.** `AVD := cd avd && …` is used as a command prefix, and because the
whole recipe is a single shell, everything after it runs from `avd/`.
`make deploy` failed with `./scripts/wan-deploy.sh: No such file or directory`
for exactly that reason — the script existed, the shell was just somewhere
else. Wrap such a variable in a subshell (`( $(AVD) … )`) and use absolute
paths for scripts. Same family of problem as the `make -n` one below.

**The routers read `config.cli` once, at boot.** ContainerLab applies a `.cli`
startup configuration on top of the image defaults when the node is created;
editing the file afterwards changes nothing on a running router. `make
wan-deploy` is what makes a running router match it. The hosts are different:
they still bind-mount `init.sh`, and `docker cp` onto a bind-mounted file fails
with `device or resource busy` -- so `wan/render.py` overwrites in place and
never `rmtree`s its output, which would leave every running host mounted on a
file that no longer exists.

**A push replaces the whole configuration, in one candidate.** The rendered
file is the router's complete configuration -- `/system` included -- and opens
with `delete /`. `wan-deploy` loads it into a private named candidate (after its
own `delete /`) and commits with `commit confirmed timeout 120`. It accepts only
once gNMI (57400) and SSH (22) are listening again in the management namespace;
otherwise it rejects, and SR Linux rolls back by itself if nothing answers. The
commit applies only the net difference, so an unchanged tenant's session is not
bounced, and anything removed from `tenants.yml` is removed from the router.

Three things on a ContainerLab-booted router are deliberately left out of the
file, and a first push removes them:

- the TLS profile, whose private key is `$aes1$`-encrypted per device. gNMI uses
  `default-tls-profile` instead, a certificate the router generates for itself,
  and JSON-RPC listens on HTTP only.
- the deploying host's SSH keys.
- SNMP, DNS, the EDA servers and the banner.

The admin password is the sha512-crypt hash of the lab password (`admin`) that
the fabric switches also use (`tenants.yml` `admin_password_hash`).

**sr_cli tokenises quotes before it recognises a comment.** One apostrophe in a
`#` line swallows every following line up to the next quote, and those lines
are never applied -- with no error, on a router that boots "successfully". It
was measured here as a router missing its management interface, every address
and half its routing policy. No comment in a template may carry `'` or `"`;
`wan/render.py` refuses to write one that does.

**Route leaking needs both halves, and either alone fails silently.** A tenant
VRF importing from `default` gets nothing unless `default` also exports its
routes as leakable (`inter-instance-policies ... export-policy [ LEAKABLE ]`),
and a leaked route sits in the route table but not in BGP unless
`bgp rib-management table ipv4-unicast route-table-import` names a policy that
takes it -- at which point that policy is also the only way a loopback or a
static route enters BGP. Both failures were measured with every session up.

**sr_cli stops at the first error and commits nothing.** A malformed line or a
commit SR Linux refuses (a policy naming a prefix-set that is gone) leaves the
running configuration untouched and exits non-zero -- but it leaves the named
candidate behind, and a router holds at most ten. `wan-deploy` clears its
candidate on failure.

**`ip-mtu` defaults to 1500 on every subinterface**, whatever the port carries.
Each routed subinterface states 9214, matching the border leaf.

**ICMP to a LoadBalancer VIP does not work, and the error is misleading.**

```text
From 10.110.0.12 icmp_seq=1 Time to live exceeded
```

Cilium programs the service's TCP port, not ICMP, so an echo request to a VIP
lands on a node with no route for it, is forwarded back out on the node's
default route, and loops until the TTL expires. It looks like a routing loop
in the fabric and it is not — it says nothing about policy at all. `curl` the
VIP; ping a node address.

**"The network works but the app times out" is usually the fourth gate.** A
route existing and the firewall permitting the session is not enough: the
application's own `CiliumNetworkPolicy` has to name the source, which for a
`FabricApp` means an entry in the claim's `policy.allowFrom`. This caught the
WAN during development — the ISP, the border leaf and the firewall were all
passing traffic (21 packets on the firewall's allow counter) while Cilium was
still dropping it. That is the design working, but only if you know to look
there fourth.

**A preflight that measures free memory will refuse to redeploy a running
lab.** `make deploy` runs containerlab with `--reconfigure`, which tears the
existing lab down *before* building the new one, so its memory is about to
come back. Checking `MemAvailable` alone fails every time the lab is already
up — which is most of the times you actually run it — and then advises using
the lite profile, when the full one would have fit. `scripts/preflight.sh` adds
the current lab's own committed memory back before comparing.

**`make -n` is not a dry run in this Makefile, and it destroyed a running lab.**
This file sets `.ONESHELL`, so a whole recipe is one shell invocation — and GNU
make executes any recipe line containing `$(MAKE)` even under `-n`, on the
assumption a recursive make will honour the dry run itself. With `.ONESHELL`
that "line" is the *entire recipe*, so a single `$(MAKE)` at the bottom makes
every command above it run for real. `make -n` also skips prerequisites, so the
`preflight` guard did not fire. `make -n deploy` therefore ran
`containerlab deploy --reconfigure`, which tears the lab down before rebuilding
it, then failed the virtualization check — so a dry run deleted the lab and did
not bring it back. There is now no `$(MAKE)` anywhere in a recipe; shared
sub-steps are shell variables (`POST_DEPLOY`, `WAN_DEPLOY`) called directly.

**A make target that shares a name with a directory silently does nothing.**
`make crossplane` printed `make: 'crossplane' is up to date.` and exited 0,
because the `crossplane/` directory exists and make treated the target as an
already-built file. Nothing ran, nothing failed, and the exit status was
success. Every target in the Makefile is now declared `.PHONY`.

**A k3s-in-containerlab node lies to the scheduler about how much memory it
has.** The kubelet reports the *host's* memory as the node's capacity; it knows
nothing about the containerlab `memory:` cgroup limit on the container it is
running inside. So the scheduler will happily place 2268Mi of pod limits inside
a 2048MB node — nothing rejects it, no pod goes Pending, and there is no event
about it. The kernel then OOM-kills processes inside that cgroup, and what dies
is not necessarily what caused it: here the visible symptoms were Grafana's
*sidecars* being OOMKilled, Grafana itself never going ready, and a
`node-exporter` on the same node SIGTERMed eight times because its liveness
probe timed out under the pressure. None of those point at the real cause.

The rule for this lab: the sum of pod memory limits scheduled onto a k8s node
must fit inside that node's `memory:` in `otternet.clab.yml`, alongside k3s itself
(~700MB for the server) and Cilium (~250MB). Check it by hand, because nothing
else will:

```bash
kubectl get pods -A -o json | python3 -c '
import json,sys,collections
t=collections.Counter()
for p in json.load(sys.stdin)["items"]:
    n=p["spec"].get("nodeName")
    for c in p["spec"]["containers"]:
        m=c.get("resources",{}).get("limits",{}).get("memory","")
        if m.endswith("Mi"): t[n]+=int(m[:-2])
        elif m.endswith("Gi"): t[n]+=int(m[:-2])*1024
for n,v in t.items(): print(n, v, "Mi of limits")'
for n in k8s-node1 k8s-node2 k8s-node3; do
    printf '%s cgroup limit: %s MB\n' "$n" \
      "$(( $(docker inspect clab-otternet-$n --format '{{.HostConfig.Memory}}') / 1000000 ))"
done
```

The observability stack now carries node affinity keeping Prometheus and
Grafana off the control-plane node and apart from each other, and node2/node3
are 2560MB rather than 1536MB. A `memory:` change does not need a redeploy:
`docker update --memory 2560m --memory-swap -1 clab-otternet-k8s-node2` applies it
live.

**Grafana is OOMKilled at a 384Mi limit, and it does not look like OOM.**
It registers every bundled datasource plugin before it opens its port, and that
startup peak is well above its steady state. Under a tight limit it dies
part-way through and starts over, so the logs show plugin registration slowing
to roughly one plugin a minute — GC thrash — and then a restart. That reads as
a slow host, and on a lab host that genuinely is busy it is very easy to
believe. `kubectl get pod` showing `OOMKilled` between restarts is the only
clear tell; the limit is now 768Mi.

The knock-on is worth knowing because it points away from the cause: while
Grafana churns, no node has a ready backend, so `externalTrafficPolicy: Local`
withdraws the VIP from BGP and the *fabric* demo fails. `make verify` reports
that Grafana's VIP is missing from the fabric and that Grafana no longer answers
on it, which looks like a routing or policy problem and is a memory limit.

**containerlab refuses VM-based kinds outright without `vmx` or `svm`.** It does
not try and fail, it checks `/proc/cpuinfo` during topology validation and stops
with `Cpu virtualization support is required for node "fw1"`. Note the
capitalisation if you are grepping for it. A cloud instance almost never
exposes this — on AWS, only `.metal`.

**`startup-config:` works here, and that is not the norm.** For many vrnetlab
kinds containerlab mounts a `/config` directory that the vendor's `launch.py`
never reads, so the plumbing looks present and nothing loads your file. The
`juniper_vsrx` launcher genuinely uses it — but by *appending* to its own
`init.conf`, not replacing it, so `junos.conf` must not restate `fxp0`, the
admin user, the `mgmt_junos` instance, SSH or NETCONF.

**vrnetlab derives the image tag from the qcow2's filename.** Its Makefile
strips `junos-vsrx3-x86-64-` and `.qcow2`, so the name Juniper ships produces
the right tag and a renamed file produces a confident tag for the wrong
software. `scripts/build-vsrx.sh` fails early rather than building a mislabelled
image.

**`plain-text-password-value` is not hashed in a boot configuration.** vrnetlab's
`init.conf` sets the admin password that way, and Junos stores the leaf verbatim
when the file *is* the boot config — the account ends up with no usable
credential. Everything else commits, the box looks healthy, and the only symptom
is "Login incorrect". `junos.conf` sets an `encrypted-password` explicitly for
this reason. If you are ever locked out, `root` on the serial console has no
password.

**vSRX will not accept the fabric's MTU.** The interface maximum is 9192 and
Junos counts the Ethernet header in it, so `mtu 9228` is rejected with `Value
9228 is not within range (256..9192)` and the best available IP MTU is 9178
against the fabric's 9214. The config clamps TCP MSS to 9124, sized for the VXLAN fabric
behind the firewall (9214 − 50 − 20 − 20) rather than for its own interface; without that,
large transfers stall while ping and session setup work perfectly.

**A `docker restart` of the firewall loses its data interfaces.** The restart
rebuilds the container's network sandbox without the veths containerlab wired in
from outside, and the box comes back with `fxp0` and nothing else. Redeploy
rather than restart.

See `docs/verifying.md` to check all of this yourself command by command,
`docs/design.md` for the rationale, and `docs/troubleshooting.md` when it
breaks.
