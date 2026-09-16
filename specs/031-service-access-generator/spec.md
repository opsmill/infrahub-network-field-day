# Generator Specification: Application Access Grant Generator

> **Workflow type**: Infrahub Generator (design-driven automation)
> **Skill**: Use the `infrahub-managing-generators` skill to implement this specification.

**Feature Branch**: `031-service-access-generator`
**Created**: 2026-09-16
**Status**: Draft
**Input**: User description: "Now we have a lab with Infrahub. We need to be able to deploy services to the lab using the services schema in Infrahub, and then use this schema to have generators build the technical layer. This then gets distilled into applications, security policies, and fabric information that gets deployed to the network. The ideal goal is that we use something like Backstage to request these services as a user." Followed by: "The service catalog can come later, but we just need the services to work in Infrahub."

## What already works, and the one kind that does not

The loop the request describes has five stops. Four exist.

| Stop | State today |
| --- | --- |
| A service exists as an object | **Built.** Six kinds under `ServiceGeneric`, all inheriting `GeneratorTarget`. |
| A generator builds the technical layer | **One of six.** `generate-fabric-peering` only. |
| Distilled into applications | **Built.** `crossplane_fabric_app`, `crossplane_fabric_peering`. |
| Distilled into security policies | **Rendered, never generated.** `junos_config` renders `SecurityPolicyRule` onto the firewall. Nothing creates a rule from a service. |
| Distilled into fabric information, and deployed | **Built.** The AVD chain, Vidra, and the deployment reconciler. |

Of the five kinds without a generator, four are not actually inert:

- **`ServiceL3vpn`, `ServiceInternetAccess`, `ServiceTenantCloud`** are read directly by `frr_config`, which `AGENTS.md` records as the deliberate exception to "renderers read technical objects" — a provider edge's import policy *is* the service intent. They work. Giving them generators would relocate working behaviour, not add any.
- **`ServiceFabricApp`** is rendered by `crossplane_fabric_app` into a Crossplane manifest that Vidra delivers. Its technical layer is in-cluster and Crossplane composes it.

**`ServiceAppAccess` is the one that does nothing at all.** It has a schema, a menu entry at `menus/menu.yml:389`, and six contract tests. It has no generator, no transform, no artifact definition, and no seed object anywhere under `objects/`. Approving a grant today produces exactly nothing.

That is also the kind whose generator closes the whole loop the request describes, end to end and with no schema change: a grant produces firewall rules, `junos_config` renders them into the existing Junos artifact, and the deployment reconciler pushes that artifact onto `fw1`. Every one of those stages is already built and under test.

### Two findings that set this scope

**The SDK already owns realization.** `InfrahubGenerator.run()` wraps `generate()` in `start_tracking(identifier=..., delete_unused_nodes=True)`: objects a previous run created and this run did not touch are deleted automatically. `generate_fabric_peering.py` says so in its own header — "the tracking context deletes previously-managed objects this run did not touch". So no schema for recording what a service built is required; the tracking group is that record. This is why this cycle is a generator cycle and not a schema one.

*(Implementation found the withdrawal half of that claim to be only partly true — `update_group` returns early when a run touches nothing, so revoking a grant prunes nothing. See [research.md](./research.md) R8. It does not change the conclusion above: the tracking group is still the record, and no schema was needed.)*

**No schema change is needed.** `SecurityPolicyRule.managed_by_service` exists as the guard that lets a generator reconcile a firewall carrying hand-written rules, and defaults to `false` so everything loaded today reads as unowned. `ServiceAppAccess.granted_rules` exists to hold what a grant caused. `book_index` and `log_session_close` exist. Both were added by earlier cycles in anticipation of exactly this generator, and neither has a writer.

## Generator Overview

**Design Object (Source)**: `ServiceAppAccess` — a grant naming an application, a source zone, a source address-book entry, a destination VIP, a port list, and an approval flag.

**Generated Objects (Targets)**: `SecurityGenericAddress` (an address-book entry for the destination VIP), `SecurityGenericService` (one per permitted port), and `SecurityPolicyRule` (the rule permitting the session), linked back to the grant through `granted_rules`.

**Target Group**: a new `CoreStandardGroup`, `service_app_accesses`, declared in `objects/00_groups.yml` beside the existing `service_fabric_peerings` and `service_fabric_apps`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An approved grant becomes a firewall rule (Priority: P1)

An operator approves an access grant naming an application, where the request comes from, and which ports it needs. The firewall rule permitting that session appears, built from the firewall's own address-book and service vocabulary rather than from synthesised CIDRs and port literals, and it is marked as owned by a service so the hand-written baseline beside it is never at risk.

**Why this priority**: it is the whole request in one story. It is also the only one of the six service kinds that produces nothing today, so this is the difference between a service layer that models intent and one that acts on it.

**Independent Test**: create one `ServiceAppAccess` in the target group with `approved: true`, run `infrahubctl generator generate-app-access`, and verify the address-book entry, the service objects and the rule exist, are linked from `granted_rules`, and carry `managed_by_service: true`. Delivers value alone: the rule is rendered by the existing `junos_config` artifact with no further work.

**Acceptance Scenarios**:

1. **Given** an approved grant in the target group, **When** the generator runs, **Then** a `SecurityPolicyRule` exists permitting the named source to reach the destination VIP on the named ports, in the correct zone pair
2. **Given** the generator has already run for a grant, **When** it runs again with nothing changed, **Then** no duplicate rule, address or service object is created and no existing object is modified
3. **Given** a grant whose ports list is empty, **When** the generator runs, **Then** it fails loudly rather than producing a rule that permits everything — an empty list is rejected, never read as "all"
4. **Given** a grant with `approved: false`, **When** the generator runs, **Then** nothing is created, because approval is the gate and an unapproved request must be inert rather than merely hidden
5. **Given** the generated rule, **When** it is read, **Then** `managed_by_service` is `true`, and every hand-written rule in the same zone pair still reads `false`
6. **Given** the generated objects, **When** the grant is read, **Then** `granted_rules` names the rule the grant caused, so revocation has a list to work from
7. **Given** a grant, **When** the generator determines the destination zone and the policy the rule joins, **Then** it derives them from the graph rather than from a constant, and fails loudly when the derivation is ambiguous or empty

---

### User Story 2 - Revoking a grant removes what it created, and nothing else (Priority: P2)

A grant is revoked — unapproved, decommissioned, or deleted. The rule it created disappears, the address-book entry and service objects it created disappear if nothing else uses them, and the hand-written baseline in the same zone pair is untouched.

**Why this priority**: it is the half that is always forgotten, and the half an audit asks about. It is P2 rather than P1 because a grant that only ever creates is still useful, and because the tracking context supplies most of the mechanism — this story is mainly about proving it behaves correctly against a firewall that is also maintained by hand.

**Independent Test**: run the generator for a grant, confirm the rule exists, set the grant to `approved: false`, run again, and confirm the rule is gone while the baseline rules in that zone pair and their `book_index` ordering are unchanged.

**Acceptance Scenarios**:

1. **Given** a grant whose rule exists, **When** the grant is unapproved and the generator runs, **Then** the rule is removed
2. **Given** a grant whose rule exists, **When** the grant is deleted and the generator runs, **Then** the rule is removed
3. **Given** a zone pair holding one generated rule and several hand-written rules, **When** the generated rule is removed, **Then** every hand-written rule survives with its `index` and the address book keeps its `book_index` ordering
4. **Given** two grants that resolved to the same address-book entry, **When** one is revoked, **Then** the entry survives because the other grant still needs it
5. **Given** a grant whose ports are narrowed from three to one, **When** the generator runs, **Then** the two service objects that are no longer justified are removed and the remaining rule permits only the surviving port

---

### User Story 3 - The rule reaches the firewall (Priority: P3)

The rule a grant created is rendered into the firewall's Junos artifact and pushed onto `fw1` by the reconciler, and the grant's status reflects that it was materialized.

**Why this priority**: it is the claim the request actually makes — "deployed to the network". It is P3 because it requires no new code if P1 is correct: `junos_config` already renders every `SecurityPolicyRule`, and the reconciler already pushes the artifact. This story exists so that "it generated objects" is not mistaken for "it changed the firewall", which are different claims and only an end-to-end run distinguishes them.

**Independent Test**: create an approved grant on a branch, run the generator, regenerate the Junos artifact, download it, and confirm the permitted session appears in the rendered configuration; then reconcile and confirm the firewall reports no difference.

**Acceptance Scenarios**:

1. **Given** a generated rule, **When** the Junos artifact is regenerated, **Then** the artifact contains the permitted session in the correct zone pair
2. **Given** the regenerated artifact, **When** the reconciler compares `fw1`, **Then** the firewall is reported as differing, and after the push it is reported as matching
3. **Given** the generator ran successfully for a grant, **When** the grant is read, **Then** its status distinguishes "materialized" from "ordered but not yet built"
4. **Given** the generator ran and failed for a grant, **When** the grant is read, **Then** its status distinguishes that failure from "not yet built", because both leave no technical objects behind
5. **Given** a grant is added and the change is merged, **When** nothing is run by hand, **Then** the generator runs on merge, because it is registered with the default `execute_after_merge`

---

### Edge Cases

- The destination VIP sits outside every prefix the border leaf re-advertises to the source, so the grant is permitted by the firewall and still unroutable. The schema comment on `destination_vip` says this belongs to a check; does the generator refuse, warn, or proceed?
- The destination VIP is an `IpamIPAddress` and the rule needs a `SecurityGenericAddress`. Nothing links the two today. If an address-book entry already exists for that address, is it adopted or duplicated?
- Two grants name the same application, the same source zone and overlapping ports. Do they produce one rule or two, and does revoking one leave the other's access intact?
- The derived `index` collides with a hand-written rule. The firewall holds only `10`, `20` and `30` across all nineteen rules, so the generated range must not overlap and must stay deterministic across runs.
- Junos evaluates first-match within a zone pair, so a generated rule placed above a hand-written deny changes the meaning of the baseline. Where in the order does a generated rule belong?
- The grant's source zone and the VIP's zone resolve to the same zone, producing an intrazone rule the firewall may not need.
- A grant is approved, the generator runs, and then the application it names is deleted.
- The address-book entry a grant created is later referenced by a hand-written rule; the tracking context would still delete it when the grant is revoked.
- Two grants are approved in the same proposed change, and both try to allocate the same rule index.
- `book_index` is hand-maintained and pinned by `tests/unit/test_junos_config.py`. A generated address-book entry has to take an index without disturbing the ones already asserted.

## Requirements *(mandatory)*

### Functional Requirements

#### Generator Structure

- **FR-001**: Generator MUST inherit from `infrahub_sdk.generator.InfrahubGenerator`
- **FR-002**: Generator MUST implement `async generate(self, data: dict) -> None`
- **FR-003**: Generator MUST use `self.client` for all Infrahub SDK operations
- **FR-004**: Generator MUST live at `generators/generate_app_access.py`, following the repository's `generate_<entity>.py` convention

#### GraphQL Query

- **FR-010**: A query file MUST exist at `generators/generate_app_access.gql`, beside the generator, following the convention every other generator here uses
- **FR-011**: The query MUST accept the parameter declared in the `.infrahub.yml` `parameters` mapping, matching how `generate-fabric-peering` is registered
- **FR-012**: The query MUST fetch, for one grant: its approval state, ports, requester, the application and that application's VIP block and cluster, the source zone, the source address-book entry, the destination VIP, and the rules it has already granted
- **FR-013**: The query MUST fetch enough of the firewall's model to derive the destination zone and the policy the rule joins, rather than the generator holding either as a constant
- **FR-014**: Return types MUST be regenerated with `infrahubctl graphql generate-return-types` into `generate_app_access_query.py` and used in the generator; the file MUST NOT be hand-written

#### Object Creation

- **FR-020**: Generator MUST create a `SecurityGenericAddress` for the destination VIP when no entry for that address exists, and adopt the existing entry when one does
- **FR-021**: Generator MUST create one `SecurityGenericService` per permitted port, adopting an existing service object for the same protocol and port rather than duplicating it
- **FR-022**: Generator MUST create a `SecurityPolicyRule` whose source is the grant's address-book entry and whose destination is the VIP's entry, referencing the firewall's own objects rather than synthesised CIDRs or port literals, so a generated rule reads like the hand-written rules beside it
- **FR-023**: Generator MUST set `managed_by_service: true` on every rule it creates, and MUST NOT set it on any object it did not create
- **FR-024**: Generator MUST link every rule it creates into the grant's `granted_rules` relationship
- **FR-025**: All `save()` calls MUST use `allow_upsert=True`
- **FR-026**: Objects MUST be created in dependency order: address-book entry and service objects before the rule that references them
- **FR-027**: Generator MUST allocate the rule's `index` deterministically and outside the range the hand-written baseline occupies, so two runs produce the same index and no generated rule displaces a baseline rule
- **FR-028**: Generator MUST derive the destination zone from the graph, and MUST raise rather than guess when nothing matches or more than one thing does. *(Phase 0 corrected the mechanism this originally named: see [research.md](./research.md) R2. Deriving it from the firewall interface whose subnet contains the VIP cannot work — the handoff interfaces are `/30` point-to-points that contain no VIP. The derivation is through `IpamVRF`, which both `ServiceFabricApp` and `SecurityZone` already relate to.)*
- **FR-029**: Generator MUST raise before writing anything when the model is incomplete, following `generate_fabric_peering.py`, where that ordering is load bearing because a partial write is the one path by which tracking can delete a real object

#### Approval Gate

- **FR-030**: Generator MUST create nothing for a grant whose `approved` is `false`, so an unapproved request is inert rather than merely hidden
- **FR-031**: Generator MUST reject a grant whose `ports` list is empty rather than treating it as permitting all ports, matching the lab's `FirewallAccess` CRD which sets `minItems: 1`
- **FR-032**: Generator MUST set the grant's `status` to distinguish materialized from ordered-but-unbuilt, and a failed run from a run that has not happened

#### Cleanup

- **FR-040**: Generator MUST withdraw what it created when a grant is revoked. *(Implementation corrected the mechanism this originally named: see [research.md](./research.md) R8. The SDK tracking context covers narrowing but **not** revocation — `update_group` returns early when a run touches nothing — so the unapproved path deletes explicitly, keyed on the generated name.)*
- **FR-041**: Objects the generator did not create MUST NOT be deleted, whatever the tracking context would otherwise do — the hand-written baseline in the same zone pair has no service behind it and must survive
- **FR-042**: An object created for one grant and still required by another MUST survive the first grant's revocation

#### Registration

- **FR-050**: Generator MUST be registered in `.infrahub.yml` under `generator_definitions` as `generate-app-access`, with `file_path`, `query`, `targets`, `class_name` and `parameters`
- **FR-051**: The query MUST be registered in `.infrahub.yml` under `queries`
- **FR-052**: A `service_app_accesses` group MUST be declared in `objects/00_groups.yml`, with a comment recording why a group exists rather than a direct target, matching the surrounding entries
- **FR-053**: Grant objects MUST declare their group membership explicitly, as `objects/35_nfd41_peering_service.yml` and `objects/36_nfd41_app_services.yml` do

#### Demonstrable in the lab

- **FR-060**: At least one `ServiceAppAccess` object MUST be seeded under `objects/`, because the kind currently has none and an unexercised generator is an untested one
- **FR-061**: The seeded grant MUST name objects that already exist in the lab — a real application, a real source zone, a real address-book entry — so it is materializable on a fresh `invoke bootstrap`
- **FR-062**: Adding the seeded grant MUST NOT change the byte-for-byte Junos assertions in `tests/unit/test_junos_config.py`. *(Phase 0 resolved the tension between this and FR-060: the seeded grant is **unapproved**, so it materializes nothing and the artifact stays byte-identical, while the kind stops being empty and the demo is one field-flip away. See [research.md](./research.md) R5.)*

#### Tests

- **FR-070**: Unit tests MUST cover the derivation of the destination zone, the rule index allocation, the empty-ports rejection, and the unapproved-grant no-op
- **FR-071**: An idempotence test MUST assert that a second run against unchanged input creates, modifies and deletes nothing
- **FR-072**: A test MUST assert that revocation removes the generated rule and leaves hand-written rules in the same zone pair untouched
- **FR-073**: `tests/unit/test_the_exclusions_add_up` in `test_junos_config.py` MUST still pass, or be updated with the new line count

### Key Entities

- **`ServiceAppAccess`** *(source, unchanged)*: the grant. Names the application, source zone, source address, destination VIP and ports; carries the approval gate and the `granted_rules` backlink.
- **`SecurityPolicyRule`** *(generated)*: the rule permitting the session. Needs `index`, `name`, `action`, `policy`, `source_zone`, `destination_zone`, addresses and services. Carries `managed_by_service`, the guard that makes a reconciling generator safe against a hand-maintained firewall.
- **`SecurityGenericAddress`** *(generated or adopted)*: the address-book entry for the destination VIP. Ordered by `book_index`, which is hand-maintained and pinned by existing tests.
- **`SecurityGenericService`** *(generated or adopted)*: one per permitted port.
- **`SecurityPolicy`** *(referenced)*: the policy a rule joins. Mandatory on every rule and not named by the grant, so it must be derived.

### Key Files

| File | Change |
| --- | --- |
| `generators/generate_app_access.gql` | new |
| `generators/generate_app_access_query.py` | new, generated |
| `generators/generate_app_access.py` | new |
| `.infrahub.yml` | register the query and the generator definition |
| `objects/00_groups.yml` | add `service_app_accesses` |
| `objects/3x_nfd41_access_grants.yml` | new, at least one seeded grant |
| `tests/unit/test_app_access_generator.py` | new |
| `tests/unit/test_junos_config.py` | update the line-count assertion if the seeded grant changes the artifact |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An approved grant produces a firewall rule permitting exactly the named source, destination and ports, and no other rule changes
- **SC-002**: Running the generator twice against unchanged input produces no second rule, no modified object and no deletion
- **SC-003**: Revoking a grant removes the rule it created, and all nineteen hand-written rules and their zone-pair ordering survive
- **SC-004**: The rule appears in the rendered Junos artifact, and the reconciler reports `fw1` as differing before the push and matching after it
- **SC-005**: `uv run invoke bootstrap --fresh` completes and `scripts/verify_bootstrap.sh` passes all sixteen assertions with the seeded grant present
- **SC-006**: An unapproved grant and a grant with no ports both produce zero objects, and the second reports why
- **SC-007**: `uv run pytest tests/unit` passes and `uv run invoke lint` is clean
- **SC-008**: No file under `schemas/` changes in this cycle

## Assumptions

- **No schema change is required.** `managed_by_service`, `granted_rules`, `book_index` and `log_session_close` were all added by earlier cycles for this generator and have no writer yet. If implementation finds a genuine gap, that becomes a schema cycle first, per the constitution.
- **Withdrawal is the SDK's tracking context**, not a hand-rolled ownership model. `delete_unused_nodes=True` is already how `generate-fabric-peering` prunes.
- **Firewall rules only.** `ServiceFabricApp.policy_allow_ports` is the cluster-side allowlist, and it is declared intent on the application rather than per-grant. Writing to it from a grant generator would put two writers on one attribute, so the Kubernetes network policy is left alone this cycle.
- **The WAN services already work** through `frr_config` reading the service layer directly, which `AGENTS.md` records as deliberate. Giving them generators is a refactor, not a fix.
- **`ServiceFabricApp` already works** through `crossplane_fabric_app` and Vidra. Its technical layer is composed in-cluster by Crossplane.
- **The destination VIP is modelled by hand** for now, as an `IpamIPAddress` in the seed data. Allocating it automatically depends on how MetalLB assigns from `vip_block`, which is unresolved and would risk two allocators disagreeing.
- **One artifact type per cycle**, per the repository's spec-driven workflow. This cycle is a generator.

## Out of Scope

- **The service catalogue.** Explicitly deferred by the user. There is no orderable-offering model, no input definitions and no availability state in this cycle.
- **Backstage.** No plugin, no descriptor, no software template. Ordering still happens through the Infrahub UI, the API, or a seeded object.
- **Changes to the Streamlit portal** under `service_catalog/`.
- **Generators for `ServiceL3vpn`, `ServiceInternetAccess` and `ServiceTenantCloud`.** They are consumed today by `frr_config`; relocating that is a refactor with no behaviour change.
- **A generator for `ServiceFabricApp`**, including automatic VIP allocation from `vip_block`.
- **Kubernetes NetworkPolicy changes** driven by a grant.
- **Request provenance on `ServiceGeneric`.** Lifting requester, justification and approval off `ServiceAppAccess` so every kind can be ordered is real work, but it is schema work and it is only needed once more than one kind is orderable.
- **A check enforcing that the destination VIP sits inside an advertised prefix.** The schema comment marks this as a check's job; this cycle notes the gap as an edge case.
- **`DeploymentState` and `DeploymentDiffFile`.** Nothing may generate from them, and nothing here does.
