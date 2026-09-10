# Implementation Plan: Technical and Service Layers for the Full NFD41 Lab

**Branch**: `nfd41-fabric-model` (feature directory `010-lab-service-layer-model`) | **Date**: 2026-09-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/010-lab-service-layer-model/spec.md`

## Summary

Add two schema layers to the repository. A **technical layer** modeling everything in
the NFD41 lab that lives off the Arista fabric — the Kubernetes cluster and its Cilium
BGP sessions, the vSRX perimeter firewall in full, and the ISP, WAN tenants, sites and
branch office — and a **service layer** above it whose nodes express ordered intent and
carry no per-device detail.

The approach is nine schema files under `schemas/`, plus one extension to
`schemas/dcim_extensions.yml` to add the non-EOS device roles the new domains need. The
layering is enforced structurally: technical files never name a service kind, so they
load standalone, while service files depend on technical kinds one way only. Each
service kind inherits the project's existing `GeneratorTarget` generic (giving the
`checksum` attribute the constitution's idempotence principle requires) and, where its
intent is delivered to the cluster as a Crossplane manifest, `CoreArtifactTarget`. That
is the whole mechanism by which "a generator sits underneath the services schema" and
by which a later cycle can attach an artifact definition without touching the schema
again.

Validation is unit-test-first, following the repository's established
`test_*_schema_contract.py` pattern: the schema YAML is parsed and asserted against the
spec's functional requirements, so the design is checkable without a live server. A
live `infrahubctl schema check` and protocol regeneration follow.

## Technical Context

**Language/Version**: Python >=3.11,<3.14 (schema artifacts are YAML; the generated
protocols and the contract tests are Python)

**Primary Dependencies**: Infrahub 1.10.6, `infrahub-sdk[all]>=1.19.0`,
`infrahubctl` for `schema check` / `schema load` / `protocols`, PyYAML for the contract
tests. No new runtime dependency is introduced.

**Storage**: Infrahub graph (Neo4j) — the schema defines nodes and generics; no separate
persistence layer.

**Testing**: `pytest` unit tests following the existing
`tests/unit/test_*_schema_contract.py` pattern (parse the YAML, assert kinds,
attribute kinds, relationship cardinality/identifier/on_delete, and uniqueness
constraints). `uv run infrahubctl schema check schemas/` for server-side validation.
`yamllint` via `uv run invoke lint`.

**Target Platform**: Infrahub 1.10.6 running locally via the project's Docker Compose
stack (`uv run invoke start`), reachable at `http://localhost:8000` — verified by
`infrahubctl info` during the specify cycle.

**Project Type**: Infrahub schema definitions inside an existing Infrahub reference-design
repository. Not an application.

**Performance Goals**: N/A — schema loading is a one-time operation. The only
performance-adjacent constraint is that `infrahubctl schema load` must converge; the
project's `invoke load-schema` already allows for that.

**Constraints**:

- Schema-first (Constitution I): nothing in `generators/`, `transforms/`, or `src/` may
  reference the new kinds until the schema is loaded and protocols are regenerated.
- No node may redefine what the fabric already models. Every prefix and address is a
  relationship to `IpamPrefix` / `IpamIPAddress` (spec FR-010, FR-022, FR-044).
- New device roles MUST NOT be added to `ROLE_TO_AVD_TYPE` in
  `src/solution_arista_avd/avd.py`, and non-EOS devices MUST NOT join the `avd_devices`
  group. See [research.md](./research.md) R7 — `get_avd_type` raises `ValueError` on an
  unmapped role.
- The technical layer must load without the service layer (spec SC-009), which forbids
  any technical→service relationship (FR-080).

**Scale/Scope**: 9 new schema files, 1 modified. 4 new namespaces (`Service`,
`Kubernetes`, `Security`, `Wan`) and 1 extended (`Organization`). 3 new generics and
25 new nodes. 7 device roles added to the existing `DcimDevice.role` dropdown. The
model must absorb the lab's 30 nodes, 6 firewall zones, 15 address-book entries, 2 WAN
tenants, 3 sites, and 1 Kubernetes cluster with 3 nodes and 2 BGP peerings.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against `.specify/memory/constitution.md` v1.2.0.

| Principle | Gate | Pre-Phase-0 | Post-Phase-1 |
| --- | --- | --- | --- |
| **I. Schema-Driven Architecture** | Schemas defined before any code references them; namespaces follow project conventions; extensions used rather than editing base schemas; protocols regenerated | ✅ PASS — this cycle is schema-only by construction, and the spec's Out of Scope section defers all consuming code | ✅ PASS — R1 confirms the four namespaces satisfy `^[A-Z][a-z0-9]+$` and collide with no Core/Internal/Builtin namespace; R6 puts the `DcimGenericDevice` / `DcimInterface` back-references in an `extensions:` block per FR-052; `schemas/base/*` is untouched |
| **II. Idempotent Operations** | Generators must be idempotent; HFID-based dedup; checksum change detection | ✅ PASS (enabling) — no generator is written here | ✅ PASS — R2 has every service kind inherit `GeneratorTarget`, supplying the `checksum` attribute the principle names, and every node carries a `human_friendly_id` (FR-060) so the later generators have a natural key rather than a UUID |
| **III. Type Safety** | Typed models; protocols regenerated, not hand-edited; mypy passes with `disallow_untyped_defs` | ✅ PASS | ✅ PASS — protocol regeneration is a numbered implementation step, not a follow-up; the contract tests are fully annotated; no `*_query.py` is written this cycle because no GraphQL query is |
| **IV. Test-Required Quality** | Unit tests for changed behavior; integration tests for Infrahub changes; all linters pass | ⚠️ CONDITIONAL — see Complexity Tracking | ⚠️ CONDITIONAL — unit coverage is fully planned via the repo's `test_*_schema_contract.py` pattern, and `yamllint`/`rumdl` pass through `invoke lint`. The constitution's mandated `$infrahub-run-integration-tests` skill is **not installed in this environment**; a documented alternative is proposed below |
| **V. Convention-Based Structure** | Established naming and directory organization; deviations justified | ✅ PASS | ✅ PASS — R11 places files by domain under `schemas/`, matching the existing `schemas/{avd,base,compute,cv,evpn,lag,mlag,routing,vlan,vrf}/` split; no generator or transform naming applies this cycle |

### Gate detail — Principle IV

Two of the constitution's three quality gates are satisfiable here and one is not:

- **Unit tests** — satisfiable and planned. The repository already validates schema
  design with YAML-parsing contract tests (`test_dci_schema_contract.py`,
  `test_fabric_pool_schema_contract.py`, `test_evpn_gateway_schema_contract.py`,
  `test_l2ls_services_schema_contract.py`). This feature adds four more in the same
  shape, one per domain. These assert the spec's FRs directly and need no server.
- **Linters** — satisfiable. `uv run invoke lint` covers `yamllint` over the new schema
  files and `mypy` over the regenerated protocols.
- **Integration tests** — the constitution requires `$infrahub-run-integration-tests`
  for every Infrahub code change and states it "owns integration-suite execution in the
  project-designated validation environment". That skill is not present in this
  environment (checked: no `~/.claude/skills`, nothing matching in `.agents/skills/` or
  `.claude/skills/`). This is recorded in Complexity Tracking with the alternative
  validation plan the constitution's own escape clause requires, and it needs a
  maintainer decision rather than a silent pass.

## Project Structure

### Documentation (this feature)

```text
specs/010-lab-service-layer-model/
├── plan.md              # This file
├── research.md          # Phase 0 output — 14 decisions
├── data-model.md        # Phase 1 output — every kind, attribute and relationship
├── quickstart.md        # Phase 1 output — validation guide
├── contracts/
│   └── schema-kinds.md  # Phase 1 output — the kind surface and graph invariants
├── spec.md              # /speckit-specify output
├── checklists/
│   └── requirements.md  # /speckit-specify output
└── tasks.md             # Phase 2 output (/speckit-tasks — NOT created here)
```

### Source Code (repository root)

```text
schemas/
├── organization_extensions.yml     # NEW  OrganizationCustomer (R8)
├── dcim_extensions.yml             # EDIT add 7 non-EOS device roles (R7)
├── service/
│   ├── service.yml                 # NEW  ServiceGeneric + binding generics (US1)
│   ├── kubernetes_services.yml     # NEW  ServiceFabricPeering, ServiceFabricApp (US3)
│   ├── access_services.yml         # NEW  ServiceAppAccess (US5)
│   └── wan_services.yml            # NEW  ServiceL3vpn, ServiceInternetAccess,
│                                   #      ServiceTenantCloud (US7)
├── kubernetes/
│   └── kubernetes.yml              # NEW  Cluster, Node, FabricPeering (US2)
├── security/
│   └── security.yml                # NEW  Zone, Address, AddressGroup, Application,
│                                   #      Policy, PolicyRule (US4)
└── wan/
    └── wan.yml                     # NEW  Tenant, Site, Circuit, InternetPeering (US6)

src/solution_arista_avd/
└── protocols.py                    # REGENERATED — never hand-edited

tests/unit/
├── test_service_layer_schema_contract.py     # NEW  US1, US3, US5, US7 + layering FRs
├── test_kubernetes_schema_contract.py        # NEW  US2
├── test_security_schema_contract.py          # NEW  US4
└── test_wan_schema_contract.py               # NEW  US6
```

**Structure Decision**: New schema files are grouped into per-domain directories under
`schemas/`, matching the existing convention (`schemas/evpn/`, `schemas/routing/`,
`schemas/vrf/`, `schemas/compute/`). The service layer gets its own directory holding
four files rather than one, so a reader can load `schemas/kubernetes/` and
`schemas/security/` without `schemas/service/` and see the technical layer standing
alone — which is spec SC-009 made visible in the directory tree.

Two files sit at `schemas/` root rather than in a directory, following the existing
`dcim_extensions.yml` / `ipam_extensions.yml` / `location_extensions.yml` convention for
files whose only job is to extend kinds defined elsewhere.

`.infrahub.yml` is deliberately **not** modified. Schemas are not declared there in this
repository — they are loaded explicitly by `invoke load-schema` — and no query,
generator, transform, or artifact definition belongs to this cycle.

## Complexity Tracking

> Constitution Check violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| **Principle IV** — `$infrahub-run-integration-tests` cannot be run; it is not installed in this environment | The constitution mandates it for every Infrahub code change. The change itself is still necessary and cannot be validated by that named path here | Skipping validation entirely was rejected. **Alternative plan**: (1) four `test_*_schema_contract.py` unit suites asserting the spec's FRs against the YAML; (2) `uv run infrahubctl schema check schemas/` against a branch, which returns both a validation result and a diff of what would change; (3) `uv run infrahubctl schema load schemas --branch <feature>` followed by a re-run of `schema check` to prove convergence and idempotence of the load; (4) protocol regeneration plus `mypy` as a compile-time proof that every kind and relationship resolves. Steps 2–4 exercise the real server, which is what the integration gate exists for. This needs maintainer sign-off, or installation of the skill, before merge |
| **9 new schema files instead of 1** | The layering contract is the feature. One file cannot demonstrate that the technical layer loads without the service layer (SC-009), and one file for four unrelated domains would make the service/technical boundary a matter of comment convention | A single `schemas/lab_extensions.yml` was rejected: it would hide the dependency direction the spec's FR-080 requires, and it would put four domains' migration history in one file's diff |
| **4 new namespaces** | `Service`, `Kubernetes`, `Security`, and `Wan` each name a distinct domain with no existing home. `Security` matches `opsmill/infrahub-demo-dc`, keeping the two repositories comparable | Folding all four into the existing `Network` namespace was rejected: `NetworkZone`, `NetworkCluster`, and `NetworkTenant` would collide conceptually with `NetworkFabric`/`NetworkPod`/`NetworkLink` (fabric building blocks) and with `EvpnTenant` (a different kind of tenant entirely). See R1 and R9 |

## Phase Status

- [x] **Phase 0** — [research.md](./research.md): 14 decisions, no NEEDS CLARIFICATION remaining
- [x] **Phase 1** — [data-model.md](./data-model.md), [contracts/schema-kinds.md](./contracts/schema-kinds.md), [quickstart.md](./quickstart.md)
- [ ] **Phase 2** — `tasks.md` (run `/speckit-tasks`)
