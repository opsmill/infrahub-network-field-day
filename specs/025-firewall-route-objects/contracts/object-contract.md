# Object Contract: The Perimeter Firewall's Static Routes

**Cycle**: 025 | **Consumed by**: `tests/unit/test_fw_static_route_objects.py` (new)

Every clause is an assertion the test module makes by reading files. None needs a running
Infrahub — see [research.md](../research.md) R6.

## Sources

| Alias | Path |
| --- | --- |
| `ROUTES` | `objects/32b_nfd41_fw_static_routes.yml` |
| `SECURITY` | `objects/32_nfd41_security.yml` |
| `ORACLE` | `../lab/configs/fw/vsrx/junos.conf` |

`ORACLE` lives outside this repository. The module must **skip**, not fail, when the lab repo is
not checked out alongside — matching `tests/unit/test_junos_config.py`.

## C1 — File shape

`ROUTES` is a single YAML document with `apiVersion: infrahub.app/v1`, `kind: Object`,
`spec.kind: RoutingStaticRoute`, and a `spec.data` list.

## C2 — Exactly eight routes, all on `fw1`

`spec.data` has eight entries. Every entry's `device` is the scalar string `"fw1"`.

The scalar form is pinned deliberately: `device` peers a generic, and the reflex fix for that is
an inline concrete-kind block. It is not needed here because `DcimGenericDevice` has an HFID
(R2), and a later "correction" to the inline form would be a silent change of shape.

## C3 — The oracle comparison runs BOTH WAYS

Parse `ORACLE`'s `routing-options { static { … } }` block into
`{prefix: (next_hop, comment)}`, and `ROUTES` into the same shape. Then assert:

| Direction | Assertion |
| --- | --- |
| oracle → routes | every destination in the device file appears in the object file |
| routes → oracle | every destination in the object file appears in the device file |
| values | for each shared destination, `next_hop` and `route_name` match exactly |

**Both directions are required, separately.** Cycle 023 deleted fourteen lines of correct data
after a one-way read concluded something was absent when the search was at fault. A single-
direction check here passes with a route missing.

## C4 — The oracle parser handles the real line shape

The stanza's lines are column-aligned by hand, with a variable run of spaces between the prefix
and `next-hop` and between the `;` and the comment:

```text
route 10.110.0.0/24 next-hop 10.250.110.1;   /* k8s nodes */
route 10.60.0.0/16  next-hop 10.250.150.1;   /* WAN customer supernet */
route 10.220.10.0/24 next-hop 10.250.10.1;  /* acme cloud instances */
```

A parser assuming single spaces reads six of eight. Pinned as its own clause because in cycle 023
the equivalent bug **overstated a gap by six corrections** and was believed for a while — the
parser was the thing that was wrong.

Assert the parser returns exactly eight routes from `ORACLE`.

## C5 — Only the intended fields are set

Each entry sets `prefix`, `next_hop`, `route_name`, `device` — and **nothing else**. No `gateway`,
`interface`, `distance`, `tag`, or `vrf`.

`vrf` in particular: the schema default `"default"` is the master instance, which is where these
routes live. Setting it would be redundant, and R1 found a uniqueness constraint on
`[device, prefix]` derived from the HFID in addition to the declared one that names `vrf`.

Inventing a `distance` or an `interface` would make cycle 026 render configuration the device does
not have.

## C6 — Every next hop lands on a connected subnet

For each route, its `next_hop` lies inside a network that one of `fw1`'s
`SecurityFirewallInterface` addresses in `SECURITY` is numbered on.

This is the clause that earns its keep. A comparison against `ORACLE` cannot catch a typo *in*
`ORACLE`, because that is the file being compared to. Interface addresses are an independent
witness. A next hop off a connected subnet is accepted by Junos and silently never installs.

Expected mapping: `10.250.110.1`→ge-0/0/0, `10.250.210.1`→ge-0/0/1, `10.250.150.1`→ge-0/0/2,
`10.250.170.1`→ge-0/0/3, `10.250.10.1`→ge-0/0/4, `10.250.20.1`→ge-0/0/5.

## C7 — Every destination is an address-book prefix

Each route's `prefix` equals the `ip_prefix` of a `SecurityGenericAddress` in `SECURITY`:
`k8s-nodes`, `k8s-pods`, `k8s-services`, `app-hosts`, `wan-customers`, `branch-users`,
`acme-cloud`, `globex-cloud`.

**Do NOT assert the converse.** Five book entries correctly have no route of their own — three
sit inside `10.60.0.0/16`, `access-portal` (`10.112.240.33/32`) sits inside `10.112.0.0/16`, and
`fabric-infra` is never a destination, appearing six times as a rule `source_address` in the
anti-spoofing rules. "Every address-book prefix has a route" would fail on all five (R5).

## C8 — Load order

`ROUTES`'s filename sorts after the file defining `fw1`
(`objects/31_nfd41_offfabric_devices.yml`), so `infrahubctl object load objects/` resolves the
`device` reference on a fresh instance.

## C9 — Nothing else changed

No file under `schemas/` differs. No existing file under `objects/` differs. Asserted by the
reviewer and by `git`, not by this module.

## Behavioural clauses — need a running Infrahub

Covered by [quickstart.md](../quickstart.md). All were demonstrated during Phase 0 against a
scratch branch before this plan was written.

| # | Behaviour |
| --- | --- |
| B1 | The file loads without error |
| B2 | `fw1.static_routes` returns exactly eight |
| B3 | The total `RoutingStaticRoute` count rises by eight and the eleven existing fabric routes are untouched |
| B4 | All eight read back `vrf = "default"` with the file setting it nowhere |
| B5 | `gateway`, `interface`, `distance`, `tag` read back unset |
| B6 | A second load leaves eight, not sixteen |
