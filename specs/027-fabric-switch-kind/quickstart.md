# Quickstart Validation: A Device Kind for Fabric Switches

**Cycle**: 027 | **Branch**: `027-fabric-switch-kind`

Thirteen steps. Step 0 is the one that cannot be repeated — **capture the baseline before
anything is destroyed**, because every comparison in SC-003 to SC-006 is against output that
stops existing the moment the environment is rebuilt.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
export INFRAHUB_API_TOKEN=...    # writes need auth
```

The lab repo must be checked out alongside, or the FRR and Junos comparisons skip rather than
fail.

## 0. Capture the baseline — do this FIRST

```bash
BASE=/tmp/027-baseline && mkdir -p $BASE
```

Pull every artifact's current content into `$BASE`: the 7 EOS configs, 7 device docs, 7 ANTA
catalogs, 1 fabric doc, 1 cabling plan, 1 ContainerLab topology, 2 Crossplane manifests, 6 FRR
configs and 1 Junos config.

**Expected**: **33** files. Verified live today, not carried from an earlier spec.

Also record the current schema shape:

```bash
uv run infrahubctl schema load schemas --dry-run 2>/dev/null || true
uv run python - <<'EOF'   # counts, for step 9
# DcimDevice: 14, DcimGenericDevice: 22 {DcimDevice 14, ComputePhysicalServer 7, SecurityFirewall 1}
EOF
```

**Expected**: `DcimDevice` 14, `DcimGenericDevice` 22. After the split these become
`DcimFabricSwitch` 7, `DcimDevice` 7, `DcimGenericDevice` still 22.

**If you skip this step you cannot prove SC-003 to SC-006**, and re-deriving the baseline after a
rebuild proves only that the new code agrees with itself.

## 1. The schema validates

```bash
uv run infrahubctl schema check schemas/
```

**Expected**: all files valid. The diff names `DcimFabricSwitch` under `added` and `DcimDevice`
under `changed`, and **nothing else**. This is L1.

If any third kind appears in the diff, a reverse side landed on the wrong node — the exact failure
C6e is written about.

**Do not `schema load` onto the live instance at this point.** Moving twelve fields off
`DcimDevice` while seven switches hold values in them is a destructive migration, and the
requester's decision (Assumption 1) is to avoid it entirely by rebuilding. Probing it here risks
the very baseline step 0 just captured.

## 2. Both ends of every identifier agree

```bash
uv run pytest tests/unit/test_dcim_schema_contract.py -q
```

**Expected**: C6e passes — every identifier declared on two ends names the same peer on both.

This is the clause worth running before anything else, because a one-way relationship produces
**no error at load time**. It surfaces later as a field that is silently always empty.

## 3. The role dropdowns are disjoint and exhaustive

**Expected**: `DcimFabricSwitch`'s ten choices equal `ROLE_TO_AVD_TYPE.keys()`; `DcimDevice`'s six
are disjoint from it; the union is today's sixteen. This is C5.

Check that `tests/unit/test_avd.py`'s `NON_AVD_DEVICE_ROLES` exclusion list is now doing less
work, not more — after the split the kinds separate what that list separated by hand.

## 4. No fragment can silently return nothing

```bash
grep -rn "\.\.\. on Dcim" transforms/ service_catalog/ generators/
```

**Expected**: every hit is accounted for by a row in C11. This is SC-008, and counting the sites
is explicitly **not** enough — each needs a named disposition.

`transforms/frr_config.gql` must appear in the grep **unchanged**. Diff it against `main`; C10
requires it byte-identical.

## 5. The offline suite

```bash
uv run pytest tests/unit -q
```

**Expected**: green, at or above **1043** — the count collected today.

## 6. Destroy and rebuild

```bash
uv run invoke destroy
uv run invoke build
uv run invoke start
uv run invoke load
```

**Expected**: schema, menus and objects load clean. The seven switches come up as
`DcimFabricSwitch` (C12) and the seven routers as `DcimDevice`.

This is the step Assumption 1 buys. Nothing here is a migration; the switches are seeded, so
changing `spec.kind` is the entire data story.

## 7. The generators run

```bash
uv run invoke avd --topology
```

**Expected**: `generate-fabric` → `generate-pod` → `generate-rack` create switches of the **new**
kind and cable them, then the two AVD generators populate hostvars and structured configs for all
seven.

`--topology` is required on a fresh instance and only there: `generate-pod` is destructive on
re-run — it takes spines from 9 interfaces to 4, after which `generate-rack` dies with an
`IndexError`. That is why cycle 026 put the topology generators behind the flag.

## 8. Artifacts regenerate

**Expected**: **33** artifacts again, the same ten definitions with the same per-definition counts
as step 0.

A missing definition here means a target group lost its members — the likeliest cause being
`avd_devices` membership, which `src/solution_arista_avd/generator.py` sets in one place.

## 9. The counts moved as predicted

**Expected**: `DcimFabricSwitch` 7, `DcimDevice` 7, `DcimGenericDevice` **22** — unchanged,
because every kind still inherits it. This is L2, and the third number is the one that proves the
polymorphic paths survived.

## 10. The EOS configs are unchanged

Diff the seven rendered configs against `$BASE`, and against
`lab/avd/intended/configs/*.cfg` with device names normalised.

**Expected**: **zero lines differ** in both comparisons — the same result as before this cycle.
This is SC-003, and it is the cycle's headline claim: the split moved fields between kinds and
changed nothing a device would see.

## 11. The WAN and the firewall did not move

Diff the six FRR configs and the Junos config against `$BASE`.

**Expected**: **byte-identical**. This is SC-004 and US3 — the expected outcome, given routers
keep their kind, which is exactly why it deserves a check rather than an assumption.

## 12. The two mixed relationships still hold both kinds

**Expected**: `RoutingAsn.devices` resolves 6 routers **and** 7 switches; a tenant
`RoutingVrfStaticRoute` resolves `isp-pe1` **and** `leaf-nfd41-pod1-3-1`.

These are C6b, and they are the pair no one would have predicted from the field names — the
dispositions came from counting objects, not from reading the schema. If either now resolves only
one kind, the peer was narrowed to a concrete kind instead of widened to the generic.

## 13. The full gates

```bash
uv run invoke test
uv run invoke lint
```

**Expected**: the unit suite green at or above 1043; ruff, ruff-format, yamllint, mypy and rumdl
clean.

## Integration tests

`$infrahub-run-integration-tests` is not installed in this environment, as in cycles 020–026. The
constitution's escape clause applies and **the pull request must say so explicitly**. Steps 0–13
are the non-live alternative, and steps 6 to 12 are a fuller end-to-end exercise than any previous
cycle in this sequence ran.

## Merging

This cycle changes schema, so cycle 023's trap is live: `infrahubctl graphql export-schema` has
**no `--branch` flag**. Do not load this cycle's schema into Infrahub `main` to regenerate
`schema.graphql` — that is what made 023's Infrahub merge fail on a `SchemaAttribute` uniqueness
violation.

Merge first, regenerate `schema.graphql` and `protocols.py` after, as cycles 024 and 026 did.
