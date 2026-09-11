# Acceptance Evidence

**Feature**: `specs/014-k8s-leaf-peering-svi` | **Date**: 2026-09-10
**Git branch**: `014-k8s-leaf-peering-svi` (based on `acf7011`, the cycle 012 merge)
**Infrahub branch**: `svi-model` | **Infrahub**: 1.10.6 | **SDK**: 1.22.0

Every command below was run; every block is real output, trimmed only for width. Where
something could not be measured, it says so rather than being quietly omitted — see
"Gaps and caveats" at the end.

---

## SC-001 — the object files load without error

```text
$ uv run infrahubctl object load objects/36_nfd41_peering_svis.yml --branch svi-model
[23:38:42] INFO     Created node: InterfaceVirtual : 18d419fc-161a-aa38-2ddb-c518872536b7
           INFO     Created node: InterfaceVirtual : 18d419fc-2158-eafd-2ddf-c51b99366f01
```

A full `uv run infrahubctl object load objects/ --branch svi-model` was then run three more
times across the cycle, each exiting 0.

## SC-002 — exactly two peering SVIs, one per k8s leaf

```json
{"InterfaceVirtual": {"count": 2, "edges": [
  {"node": {"name": "Vlan110", "index": "110", "role": "peering", "status": "active",
            "dot1q_id": 110, "device": "leaf-nfd41-pod1-1-1",
            "ip_address": null, "ip_addresses": {"count": 1, "edges": ["10.110.0.2/24"]}}},
  {"node": {"name": "Vlan110", "index": "110", "role": "peering", "status": "active",
            "dot1q_id": 110, "device": "leaf-nfd41-pod1-1-2",
            "ip_address": null, "ip_addresses": {"count": 1, "edges": ["10.110.0.3/24"]}}}]}}
```

Three things in that response are worth reading deliberately:

- `ip_addresses.count` is 1 on each — the address is attached (FR-013).
- `ip_address` is `null` on each — the *other*, one-directional relationship was deliberately
  left alone (research R2). This is the field whose accidental use would have made the whole
  cycle a no-op.
- `index` computed to `"110"`. This is the read-only Jinja2 attribute from
  `schemas/dcim_extensions.yml`; research R4 predicted `110` and asserted it rather than
  assuming a computed attribute would tolerate a name it had never seen.

## SC-003 — the traversal the cycle exists to create

**Before** (captured on `svi-model` before any change — this is the defect):

```json
{"IpamIPAddress": {"count": 2, "edges": [
  {"node": {"address": "10.110.0.2/24", "interface": {"node": null}}},
  {"node": {"address": "10.110.0.3/24", "interface": {"node": null}}}]}}
```

**After**:

```json
{"IpamIPAddress": {"count": 2, "edges": [
  {"node": {"address": "10.110.0.2/24", "interface": {"node": {
      "__typename": "InterfaceVirtual", "display_label": "Vlan110",
      "device": {"node": {"display_label": "leaf-nfd41-pod1-1-1"}}}}}},
  {"node": {"address": "10.110.0.3/24", "interface": {"node": {
      "__typename": "InterfaceVirtual", "display_label": "Vlan110",
      "device": {"node": {"display_label": "leaf-nfd41-pod1-1-2"}}}}}}]}}
```

`IpamIPAddress -> interface -> device` now resolves for both addresses, and lands on the leaf
each session names as its peer. This is contract C1.

Note this was verified from the **address** side, not the interface side. Querying the
interface and seeing an address attached would have passed even if the wrong relationship had
been used; only this direction distinguishes the two.

## SC-004 — the shared VARP gateway is not a candidate

```json
{"IpamIPAddress": {"count": 0, "edges": []}}    // query: address in [10.110.0.1/24, 10.110.0.1/32]
```

Stronger than "unattached": `10.110.0.1` does not exist as an address object at all. It lives
on `EvpnSvi.ip_virtual_router_addresses` as intent, where it belongs. Nothing can attach it
because there is nothing to attach.

## SC-005 — the derivation is unambiguous and reproduces the declared value

Every one of the 26 seeded `IpamIPAddress` objects was scanned and filtered to the peering
prefix. The scan was checked for pagination truncation first (`count` reported 26, the query
returned 26 edges), because an under-fetched enumeration would have made this look cleaner than
it is:

```text
scanned 26 address objects
inside 10.110.0.0/24: 2
  10.110.0.2/24      leaf-nfd41-pod1-1-1/Vlan110
  10.110.0.3/24      leaf-nfd41-pod1-1-2/Vlan110
```

Cross-referenced against the sessions:

| Session | `peer_device` | Declared `peer_address` | Derived from the device | Match |
| --- | --- | --- | --- | --- |
| `k8s-leaf1` | `leaf-nfd41-pod1-1-1` | `10.110.0.2/24` | `10.110.0.2/24` | ✅ |
| `k8s-leaf2` | `leaf-nfd41-pod1-1-2` | `10.110.0.3/24` | `10.110.0.3/24` | ✅ |

Exactly one candidate per device, and it equals the hand-declared value. This is contracts C2
and C3, and it is what makes the follow-up cycle a refactor that moves no value.

## SC-006 — nothing that reaches the cluster moved

**The baseline had to be reconciled before it could be trusted.** The first capture did not
match the recorded oracle:

```text
raw CLI stdout   495 bytes  9ee73ec9799d1ceba593b9e27ead129a
single-newline   494 bytes  0d800c9d5005b5fdb6b371bb5627d143   <- cycle 011/012 value
```

`infrahubctl transform` prints one extra trailing newline versus the bytes Infrahub stores for
the artifact — the same observation cycle 011 recorded from the other direction. Left
unreconciled, this looks exactly like a regression. Both forms are used below: `diff` against
the raw capture, digest against the normalised bytes.

```text
$ diff /tmp/svi-baseline.yaml /tmp/svi-after.yaml
BYTE-IDENTICAL

$ md5sum /tmp/svi-baseline.yaml /tmp/svi-after.yaml
9ee73ec9799d1ceba593b9e27ead129a  /tmp/svi-baseline.yaml
9ee73ec9799d1ceba593b9e27ead129a  /tmp/svi-after.yaml

normalised after-digest: 0d800c9d5005b5fdb6b371bb5627d143
oracle                 : 0d800c9d5005b5fdb6b371bb5627d143
MATCH: True
```

Re-checked twice more — after the repeated loads (SC-007) and once more against the final file
state after the annotation edit. Byte-identical every time.

**That is the same value cycles 011 and 012 recorded**, so the artifact is now unchanged across
three cycles and two changes of mechanism.

### Beyond the declared oracle: what the AVD generator sees

The declared oracle covers the Crossplane artifact only. The new interfaces sit closest to the
AVD pipeline, so that was measured too.

The obvious check turned out to be worthless and is reported rather than dressed up:

```text
$ uv run infrahubctl transform avd_eos_config name=leaf-nfd41-pod1-1-1 --branch svi-model
! No structured config available for leaf-nfd41-pod1-1-1
```

57 bytes of stub. The AVD generator chain has not run on this branch, so that render would have
been identical before and after no matter what the change did — a passing check that proves
nothing.

What was done instead: run the hostvar generator's **own** query (`generators/avd_device_hostvar.gql`)
against the branch for an affected leaf, before and after. That is exactly the generator's input,
so a diff shows whether the change can reach AVD at all.

```text
before  38a967d30b8bcd38cf9bc7a2c9830ec5   323196 bytes
after   62865aad6bfafde7d804e55142d52e66
```

It **does** differ — and the difference is precisely characterised:

```text
every new-interface entry is a field-less {__typename, id} stub: OK
after-minus-new-stubs == before : True
```

The two new interfaces appear in the `interfaces` edges carrying `__typename` and `id` and
nothing else, because the query selects interface fields only inside `... on InterfacePhysical`
fragments. Removing exactly those stubs makes the input identical to before. The generator then
discards them explicitly — `if _typename(...) != "InterfacePhysical"` at
`generators/generate_avd_device_hostvar.py` lines 802, 1137, 1202 and 2109.

So the honest statement is: the generator's input changed by two empty stubs, and cannot change
its output. That is a measurement, not the argument research R5 started with.

## SC-007 — idempotent

`uv run infrahubctl object load objects/ --branch svi-model` was run three times after the
change. Each run logs "Created node" for the SVIs — that is the loader's wording for an upsert,
and the node IDs give it away:

```text
run 1: InterfaceVirtual : 18d419fc-161a-aa38-2ddb-c518872536b7
       InterfaceVirtual : 18d419fc-2158-eafd-2ddf-c51b99366f01
run 2: InterfaceVirtual : 18d419fc-161a-aa38-2ddb-c518872536b7   <- same IDs
       InterfaceVirtual : 18d419fc-2158-eafd-2ddf-c51b99366f01
run 3: identical
```

Same IDs each time: matched by human-friendly id and updated in place, not duplicated.

Counts after the repeated loads:

```json
{"all_virtual_interfaces": 16, "peering_svis": 2, "ip_addresses": 26, "peerings": 2}
```

16 = the 14 pre-existing template-generated `Loopback0` plus the 2 new `Vlan110`. Each SVI
still holds exactly 1 address. The render after the repeated loads was still byte-identical to
the baseline.

## SC-008 — the scope boundary held

```text
$ git status --short
 M objects/34_nfd41_cluster.yml
?? objects/36_nfd41_peering_svis.yml
?? tests/unit/test_peering_svi_seed_data.py

$ ... | grep -E "schemas/|generators/|transforms/"
NONE - scope boundary held
```

No schema change (FR-019), no generator change (FR-020). The only edit to an existing file is
`objects/34_nfd41_cluster.yml`, and it was mechanically verified to be comment-only:

```text
$ git diff --unified=0 objects/34_nfd41_cluster.yml | (non-comment changed lines)
OK - every changed line is a comment
```

That matters for two reasons: FR-021 requires the declared `peer_address` values to survive
untouched, and a value change there would have moved the artifact.

## SC-009 — tests and linters

```text
$ uv run pytest tests/unit
842 passed in 8.33s
```

832 before, 842 after — the 10 new contract tests, none failing.

| Gate | Result |
| --- | --- |
| `uv run invoke lint-ruff` | ✅ All checks passed; 94 files already formatted |
| `uv run invoke lint-yaml` | ✅ clean |
| `uv run invoke lint-mypy` | ✅ Success: no issues found in 8 source files |
| `uv run invoke lint-markdown` | ✅ No issues found in 34 files |
| `uv run invoke lint-prose` | ✅ 7 errors, 4 warnings — **unchanged** from the known baseline |

The prose findings are all pre-existing and all in `docs/`
(`extending.md`, `home.md`, `supported-capabilities.md`, `schemas.md`); none is in a file this
cycle touched, and no new vocabulary entry was needed.

`ruff format` did reformat the new test file once, on its first run. Fixed and re-verified;
the full suite was re-run afterwards and still passes at 842.

### The tests were checked for whether they can actually fail

A contract test that cannot fail is decoration. The two most important guards were
mutation-tested against the seed file, then the file was restored:

**Mutation 1 — `ip_addresses` renamed to `ip_address`** (the silent failure this cycle exists
to prevent: loads cleanly, shows an address in the UI, leaves the traversal dead):

```text
FAILED test_each_peering_svi_carries_exactly_one_address
FAILED test_peering_svi_addresses_match_the_declared_peer_addresses
FAILED test_exactly_one_seeded_address_per_leaf_inside_the_peering_prefix
FAILED test_peering_svis_use_ip_addresses_not_ip_address
4 failed, 6 passed
```

**Mutation 2 — leaf 1's address changed to the VARP gateway `10.110.0.1`**:

```text
FAILED test_peering_svi_addresses_match_the_declared_peer_addresses
FAILED test_peering_svis_never_carry_the_varp_gateway
2 failed, 8 passed
```

Restored, 10 passed.

---

## Success criteria summary

| Criterion | Status |
| --- | --- |
| SC-001 objects load without error | ✅ |
| SC-002 exactly 2 peering SVIs, one per leaf | ✅ |
| SC-003 addresses resolve through `interface` to the right device | ✅ |
| SC-004 VARP gateway attached to no interface | ✅ (stronger: not an object at all) |
| SC-005 derivation single-valued and equal to the declared value | ✅ |
| SC-006 artifact byte-identical, digest `0d800c9d…` | ✅ |
| SC-007 repeated loads idempotent | ✅ |
| SC-008 no `schemas/` or `generators/` change | ✅ |
| SC-009 tests ≥ baseline, all linters clean | ✅ 842 (was 832) |

---

## Gaps and caveats

Things a reviewer should know that the table above does not say:

1. **The worktree started behind `main`.** It was based on `f28b794`, before cycle 012 merged.
   Since the whole premise of this cycle is cycle 012's annotation and generator, the feature
   branch was created from `acf7011` (the cycle 012 merge, and `main`'s tip) after confirming
   `f28b794` is an ancestor — a fast-forward, not a merge. `main` itself was never checked out
   or modified.

2. **The recorded checksum did not match on first capture.** It reconciled exactly once the
   CLI's extra trailing newline was normalised away (SC-006). If a future cycle sees
   `9ee73ec9…` from `infrahubctl transform`, that is the same artifact, not a regression.

3. **The AVD EOS config render is not a meaningful check on this branch** and was not counted
   as one. The generator chain has not run there, so it returns a 57-byte stub. The hostvar
   query diff was substituted; see SC-006. Nobody has rendered a *real* AVD config before and
   after this change — the claim rests on the type guards plus the measured fact that the new
   interfaces reach the generator as field-less stubs.

4. **Integration tests were not run.** The project constitution requires them for every
   Infrahub *code* change; this cycle changes no code, only data, so there is no new path to
   exercise. This is recorded as a deviation in `plan.md` rather than waved away, and a
   reviewer who disagrees should say so.

5. **The `k8s-leaf1`/`k8s-leaf2` device duplication is untouched.** The lab models the same two
   physical switches twice; the duplicates carry a `Loopback0` and no peering address. This is
   pre-existing and out of scope, but it is a live hazard for the follow-up cycle, which must
   resolve peers through `peer_device` and not by hostname. Recorded in research R3, the seed
   file's header, and a test (`test_peering_svis_target_the_devices_the_sessions_name`).

6. **`EvpnSviNode.ip_address` is still an attribute, not a relationship.** The fabric therefore
   now records each leaf's peering address in *two* places — as an `EvpnSviNode` attribute and
   as an attached `IpamIPAddress`. They agree today and a test enforces that the SVI side
   agrees with the sessions, but nothing enforces agreement between the SVI and `EvpnSviNode`.
   Converting that attribute to a relationship would collapse the duplication and is the better
   long-term model; it is a schema change that moves AVD output through three call sites, so it
   was deliberately deferred (research R1) rather than smuggled into a data cycle. **This is
   the single thing about this cycle most worth a reviewer's second opinion.**

7. **Nothing consumes the new edge yet.** `peer_address` is still hand-declared and still
   authoritative. The cycle delivers the precondition, not the payoff; the follow-up generator
   change is what collects it.
