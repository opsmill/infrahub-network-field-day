# Marketplace-sourced schemas

Some files under `schemas/` come from the [Infrahub
Marketplace](https://marketplace.infrahub.app) rather than being authored here. They are kept
**byte-identical to the published version** so a re-download diffs cleanly, and they are
never hand-edited. Anything this project needs on top goes in a separate
`*_extensions.yml`.

Check the marketplace before authoring a new schema. `infrahubctl marketplace get` is
the intended path, and it publishes 56 schemas across 10 collections — so a new domain
is likely already covered.

## Adopted

| File | Marketplace identifier | Version | Provides |
|------|------------------------|---------|----------|
| `security/security.yml` | `infrahub/security` | 1.0.2 | 22 kinds: zones, the polymorphic address book, service objects, zone-pair policy rules, `SecurityFirewall` as a device kind, `SecurityFirewallInterface` |
| `cluster/cluster.yml` | `infrahub/cluster` | 1.0.2 | `ClusterGeneric`, `ClusterGenericComputeUnitNodes` |
| `circuit/circuit.yml` | `infrahub/circuit` | 1.0.1 | `DcimCircuit`, `DcimCircuitEndpoint` |
| `tenancy/tenancy.yml` | `infrahub/tenancy` | 1.0.1 | `OrganizationTenant`, plus tenant back-references on device, prefix, address and location |

## Verifying a file is unmodified

```bash
diff <(uv run infrahubctl marketplace get infrahub/security --stdout) \
     schemas/security/security.yml
```

No output means the local copy matches the published version. To take a newer version,
re-download over the file and re-run `uv run infrahubctl schema check schemas/`:

```bash
uv run infrahubctl marketplace get infrahub/security --stdout > schemas/security/security.yml
```

Pin a specific version with `--version`, for example
`infrahubctl marketplace get infrahub/security --version 1.0.2 --stdout`.

## Local additions on top

| File | Extends | Adds | Why it is not upstream |
|------|---------|------|------------------------|
| `security_extensions.yml` | `SecurityZone`, `SecurityPolicyRule`, `DcimFabricSwitch` | `trust_level`, `vrf`, `dc_advertised_prefix_list`, `advertising_device`, `advertised_zones`, `managed_by_service` | The VRF link is this fabric's handoff pairing; `managed_by_service` is the guard that lets a generator reconcile a firewall that also carries hand-written rules. The advertisement pair is the fabric side of a zone — a prefix-list **name** (there is no object to reference) plus the switch applying it; its inverse lives on `DcimFabricSwitch` in this file so both halves of one `identifier` stay together |
| `cluster/kubernetes.yml` | `ClusterGeneric`, `ClusterGenericComputeUnitNodes` | `ClusterKubernetes`, `ClusterFabricPeering` | Nothing published covers a CNI, pod/service CIDRs, LoadBalancer VIP pools, or a cluster that speaks BGP with a fabric |
| `tenancy_extensions.yml` | `OrganizationTenant`, `DcimCircuit` | `tenant_id`, `classification`, `sites`, `circuits` | A tenant crosses the provider edge, the fabric and the cluster at once, so these hang off the one adopted tenant rather than a per-domain copy of it |
| `wan/wan.yml` | — | `WanSite`, `WanInternetPeering` | How a site attaches — its LAN, eBGP or static, its own ASN — and plain transit to one upstream AS have no published equivalent |
| `service/*.yml` | — | `ServiceGeneric` and six service kinds | The marketplace offers no service-layer abstraction anywhere |

## Evaluated and not adopted

Recorded so the next person does not re-litigate these.

| Schema | Why not |
|--------|---------|
| `infrahub/hosting_cluster` | `ClusterHosting` inherits `VirtualizationHostVirtualMachine` because it hosts virtual machines. A k3s cluster hosts pods, so `ClusterKubernetes` takes `ClusterGeneric` directly. Its structure was still followed as the pattern for building a concrete cluster kind |
| `infrahub/routing_bgp` | Brings a second `RoutingBGPPeerGroup` that collides with this repository's, and a `RoutingAutonomousSystem` that duplicates `RoutingAsn`. Replacing the existing AVD-integrated routing model is a separate piece of work, not part of this feature |
| `infrahub/peering_ixp` | Models Internet Exchange peering with route servers and an IX LAN. The lab's internet edge is plain transit to a single upstream AS |
| `infrahub/circuit_service` | `CircuitService` bundles circuit endpoints under a provider service id. Close to `ServiceL3vpn`, but it carries no tenant, VRF or import policy, and it sits in the technical layer rather than above it. `ServiceL3vpn` references `DcimCircuit` instead |
| `infrahub/circuit_contract` | Commercial contract terms — start, end, monthly cost, currency. Not modeled by this lab |
| `infrahub/compute` | Already present as `schemas/compute/compute.yml`, a diverged local copy with the same kind set. Re-adopting it cleanly is worthwhile but is a change to existing working schema, so it is out of scope here |
| `infrahub/firewall_policer`, `infrahub/qos`, `infrahub/snmp` | In the `security-mgmt` collection alongside `infrahub/security`, but the lab configures none of them |

## Note on the address book

`infrahub/security` offers both literal address kinds (`SecurityPrefix`,
`SecurityIPAddress`, carrying `IPNetwork` / `IPHost` attributes) and IPAM-backed ones
(`SecurityIPAMIPPrefix`, `SecurityIPAMIPAddress`, referencing `IpamPrefix` /
`IpamIPAddress`).

**Use the IPAM-backed variants** for any network a route policy or a network policy also
matches on. Several enforcement points in this lab match on the same ranges, and the
point of the model is that they reference one object rather than one object plus copies
of its CIDR.

## Two problems found while loading data against the adopted schema

Both surfaced only when real objects were loaded, not during `schema check`.

### `SecurityPolicyRule` declares no `human_friendly_id`

`infrahubctl object load` upserts by HFID. Without one it can only CREATE, so a
second run of any file containing rules collides with the uniqueness constraint
`index-source_zone-destination_zone-policy` and the load is not re-runnable —
which the project's idempotence rules do not allow.

An `extensions:` block cannot add a `human_friendly_id` (it takes only
attributes, relationships and `inherit_from`), so `security_extensions.yml`
re-declares the node with just the HFID, derived from the uniqueness constraint
upstream already defines. Every element is reachable because `SecurityZone.name`
and `SecurityPolicy.name` are both unique upstream. Verified idempotent: two
consecutive loads leave 19 rules.

Worth raising upstream — any node intended to be loaded from object files needs
an HFID, and this one has a perfectly good natural key already written down.

### Infrahub 1.10.6 returns a 500 for a JSON attribute key containing `.` or `/`

Writing a `JSON` attribute whose object key contains a dot or a slash fails with
an internal server error. Isolated by bisection:

| Key | Result |
|-----|--------|
| `bgp` | ok |
| `otternet.lab` | **500** |
| `otternet/bgp` | **500** |
| `otternet.lab/bgp` | **500** |

Every Kubernetes label selector is of the last form, so this blocks storing one
as a JSON map. `node_selector`, `advertisement_selector`, `service_selector` and
`workload_selector` are therefore `List` attributes holding `key=value` strings —
the same shape `opsmill/infrahub-dogfooding` uses for its AWS labels, parsed in
the transform.

**Still armed for the service-data cycle**: `ServiceFabricApp.manifests` and
`chart_values` are `JSON` by necessity — arbitrary Kubernetes and Helm payloads,
which routinely contain dotted keys such as `otternet.lab/advertise`. Loading real
application data will hit this. Options at that point are to store the payload
as a text blob, attach it as a `CoreFileObject`, or wait for a server fix.
