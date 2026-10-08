---
title: Generator, transform and check inventory
description: Every registered generator, transform and check, with the traps behind each, covering allocation, grants, WAN rendering, the firewall artifact and the consistency checks.
audience: developer
sidebar_position: 30
---

# Generator, transform and check inventory

The service layer offers seven kinds, each described where its generator or renderer is.
`ServiceNetworkSegment` is the newest: a segment is the three technical objects that always
appear together and are always consistent — an `IpamPrefix`, an `IpamVLAN`, and an `EvpnSvi`
giving it a gateway in a VRF. **It allocates rather than selects**, which is what separates it
from the WAN kinds: leaving `vlan_id` or the subnet empty is the normal case, and
`generate-network-segment` takes the next free one from `OTTERNET-Segment-VLAN-Pool` and
`OTTERNET-Segment-Subnet-Pool`.

The portal's generated `ServiceNetworkSegment` template is the request path. It creates a single
segment on a branch and opens a proposed change; the generator builds the three technical objects.
An earlier form wrote `IpamVLAN`, `IpamVRF` and `EvpnSvi` itself — no requester, no status, nothing
to withdraw, and **no `avd_tags`, so every SVI it created rendered on no switch**, which is why
`avd_tags` is mandatory on the kind.

**Resource pools are branch-agnostic and their resources are not**, which is worth knowing before
testing one on a branch. `CoreIPPrefixPool` and `CoreNumberPool` carry `branch: agnostic`, so a pool
created on a branch is live on `main` the moment it exists and deleting that branch does not remove
it. The `IpamPrefix` it draws from is branch-aware and *does* go with the branch — leaving a pool
that exists globally, has empty `resources`, and can never allocate. Two further traps sit behind it:

- A pool needs `default_prefix_type: IpamPrefix`. Omitting it costs nothing at load time and fails at
  allocation with `A prefix_type or a default_value type must be provided`, naming the pool but not
  the file that declares it.
- The caller passes the role: `allocate_next_ip_prefix(..., data={"role": "tenant_host"})`, because
  `IpamPrefix.role` is mandatory here and depends on what the prefix is for rather than on the pool.

What is **not** a trap, having been measured: an allocation made on a branch is branch-aware and
invisible on `main`, so a proposed change that is opened and then rejected does not burn a subnet.

Current generator definitions are registered in `.infrahub.yml`:
`generate-fabric`, `generate-pod`, `generate-rack`, `generate-server-cabling`,
`generate-avd-device-hostvar`, `generate-avd-device-structured-config`,
`generate-fabric-peering`, `generate-app-access`, `generate-network-segment`,
`generate-fabric-app`, `generate-tenant-onboarding`, `generate-server-placement`,
`generate-monitoring-collector`, and `generate-dns-record`.

`generate-dns-record` puts `<name>.<zone>` on an exposed, live application's VIP address and asks for the
`DNS Zone Configuration` artifact to be rendered again for the resolver. It runs on four trigger rules, in the proposed-change pipeline and after a merge.
It creates an address only when none exists, and deletes only an address whose description starts with `DNS name for`. Read
[the DNS service](./dns-service.md) before changing it.

No `backfill-structured-config` exists any more. It read each switch's structured
config back into `Routing*`, `IpamPrefix` and interface MTU objects that nothing
consumed, and after the device-kind split it failed on every run — four of the
`Routing*` kinds peer `DcimDevice` — leaving a red task in every proposed change that
rebuilt the fabric. **Retiring a generator needs its trigger rules and action deleted
first**: `CoreGeneratorAction.generator` is mandatory, and the repository import
deletes queries *before* generator definitions, so a definition still held by an
action wedges the import at `error-import`.

**An application is a Helm chart, and nothing else.** Cycle 033 made `chart_repository`,
`chart_name` and `chart_version` mandatory together — which is what the Crossplane XRD already
required — and withdrew the `manifests` attribute, the `manifests_file` relationship and the
`ServiceFabricAppManifestsFile` kind. Five things are worth knowing before touching this:

- **`crossplane_fabric_app` forces `externalTrafficPolicy: Local` on every exposed application.**
  Charts default to `Cluster`, which SNATs a request to a node address whenever it lands on a node
  whose backend is elsewhere. The pod policy then admits it as `remote-node`, not on its source
  prefix, so `allowed_source_prefixes` (the third gate) decides nothing. Measured on
  `otternet-demo`: 4 of 6 requests from host-a reached whoami as `10.110.0.x`. The Service's
  values path is known per chart (`_LB_SERVICE_VALUES_PATH`). For any other chart rendering
  **refuses** unless the values already say `Local`, because a guessed key is one the chart
  ignores. Measured on a copy of the whoami chart: with `Local`, 10/10 from host-a and both WAN
  customers kept their own address, and the VIP's `/32` moved to whichever nodes ran a pod. The
  one gap was a single refused connection while a new pod was still starting.
- **A chart's Kubernetes Services are invisible to Infrahub**, because they exist only once Helm
  has run. `generate-app-access` used to derive a grant's ports by reading the manifests for
  LoadBalancer Services; an exposed application now names them through `advertised_services`, a
  relationship to `SecurityService`. That is the same kind `SecurityPolicyRule.destination_services`
  peers, so the application's advertised port and the rule's permitted port are **one object**
  rather than two numbers that have to agree. Naming a service never writes to it, so it is never
  marked `managed_by_service` and revoking a grant never deletes the firewall's own `junos-http`.
- **Making an attribute mandatory is refused against existing data**, with
  `Attribute-level 'optional' constraint violation on schema 'X'. Node (y) is not compliant.` once
  per attribute per object — naming the node and never the field, so a partial migration looks
  exactly like none. Objects must be migrated before the schema loads, which inverts `invoke load`.
  `scripts/migrate_fabric_app_charts.py` is the worked example, and it enumerates from the **graph**
  rather than from `objects/` because portal-created objects appear in no seed file.
- **`infrahubctl protocols` ignores `state: absent`.** It reads the YAML rather than the loaded
  schema, so a block left marked absent keeps generating a protocol class or field for something
  the graph no longer has — and mypy stays clean, because the types are internally consistent.
  `state: absent` is a migration step: mark, load, then delete the block and regenerate.
- **Withdrawing a node kind does not delete its instances.** The loader removes the kind whether or
  not any exist, and afterwards the kind does not resolve, so anything still attached is
  unreachable rather than deleted and no query can find it. Delete the instances first.

`generate-fabric-app` gives an exposed `ServiceFabricApp` a LoadBalancer VIP block from its
cluster's pool. It closes a harder edge than the other allocating generator, because an exposed
application with no block does not degrade — `crossplane_fabric_app.py` **raises**
`is exposed but has no vip_block; the XRD requires expose.vipBlock`. Two things to know:

- **`vip_block_managed` is what makes withdrawal safe.** `vip_block` holds either a block a
  human declared in `objects/` — `10.112.240.0/28` for `otternet-demo` — or one this generator took
  from the pool, and only the second is ever safe to delete. The flag records which, is set only
  on the allocating path, and is the only thing withdrawal consults; it plays exactly the role
  `managed_by_service` plays on `SecurityPolicyRule`. It is written in the **same save** as the
  block, because two saves leave a window in which the block exists and nothing records who owns
  it. A block that already exists is kept whoever created it, which is how the seeded
  application's manifest stays byte-identical.
- **The pool is resolved through the CLUSTER**, not by name and not by role. A cluster's
  `vip_pools` are the only supernets the leaves' inbound route policy permits
  (`10.112.240.0/24 le 32`), so a block from anywhere else is advertised by the cluster and
  refused by the fabric.

**`generate-fabric-app` also pins an application from its catalogue entry**
(`ServiceApplicationDefinition`, see [schemas](./schemas.md#the-application-catalogue)). On the
build path, and never for a withdrawn status, `_pin_definition` runs first. It reads the entry
through the SDK rather than the generator's query, because a new query model needs
`schema.graphql`, which only a live Infrahub can re-export; `generate_fabric_app.gql` and its model
did not change. Four traps:

- **The file is written before the marker.** The values file is created from `default_values`, then
  the chart fields and `definition_pinned` are saved together. The marker is the commit point, so a
  failure in between is retried rather than recorded as done.
- **It never writes `vip_block_size`.** That field is a watched input of the application's event
  rules; a write-back to it would feed the run into the next. The portal sends the entry's default
  in the create, and the generator fills only `service_selector` and `advertised_services`, both
  unwatched, and only when the request left them empty.
- **`definition` and `definition_pinned` are not watched.** Re-pointing an application is an upgrade
  and its own reviewed change; watching `definition` would rebuild on every edit. See
  [service triggers](./service-triggers.md).
- **A catalogue edit never reaches a running application.** The artifact reads the application's own
  fields, and `crossplane_fabric_app.gql` selects nothing from the entry, which a test asserts.

`crossplane_fabric_app.build_chart` also **raises** for a chart name without a repository and a
version, naming the application. The schema keeps all three mandatory together, but a catalogue
request is pinned in two steps, so a half-pinned application is refused where it can be read.

`generate-network-segment` and `generate-fabric-app` are the two generators that **allocate
rather than select**: every other one here derives from objects that already exist, while these
take the next free resource from a pool. Two things to know before changing the segment one:

- **`ServiceNetworkSegment.avd_tags` is what decides whether the segment renders at all.** AVD
  puts an SVI on a device only where `svis[].tags` intersects that device's node-group
  `filter.tags`, and in this fabric those filters are the racks' own `AvdTag`s — `k8s`, `app`,
  `cloud`, `border`. `EvpnSvi.rack_tags` exists, looks like the scoping relationship, and
  contributes the rack's *name*, `K8S_LEAFS`, which matches no filter. Measured: an untagged SVI
  rendered on zero switches; tagged `k8s` the same SVI rendered on exactly the two K8S leaves.
  Nothing errors on that path, so the relationship is mandatory and the generator checks it again.
- **Its pools are resolved by role rather than by name** — the prefix pool whose resources carry
  `tenant_host`, and the number pool allocating `IpamVLAN.vlan_id` — and both demand exactly one
  candidate. A hard-coded `OTTERNET-Segment-Subnet-Pool` would fail naming a string that appears in
  no schema.

**`status` withdraws, and `decommissioning` counts as gone rather than going.** For every kind in
the table below, `decommissioning`/`decommissioned` means the same thing: downstream treats the
service as **absent**.

`ServiceAppAccess` joins that list rather than being the exception it was. It used to be gated on
an `approved` Boolean, so withdrawal meant unapproving and setting `decommissioning` did nothing
visible. The field is gone — see the generator — and the grant now withdraws on status like
everything else.

| Kind | What withdraws it |
| --- | --- |
| `ServiceNetworkSegment` | its generator deletes the subnet, VLAN and SVI, releasing both pools |
| `ServiceTenantOnboarding` | its generator deletes the EVPN tenant, *refusing* while VRFs hang off it |
| `ServiceServerPlacement` | its generator deletes the machine and its cabling |
| `ServiceFabricApp` | its generator returns the VIP block, if it allocated it |
| `ServiceFabricPeering` | its generator deletes the sessions **the service recorded** |
| `ServiceL3vpn`, `ServiceTenantCloud`, `ServiceInternetAccess` | `srl_config` renders them as though absent |

`decommissioning` withdraws rather than waiting, because the alternative is a window in which
the intent is withdrawn and the router still carries the route — which is the window the state
exists to close.

**The WAN half was safe to change precisely because it is pinned.** `srl_config` is held
byte-for-byte against `lab/wan/rendered/*/config.cli`, and filtering a status nothing currently
carries is a no-op — so the existing assertions proved the change altered nothing, and a new test
holds a decommissioned service's output against the *removal* of that service rather than merely
asserting it changed.

**What still does not withdraw is the Crossplane delivery path**, and that is deliberate.
`crossplane_fabric_peering` and `crossplane_fabric_app` render one artifact per service; an
artifact that rendered empty would be a manifest Vidra has to interpret, and
[vidra-delivery](./vidra-delivery.md) records that the operator only
deletes a resource when the manifest it delivered goes away. Withdrawing a delivered resource is
therefore done by deleting the service, not by labelling it.

`generate-app-access` sits underneath `ServiceAppAccess` and turns a grant into
the firewall objects permitting the session: an address-book entry for the destination VIP, a
`SecurityService` per permitted port, and the `SecurityPolicyRule` joining them, linked back
through `granted_rules`. Generated objects render into the existing Junos artifact, because
`junos_config.gql` queries `SecurityGenericAddress` and `SecurityPolicy` unfiltered. Nine things
to know before changing it:

- **A grant's ports come from `ServiceFabricApp.advertised_services`, and two earlier sources were
  both wrong in the same direction.** `policy_allow_ports` is the CiliumNetworkPolicy's ingress
  port, applied to the **pods**, while a firewall rule's destination is the **VIP** — for an
  application whose Service maps `port: 80` to `targetPort: 8080` those are 80 and 8080, so the
  rule permitted a port the VIP never answered on. Reading the raw manifests' LoadBalancer Services
  fixed that and then stopped existing: cycle 033 made a chart the whole workload source, and a
  chart's Services are created by Helm inside the cluster, which Infrahub cannot do.
  **Nothing reported a fault in either case** — the rule rendered, the proposed change merged, the
  reconciler pushed it and confirmed `fw1` in sync, and the only symptom was a healthy application
  nobody could reach. The relationship names the `SecurityService` objects the firewall already
  declares, so one object carries the port and the protocol and the rule references the very object
  the application named, which is what stops the VIP's port and the rule's drifting apart. Two
  consequences worth keeping: a non-TCP advertised service is skipped, because widening a TCP rule
  to UDP is a different permission; and the derivation **refuses rather than guessing** when an
  application advertises nothing, because every earlier fallback was always populated and always
  plausible, which is precisely why a wrong port was never once reported as wrong.
- **IT OPENS ALL THREE GATES, and the third was the one nobody could see.** A session needs the
  route to exist, the firewall to permit it, and the APPLICATION's own CiliumNetworkPolicy to name
  the source — `policy_default_deny` is true on every application here, so an unnamed source is
  dropped at the pod. The generator opened the first two. The third was left to whoever created the
  application, and **the portal cannot ask for it**: `allowed_source_prefixes` is an optional
  cardinality-many relationship and the form builder admits cardinality-one plus *mandatory* many
  only. An application requested through the portal deployed cleanly, took a VIP, passed the
  firewall and dropped every packet — measured, with `allowFrom: []`, the rule on the device and the
  leaf holding the VIP's `/32`. **Nothing logged a denial, because the drop is not on `fw1`.**
  The grant now adds its source to the application, which needs no parsing and creates nothing: a
  `SecurityIPAMIPPrefix` address already points at the very `IpamPrefix` that
  `allowed_source_prefixes` peers, so both gates name one object. A source of another kind opens the
  two gates it can and says so.
- **`granted_source_prefixes` is what makes revoking it safe**, and it is not decoration.
  `allowed_source_prefixes` is a SHARED list — `otternet-demo` declares three by hand and two grants may
  name one source — so withdrawal removes only what this grant recorded, minus what a **live sibling
  grant on the same application** still records. Both halves are load bearing: the first keeps a
  human's entry out of reach, the second stops one revocation closing a gate another grant relies on,
  which would fail in the worst direction — firewall still permitting, pod still dropping. It plays
  exactly the role `managed_by_service` plays for rules and `vip_block_managed` for VIP blocks.
  Withdrawal runs **outside** the `if removed:` branch, because a grant whose rule an earlier run
  already cleaned up still has its source named.
- **It asks for the firewall's artifact to be re-rendered, and must.** An artifact regenerates
  when its *target* changes, and the target is `fw1` — a new `SecurityPolicyRule` is not a
  change to the firewall. Without the explicit request the objects appear, the artifact keeps
  its old checksum, and the reconciler compares the device against stale output and reports no
  difference. Infrahub's trigger rules cannot close this: `CoreGeneratorAction` and
  `CoreGroupAction` are the only actions and neither renders an artifact.
- **A generated service object needs `junos_config` to declare it.** Every service in the
  hand-written baseline is a Junos built-in (`junos-http`, `junos-https`, `junos-ping`), so for
  three cycles the renderer referenced applications and declared none. A policy naming an
  undeclared application is refused with `commit failed: (statements constraint check failed)`,
  which names no object and points at no line. `_applications` now emits the stanza for any
  service without the `junos-` prefix, and renders nothing when they are all built-ins — which
  is what keeps the artifact byte-identical to the device file.
- **THE BRANCH IS THE GATE, and there is no `approved` field.** The kind carried `approved`,
  `approved_by` and `approved_at`, and composed nothing while the first was false. That was a
  second gate in front of one the workflow already has: a request is made on a branch and reaches
  no device until its proposed change merges. Two gates can only disagree — approved but unmerged
  changed nothing, and merged but unapproved left an object on `main` doing nothing and saying
  nothing about why. Merging is the approval, and it is the better record: a reviewer, a diff and
  a history, where the Boolean had one person's patch.
- **Nothing is seeded, and `test_no_grant_is_seeded` keeps it that way.** While the gate existed a
  seeded grant was inert; without it one would materialise a rule, a service object and an
  address-book entry into the default data set permanently, and the rendered Junos artifact is
  held byte-for-byte against a device file that has no such rule. A real request through the
  portal takes about thirty seconds, which is the workflow worth demonstrating anyway.
- **Two allocation floors, and both are load bearing.** Rule `index` starts at 100 because
  Junos is first-match within a zone pair and the baseline puts `deny-spoofed-infra` at index
  10 — a generated permit below it would turn every grant into a bypass for a spoofed
  `fabric-infra` source. Address `book_index` starts at 1000 because hand-written entries
  occupy 10–130 and their order is pinned; an entry with **no** `book_index` is skipped by
  `junos_config.py::_addresses` entirely, so it would be referenced by a rule and never
  declared, and the configuration would not load.
- **The destination zone comes from the VRF, not from interface containment.**
  `ServiceFabricApp.vrf` and `SecurityZone.vrf` both peer `IpamVRF`. Deriving it from "the
  firewall interface whose subnet contains the VIP" cannot work — the handoff interfaces are
  `/30` point-to-points and contain no service VIP, so containment matches nothing.
- **Adoption fetches and modifies; it never upserts.** The firewall already declares
  `junos-http` and `junos-https`, so a grant for 443 references the existing object rather than
  declaring a second application for the same port. An adopted object is never marked
  `managed_by_service` and so is never deleted by the tracking context when the grant is
  revoked — which is what keeps `junos-https` alive for the baseline rules that share it.

Current Python transforms are: `computed_interface_description`, `cabling_plan`,
`avd_eos_config`, `avd_fabric_doc`, `avd_device_doc`, `avd_anta_catalog`,
`containerlab_topology`, `cv_workspace_submission_webhook_payload`, `crossplane_fabric_peering`,
`crossplane_fabric_app`, `srl_config`, `junos_config`, `telemetry_collector_config`, and `dns_zone_config`.

`dns_zone_config` renders the Corefile and the zone file of the lab resolver as one ConfigMap (`DNS Zone Configuration`, target group
`dns_resolvers`). It raises on an empty zone, on two addresses for one name, and on a resolver with no name of its own. See
[the DNS service](./dns-service.md).

`srl_config` renders the WAN's SR Linux configuration — the two ISP provider-edge routers, the
internet router, the two customer edges and the branch router — as one `text/plain` artifact per
device (`SR Linux Configuration`), targeting the `srl_routers` group. It is the half of the lab
PyAVD does not cover, and it is held byte-for-byte against `lab/wan/rendered/*/config.cli` by
`tests/unit/test_srl_config.py` — files that were BOOTED on a six-router prototype and passed
the WAN reachability matrix. It replaced `frr_config`. Things to know before changing it:

- It reads the **service** layer as well as the technical one. A provider edge's per-tenant
  import route-map is assembled from `ServiceL3vpn.dc_service_prefixes`,
  `ServiceTenantCloud.prefix` and whether a `ServiceInternetAccess` exists. That is the
  documented exception to "renderers read technical objects" — the provider edge's policy *is*
  the service intent.
- **No tenant is named in it, and for a while two were — which made every other tenant a
  silent no-op.** `TENANT_ORDER = ("acme", "globex")` was both the render order and the render
  *set*, so an L3VPN the portal created for any third tenant was skipped: the request merged
  green and no router changed. Measured on a scratch branch with a third tenant fully modelled
  (cloud, static site, CE, provider-edge port): `isp-pe1` rendered byte-identical to `main` except
  for that port, rendered *shut* because it matched no tenant the renderer looked at. Tenants are
  now every tenant with a live L3VPN, ordered by name (which reproduces acme-before-globex
  without stating it), and the same branch rendered `CUST_INITECH`, its port, its static route
  and its `RM-INITECH-IMPORT` policy, with acme and globex untouched — additions only, held by
  `test_adding_a_tenant_only_adds_lines`. Everything else was already derived: the VRF from
  `ServiceL3vpn.vrf`, the policy names from the tenant's name, ports from attachment addresses.
  SR Linux leaks between instances by policy, not by route target or RD, so there is none to
  allocate. The branch router's site is found by its router, not by a tenant called `branch`.
- **What a tenant still needs before it can render is `wan-service-consistency`'s business**, so
  a request that cannot reach a router fails its proposed change naming the gap rather than
  merging as a no-op. The renderer refuses the same things (two live L3VPNs, no tenant cloud, a
  BGP site with no CE session — it used to render `neighbor None` — a name SR Linux cannot carry),
  and a refusal fails the artifact for every tenant on that router, so the check is the gate that
  matters.
- **The shared DC range comes from every live L3VPN that states one**, not from the first the
  query returns. The portal's L3VPN form cannot offer `dc_service_prefixes` (optional
  cardinality-many), so a portal-created L3VPN states none and takes the shared range; had it
  come first, the old code would have emptied `PL-DC-SERVICES` for every tenant. Two live L3VPNs
  stating different ranges are refused rather than merged, because the range is in every
  tenant's import policy.
- Its templates are copies of `lab/wan/templates/*.srl.j2` with exactly one line changed, the
  provenance header, and `test_the_templates_are_the_labs_with_one_line_changed` holds every
  line. Every comment is deliberate; they are most of the teaching value of those configs.
- **The output is the router's WHOLE configuration, and every use of it is a full replace.**
  Flat `set` commands opening with `delete /`: the ContainerLab startup configuration (so a
  booted router already matches), what the reconciler loads to compare, and what it commits —
  EOS's `rollback clean-config`, in SR Linux terms. `/system` is in it too: management
  interface and VRF, gNMI/SSH/NETCONF/JSON-RPC servers, AAA, logging, LLDP, and the image's
  control-plane ACL (`_cpm_acl.srl.j2`, 537 lines captured verbatim from 26.7.2 — re-capture it
  when the image moves, or a push strips the control plane of its own protection).
- **Nothing secret is rendered, and two things ContainerLab writes CANNOT be.** The admin
  password is the `$6$` hash of `NetworkLocalUser` `admin` — the fabric's — which SR Linux takes
  verbatim (measured: the lab password then logs in, the image default is refused). The TLS
  profile's private key and the SNMP community are `$aes1$`-encrypted with a per-device key, so
  gNMI uses `default-tls-profile` (a self-generated certificate, survives a full replace) and
  JSON-RPC is HTTP only — its HTTPS listener has no such option. The deploying host's SSH keys
  and the EDA servers are dropped too; a first push after a plain ContainerLab boot removes
  them, which is why the artifact opens with `delete /` and boots in sync instead.
- **No quote characters in a comment, ever.** sr_cli tokenises quotes before it recognises `#`,
  so one apostrophe swallows every line up to the next quote and those lines are never applied
  — measured: a router booted with no management interface, no addresses and half its policy,
  and nothing errored. `assert_comments_unquoted` refuses such a render, and `render.py` too.
- **Route leaking needs BOTH halves, and each half alone fails silently.** An inter-instance
  import policy leaks nothing unless the SOURCE instance marks routes leakable with an
  inter-instance export policy (`LEAKABLE`) — measured: every session up, every tenant VRF
  empty. And a leaked route reaches the route table, not BGP, so nothing advertises it until
  `bgp rib-management table ipv4-unicast route-table-import` takes it in — measured: the core
  learned a loopback and nothing else. Once `rib-management` is configured it is the ONLY way a
  non-BGP route enters BGP, so the loopback and the static sites are named there too: the
  `BGP-TABLE-*` policies are exactly FRR's `network`, `redistribute static` and `import vrf`.
- **It renders interfaces, which `frr_config` never did** — a boot script used to own them. A
  provider-edge port's VRF is derived (the port whose subnet holds a site's attachment
  address), and a `cust` port whose tenant is withdrawn is rendered SHUT, never left to fall
  into the default instance with the tenant's subnet in the provider table.
- **The routers' interfaces carry native names** (`ethernet-1/N`, `lo0`, `irb0`), the precedent
  the fabric set with `Ethernet1` against ContainerLab's `eth1`. A graph loaded before the
  re-platform holds `eth*`/`lo`, and an object load cannot rename — the HFID is `[device, name]`,
  so it would create a second interface beside each old one, which `srl_config` would render
  under a name SR Linux rejects. `scripts/migrate_wan_srlinux.py` renames in place first (and
  renames the `frr_routers` group, keeping its members); `--phase post` then removes the FRR
  platform, device type, manufacturer and artifacts once nothing references them. One thing it
  measured: **on a branch, a `name__value` filter also matched a node's PRE-rename value** —
  `frr_routers` returned the renamed group — so the script re-checks every name it filters on.

`junos_config` renders the perimeter firewall's Junos configuration as one `text/plain` artifact
targeting the `junos_firewalls` group. Four things to know:

- **It is the firewall's WHOLE configuration, because the push is `load override`** (cycle 035).
  Anything the artifact omits is deleted from the device, so it renders every line of
  `junos.conf` except the 72 lines of top-level commentary — 68 comments and 4 blanks of lab
  documentation about the file, replaced by the artifact's own provenance line because
  reproducing it would make a false claim about where the file came from — **plus what
  vrnetlab's `init.conf` injects at boot**: `fxp0`, `host-name`, `services { ssh; netconf; }`,
  `management-instance` and the `mgmt_junos` routing instance. `init.conf` is generated inside
  the container and committed nowhere, so `tests/unit/fixtures/junos/vsrx_booted.conf` — the
  running configuration of a vSRX booted exactly like `fw1` — is the committed record of it, and
  `test_the_artifact_states_everything_a_booted_vsrx_runs` holds the artifact against it
  statement by statement. `test_the_exclusions_add_up` keeps the arithmetic.
- **The firewall's two login hashes are in the artifact, deliberately — a user-approved
  exception.** A full replace without `system` leaves the device with no logins and no SSH, so
  the artifact must carry `root-authentication` and the `admin` login. They are the **lab's
  existing hashes** (SHA-512 of the password vrnetlab and containerlab already use, copied from
  `junos.conf`), and they are **template content in `templates/junos/system.j2`, never data**: in
  the model they would reach every branch, every export and the MCP server's read access, while
  in the template they are where they already were — in git. Never cleartext:
  `test_the_only_credentials_are_the_labs_existing_hashes` pins exactly those two values and
  refuses `plain-text-password-value`, which is what `init.conf` writes and Junos keeps
  verbatim — the first full replace removes it. `host-name` comes from the model; `services` and
  `management-instance` are the delivery path, fixed in the template, because every other value
  makes the firewall unreachable. Nothing runs syslog, NTP or a name server, so none is rendered.

  Everything else matches the device byte for byte, **with one exception the model cannot close**:
  the *sequence* of the eleven zone-pair blocks. A zone pair is derived from each rule's source and
  destination zone, so no pair object exists to carry an order, and `SecurityPolicyRule.index`
  orders rules *within* a pair — it holds only 10, 20 and 30 across all nineteen. Junos matches a
  packet to its pair by zone, not by position, so the sequence is presentation. Every pair is
  present and each is byte-for-byte identical.

  The eight static routes are held against three sources by
  `tests/unit/test_fw_static_route_objects.py`, and the third is the interesting one: every next
  hop must lie on a subnet `fw1` has an interface on. A comparison against `junos.conf` cannot
  catch a typo *in* `junos.conf`, so the interface addresses are an independent witness.
  `test_the_exclusions_add_up` makes the total an assertion rather than a caveat, so it is the
  thing to update when those twelve lines move in scope.
- **Order is checked where it is behaviour and relaxed where it is not.** Junos evaluates
  first-match within a zone pair, so rule order is semantic and pinned; the sequence *between*
  pairs is presentational and asserted as a set. The address book's order *is* pinned, through
  `book_index` — added locally because Junos writes it in authoring order and nothing derives it.
- **Two attributes are local additions** in `schemas/security_extensions.yml`: `book_index` on
  `SecurityGenericAddress` and `log_session_close` on `SecurityPolicyRule`. Upstream models `log`
  as a Boolean; the device distinguishes `session-init` from `session-init` plus `session-close`.
- **Node-level fields upstream leaves unset are supplied by re-declaring the node** in the same
  file's `nodes:` block, never by editing `schemas/security/security.yml`: the
  `human_friendly_id`, `display_label` and description of `SecurityPolicyRule`. The server merges
  the re-declaration onto the adopted node and keeps upstream's label, icon, menu placement and
  `order_by` — read back from the live schema, not assumed. An `extensions:` entry cannot do this;
  it adds attributes and relationships only. Two costs keep it to that one node:
  `infrahubctl protocols` does **not** merge, so the re-declared node's protocol comes out empty;
  and a node that inherits must repeat its `inherit_from`, or the server refuses it with
  `Node-level 'inherit_from' constraint violation`. Both are why `SecurityFirewall` still has no
  kind description.

Check definitions are `fabric-pool-validation` (`checks/fabric_pool_check.py`);
`peering-consistency` (`checks/peering_consistency_check.py`); `zone-advertisement`
(`checks/zone_advertisement_check.py`); `wan-service-consistency`
(`checks/wan_service_check.py`); `allocation-consistency`
(`checks/allocation_consistency_check.py`); and `dns-zone-consistency`
(`checks/dns_zone_check.py`). The first is targeted on `fabrics`; the other five
are **global** — they have no `targets`, because their rules are statements about the whole
graph rather than about one fabric.

**`cv-config-validation` is deliberately not registered.** Its code is still here
(`checks/cv_config_check.py`, with `checks/cv_workspace_lifecycle.py` and `checks/cv_helpers.py`),
tested, and its query is still registered, but this lab has no CloudVision: `OTTERNET_FABRIC`
leaves `cloudvision_managed` false, so on every proposed change the check logged a skip and
passed — a green row that reads as "CloudVision validated this" when nothing was. The
**Deployment → CloudVision Workspaces** menu entry went with it, because that list could only
ever be empty. Re-enabling is two blocks, quoted in `.infrahub.yml` and `repository_checks.yml`.
Removing a check definition needs no pre-merge cleanup: the importer deletes it, and its
`CoreUserValidator`s cascade with it. `.infrahub.yml` cannot carry a check `description` — the
SDK's config model forbids extra keys, so one fails the import — which is why the comments there
do that job.

`wan-service-consistency` guards the lab's central claim. The WAN service kinds **name**
technical objects rather than creating them — which is why no generator sits beneath them, and
also why every one of their references was unverified. `schemas/service/wan_services.yml` says
the isolation is *structural*: no VRF imports another's route targets anywhere, so there is no
east-west path to filter in the first place. That is only true while the services are wired
correctly, and nothing checked that they were. Four rules:

- **A circuit belonging to another tenant.** `ServiceL3vpn.circuits` is not a label, it is the
  routing domain — two of a tenant's sites reach each other because both circuits are in the
  list. A foreign one joins two tenants directly across the provider edge, which is what cycle
  019's FR-005 warns about.
- **Two L3VPNs sharing a provider-edge VRF**, which is the same collapse by another route.
- **A tenant cloud whose zone governs a different VRF.** `generate-app-access` derives a grant's
  destination zone by matching the application's VRF against `SecurityZone.vrf`, so a mismatch
  silently writes grants into a policy for somewhere else.
- **Two clouds sharing a VRF or a zone** — the one that most looks like tidy reuse.

Two more ask whether a request **will render at all**, because a portal request for a third
tenant used to merge green and reach no router (see `srl_config` above):

- **A live L3VPN that cannot be put on a port.** No provider-edge VRF; no live tenant cloud; no
  `WanSite` for the tenant — which is what a portal request for a new tenant looks like, since
  the lab has no circuit, CE or provider-edge port for it; or a site that cannot attach: a BGP
  site without sessions on both an `isp_edge` and a `customer_edge`, a CE outside `srl_routers`
  (no artifact, so the session never comes up), no `site_asn`, a static site whose next hop no
  device owns, an attachment address no provider-edge port is on, a LAN outside the peering's
  `customer_aggregate` (`10.60.0.0/16` — all `border-leaf1` accepts from the WAN and all `fw1`
  routes back), or a name SR Linux cannot splice into a policy.
- **A service that renders only through a live L3VPN, without one**: a tenant cloud whose tenant
  has none, internet access on a withdrawn L3VPN or with no `WanInternetPeering`, and live
  L3VPNs that disagree on, or all omit, the shared DC range.

Measured on a scratch branch: a portal-shaped L3VPN for `initech` failed naming the missing
tenant cloud and the missing `WanSite`; the same tenant fully modelled passed and rendered.
`SAFE_NAME` and the decommissioned statuses are restated from `srl_config` rather than imported
(a check loads on its own), and a test holds the copies equal.

**Rules 1–4 judge decommissioned services too**, deliberately; rules 5–6 do not, because a
withdrawn service renders as absent by design and needs no attachment. For rules 1–4, skipping a
decommissioned service would excuse a misconfiguration because of a label — one that returns the
moment the status is set back.

A thing worth knowing before extending it: **`IpamVRF.tenant` cannot identify a tenant here.**
Every tenant VRF in this lab points at the `EvpnTenant` named `TENANT_CLOUD`, not at the
`OrganizationTenant` — so VRFs are compared by identity and never attributed to an owner.
`DcimCircuit.tenant` *does* resolve to the organization tenant, which is what makes the first
rule possible at all.

`zone-advertisement` discharges the condition cycle 032 attached to its own design. A zone
names its prefix list rather than relating to one, because no `RoutingPrefixList` object
exists — the fabric's whole BGP policy lives inside `avd_custom_hostvars` — and that was only
defensible if a wrong name were detectable. It reports four things: a zone naming a list the
fabric does not declare, a zone carrying one half of the policy, an approved grant whose VIP
falls outside its application's `vip_block`, and an approved grant on an application that is
not exposed.

**It counts fabric scope only, and that is the whole subtlety.** `generate-app-access` creates
the named list at device scope whenever it advertises, so once a grant has run the device
declares the very name the rule questions. Reading device scope made the reference
self-fulfilling: a branch naming a nonexistent list failed the check before a grant ran and
passed it afterwards.

`allocation-consistency` covers what the two allocating generators and hand-entered data can
collide on, in the domains no schema constraint reaches. Three rules:

- **A VLAN id is unique per FABRIC, not per `IpamL2Domain`.** `IpamVLAN`'s
  `[vlan_id, l2domain]` constraint already refuses a duplicate inside one domain — measured:
  `Violates uniqueness constraint 'vlan_id-l2domain'` — but a second `IpamL2Domain` with the
  same id loads cleanly, and AVD never renders `IpamVLAN.vlan_id` anyway. It renders
  `EvpnSvi.svi_id` and `EvpnL2Vlan.vlan_id` for every tenant naming the fabric, constrained only
  per VRF and per tenant. Reported: the same id with **intersecting tags** (one switch carries
  both), the same **VNI** on one fabric (`vni_override`, else base + id — two VRFs of one tenant
  collide this way whatever the tags), and an SVI/L2 VLAN whose id disagrees with the `IpamVLAN`
  it names. The same id on disjoint tags in different tenants is legitimate and passes.
- **Tenant subnets do not overlap within a VRF.** Candidates are segment subnets plus
  `tenant_host`/`tenant_cloud` prefixes, **minus pool resources** — `10.230.0.0/16` contains every
  allocation by design. A segment subnet carries no `vrf` (the generator sets a role and a
  description only), so the VRF comes from the segment, then the prefix, then the SVI whose
  gateway lies inside it; an unresolvable prefix is compared against every VRF. One subnet
  recorded by two segments is reported too — withdrawing either deletes the other's.
- **A VIP block sits inside its cluster's `vip_pools` and overlaps no other app's block.** The
  pools are the only supernets the leaves accept, so a block outside them is advertised and
  refused with nothing logged.

Like `wan-service-consistency`, it ignores `status`: a decommissioning service still holds its
allocation until its generator returns it, and a hand-declared block is never returned.
