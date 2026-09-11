# Phase 0 Research: Making the WAN's Addressing Real

**Feature**: `020-wan-addressing-schema` | **Date**: 2026-09-11

Every decision below was checked against the repository or against the running Infrahub
instance rather than reasoned about. Two of them overturned what the specification assumed,
and one of those removes a requirement outright.

## R1 — The `loopback` interface role already exists

**Decision**: Drop FR-020 and FR-021. No dropdown change is needed.

**Rationale**: The specification asked for a `loopback` choice on the interface `role`
dropdown, reasoning from `schemas/base/dcim.yml`, whose list runs `lag, core, cust, access,
management, peering, upstream`. That list is not the effective one.
`schemas/dcim_extensions.yml` re-declares `DcimInterface.role` in full, and its list already
contains `loopback` and `vtep_loopback` alongside the fabric roles. The extension overrides
the base, so a loopback interface is already expressible today.

**How it was missed**: the spec's inventory read the generic's definition and stopped there.
The lesson generalizes past this cycle — in this repository, `schemas/base/*` is the
*starting* definition of a kind and `schemas/*_extensions.yml` is the *effective* one, so any
claim about an attribute must be checked against both.

**Alternatives considered**: none. There is nothing to decide once the choice exists.

## R2 — `RoutingAsn` and the device ASN relationship already exist

**Decision**: No schema change for autonomous-system numbers. Confirms spec assumption 5.

**Rationale**: `schemas/dcim_extensions.yml` gives `DcimDevice` an optional `asn`
relationship to `RoutingAsn` (`identifier: device__asn`), and `RoutingAsn.fabric` is optional,
so an off-fabric router can hold one. AS 65500 on the two PEs and AS 64500 on the internet
router are therefore object data for the next cycle, not schema.

## R3 — Router ID is explicit, and the precedent for it is three relationships away

**Decision**: Add an optional `router_id` relationship from `DcimDevice` to `IpamIPAddress`,
in `schemas/dcim_extensions.yml`, beside the existing address relationships.

**Rationale**: The lab's own templates settle the question. Router ID is a loopback in three
of six routers and is *not* in the other three:

| Router | Template expression | Source |
| --- | --- | --- |
| isp-pe1, isp-pe2 | `{{ isp.edge.loopback }}` | a loopback |
| branch-rtr | `{{ branch.loopback }}` | a loopback |
| cust-acme-ce, cust-globex-ce | `{{ site.ce.lan_address \| replace('/24','') }}` | the LAN interface address |
| internet-rtr | `{{ isp.internet.peering.peer }}` | the peering address |

A renderer that inferred the router ID from a loopback would be wrong for half the fleet, and
silently — a BGP router-id that is merely *different* still forms a session, so the error
would not announce itself. Making it explicit costs one optional relationship.

The shape is not invented here. `DcimDevice` already carries `loopback_ip`,
`vtep_loopback_ip` and `mgmt_ip`, each an optional cardinality-one `Attribute` relationship to
`IpamIPAddress` in the same extensions file. `router_id` is the fourth of an existing set.

**Alternatives considered**:

- *Reuse `loopback_ip`*: rejected. For a customer edge it would record a LAN address as a
  loopback, which is false, and `loopback_ip` is read by the AVD path.
- *Derive from an interface by role*: rejected for the reason above.
- *A `router_id` text attribute*: rejected. It would restate an address that is already an
  object, which is the precise failure this cycle exists to fix.

## R4 — The circuit schema is adopted, so the endpoint relationship goes in an extension

**Decision**: Create `schemas/circuit_extensions.yml` carrying an `extensions:` block that
adds `interface` to `DcimCircuitEndpoint`.

**Rationale**: `schemas/MARKETPLACE.md` lists `circuit/circuit.yml` as `infrahub/circuit`
version 1.0.1 and states adopted files are "kept byte-identical to the published version so a
re-download diffs cleanly, and they are never hand-edited. Anything this project needs on top
goes in a separate `*_extensions.yml`." Five such files already exist (`dcim_`, `ipam_`,
`l3ls_`, `location_`, `security_`, `tenancy_`), so the name and placement follow an
established convention.

MARKETPLACE.md also records the limit of the mechanism — an extensions block "takes only
attributes, relationships and `inherit_from`" — which is why `security_extensions.yml` has to
re-declare a whole node to add a `human_friendly_id`. A relationship is within the limit, so
no re-declaration is needed here. A live `schema check` confirmed it.

**Alternatives considered**: editing `circuit/circuit.yml` directly — rejected by
MARKETPLACE.md, and it would make the next marketplace re-download a conflict.

## R5 — The peer is the `DcimInterface` generic

**Decision**: `DcimCircuitEndpoint.interface` peers with `DcimInterface`.

**Rationale**: `DcimInterface` is a generic; `InterfacePhysical` and `InterfaceVirtual` are the
concrete kinds, and both inherit it along with `InterfaceLayer3`, which is what carries
`ip_addresses`. Peering with the generic accepts either. Peering with `InterfacePhysical`
would work for every WAN circuit today and fail the first time a circuit terminates on a
sub-interface.

Nothing else is needed to reach an address: `InterfaceLayer3.ip_addresses` is already
cardinality many and optional, so `endpoint → interface → ip_addresses` is a complete path the
moment the relationship exists.

## R6 — A relationship rename leaves a ghost unless it is tombstoned, and the check does not warn

**Decision**: Rename `WanSite.bgp_session` to `bgp_sessions` with cardinality many, **and**
retain the old relationship in the file marked `state: absent`.

**Rationale**: This was tested against the running instance both ways, and the difference is
not visible without doing so.

Renaming alone — adding `bgp_sessions`, deleting `bgp_session` from the YAML:

```text
WanSite:
    relationships:
        added:    { bgp_sessions: null }
        removed:  {}                       # <- the old relationship is NOT removed
```

The server still reports `bgp_session` among `WanSite`'s relationships after such a load,
because a schema load is an upsert: a relationship absent from the file is left alone, not
dropped. `schema check` reports this as a pure addition and raises nothing.

Adding `state: absent` to the old entry:

```text
WanSite:
    relationships:
        added:    { bgp_sessions: null }
        removed:  { bgp_session: null }    # <- now it goes
```

The skill's migration rule states this for attributes — "Use `state: absent` to remove an
attribute. Don't just delete it from the YAML" — and it holds for relationships too.

This is the repository's first `state: absent`; a grep over `schemas/` returns none. That is a
deliberate new pattern, not an accident, and the tombstone can be deleted once the Infrahub
instance has been rebuilt from empty (`invoke destroy` then `invoke build`), at which point
there is no prior schema for it to remove.

**Alternatives considered**:

- *Widen in place — keep the name `bgp_session`, change only `cardinality` to `many`.* This
  works: the server reports it cleanly as `changed: {cardinality, max_count}`, with no
  tombstone, no removal, and no new pattern. It was rejected on the name alone. The
  relationship is read by every query the FRR transform will write, and
  `bgp_session { edges { node } }` describes two objects with a singular noun, permanently, to
  save one tombstone once. This repository's schema files argue with themselves in comments
  about exactly this kind of choice; the name is worth more than the churn.
- *A second relationship, `ce_bgp_session`, beside the first.* Rejected by the spec (FR-005)
  and on the merits: a session's two ends are the same kind of thing, and splitting them by
  which device holds them invites a renderer to treat one as primary.

## R7 — The widening is safe for data, and touches one test

**Decision**: Proceed. Update `tests/unit/test_wan_schema_contract.py` in the same commit.

**Rationale**: Verified rather than assumed, as FR-040 requires:

- **Instance data**: `objects/33_nfd41_wan.yml` seeds four `WanSite` objects — acme/hq,
  acme/dr, globex/hq, branch/office — and not one sets `bgp_session`. Nothing is lost.
- **Code**: no `.gql` query, generator, transform or check references it. A repository-wide
  grep returns two hits only: `tests/unit/test_wan_schema_contract.py:240`, which asserts
  `relationships["bgp_session"]["peer"] == "RoutingBGPNeighbor"`, and
  `src/solution_arista_avd/protocols.py:693`, which is generated.

The contract test is the mechanism that would otherwise catch this as a regression, so it is
updated deliberately — re-pointed at `bgp_sessions` and extended to assert the new cardinality,
never loosened to stop failing.

## R8 — The internet peering needs two sessions, not one

**Decision**: `WanInternetPeering` gains `bgp_sessions`, cardinality many, not a
cardinality-one `bgp_session` as the specification's FR-004 worded it.

**Rationale**: The specification treated the transit peering as a single session because it is
one link. It is not one object. `isp-pe2` holds `neighbor 10.52.0.2 remote-as 64500` and
`internet-rtr` holds `neighbor 10.52.0.1 remote-as 65500`; `RoutingBGPNeighbor` is
device-scoped with a uniqueness constraint of `[device, peer_address__value]`, so those are two
objects, exactly as a PE↔CE session is. Modelling the peering's session as cardinality one
would make it the only place in the model where half a session is recorded.

This keeps `WanSite` and `WanInternetPeering` symmetric: both name every end of the session
they justify. FR-004 is satisfied in substance — the transit neighbor becomes reachable from
the peering — with the cardinality corrected.

## R9 — Nothing else in the five gaps needs schema

**Decision**: The cycle is four schema changes, not five.

**Rationale**: Re-running the specification's gap list after R1:

| Gap | Resolution |
| --- | --- |
| 1. Circuit end cannot name its interface | `DcimCircuitEndpoint.interface` (R4, R5) |
| 2. Internet peering has no session | `WanInternetPeering.bgp_sessions` (R8) |
| 3. Nothing carries a router ID | `DcimDevice.router_id` (R3) |
| 4. Nothing marks a loopback | **Already modelled** (R1) |
| 5. `WanSite.bgp_session` is cardinality one | `WanSite.bgp_sessions` + tombstone (R6) |

A full `uv run infrahubctl schema check schemas/` against the live instance, with all four
changes applied, returned `is Valid!` for every file and a diff containing exactly those four
additions and nothing else. SC-006 — "no remaining row whose obstacle is schema" — is
reachable within this scope.

## R10 — The tombstone leaks a phantom into `protocols.py` (found during implementation)

**Decision**: Keep the tombstone and the `bgp_sessions` name. The phantom is bounded,
documented, and removes itself.

**What was found**: `uv run infrahubctl protocols --schemas schemas` generates from the YAML
files and **does not honour `state: absent`**. After the change, `protocols.py` carries both:

```python
class WanSite(CoreNode):
    bgp_session: RelationshipAttribute[RoutingBGPNeighbor]   # no longer exists on the server
    bgp_sessions: RelationshipManager[RoutingBGPNeighbor]
```

The server does not have `bgp_session` — the read-back in
[acceptance-evidence.md](./acceptance-evidence.md) proves it — so the generated type describes
a relationship that is gone. Code written against it would type-check and fail at runtime.

**Why the tombstone stays anyway**:

- The phantom is **temporary by construction**. The tombstone's documented removal condition is
  the next rebuild from empty, and the phantom goes with it. It is a migration artifact, not a
  standing lie.
- Nothing references it. A repository-wide grep for `.bgp_session` outside the contract test
  returns nothing, and the contract test asserts `bgp_sessions` is the real one.
- The alternative costs more than it saves. Widening in place under the singular name would
  fix the phantom, but leaves `WanSite.bgp_session` and `WanInternetPeering.bgp_sessions`
  naming the same concept differently — an inconsistency the FRR transform would have to write
  around in every query, permanently, to avoid a transient artifact.
- Hand-editing `protocols.py` is not an option: Constitution III forbids it explicitly.

**Alternatives considered**:

- *Generate protocols with `--branch` instead of `--schemas`.* `infrahubctl protocols` accepts
  it, and generating from the server would honour `state: absent` **and** pick up extensions.
  Rejected as out of scope: it changes how `protocols.py` is produced for the whole
  repository, and `AGENTS.md` documents the `--schemas` form. Worth its own cycle — see below.
- *Widen in place.* R6's rejected alternative, re-examined and rejected again for the naming
  inconsistency above.

## R11 — `protocols.py` reflects no `extensions:` block at all (pre-existing)

**Finding, not a decision**: neither `router_id` nor `DcimCircuitEndpoint.interface` appears in
the regenerated `protocols.py`. This is not caused by this cycle. `DcimDevice.loopback_ip`,
`mgmt_ip`, `asn`, `rack` and `pod` have been extension relationships for many cycles and appear
nowhere in the file either — the generated `DcimDevice` carries only `status`.

`infrahubctl protocols --schemas <dir>` reads the YAML files and does not apply `extensions:`
blocks, so every extension field in this repository is invisible to the generated protocols.
Generating with `--branch` against a loaded server would fix it.

This is worth a cycle of its own — it means typed access to a large part of this repository's
model silently falls back to untyped attribute access, which Constitution III exists to
prevent. It is recorded here rather than fixed here because changing how `protocols.py` is
generated affects every kind in the repository and has nothing to do with the WAN's addressing.

## Open risks carried to implementation

1. **`state: absent` is checked, not yet loaded.** `schema check` reports the removal; an
   actual `schema load` has not been run. If the load rejects it, the fallback is R6's rejected
   alternative — widen in place under the singular name — which is a one-line change and a
   contract-test edit, so the risk is bounded and reversible.
2. **`protocols.py` regeneration** will rename `bgp_session` to `bgp_sessions` and change its
   generated type from `RelationshipAttribute` to the many-cardinality form. Any consumer would
   break at type-check time; there are none today, and `mypy` is a gate.
3. **The tombstone needs an owner.** It should be removed after the next full instance rebuild.
   Left forever, it is clutter that implies a migration still pending.
