# Design notes

Why the lab is built the way it is. The README covers *what* to run; this covers
the decisions, including the ones that were reversed.

## The point of the lab

AVD, security and Kubernetes are easy to demo separately and much harder to demo
*together*. Separately, each is a slide. Together, the interesting question
appears: when a pod is unreachable from a bare-metal host, which of the three
layers stopped it, and can you tell without guessing?

So the design goal was a single path that crosses all three, with an
identifiable failure point at each layer:

```
host-a ──▶ app-leaf ──▶ EVPN ──▶ border-leaf ──▶ fw1 ──▶ border-leaf
       ──▶ EVPN ──▶ k8s-leaf [ACL] ──▶ k8s-node ──▶ Cilium [policy] ──▶ pod
```

Every hop is enforced by config that AVD or a manifest generated, and each
enforcement point logs its own verdict.

## Fabric: eBGP underlay, eBGP EVPN overlay

The most common single-DC L3LS pattern, and the one where BGP policy is most
visible. An iBGP-with-route-reflectors overlay would be equally valid and is
arguably more common at scale, but it puts the policy in fewer places, which
makes for a worse demo of "the fabric polices what the workload claims".

ASNs are per-MLAG-pair (`65101`, `65102`, `65103`) rather than per-switch, which
is what AVD's `node_groups` express naturally and what keeps EVPN route targets
tidy.

## Two tenants that deliberately cannot talk

`K8S_PROD` and `APP_PROD` are separate VRFs with no route leaking. Neither
imports the other's route targets. The only route out of each is a default
pointing at the firewall, originated on the border leaf and redistributed into
EVPN as a type-5.

This is the whole security premise. If the VRFs leaked — which is one line of
AVD config away — the firewall would be bypassed and every zone policy would be
theatre. `scripts/verify.sh` asserts the absence of a direct route between them,
because a silently-leaking fabric looks identical to a working one until you
check.

## Anycast gateway *and* unique SVI addresses

The k8s SVI carries three addresses' worth of intent:

- `10.110.0.1` — VARP anycast gateway, what the nodes point their route at
- `10.110.0.2` on `k8s-leaf1`, `10.110.0.3` on `k8s-leaf2` — unique per leaf

The unique addresses exist because Cilium needs two distinct BGP neighbours. An
anycast address as a BGP peer across an MLAG pair is ambiguous: ARP decides
which leaf you land on, and the session moves when it re-resolves.

This is why the SVI uses `ip_address` plus `ip_virtual_router_addresses` rather
than the more common EVPN `ip_address_virtual`.

## Kubernetes as a routing peer, not a guest

The Cilium configuration is chosen so pod traffic is *visible to the fabric*:

| Setting | Reason |
|---|---|
| `routingMode: native` | The fabric already does VXLAN. A second encapsulation would hide pod IPs from the leaves entirely. |
| `enableIPv4Masquerade: false` | Pods appear on the wire as pod IPs. With masquerading on, the leaves only ever see node addresses and every ACL and firewall rule below L3 becomes meaningless. |
| `bgpControlPlane.enabled` | Pod CIDR and LoadBalancer VIPs reach the leaves as BGP routes, then EVPN as type-5. |
| `devices: eth1` | Bind the datapath to the fabric link, not management. |

`kubeProxyReplacement: true`, and k3s runs with `--disable-kube-proxy` to match.
This is not a tuning choice: Cilium only programs LB-IPAM VIPs into a datapath
it owns, so with kube-proxy in charge the VIP is allocated and advertised over
BGP -- the fabric even installs the /32 -- and no node ever answers it.

`bpf.hostLegacyRouting: true` for a related reason. eBPF host routing redirects
a packet leaving a pod straight to the egress device without entering the host's
upper stack, which is the point of the feature and also means it never passes
POSTROUTING. Pods therefore cannot be masqueraded by iptables, and this lab
needs exactly one such rule -- see *Pod egress* below.

### Advertisement is opt-in

A service reaches the fabric only if it carries `otternet.lab/advertise: "true"`.
The `CiliumBGPAdvertisement` selector and the `CiliumLoadBalancerIPPool`
selector both check it. Nothing is exposed by accident, and the contrast between
the advertised frontend and the ClusterIP-only backend is the demo.

## Defence in depth, three layers that must agree

| Layer | Enforces | Where it comes from |
|---|---|---|
| Leaf ACL | Anti-spoofing at the access port: a node may source only node, pod or service addresses | `ipv4_acls` in AVD, applied to the SVI |
| BGP route policy | What the cluster may advertise: `10.111.0.0/16 le 26`, `10.112.0.0/16` | `RM-CILIUM-IN` via custom structured config |
| Firewall zone policy | Which sessions may cross between zones | `configs/fw/vsrx/junos.conf` |
| Cilium policy | L3/L4/L7 inside the cluster, default-deny | composed by Crossplane from the `FabricApp` claim |

The layers are intentionally redundant and intentionally *independent*: the leaf
ACL does not know about the firewall, and the firewall does not know about
Cilium. Each can be broken alone to show where traffic stops.

The L7 rule is the sharpest demonstration, and it lives on the *in-cluster*
path: `allow-frontend-to-backend` permits `GET /api/.*` from the frontend to the
backend and nothing else, so a `POST` is dropped after L3 and L4 already allowed
it — something no ACL or firewall zone in this lab can express.

It is deliberately not on the cross-tenant path. With this datapath (native
routing, masquerading off) an L7 ingress redirect from an external CIDR gets as
far as a `policy-verdict:L3-L4 INGRESS ALLOWED` and a `to-proxy FORWARDED (SYN)`,
and then Envoy never completes the handshake — the client sees a timeout rather
than a 403, which is a worse demo than no L7 rule at all. The cross-tenant
policy is therefore L3/L4.

## Firewall: one, and why this one

The lab used to carry three interchangeable firewalls — an nftables container,
a FortiGate VM and a vSRX VM — selected by environment overrides on one
topology file. That was a reasonable way to reach different audiences, and it
cost more than it returned: three policy files expressing the same intent, three
sets of vendor quirks in the docs, a `verify.sh` that branched on which box was
deployed, and an access broker carrying a driver per vendor.

There is now one firewall, a **Junos vSRX 3.0**, and everything downstream is
written against it. The trade accepted along with that: the lab needs CPU
virtualization on the host, because the firewall is a VM and there is no
container fallback any more. On a machine without `vmx`/`svm` this lab does not
run at all, and `make preflight` says so before anything is torn down.

vSRX earns the slot over the alternatives for three reasons.

**It is a real box with a real management plane.** The access broker needs
something it can log into and configure at runtime. An nftables container has
nothing to drive — it can enforce policy but cannot be asked to change it — so
the self-service demo, which is the point of the branch office, is impossible
there.

**Junos does not licence object counts.** Juniper sells throughput tiers and
feature bundles (IPS, AppSecure, Content Security); nothing caps how many
security policies you may write. The FortiGate profile did have such a cap — its
evaluation licence allows ten firewall policies in total — and the whole
hand-written baseline had to be merged down to seven rules to leave three slots
for user requests. Rules that differed only by source zone were combined, an
explicit anti-spoofing deny became a shared one, and `make verify` had to police
the budget so it did not creep back. None of that shapes the config here: the
rules are one-per-intent, and the anti-spoofing deny is repeated as the first
policy of every zone pair because repeating it is free.

**Its config loads at boot.** `startup-config` genuinely works for the
`juniper_vsrx` kind, so the box comes up carrying its zones and policy with no
post-boot push step and no serial-console driver to maintain.

**cSRX would have been lighter** — a container doing the same job in seconds
rather than a VM needing 4 GB and a two-minute boot — and it is still the better
answer for anyone who wants Junos without the memory. It is not used here
because the image available on this host, `csrx:26.2R1.7`, is newer than
containerlab's `juniper_csrx` kind supports: `srxpfe` wants 4 GB, Junos never
registers `ge-0/0/0`, and it logs a missing `/usr/local/bin/jhost`. An older
22.x or 24.x cSRX would likely just work.

## The WAN: an ISP, its tenants, the internet, and a branch office

The datacentre had two internal tenants and nothing outside it. That makes the
firewall demo a little artificial: both sides of every policy were networks we
controlled. The WAN adds the cases that actually matter — a paying customer
arriving through somebody else's network, and our own remote office — and they
are deliberately not the same thing.

```
cust-acme-host ─ CE ─┐                                    ┌─ fw1 [zone wan]
                     ├─ isp-pe1 ─ isp-pe2 ─ border-leaf1 ─┤
cust-globex-host ─CE─┘   AS 65500          VRF WAN         └─ back in → K8S_PROD → VIP

branch-host ─ branch-rtr ───────────────── border-leaf1 ─── fw1 [zone branch]
                  AS 65030                 VRF BRANCH        (private circuit,
                                                              no ISP in path)
```

### Tenant, not customer

The unit of isolation is the **tenant**; a **site** is one attachment circuit
into it. The two get conflated constantly and the cost shows up the first time
a customer opens a second office.

- a tenant gets one VRF on the PE, one identity, one import policy
- a site gets an interface, and nothing else of its own

Everything useful falls out of that. Two sites of one tenant reach each other
because they are in the same VRF — there is no leaking to configure, no
site-to-site policy, and nothing to forget when the third site arrives. Two
tenants cannot reach each other because they are in different VRFs and the
import policy says so.

Sites of one tenant need not attach the same way. `acme` has two:

| site | kind | LAN | how it attaches |
|---|---|---|---|
| `hq` | `bgp` | `10.60.10.0/24` | eBGP session with the PE, AS 65010 |
| `dr` | `static` | `10.60.11.0/24` | no protocol at all — a static route on the PE, redistributed |

`cust-acme-dr-ce` runs no routing daemon. It has an address on each side, IP
forwarding, and a default route at the PE; the PE holds `ip route 10.60.11.0/24
10.51.11.2` inside `CUST_ACME` and redistributes it. Downstream — the DC, the
internet, and acme's *other* site — every one of them learns `10.60.11.0/24`
the same way they learn the eBGP site. That is the point of normalising at the
PE: the tenant's service does not depend on what its edge router can run, and a
large number of real small sites attach exactly like this.

### Isolated cloud instances, and where isolation actually lives

A tenant's cloud resources are a VRF in the fabric — `TENANT_ACME`,
`TENANT_GLOBEX` — with an SVI on the app leaves and instances on ordinary
access ports. Bare metal, a VM, a container host: from the fabric's point of
view they are the same thing, a host in the tenant's VLAN. Kubernetes is the
other shape this takes, and a tenant gets that through the access portal rather
than through this file.

Isolation is enforced in **three independent places**, and it is worth being
precise about which does what, because only the first is structural:

1. **The fabric.** `TENANT_ACME` and `TENANT_GLOBEX` are separate VRFs with no
   route between them on any switch. There is no east-west path to filter,
   because there is no path.
2. **The PE import policy.** `RM-ACME-IMPORT` permits the shared DC services,
   acme's own cloud subnet, and a default route. Every tenant's prefixes are in
   the provider's default table — they have to be, or the DC could not route
   back — so this route-map is the only thing stopping acme learning globex's
   cloud.
3. **The firewall.** Traffic from a tenant site arrives in the shared `wan`
   zone and leaves into that tenant's own zone. `acme-sites-to-acme-cloud`
   matches source `acme-sites` (an address-set of *both* acme sites) to
   destination `acme-cloud`. Globex's packets match no rule and the default
   policy drops them.

Note what gate 3 does *not* contain: any rule mentioning globex in acme's zone
pair. **The isolation is the absence of a permit**, which is why `make verify`
asserts the negative — that globex cannot reach acme's cloud — rather than only
the positive. A flat network passes every positive check in this section.

The handoff is one wire per tenant (`ge-0/0/4`, `ge-0/0/5`), for the same
reason the zones are one wire each elsewhere: a tagged trunk would work and
would read far less clearly when the point being demonstrated is that adding a
tenant adds a zone rather than an exception.

### Internet access is a product

`acme` buys it and `globex` does not, and the entire difference in the
generated config is one route-map clause:

```
route-map RM-ACME-IMPORT permit 30      route-map RM-GLOBEX-IMPORT
 description acme buys internet access   (no permit 30)
 match ip address prefix-list PL-DEFAULT
```

Both halves are policy. Inbound, only acme's VRF imports the default route, so
globex has nowhere to send an internet-bound packet — the failure happens at
the first hop, not at a firewall. Outbound, `RM-INTERNET-OUT` on `isp-pe2`
announces only the sites of tenants that bought transit, so nothing on the
internet has a route back to globex even by accident. The host configuration
follows the same split: a host behind an internet tenant gets a default route,
one behind globex gets `10.0.0.0/8` and nothing else.

**There is no NAT anywhere, and that is the one dishonest part of this.**
Customer LANs are RFC1918 and `internet-rtr` simply holds a route back to
them, which a real internet does not. A production design assigns the customer
public space or NATs at the provider edge; neither is modelled because the FRR
image carries no `iptables` or `nft`, and the thing worth showing here is the
routing policy — who gets a default route and whose prefixes get announced —
rather than address translation. Adding it later means one gateway node with a
NAT ruleset, not a redesign.

### Why FRR and not more ceOS

The ISP is not part of the fabric AVD builds, and nothing about being an Arista
box makes the demo better. FRR is a real BGP implementation at ~200 MB, so the
entire WAN layer — two PEs, two CEs, a branch router and three hosts — costs
less than one additional ceOS node. On a host that was already at 22 GB of 30,
that was the difference between building this and not.

It also keeps the boundary honest: the fabric is rendered by AVD from
`avd/group_vars/`, the WAN is rendered by `wan/render.py` from
`wan/tenants.yml`, and the two meet at one eBGP session.

### Customer separation without MPLS

Each customer terminates in its own VRF on `isp-pe1`. There is no MPLS, no
VPNv4 and no route targets: with two PEs and a lab-sized customer count, LDP
and a labelled core buy realism at the cost of a dataplane that is materially
more likely to need debugging than to teach anything.

What replaces it is BGP VRF leaking, and the interesting part is that isolation
becomes a route-policy property rather than a dataplane one:

1. the CE announces its LAN over eBGP into `CUST_<name>`
2. the ISP's default table does `import vrf CUST_<name>`, so the DC learns a
   route back to the customer
3. each customer VRF does `import vrf default` — but through
   `RM-DC-SERVICES-ONLY`, which permits only `dc_service_prefixes`

Step 3 is the whole design. After step 2 **both** customers' prefixes are
sitting in the provider's default table; they have to be, or return traffic
could not be routed. So if step 3 imported the default table unfiltered, each
customer would be handed the other's routes and the provider would be
transiting between them. The route-map is the only thing preventing it, which
is why `make verify` asserts the negative directly rather than trusting the
config:

```
PASS  customer isolation: acme has no route to globex's LAN
PASS  customer isolation: globex has no route to acme's LAN
PASS  a WAN customer never learns the DC pod CIDR
```

The honest limitation: the `isp-pe1`–`isp-pe2` link carries customer traffic in
a single table. One hop of this provider's core has no per-customer separation.
That is exactly what MPLS L3VPN would fix, and it is the trade that was chosen
knowingly.

### Three independent places say what a customer may do

The same defence-in-depth argument the fabric already makes, extended outward.
Each of these is enforced by a different party and none of them trusts the
others:

| Control | Enforced by | Says |
|---|---|---|
| `RM-CUST-<name>-IN` | the ISP, on isp-pe1 | this customer may originate only its assigned prefix — not a default route, not another customer's LAN |
| `RM-DC-SERVICES-ONLY` | the ISP, on isp-pe1 | this customer may learn only the DC's published service prefixes |
| `RM-WAN-IN` + `ACL-FROM-WAN` | the DC, on border-leaf1 | the provider may announce only customer space, and may only source packets from it |
| `RM-DC-TO-EXTERNAL` | the DC, on border-leaf1 | the outside world learns the service VIP range and nothing else — not the pod CIDR, not the node subnet |
| zone policy | the firewall | a customer gets tcp/80 and tcp/443 to the service range; the branch also gets ICMP |

Note the fourth row. A WAN customer never learns `10.111.0.0/16` or
`10.110.0.0/24`, so reaching a pod or a node is not something the firewall has
to refuse — there is no route to try.

### The branch is not a customer

It would have been less work to hang the branch off the ISP as a third
customer. It is on a private circuit into `border-leaf1` instead, because the
point of having a branch at all is that it is a *different trust level*: our
own users, on our own circuit, with no third party in the path. That earns it
its own VRF and its own firewall zone, and lets the branch policy be more
permissive — it may ping the DC, a customer may not — without loosening
anything for the customers.

The two are also explicitly denied to each other, in both directions, on the
firewall. A customer and our own office have no reason to meet.

### Onboarding a customer is a data-model change

`wan/tenants.yml` is the model; `make wan-build` renders every device config
offline into `wan/rendered/`, reviewable as a diff before anything is pushed;
`make wan-deploy` makes the running devices match. The same shape as
`make avd-build` / `make avd-deploy`, for the same reason: a change you can
read as a diff is a change you can refuse.

Two details worth knowing:

- **`make wan-deploy` reloads, it does not restart.** It runs FRR's own
  `frr-reload.py`, which diffs the running config against the file and applies
  only the difference, so onboarding a customer does not bounce the BGP
  sessions of the customers who were already there. `vtysh -f` would *merge*,
  which is worse than useless here: a customer deleted from the model would
  keep its VRF and its session.
- **The renderer overwrites in place and never `rmtree`s.** The topology
  bind-mounts `wan/rendered/<node>/frr.conf` straight into the container, so
  deleting and recreating the file swaps the inode and leaves every running
  router mounted on a file that no longer exists. Overwriting means a
  re-render is immediately visible inside the container and the reload has
  nothing to copy.

## Crossplane owns the platform, not just the apps

The lab originally applied its Kubernetes side from `k8s/manifests/`: four BGP
manifests, a namespace, a workload and five network policies, pushed by
`kubectl apply -f` from a shell script. That works, and it is how most demos of
this shape are built. It also has a specific weakness that is worth naming,
because it is the thing Crossplane fixes here.

`kubectl apply` is a one-shot. Once the BGP peering, the VIP pool and the
network policies are applied, nothing is watching them. Someone debugging an
incident edits the `CiliumBGPClusterConfig` by hand, the fix works, and the
repository now describes a cluster that does not exist — with no signal of any
kind. For a lab whose whole argument is *the network and the workload are one
system*, having half that system be un-reconciled state is the wrong shape.

So the split is:

| | Applied how | Why |
|---|---|---|
| Cilium the CNI | `helm install`, imperatively, once | There is no pod network for a controller to run in until it exists. This is genuinely irreducible. |
| Cilium the network intent | Crossplane XRs | BGP peering, advertisements, VIP pools and network policy are ordinary desired state, and continuously reconciled. |
| Applications | Crossplane XRs | Including their Cilium resources, declared in the same object. |

`k8s/bootstrap/install-cilium.sh` now stops after the CNI, the BGP session
password and the node labels. Everything downstream of a working pod network is
in `crossplane/`.

### Two APIs, not a pile of manifests

**`FabricPeering`** is the cluster's side of the BGP contract with the fabric:
local AS, the leaf addresses to peer with, the session password, and what the
cluster is willing to advertise about itself. There is one per cluster. Every
field has a counterpart AVD rendered onto the leaves, and the XRD says so in the
field descriptions, because the two drifting apart is the failure this API is
meant to prevent.

**`FabricApp`** is an application that participates in the fabric. One claim
produces a namespace, the app (an upstream Helm chart, raw manifests, or both),
a VIP pool cut for that app alone, a BGP advertisement that puts the VIP into
EVPN, and a default-deny policy plus the specific allows the app needs.

Bundling those is the actual design decision, and the reason is that they are
not separable in practice:

- a Service with no pool never gets a VIP
- a VIP with no advertisement is unreachable off-cluster
- an advertisement with no policy exposes the app to the entire app tenant

Each of those is a working cluster and a broken application, and each fails
differently enough that diagnosing them is three separate exercises. Making them
one API means an app's reachability and the policy protecting it are declared
together and cannot drift apart. It is the same argument AVD makes about device
config, applied one layer up.

### Why go-templating and not patch-and-transform

Crossplane 2 removed the old `mode: Resources` composition style; every
Composition is a function pipeline. `function-patch-and-transform` is the direct
translation of the old style, but it can only patch a *fixed* list of resources
declared up front. These compositions fan out variably — one `Object` per raw
manifest, one BGP peer per leaf, a policy per rule that was actually requested,
a pool and an advertisement only if the app is exposed — so with
patch-and-transform every one of those would need a declared maximum and unused
slots pruned. `function-go-templating` renders the resources the claim actually
implies.

### The Cilium CRDs are wrapped in Objects

There is no Cilium provider for Crossplane, so each Cilium CRD is managed as a
`provider-kubernetes` `Object`. This is the standard approach for bringing a
CRD-only controller under management, and the Object is a managed resource in
every ordinary sense — it reconciles on a poll, so hand-editing the underlying
CRD is reverted. `make xp-drift` breaks the `CiliumBGPClusterConfig`'s local AS
by hand and waits for it to heal; the provider polls every 20s (set in
`crossplane/providers/01-runtime.yaml`) purely so that is watchable during a
demo rather than a minute of dead air.

One consequence worth stating: an `Object` reverting a hand-edit is exactly what
you want in production and exactly what makes live debugging confusing. If you
are deliberately experimenting with a Cilium CRD, either edit the XR or delete
the `Object` first.

### The advertisement selectors are namespace-scoped, and have to be

A `CiliumLoadBalancerIPPool`'s `serviceSelector` matches Services *cluster-wide*
by label, and so does a `CiliumBGPAdvertisement`'s. Two `FabricApp`s that both
select `otternet.lab/advertise: "true"` — the obvious label, and the one this lab
already documented — therefore match each other's Services. Whichever pool
LB-IPAM considers first hands out the address, so an app silently gets a VIP from
another app's block and is advertised by another app's advertisement. Per-app
blocks mean nothing without this.

The composition pins `io.kubernetes.service.namespace` into both selectors,
which Cilium includes in the labels it matches against. It was caught here the
obvious way: the observability app was given `10.112.240.16/28` and Grafana came
up on `10.112.240.1`, out of the demo app's block.

## Living with vSRX

The config itself is unremarkable Junos and reads as you would expect. Three
things about running it under vrnetlab were not obvious and cost real time.

### Three things that cost time

**vSRX cannot match the fabric MTU.** The interface maximum is 9192 and Junos
counts the 14-byte Ethernet header in that figure, so the best IP MTU available
is 9178 against the fabric's 9214:

```
Value 9228 is not within range (256..9192)
```

36 bytes short is enough to produce the failure this lab warns about everywhere
else — ping fine, sessions establish, bulk transfers stall. The config clamps
TCP MSS to 9138 (`security flow tcp-mss all-tcp`) so endpoints never build a
segment that cannot fit, rather than relying on PMTUD and ICMP finding their way
back through a default-deny firewall. `make verify` asserts the clamp is
present.

**`plain-text-password-value` is not hashed in a boot configuration.** vrnetlab's
init.conf sets the admin password that way, and when the file is the boot config
Junos stores the leaf verbatim instead of converting it: `show configuration
system login` shows `plain-text-password-value` where you would expect
`encrypted-password`, and the account has no usable credential. Everything else
commits, the box looks completely healthy, and the only symptom is "Login
incorrect".

`junos.conf` therefore sets an `encrypted-password` explicitly. That is the one
place it deliberately restates a `system` stanza from init.conf, and the hash is
of the same `admin@123` that vrnetlab and containerlab already use so there is
still one credential across `make fw-console`, clab's tooling and the access
controller.

**Root logs in on the console with no password**, which is how the above was
diagnosed and is worth knowing when a Junos box will not let you in: `root` at
the serial console, then `cli`.

## Requesting access to an app

The branch office is where the lab stops being about packets and starts being
about people. A user sits at a desktop on the branch LAN, decides they need an
application that lives in the datacentre, and asks for it. Something then has to
deploy the app if it is not running, open the firewall, and be able to close it
again later — and be able to say, afterwards, who asked and who approved.

### The shape of it

```
  branch desktop  ──► access portal ──► AppAccess (XR)
   (Firefox, VNC)      10.112.240.33          │
                                              │ Crossplane composes
                                    ┌─────────┴─────────┐
                                    ▼                   ▼
                              FabricApp           FirewallAccess
                        (namespace, VIP, BGP        (a plain CRD)
                         advertisement, CNP)              │
                                                          ▼
                                                   fw-controller
                                                    ──SSH──► vSRX
                                                             policy 1000+
```

One object is the request, the approval, the deployment and the firewall rule.
`kubectl delete appaccess access-kanboard` removes the application *and* the
policy, because the policy is a composed resource and Crossplane owns its
lifecycle. That is the whole reason for putting this on the platform API instead
of behind a form with a database: the answer to "who can reach what" is a
`kubectl get`, and revocation cannot half-happen.

### The approval gate is one field

`spec.approved` starts false and the composition emits **nothing** while it is —
no deployment, no VIP, no rule. An unapproved request is inert rather than
merely hidden, which matters: a portal that stages resources and hides them in
the UI is one bug away from granting access it never showed anyone. Approving is
a patch on that one field, so it works from the portal, from `kubectl`, and from
anything else that can talk to the API, and it lands in the audit log either
way.

Catalog entries choose their own posture. `demo-frontend` is marked
auto-approved and skips the gate; `grafana` and `kanboard` require a human. Both
paths still create the same object, so both are equally visible.

### The branch baseline had to get *smaller*

This is the change to be aware of if you knew the lab before. The branch zone
used to carry a blanket permit — `branch-users` to the whole `10.112.0.0/16`
service range on HTTP and HTTPS — which meant a branch user could already reach
every published application. With that rule in place, self-service access is
theatre: the user clicks Request, waits, and reaches an app they could have
reached all along.

So the branch baseline is now exactly two rules: reach the access portal, and
ping. Everything else a branch user can reach was granted, and appears on the
box as a policy in the 1000+ range with the requester's name in its comment.

The WAN zone deliberately kept its blanket permit. Having one zone with standing
access and one with requested access on the same firewall is the clearest way to
show the difference, and `make verify` asserts both — including the negative,
that Grafana is *not* reachable from the branch until somebody asks.

### Why a controller and not a Crossplane provider

There is no Crossplane provider worth depending on for either firewall this lab
can run, so something had to bridge the gap. `k8s/access/fw-controller` is that
something: it reconciles `FirewallAccess` objects onto the box and writes back
what it did.

It checks the prompt before it writes anything, and refuses to push Junos
configuration at something that is not Junos. That is cheap insurance rather
than ceremony: every command it sends is Junos syntax, and against a different
CLI they would fail one by one with parse errors that read like a bug in the
grant rather than the wrong box being on the other end of the socket.
`status.policyRef` reports where the grant landed —
`branch->k8s-prod/aa-access-grafana` — which is enough to find it by hand.

It polls rather than watches, on purpose. A watch reacts faster and would never
notice that somebody deleted a generated policy in the Junos CLI. A poll
re-asserts the entire desired state every twenty seconds, which gives the
firewall the same drift correction Crossplane gives the Cilium config — the
story `make xp-drift` tells for one, you can tell for the other by deleting a
policy on the box and watching it come back.

It also sweeps orphans: anything in the 1000-1999 range named `aa-*` with no
matching `FirewallAccess` is deleted. That is the case where a firewall quietly
accumulates access nobody can account for, and it is worth handling explicitly
rather than trusting the delete path never to be interrupted.

### The desktop is a container, and Guacamole is split in two

`branch-desktop` runs XFCE on Xvnc in a container rather than as a QEMU VM. What
the demo needs is a real X session with a real browser at a branch LAN address,
and this gives that for ~1.5 GB and a thirty-second start instead of a disk
image, a vrnetlab wrapper and a two-minute boot. Nothing in the access path can
tell the difference — the firewall sees packets from `10.70.0.20` either way.

Guacamole is two nodes because it is genuinely two things. `guacd` is the half
that speaks VNC, so it sits on the branch LAN at `10.70.0.31` and its session to
the desktop crosses the site network like any other branch traffic. The web
front end has no branch LAN interface at all — it talks to `guacd` and to the
browser and to nothing else — so it lives on the management network with its
port published on the lab host. Giving it a seat on the site LAN would be
inventing an exposure the demo does not need.

Both use file-based authentication (`configs/branch/guacamole/user-mapping.xml`)
rather than the database the official image usually implies. Pointing
`GUACAMOLE_HOME` at a directory containing that file satisfies the image's
insistence on an auth backend with no database, no init SQL and no third
container. `GUACD_HOSTNAME` still has to be in the environment even though
`guacamole.properties` names guacd — the entrypoint checks the variable before
it ever reads the file.

### What this does not do

The access broker needs a firewall with a management plane, which is most of
why the lab settled on one real firewall rather than keeping a container
alternative alongside it. There is no mode in which the portal runs and the
firewall half does not.

There is also no identity here. The portal takes a name in a text box and
believes it. Wiring it to OIDC would be the obvious next step and would change
nothing about the shape above — the requester field is already carried through
to the firewall policy's comment.

## Pod egress, and the one NAT rule in the lab

Masquerading is off so the fabric sees real pod addresses, which is the whole
basis of the ACL and firewall demo. That is right for east-west traffic and
fatal for anything that has to reach the internet from *inside* a pod — and
Crossplane does exactly that, resolving package names and pulling OCI artefacts
and Helm charts from provider pods.

It also hides for a long time, because image pulls work: containerd runs in the
k3s container's own netns, not a pod's. The failure only appears when an
in-cluster controller needs something off-cluster.

The fix is one `iptables` MASQUERADE rule per node, installed by
`k8s/bootstrap/k3s-entrypoint.sh`:

```
-s 10.111.0.0/16 ! -d 10.0.0.0/8 -o eth0 -j MASQUERADE
```

The exclusion is what preserves both properties. Anything destined for
`10.0.0.0/8` — the fabric, the other tenant, pods, services, nodes — is never
touched, so pod IPs still appear on the wire exactly as before. Only traffic
genuinely leaving for the internet, via the management interface, is SNATed to
the node's management address.

The alternative was to let Cilium masquerade, which would mean adding `eth0` to
`devices` and widening `ipv4NativeRoutingCIDR` to `10.0.0.0/8` to keep fabric
traffic un-SNATed. Both change the part of the datapath the lab is actually
demonstrating, in exchange for a performance property that does not matter at
this scale. This way Cilium masquerades nothing at all and the only NAT in the
cluster is one explicit rule on the management path — which is also the shape a
real cluster has: a management egress path separate from the data fabric.

## What the observability stack is for

`kube-prometheus-stack` is the lab's "real application": an upstream chart of
real substance — Prometheus, Alertmanager, Grafana, kube-state-metrics,
node-exporter, an operator and a dozen CRDs — installed by Crossplane with no
manifests written here beyond the two policies it needs to see the cluster.

It was chosen over a smaller app for two reasons. First, it is a genuine test of
`provider-helm`: it has CRDs, an admission webhook with a pre-install cert job,
and its own RBAC, so if a chart of this shape installs cleanly the abstraction is
carrying real weight. Second, it closes the loop. Grafana sits on a
BGP-advertised VIP reachable from the *other* tenant, across the firewall and
over EVPN, and its Prometheus scrapes Cilium and Hubble — so what it shows you
is the state of the datapath that carried you to it.

Prometheus scrapes Cilium via plain `additionalScrapeConfigs` rather than
`ServiceMonitor`s, deliberately. ServiceMonitors are defined by *this* chart's
CRDs, so enabling `serviceMonitor` in the Cilium chart would make the CNI's
install depend on a CRD that only exists after this application is deployed.
Cilium has to come up first — it is the CNI. A scrape config has no such
ordering problem.

## One topology file, environment-driven profiles

The full fabric needs ~20 GB, which does not fit on a host already running
something substantial. The obvious answer — a second, trimmed topology file —
was rejected: two copies of a 200-line topology drift apart, and the trimmed one
is always the stale one.

Instead every tunable is `${OTTERNET_*:=default}` and the profiles are Makefile
targets that set them. `deploy-lite` additionally uses containerlab's
`--node-filter` to drop the app pod, which also drops the links to it
automatically.

The one sharp edge: `sudo -E` is refused on this host, so the Makefile names
each variable via `--preserve-env=`. With plain `sudo -E`, containerlab would
silently deploy the default profile.

## Offline config generation as the primary workflow

`make avd-build` renders every device config with no lab running, no ceOS image
and no switches. It takes a couple of seconds.

This matters more than it sounds. It means a data-model change can be reviewed
as a diff (`git diff avd/intended/`), it means CI can validate the fabric
without any licensed image, and it means the AVD half of the lab is verifiable
even on a host that cannot run the fabric at all.

## Known limitations

- **k8s nodes are single-homed.** Dual-homing them to the MLAG pair with a bond
  would be more realistic but complicates Cilium's BGP source address. The
  subnet is still MLAG-redundant via the anycast gateway.
- **No north-south / internet edge.** The border leaf hands off to the firewall
  for inter-tenant traffic only. Adding an untrust zone and a NAT policy is a
  natural extension; there is a spare `ge-0/0/2` on the cSRX.
- **MACsec is not configured** on spine-leaf links. AVD supports it, but cEOS
  does not implement it, so it would render config that never comes up.
- **ANTA validation is wired but unexercised** — `make avd-validate` needs a
  running fabric, which needs the ceOS image.
- **The fabric itself is not managed by Crossplane.** AVD renders and pushes the
  switch config; Crossplane stops at the cluster boundary. Driving EOS from a
  Crossplane provider would make the *entire* path one control plane and is the
  natural next step, but it is a different piece of work from this one.
- **Crossplane runs in the cluster it manages.** Fine for a lab, and the reason
  `InjectedIdentity` is enough. A real platform would run it out-of-cluster, or
  at least not give both providers `cluster-admin` — see the note in
  `crossplane/providers/02-rbac.yaml` for what a narrower grant would involve.
- **Grafana's admin password is in the repository.** It is
  `otternet-lab-not-a-secret`, in `crossplane/apps/20-observability.yaml`,
  alongside the BGP session password in the AVD vars. Everything in this lab is
  reachable only from this host.
