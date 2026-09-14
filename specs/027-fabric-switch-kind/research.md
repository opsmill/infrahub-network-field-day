# Phase 0 Research: A Device Kind for Fabric Switches

**Cycle**: 027 | **Date**: 2026-09-14 | **Branch**: `027-fabric-switch-kind`

Seven findings. The riskiest question — does a sibling kind actually work, and what exactly stops
seeing it — was answered by building one on a live branch and counting, not by reasoning.

---

## R1 — VERIFIED BY RUNNING: a sibling node validates and loads

A minimal `DcimFabricSwitch` inheriting `CoreArtifactTarget`, `DcimGenericDevice` and
`DcimPhysicalDevice` was inserted into `schemas/base/dcim.yml`, checked, loaded onto a branch
(`fsw-probe`), instantiated, queried, and then reverted.

`infrahubctl schema check`: all 38 files valid, and the diff named exactly one change:

```text
diff:
    added:
        DcimFabricSwitch: {}
    changed: {}
    removed: {}
```

Nothing else moved. Creating an instance succeeded on the first attempt.

---

## R2 — THE CENTRAL FINDING: what sees the new kind, and what does not

With one `DcimFabricSwitch` instance alongside the existing 22 devices:

```text
DcimDevice count        : 14    <- the new instance is NOT here
DcimFabricSwitch count  : 1
DcimGenericDevice count : 23    by kind: {DcimDevice: 14, ComputePhysicalServer: 7,
                                          SecurityFirewall: 1, DcimFabricSwitch: 1}
```

Both halves of the cycle's premise, measured:

- **A query naming `DcimDevice` does not see the new kind.** This is the cost, and it is real.
- **A query peering `DcimGenericDevice` sees all four kinds.** This is the saving grace, and it is
  larger than expected — see R3.

---

## R3 — Cycles 024 and 026 already future-proofed the polymorphic paths

This was not planned, and it substantially reduces the work.

| Fix | Cycle | Effect on this cycle |
| --- | --- | --- |
| `RoutingStaticRoute.device` widened to `DcimGenericDevice` | 024 | Static routes work for the new kind with **no change** |
| Cabling plan reads `name` from `DcimGenericDevice` | 026 | Cable rows survive the split; see below |

Cycle 026 fixed the cabling plan because it spread only `... on DcimDevice` and silently dropped
every cable to a `ComputePhysicalServer`. The fix moved `name` onto the generic and left only
`rack` on the concrete fragment. The consequence here: after the split, a cable to a fabric switch
still **resolves its name**, so the `if src_dev_name and dst_dev_name` guard still passes and the
row is still emitted. Only the rack column would empty.

That turns the worst case for the cabling plan from *silent total data loss* into *one blank
column* — and it happened because a bug was fixed properly two cycles ago rather than patched.

---

## R4 — The fragment sites, classified by what they actually read

Counting the sites was not enough; each was opened. There are two distinct behaviours:

| Site | Reads | After the split |
| --- | --- | --- |
| `transforms/containerlab_topology.gql:17` | `name` | **BREAKS** — topology loses all 7 switches |
| `transforms/containerlab_topology.gql:97` | `name` | **BREAKS** — same |
| `transforms/cabling_plan.gql:52` | `rack` | degrades — blank rack column |
| `transforms/cabling_plan.py:83` | `rack` | degrades — blank rack column |
| `transforms/cabling_plan.py:96` | `rack` | degrades — blank rack column |
| `service_catalog/pages/4_Fabric_View.py` ×5 | `name`, `role`, `interfaces` | **BREAKS** — the fabric view empties |

**Decision**: where the field lives on the generic (`name`, `interfaces`), read it from
`DcimGenericDevice` rather than adding a second concrete fragment. That fixes it for every device
kind at once — including any future one — and is the same remedy cycle 026 applied. Only `rack`,
which is genuinely concrete, needs a `... on DcimFabricSwitch` fragment.

`role` needs care: it exists on both kinds but with **different dropdown choices** (FR-008), so it
must stay on the concrete fragments rather than move to the generic.

---

## R5 — SUPERSEDED AT TASK TIME — see R8

**This finding was wrong, and the correction is R8.** It is left in place rather than rewritten,
because how it was wrong matters more than what it said.

## R5 (as written) — The three AVD queries are the whole of the hard part

```text
generators/avd_device_hostvar.gql:2    DcimDevice(name__value: $name)
transforms/avd_device_config.gql:2     DcimDevice(name__value: $name)
transforms/avd_anta_catalog.gql:2      DcimDevice(name__value: $name)
```

Each takes a device name and renders one switch. Retargeting them to `DcimFabricSwitch` is
mechanical. `transforms/frr_config.gql` has two `DcimDevice(...)` filters and **must not change**:
its targets are routers, which keep the kind.

The Python side is five places: `generate_pod.py:244` (super_spine), `generate_rack.py:179`
(spine), `generate_server_cabling.py:56` (leaf/l2leaf), `asn.py:46`, and the single creation path
`src/solution_arista_avd/generator.py:712`. `src/solution_arista_avd/cabling.py` uses `DcimDevice`
only as a type hint.

---

## R8 — THE CORRECTION: R4 and R5 undercounted, because the grep was too narrow

Found while generating tasks, by running the enumeration across **`checks/`, `src/` and Python
string literals** for the first time. R4 and R5 searched `transforms/` and part of `generators/`.

| Surface | R4/R5 said | Actually |
| --- | --- | --- |
| GraphQL query roots naming `DcimDevice` | 3 | **8** — 6 to retarget, 2 in `frr_config` that must not change |
| `... on DcimDevice` fragment sites | 6 | **20**, across 10 files |
| Python places | 5 | **12** typed call sites, plus 7 string-literal kind checks and 3 raw mutation strings |

### The three that fail silently, and were invisible to a fragment grep

These are not GraphQL fragments. They are Python comparing a kind name as a **string**, so no
amount of grepping for `... on DcimDevice` would ever have surfaced them:

```python
transforms/containerlab_topology.py:202
    if node.typename != "DcimDevice" or node.name is None or not node.name.value:
        continue                      # <- drops all 7 switches, emits a valid empty topology

generators/generate_avd_device_hostvar.py:2786
    ((raw_data.get("DcimDevice", {}).get("edges") or [{}])[0].get("node") or {})
                   # <- the response key changes with the query root; returns {} silently

checks/cv_config_check.py:57
    device_edges = normalized.get("DcimDevice", {}).get("edges", [])
```

The first is the sharpest in the cycle. `collect_devices` would `continue` past every fabric
switch and render a topology with the 7 servers and no switches — **no error, valid YAML.**

Also missed: three raw GraphQL mutation strings, `DcimDeviceUpsert(...)` in
`generators/asn.py:21` and `src/solution_arista_avd/generator.py:1063` and `:1087`. The
`vtep_loopback_ip` one fails loudly after the field moves; the two `asn` ones are the quiet kind.

### Why this happened, in one sentence

**A count established from a narrow search was carried forward into three documents without being
re-derived** — the same shape as the "12+7 lines" figure that survived three commit messages,
`AGENTS.md`, `.infrahub.yml` and two specs across cycles 023 to 026.

It was caught at task time rather than during implementation, which is the cheapest place left to
catch it. The lesson the cycle should keep: *the grep that generates tasks must be wider than the
grep that wrote the research*, because tasks are the first document that has to name every file.

---

## R6 — `SecurityFirewall` is the worked example, already in the tree

`schemas/dcim_extensions.yml` records the decision in prose:

> There is deliberately no `firewall` value: … `SecurityFirewall` … inherits `DcimGenericDevice`
> and `DcimPhysicalDevice`, so a firewall is its own device kind rather than a `DcimDevice` with a
> role.

And `junos_config.gql` targets `SecurityFirewall(name__value: $device)` by name, exactly as the
three AVD queries will target `DcimFabricSwitch`. The pattern is not being invented; it is being
applied a second time.

**Consequence for FR-002**: copy `DcimDevice`'s `inherit_from` verbatim rather than designing a
hierarchy. `SecurityFirewall` inherits two of the three generics and gets `CoreArtifactTarget`
from the marketplace schema; the new kind needs all three because it carries artifacts.

---

## R7 — The boundary is `ROLE_TO_AVD_TYPE`, and it is already exact

```python
ROLE_TO_AVD_TYPE = {
    "super_spine", "spine", "leaf", "border_leaf", "l2leaf",
    "l2spine", "l3spine", "p", "pe", "rr",
}
```

Ten roles, and `get_avd_type` raises `ValueError` on anything else. The non-EOS roles —
`isp_edge`, `isp_core`, `internet_edge`, `customer_edge`, `branch_router`, `k8s_node` — are
deliberately absent.

So the split line already exists in code and needs no invention. Worth noting that `p`, `pe` and
`rr` are in the map but marked ⬜ in `supported-capabilities.md` ("excluded from the generated
topology"), so they are fabric-kind roles with no instances — they belong on the new kind
regardless.

---

## Summary of decisions

| # | Decision | Rationale |
| --- | --- | --- |
| R1 | Sibling node, three generics copied from `DcimDevice` | Validated and loaded on a live branch |
| R2 | Accept that `DcimDevice` queries stop seeing switches | Measured; it is the cost of the split |
| R3 | Change nothing for static routes or cable-row survival | Cycles 024 and 026 already generalised those paths |
| R4 | Read `name`/`interfaces` from the generic; fragment only `rack` and `role` | Fixes every kind at once; `role` differs per kind so it stays concrete |
| R5 | ~~Retarget three queries and five Python sites~~ **superseded by R8** | The enumeration was too narrow; see R8 |
| R8 | Retarget 6 query roots, 20 fragments, 12 Python call sites, 7 string checks, 3 mutation strings | Re-derived across `checks/`, `src/` and string literals at task time |
| R6 | Follow `SecurityFirewall` exactly | The pattern is already in the tree and documented |
| R7 | `ROLE_TO_AVD_TYPE` is the boundary | Already exact, already guarded by a raise |

## No spec amendments required

Phase 0 overturned nothing in the spec. R3 and R4 make the cycle **smaller** than the spec
assumed — the cabling plan degrades rather than breaks, and static routes need no work at all —
but no requirement becomes wrong. FR-014 is refined rather than replaced: prefer the generic over
a second fragment, which the spec already stated as the preference.
