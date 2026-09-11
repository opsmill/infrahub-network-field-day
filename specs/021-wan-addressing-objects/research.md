# Phase 0 Research: The WAN's Addressing

**Feature**: `021-wan-addressing-objects` | **Date**: 2026-09-11

Every reference form below was loaded against the running instance rather than reasoned about.
Four of the eight forms this cycle needs fail on the first attempt, each for a different
reason, and none of the failures is obvious from reading the schema.

## R1 — `IpamIPAddress.interface` cannot be referenced by HFID

**Decision**: attach an address to its interface with an inline block naming the concrete kind.

**Rationale**: the obvious form fails outright:

```yaml
- address: 10.51.10.1/30
  interface: ["isp-pe1", "eth2"]
```

```text
['IpamIPAddressUpsert'] Unable to lookup node by HFID, schema 'InterfaceLayer3'
does not have a HFID defined.
```

`IpamIPAddress.interface` peers with `InterfaceLayer3`, which is a generic that declares no
`human_friendly_id`, so there is nothing to look the node up by. The working form names the
concrete kind instead:

```yaml
- address: 10.51.10.1/30
  interface:
    kind: InterfacePhysical
    data:
      name: eth2
      device: isp-pe1
```

**Alternatives considered**: setting the link from the interface side via
`InterfaceLayer3.ip_addresses`. It is the same relationship and `IpamIPAddress` *does* have an
HFID, so it ought to work — but it puts the address string on the interface object, and the
address is the thing this cycle is trying to make canonical. Attaching from the address side
keeps each address stated exactly once.

## R2 — For a cardinality-one relationship the inline `data:` is a dict, not a list

**Decision**: use a mapping under `data:` whenever the relationship is cardinality one.

**Rationale**: this is the single most expensive finding of the cycle, because the failure mode
is a Python traceback rather than a validation message:

```text
File ".../infrahub_sdk/spec/object.py", line 278, in validate_object
    for key, value in data.items():
AttributeError: 'list' object has no attribute 'items'
```

The list form is what the `infrahub-managing-objects` skill documents. Its
`rules/value-generic-relationships.md` gives this as the worked example:

```yaml
- prefix: "10.0.0.0/24"
  location:
    kind: LocationSite
    data:
      - name: "Acacias"        # a list
```

`location` is cardinality one, so against `infrahub-sdk` 1.22.0 that example crashes. The
repository's own `objects/33_nfd41_wan.yml` already uses the correct dict form — `data:` then
`name: provider-edge` with no dash — which is how the existing file loads while a
faithful copy of the documented example does not.

**This is skill friction worth reporting.** The rule is right about *when* to use an inline
block and wrong about its shape, and the error it produces names neither the file nor the
field.

## R3 — Upserting an existing object restates every mandatory attribute

**Decision**: add relationships to existing objects **in the file that already defines them**,
and use new files only for genuinely new objects.

**Rationale**: a top-level `spec` block is a full upsert, so the SDK validates the whole object,
not the fields being changed:

| Attempted update | Rejected with |
| --- | --- |
| `DcimDevice` + `router_id` | `status is mandatory` |
| `WanSite` + `bgp_sessions` | `lan_prefix is mandatory` |
| `DcimCircuitEndpoint` + `interface` | `location is mandatory` |

Restating those fields in a new file would put `status: active`, a LAN prefix and a location in
two places each — the exact two-sources-of-truth failure this cycle exists to remove. So the
endpoint links, the site sessions and the static-route links are edited into
`objects/33_nfd41_wan.yml` where the endpoints and sites already are, not added in a new file.

## R4 — `DcimDevice.asn` must be a string

**Decision**: write `asn: "65500"`, quoted.

**Rationale**: `RoutingAsn.human_friendly_id` is `[asn__value]`, and `asn` is a `Number`. An
integer is rejected:

```text
1.asn: Relationship asn doesn't have the right format one / <class 'int'>
```

The HFID is matched as a string regardless of the attribute's kind. The quoted form loads.

**Alternative used instead where possible**: `RoutingAsn.devices` is the declared reverse of
`DcimDevice.asn` (`identifier: device__asn`), and it takes a plain list of device names:

```yaml
- asn: 65500
  devices: [isp-pe1, isp-pe2]
```

This is better than setting `asn` on each device, because it avoids a `DcimDevice` upsert
entirely (R3) and states each ASN once with all of its devices — which is also how a reader
would want to see it.

## R5 — `DcimCircuitEndpoint.interface` *can* be referenced by HFID

**Decision**: use the two-element list form, `interface: ["isp-pe1", "eth2"]`.

**Rationale**: this is the instructive contrast with R1. Both relationships point at an
interface generic, but `DcimInterface` declares
`human_friendly_id: [device__name__value, name__value]` while `InterfaceLayer3` declares none.
The list form resolves:

```text
['DcimCircuitEndpointUpsert'] Unable to find the node cust-acme-ce :: eth1 /
DcimInterface in the database.
```

That is a lookup that worked and found nothing, not a form that was rejected — the interface
simply had not been created yet. So the rule is not "generics cannot be referenced by HFID"; it
is "a generic with an HFID can, one without cannot", and which is which has to be checked per
relationship.

**Consequence for load order**: interfaces must exist before the endpoints that name them.

## R6 — Verified end to end, not just accepted

**Decision**: proceed; all four traversals resolve.

After loading a probe of one circuit's worth of data, the live graph answers:

```text
endpoint side a -> eth2 (InterfacePhysical) -> ['10.51.10.1/30']
endpoint side z -> None                                  (not yet seeded)
isp-pe1 router_id -> 10.50.0.1/32   | asn -> 65500
WanSite acme/hq -> sessions: [('10.51.10.1','65500'), ('10.51.10.2','65010')]
WanSite globex/hq -> sessions: []
```

Both ends of one session hang off one site, and the site that has no data correctly returns
nothing rather than erroring. Cycle 020's schema does what it was built for.

## R7 — `RoutingVrfStaticRoute` has a weaker HFID than its uniqueness constraint

**Finding, carried rather than fixed**: the kind declares

```yaml
human_friendly_id: [vrf__name__value]
uniqueness_constraints: [[vrf, prefix__value, next_hop__value]]
```

so every static route in one VRF shares an HFID. `infrahubctl object load` upserts by HFID, so
a second route in `CUST_ACME` would match the first and overwrite it, or collide on the
uniqueness constraint — the same defect `schemas/MARKETPLACE.md` documents for
`SecurityPolicyRule`, whose fix was re-declaring the node with a stronger HFID.

This cycle seeds exactly one static route, so it does not bite. It is recorded because the next
statically attached site would hit it, and because the repository has a documented remedy for
exactly this shape.

## R8 — The load-order problem, and where the VRFs belong

**Decision**: relocate the two `CUST_*` VRF definitions from
`objects/37_nfd41_wan_services.yml` into the new technical-layer file, and place that file
between the devices and the circuits.

**Rationale**: the dependency chain is forced, and one link of it points the wrong way.

```text
devices (31) -> interfaces -> addresses -> router IDs
                interfaces -> circuit endpoint links (33)
                VRF CUST_ACME -> static route -> acme/dr's site (33)
```

Every arrow is satisfied by inserting one file after `31_nfd41_offfabric_devices.yml` and
before `33_nfd41_wan.yml` — except the VRF, which cycle 019 created in file 37, four files too
late. A static route in 37 could not be referenced by a site in 33.

Moving the VRFs is the smaller change and the more correct one. A VRF is a technical-layer
object; `37_nfd41_wan_services.yml` is the service layer, and 019 put them there only because
it was the cycle that happened to need them — its own comment describes them as "PE-side",
which is a technical fact, not an ordered service.

**Alternatives considered**:

- *A post-37 file restating each site's mandatory fields.* Rejected: it duplicates a tenant, an
  attachment kind and a LAN prefix per site to avoid moving two VRF definitions (R3).
- *Creating the VRF inline from the static route.* Rejected: the VRF would then be described in
  two files, which is the problem in miniature.

## Open risks carried to implementation

1. **`wan-addr` is now polluted.** This Phase 0 experiment loaded partial, real cycle-021 data
   into the `wan-addr` Infrahub branch — one circuit's interfaces, two addresses, one ASN, two
   BGP neighbours, one static route and one site's sessions. The values are correct but the set
   is incomplete. **`wan-addr` must not be merged into `main`**, and cycle 021 should load into
   a fresh branch. Nothing is lost by deleting it: its schema comes from the git files and its
   objects from `objects/`.
2. **The dict-versus-list trap will recur.** Every inline block this cycle writes is
   cardinality one. A single stray dash produces a traceback that names no field.
3. **Load order is now load-bearing across four files.** `31` → new file → `33`, with `37`
   losing content. A directory load processes filenames in sort order, so the new file's name
   has to sort between them, and a test should assert that rather than trusting it.
