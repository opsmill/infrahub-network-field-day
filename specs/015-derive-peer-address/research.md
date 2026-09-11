# Phase 0 Research: Derive the Peering Address

**Feature**: `specs/015-derive-peer-address` | **Date**: 2026-09-11

Five decisions, verified against the live instance on branch `peer-addr` with cycle 014's SVIs
loaded.

---

## R1 — How the peering SVI is identified

**Decision**: The interface whose `role` is `peering`.

Verified live across every `leaf`-role device:

```text
leaf-nfd41-pod1-1-1    Vlan110    role=peering vlan=110 -> ['10.110.0.2/24']
leaf-nfd41-pod1-1-2    Vlan110    role=peering vlan=110 -> ['10.110.0.3/24']
```

No other leaf has a virtual interface carrying an address — the other twelve have a
`Loopback0` with none. So the rule selects exactly one interface on the two devices that
matter and nothing elsewhere.

**Alternatives considered**:

- *Match on `dot1q_id == 110`* — rejected. It hardcodes the lab's VLAN number into the
  generator, so a second cluster on a different VLAN would silently get no address.
- *Match on the name `Vlan110`* — rejected for the same reason, and it is a string match on a
  display name.
- *Take the first interface with an address* — rejected. Positional, and it would pick a
  `Loopback0` the moment one gains an address.
- *Match the address against the cluster's peering prefix* — rejected as the primary rule: it
  requires knowing the prefix, and `role` already says what the interface is **for**. Worth
  considering later as a cross-check.

`role: peering` already exists in the `DcimInterface.role` dropdown and cycle 014 set it
deliberately, so this consumes an existing, intentional signal.

---

## R2 — The create path becomes reachable, and must be restored

**Decision**: Restore the create payload cycle 012 removed.

012 removed it as dead code with an explicit reason: `peer_address` is mandatory and was
recorded only on an existing session, so a peer without a session had no address the generator
was permitted to supply. That reason is now false. A cabled leaf with a peering SVI has
everything a session needs — device, ASN, address — so refusing to create one would be an
arbitrary limitation rather than a principled refusal.

The create payload carries `cluster`, `peer_device`, `peer_asn`, `peer_address`, `name` and
`enabled`. `name` is still not derivable (cycle 012 R-Q1), so a created session takes the peer
device's name, as 012's Q1 option C settled for genuinely new peers.

---

## R3 — Adoption still omits `name` and `enabled`, but no longer omits the address

**Decision**: The adopt payload gains `peer_address` alongside `peer_asn`.

Cycle 012 established that preserving a value means *not passing it*, because an upsert
validates every mandatory field — which is why adoption fetches the node and sets one
attribute. That mechanism is unchanged; it now sets two.

`name` and `enabled` remain untouched: the first is a lab-facing label, the second an
operator's decision.

---

## R4 — Drift must be surfaced, not silently corrected

**Decision**: When an existing session's recorded address differs from the derived one, log it
explicitly before correcting it.

This is the first run in which a derived value can *disagree* with a hand-written one that has
been live. Silently overwriting is defensible for `peer_asn` — the fabric is authoritative —
but an address change moves where BGP points, and an operator should see that in the run
output rather than in a later diff.

The same argument applied to `peer_asn` in cycle 012 and was not made then; this corrects that
omission for both fields.

---

## R5 — Ambiguity is an error

**Decision**: More than one peering SVI, or a peering SVI with more than one address, fails
naming the device.

The schema's own comment on `ClusterFabricPeering.peer_address` already warns that the address
must be the device's own SVI address and not an MLAG shared VARP gateway, because an anycast
address cannot identify a single BGP peer. A generator that picked one of several candidates
would be choosing which neighbour the session points at, which is not a choice it should make
silently.

---

## Risk register

| Risk | Mitigation |
| --- | --- |
| The derived address differs from the live one and the artifact moves | SC-002: the checksum must be unchanged; R4 surfaces any disagreement first |
| A future cluster on a different VLAN silently gets no address | R1 selects on role rather than VLAN number |
| Restoring the create path reintroduces a half-populated session | FR-006 validates before writing; cycle 012's "validate before any write" ordering is retained |
| Removing the object-file addresses makes sessions unrecreatable | The opposite of cycle 012: they are now derivable, and SC-004 proves it by deleting both sessions and re-running |
