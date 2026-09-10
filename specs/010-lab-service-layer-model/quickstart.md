# Quickstart: Validating the Technical and Service Layers

**Feature**: `specs/010-lab-service-layer-model` | **Date**: 2026-09-10

How to prove this schema feature works, in the order the proofs get expensive. Steps 1–3
need no server. Steps 4–7 need the local stack. Step 8 is the acceptance oracle.

Design details are not repeated here — see [data-model.md](./data-model.md) for kinds and
fields, [contracts/schema-kinds.md](./contracts/schema-kinds.md) for the published
surface, and [research.md](./research.md) for why.

---

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # must report Connection Status ✅ and Infrahub 1.10.6
```

If the stack is not running:

```bash
uv run invoke start
```

For repeated `infrahubctl` calls in one shell:

```bash
alias ihctl='uv run infrahubctl'
```

---

## Step 1 — Lint the new YAML (no server)

```bash
uv run yamllint schemas/
uv run invoke lint-yaml
```

**Expected**: clean. Catches indentation and duplicate-key errors before anything
parses the files semantically.

---

## Step 2 — Run the schema contract tests (no server)

The primary quality gate, following the repository's existing
`test_*_schema_contract.py` pattern.

```bash
uv run pytest tests/unit/test_service_layer_schema_contract.py \
              tests/unit/test_kubernetes_schema_contract.py \
              tests/unit/test_security_schema_contract.py \
              tests/unit/test_wan_schema_contract.py -v
```

**Expected**: all pass. These assert the spec's functional requirements directly against
the YAML — node presence, attribute kinds, relationship cardinality and `identifier`,
`on_delete: no-action` on every service→technical relationship, dropdown choices,
uniqueness-constraint shape, and HFID paths.

The one assertion no server-side check can make is the layering direction. This test is
the enforcement of FR-080 and SC-009:

```python
def test_no_technical_schema_references_a_service_kind() -> None:
    """FR-080: the technical layer must be usable with the service layer absent."""
    technical = [
        "schemas/kubernetes/kubernetes.yml",
        "schemas/security/security.yml",
        "schemas/wan/wan.yml",
        "schemas/organization_extensions.yml",
    ]
    # For each file, walk every node/generic/extension relationship and assert
    # no `peer` value starts with "Service".
```

---

## Step 3 — Confirm the layers are separable (no server)

```bash
# Every service kind must inherit GeneratorTarget (FR-081)
grep -c 'GeneratorTarget' schemas/service/*.yml

# Exactly one place couples DCIM to the service layer (FR-052, R6)
grep -rn 'peer: ServiceGeneric' schemas/ | wc -l   # expect 2 (device + interface)
grep -rln 'peer: ServiceGeneric' schemas/          # expect only schemas/service/service.yml
```

**Expected**: the `peer: ServiceGeneric` lines appear in `schemas/service/service.yml`
and nowhere else. If they appear in a technical file, the layering is broken regardless
of what the schema check says.

---

## Step 4 — Check the schema against a branch (server)

```bash
uv run infrahubctl branch create svc-layer
uv run infrahubctl schema check schemas/ --branch svc-layer
```

**Expected**: zero validation errors, plus a diff listing 3 added generics, 20 added
nodes, and 4 modified kinds (`DcimGenericDevice`, `DcimInterface`, `DcimDevice`,
`IpamPrefix`). This is SC-001.

**Expected failures worth recognizing** — each maps to a rule in the schemas skill:

| Error | Cause | Fix |
| --- | --- | --- |
| `peer not found` | `peer:` missing the namespace | Use the full kind, e.g. `IpamPrefix` not `Prefix` |
| `identifier mismatch` | Component/Parent pair disagrees | Both sides share one `identifier` |
| `uniqueness constraint references unknown field` | `__value` on a relationship, or missing on an attribute | `__value` for attributes, bare for relationships |
| `unknown field` | Property typo — `additionalProperties: false` | Check spelling against the reference |

---

## Step 5 — Prove the technical layer loads standalone (server) — SC-009

The check that makes the layering claim real rather than stylistic:

```bash
uv run infrahubctl branch create tech-only
uv run infrahubctl schema check \
  schemas/base schemas/kubernetes schemas/security schemas/wan \
  schemas/organization_extensions.yml schemas/dcim_extensions.yml \
  schemas/ipam_extensions.yml schemas/generator.yml \
  --branch tech-only
```

**Expected**: zero errors. The technical files resolve without `schemas/service/`
present.

Then confirm the reverse fails, which is the point:

```bash
uv run infrahubctl schema check schemas/service --branch tech-only
```

**Expected**: errors naming unresolvable peers (`KubernetesCluster`, `SecurityZone`,
`WanTenant`). The service layer depends on the technical layer and not the other way
round.

---

## Step 6 — Load and prove convergence (server)

```bash
uv run infrahubctl schema load schemas --branch svc-layer --wait 30
uv run infrahubctl schema check schemas/ --branch svc-layer
```

**Expected**: the second `schema check` reports **no diff**. A load that converges is
idempotent, which is the alternative evidence the plan's Complexity Tracking offers in
place of the unavailable `$infrahub-run-integration-tests` skill.

---

## Step 7 — Regenerate protocols and type-check (server)

```bash
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
uv run mypy --show-error-codes src/solution_arista_avd
uv run invoke lint
```

**Expected**: `protocols.py` gains 3 generic and 20 node classes; mypy passes. This is
SC-002 and Constitution III, and it is a compile-time proof that every kind, peer, and
inheritance chain resolves.

Sanity-check the inheritance the design depends on:

```bash
grep -nE 'class (ServiceFabricApp|ServiceAppAccess|ServiceL3vpn)\(' \
  src/solution_arista_avd/protocols.py
```

**Expected**: `ServiceFabricApp` and `ServiceAppAccess` list both `CoreArtifactTarget`
and `GeneratorTarget`; `ServiceL3vpn` lists `GeneratorTarget` but not
`CoreArtifactTarget` (research R3).

`protocols.py` is generated — never hand-edit it to satisfy mypy.

---

## Step 8 — Acceptance: can the model hold the lab?

The oracle for SC-003, SC-004, SC-005 and SC-007. Each is answered by transcription
against a lab file, not by running the lab.

| Check | Source | Success criterion |
| --- | --- | --- |
| Both WAN tenants, all 3 sites, both attachment kinds, the internet peering, the branch | `../lab/wan/tenants.yml` | SC-003 — every field has a modeled destination |
| 6 zones, ~15 address entries, 4 groups, 6 zone-pair policies with order preserved | `../lab/configs/fw/vsrx/junos.conf` | SC-004 |
| Every field the `FabricPeering`, `FabricApp`, `AppAccess`, `FirewallAccess` resources consume | `../lab/crossplane/{platform,apps,access}/` | SC-005 |
| acme and globex differ by one `ServiceInternetAccess` and nothing else | `../lab/wan/tenants.yml` | SC-007 |

Practical way to run it — walk each source file field by field and record the
destination kind and field. Anything with no destination is a gap in the schema, not a
gap in the lab. Two spot checks worth doing by hand:

```bash
# SC-007: the only difference between the two tenants
grep -n 'internet:' ../lab/wan/tenants.yml
# acme: internet: true, globex: internet: false — must reduce to the
# presence/absence of one ServiceInternetAccess object, no other field

# SC-008: no new schema restates a prefix as text
grep -rnE 'kind: (IPNetwork|IPHost)' schemas/kubernetes/ schemas/security/ \
  schemas/wan/ schemas/service/
# Expect no hits. Every network is a relationship to IpamPrefix / IpamIPAddress
```

---

## Step 9 — Clean up

```bash
uv run infrahubctl branch list
# delete the throwaway branches via the UI or API; keep svc-layer if it holds work
```

---

## What is deliberately not validated here

| Not tested | Why | Where it lands |
| --- | --- | --- |
| That a generator materializes technical objects from a service | No generator is written this cycle | Generator cycle |
| That a transform renders a valid Crossplane manifest | No transform is written this cycle | Transform cycle |
| That the lab's objects actually load | No object data is written this cycle | Object cycle |
| That new kinds appear under a service menu group | `menus/menu.yml` is untouched (research R12) | Menu cycle |
| Prefix containment, exactly-one-of, and acyclicity rules | Not expressible as schema constraints | `checks/` cycle — see data-model §13 |

---

## Failure triage

| Symptom | Likely cause | Where to look |
| --- | --- | --- |
| `ValueError: Unknown device role: firewall` | A non-EOS device joined `avd_devices` | research R7 — the invariant is that it must not |
| `SecurityZone` cannot be created | `fw1` does not exist as a `DcimDevice` | data-model §1 — object-cycle prerequisite |
| `owner` cannot be set on a service | `OrganizationCustomer` missing or not loaded | research R8 |
| `schema check` clean but the layering test fails | A technical file gained a `peer: Service*` | Step 3 |
| Contract test passes but `schema check` fails on a peer | YAML parsing cannot resolve cross-file kinds | Both gates are needed; neither replaces the other |
