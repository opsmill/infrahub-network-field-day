# Phase 0 Research: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Date**: 2026-09-12 | **Branch**: `025-firewall-route-objects`

Seven findings. The object file was built, loaded and verified against a live branch before this
plan was written, so none of the decisions below are predictions.

---

## R1 — The schema this cycle depends on is live, and carries a constraint the YAML does not

Queried from Infrahub `main` after cycle 024's merge:

```text
device peer: DcimGenericDevice | optional: False | cardinality: one
HFID: ['device__name__value', 'prefix__value']
uniqueness: [['device', 'prefix__value', 'vrf__value'], ['device', 'prefix__value']]
attributes: next_hop, gateway, prefix (mandatory), distance, tag, vrf, interface, route_name
```

`schemas/routing/routing.yml` declares **one** uniqueness constraint,
`[device, prefix__value, vrf__value]`. The live schema has **two**: Infrahub derives the second,
`[device, prefix__value]`, from the `human_friendly_id`.

Nothing in this cycle trips over it — all eight routes are in the default VRF — but it is worth
recording, because it means **`[device, prefix]` is unique regardless of VRF**. The same
destination could not later be given a second route in another routing instance without a schema
change. Discovered by reading the live schema rather than the file.

---

## R2 — A scalar HFID reference works, and the CRITICAL rule that seemed to forbid it does not apply

The Infrahub objects guidance marks generic relationship references as a CRITICAL failure:

> Unable to lookup node by HFID, schema 'LocationGeneric' does not have a HFID defined.

with the prescribed fix being an inline block naming the concrete kind. Since cycle 024 made
`RoutingStaticRoute.device` peer `DcimGenericDevice`, the rule appeared to apply directly.

**It does not.** The rule's precondition is *"the generic does not define `human_friendly_id`"*.
`DcimGenericDevice` defines `human_friendly_id: [name__value]` (`schemas/base/dcim.yml`), so the
scalar form resolves.

Confirmed by loading, not by reading: eight objects with `device: "fw1"` loaded successfully.

**Decision**: plain scalar `device: "fw1"`.
**Alternative rejected**: eight inline `kind: SecurityFirewall` blocks — the pattern cycle 023
needed for the polymorphic address book, where the peer genuinely was an HFID-less generic. Using
it here would add noise and set a precedent that the next reader would copy without the reason.

---

## R3 — VERIFIED BY RUNNING: the load is correct, complete and idempotent

The file was generated from the oracle, loaded onto a scratch branch (`fw-routes-obj`), and
compared **both ways**:

```text
fw1.static_routes = 8 | RoutingStaticRoute total = 19
oracle->graph missing : none
graph->oracle invented: none
value mismatches      : none
vrf all default       : True
```

19 = the 11 pre-existing fabric routes plus these 8. The eleven were neither read nor touched.

A **second load** left `fw1.static_routes = 8` and the total at 19. Idempotent, counted rather
than read from the log — `infrahubctl` prints "Created node" for an upsert, which cycle 023
recorded and cycle 024 relied on.

Also confirmed on the loaded objects: `gateway`, `interface`, `distance` and `tag` are all unset,
and `vrf` is `"default"` on all eight **from the schema default**, since the file sets it nowhere.

---

## R4 — Every next hop is on a connected subnet, checked against the model

Not against the device file's comment column — against `fw1`'s interface addresses as this
repository models them, in `objects/32_nfd41_security.yml`:

| Destination | Next hop | Lands on |
| --- | --- | --- |
| `10.110.0.0/24` | `10.250.110.1` | ge-0/0/0 (`10.250.110.2/30`) |
| `10.111.0.0/16` | `10.250.110.1` | ge-0/0/0 |
| `10.112.0.0/16` | `10.250.110.1` | ge-0/0/0 |
| `10.210.0.0/24` | `10.250.210.1` | ge-0/0/1 (`10.250.210.2/30`) |
| `10.60.0.0/16` | `10.250.150.1` | ge-0/0/2 (`10.250.150.2/30`) |
| `10.70.0.0/24` | `10.250.170.1` | ge-0/0/3 (`10.250.170.2/30`) |
| `10.220.10.0/24` | `10.250.10.1` | ge-0/0/4 (`10.250.10.2/30`) |
| `10.220.20.0/24` | `10.250.20.1` | ge-0/0/5 (`10.250.20.2/30`) |

All eight. This matters because **a character-for-character comparison against the
`routing-options` stanza cannot catch a typo in the `routing-options` stanza** — the stanza is
where the error would be. Checking the next hop against a different part of the model is an
independent witness. A next hop off a connected subnet is accepted by Junos and never installs.

---

## R5 — Every destination is an address-book prefix, and the four that are not routed are accounted for

Eight destinations, eight address-book entries, one for one: `k8s-nodes`, `k8s-pods`,
`k8s-services`, `app-hosts`, `wan-customers`, `branch-users`, `acme-cloud`, `globex-cloud`.

The book has thirteen indexed entries, so four have no route of their own. Rather than leave that
as a loose end, all four were accounted for — and the account closes:

| Entry | Prefix | Why it needs no route |
| --- | --- | --- |
| `acme-hq` | `10.60.10.0/24` | inside `10.60.0.0/16`, covered by the `wan-customers` route |
| `acme-dr` | `10.60.11.0/24` | inside `10.60.0.0/16`, same |
| `globex-hq` | `10.60.20.0/24` | inside `10.60.0.0/16`, same |
| `access-portal` | `10.112.240.33/32` | a host inside `10.112.0.0/16`, covered by the `k8s-services` route |
| `fabric-infra` | `10.41.0.0/16` | **never a destination.** It appears six times in the seed, every time as `source_address` — the six `deny-spoofed-infra` anti-spoofing rules |

8 routed + 3 supernet + 1 host-in-supernet + 1 source-only = 13. Every entry explained.

**This rules out a criterion that would have been wrong.** The converse of SC-005 — *every
address-book prefix has a route* — is false, and asserting it would have failed on five entries
that are all correct.

---

## R6 — Everything the test needs is available offline

The gate needs no server. Three files:

| Source | Supplies |
| --- | --- |
| `objects/32b_nfd41_fw_static_routes.yml` | the eight routes |
| `objects/32_nfd41_security.yml` | `fw1`'s interface addresses (R4) and the address book (R5) |
| `../lab/configs/fw/vsrx/junos.conf` | the oracle |

Both cross-checks were computed from these three files alone, which is how R4 and R5 above were
produced. So `tests/unit/test_fw_static_route_objects.py` can assert all of SC-001 to SC-005
without Infrahub running, matching the ten existing offline contract modules.

---

## R7 — A correction made while researching

While accounting for `access-portal` in R5 the address `10.112.240.10` was used. That was not
read from the file; it was assumed, and it was wrong — the seeded value is **`10.112.240.33/32`**.

The conclusion survives, because both are inside `10.112.0.0/16`. The method did not: a guessed
value that happens to land in the right subnet produces a correct answer for no reason, and would
have been recorded as evidence. The figure was re-read from
`objects/32_nfd41_security.yml` and corrected before it reached any artifact.

This is the seventh cycle running to record a claim that was wrong until it was checked. The
difference here is only that it was caught within minutes rather than after being written down.

---

## Summary of decisions

| # | Decision | Rationale |
| --- | --- | --- |
| R1 | Do not set `vrf` | The schema default `"default"` is the master instance; setting it changes nothing and risks disagreeing with the uniqueness constraint |
| R2 | Scalar `device: "fw1"` | `DcimGenericDevice` has an HFID, so the generic-peer rule's precondition is unmet. Verified by loading |
| R3 | One new file, loaded as-is | Both-ways comparison clean, idempotent on a second load |
| R4 | Assert next hops against interface addresses | An independent witness the oracle comparison cannot provide |
| R5 | Assert destinations against the address book, but **not** the converse | Five entries correctly have no route; the converse would fail |
| R6 | Offline unit test over three files | No server needed, matching the existing contract modules |
| R7 | Re-read the value rather than keep a lucky guess | A right answer from a wrong method is not evidence |

## No spec amendments required

Unlike cycle 024, Phase 0 overturned nothing in the spec. Every success criterion as written is
demonstrable, and R4 and R5 were already promoted to SC-004 and SC-005 during the specify phase
because they were found while reading the device file rather than after.

The one thing research adds is R5's negative result: the spec should not, and does not, assert the
converse.
