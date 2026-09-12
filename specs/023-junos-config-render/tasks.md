---

description: "Task list for the perimeter firewall seed repair and Junos render"
---

# Tasks: Junos Configuration for the Perimeter Firewall

**Input**: Design documents from `/specs/023-junos-config-render/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/transform-contract.md](./contracts/transform-contract.md)

**Tests**: **REQUIRED.** Constitution IV. Two modules: a seed-parity test against the oracle
(US1's gate, no renderer needed) and a golden-file test over the rendered output.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel — different files, no dependency on an incomplete task
- **[Story]**: the user story from [spec.md](./spec.md) this task serves

## Re-scoped: two artifact types, Objects then Transform

Implementation reached T011 and stopped: **the seeded data does not transcribe the oracle**
(research.md R9). Cycle 010 modelled the firewall's structure faithfully and its values
approximately, so no renderer could reach SC-001.

The seed repair is now inside this cycle rather than split out — the requester's call, recorded
because the extension's routing normally takes one artifact type per cycle. It is defensible
because the object work is transcription, not design: **33 corrections** from a file that already
exists, no schema component, verified by the same oracle as the render.

| Correction | Count |
| --- | --- |
| Rule `application` links, every one of them `any` | 14 |
| Interface descriptions | 6 |
| Interface MTUs (`1514` → `9192`) | 6 |
| New service object `any` | 1 |
| **Total** | **27** |

**Corrected during implementation (research.md R10).** An earlier table here claimed 33
corrections including six missing address-**group** references. That was wrong: all six were
present in cycle 010's seed on the correct `source_groups`/`destination_groups` relationships,
and the gap was an artefact of a schema query that filtered out every field ending in `groups`.

**Phases 1 and 2 are already done** (T001–T011) and reusable unchanged — the query with its
concrete-kind fragments, the generated types, and the captured fixture. They are what revealed
the gap.

## Traps

Five, four found by checking the live graph and one by a broken extractor:

1. **`any` must never reach the address book.** It is a Junos keyword — referenced by rules,
   never declared. One extra line in the book is this bug.
2. **Bracket form.** `application junos-http;` for one, `application [ a b ];` for several. It
   also broke the first gap count, which read bracketed rules as empty and overstated the repair.
3. **Polymorphic fragments must name the concrete kind.** Three distinct places now: the address
   book, the service list, and `SecurityFirewall.interfaces` — which peers with `DcimInterface`,
   so `security_zone` and `ip_addresses` need `... on SecurityFirewallInterface`.
6. **Addresses and groups are separate relationships.** `source_address` peers with
   `SecurityGenericAddress`; `source_groups` with `SecurityGenericAddressGroup`. A group cannot
   be referenced through the address field, and a query reading only the address field concludes
   the groups are unreferenced — which is exactly the wrong turn this cycle took.
4. **Rule order within a zone pair is semantic.** Junos evaluates first-match. Sort by `index`.
5. **No credential may reach the artifact, the model or the query.** Permanent, not deferred.

---

## Phase 1: Setup

- [X] T001 Verify preflight: `uv run infrahubctl info` shows Connection Status ✅ against Infrahub 1.10.6
- [X] T002 Export `INFRAHUB_API_TOKEN` from the stack's environment
- [X] T003 Create the git branch `023-junos-config-render` from `main`
- [X] T004 Create the Infrahub branch `fw-render` with `--sync-with-git`, then load `schemas/` and `objects/` into it

---

## Phase 2: Foundational (Blocking Prerequisites)

- [X] T005 Write `transforms/junos_config.gql` — the firewall, its interfaces, every zone, the address book, the groups, the services, and the policy with all 19 rules
- [X] T006 Add an inline fragment per **concrete** kind: `SecurityIPAMIPPrefix` reads `ip_prefix`, `SecurityIPAMIPAddress` reads `ip_address`, `SecurityPrefix` reads `prefix`, and `SecurityFirewall.interfaces` needs `... on SecurityFirewallInterface`
- [X] T007 Run the query against `fw-render` and confirm every address resolves a value
- [X] T008 Regenerate `transforms/junos_config_query.py`; the generator names its output from the **operation name**, so it must be `JunosConfigQuery`
- [X] T009 [P] Create `transforms/templates/junos/` and `tests/unit/fixtures/junos/`
- [X] T010 Capture the query response for `fw1` into `tests/unit/fixtures/junos/fw1.json`
- [X] T011 Confirm the fixture contains no credential field

**Checkpoint**: query proven, fixture captured — and the gap that forced the re-scope found.

---

## Phase 3: User Story 1 — The seed transcribes the firewall (Priority: P1) 🎯 MVP

**Goal**: `objects/32_nfd41_security.yml` describes the same firewall as `junos.conf`, not a
similar one.

**Independent Test**: compare every rule's addresses, groups and applications, and every
interface's description and MTU, against the oracle in both directions. No renderer, no server.

### Implementation for User Story 1

- [X] T012 [US1] Add `any` as a `SecurityService` in `objects/32_nfd41_security.yml`. Eleven rules reference it and it is the only named application the model lacks — `junos-http`, `junos-https` and `junos-ping` are already seeded (FR-053)
- [X] T013 [US1] Link the 14 missing `destination_services`, all of them `any`. `SecurityGenericService` declares no HFID, so the inline concrete-kind form is required and its `port` is mandatory (FR-052)
- [~] T014 [US1] ~~Link the three missing **source** address-group references~~ — **not needed.** Already present on `source_groups` in cycle 010's seed (R10)
- [~] T015 [US1] ~~Link the three missing **destination** address-group references~~ — **not needed.** Already present on `destination_groups` (R10)
- [X] T016 [US1] Replace the six interface descriptions with the file's strings, e.g. `ge-0/0/0` becomes `"ZONE-K8S-PROD handoff - border-leaf1 Et10"`, not the current paraphrase (FR-054)
- [X] T017 [US1] Set the six interface MTUs to `9192`, replacing the schema default `1514` (FR-055)
- [X] T018 [US1] Comment the MTU in the object file with the reason the lab records: Junos counts the 14-byte Ethernet header, so matching the fabric's 9214 would need 9228, which vSRX rejects — 9192 is the platform maximum and `flow tcp-mss` is what makes the shortfall safe
- [X] T019 [US1] Transcribe nothing that is not in the oracle. Every one of the 33 corrections comes from the file (FR-050)

### Tests for User Story 1

- [X] T020 [US1] Create `tests/unit/test_junos_seed_data.py` with an oracle parser that **handles Junos' bracket form** — `destination-address [ a b c ];`. A parser that misses it reads bracketed rules as empty and overstates the gap, which is exactly what happened during research
- [X] T021 [US1] Add a two-directional parity test for every rule's source addresses, destination addresses and applications. An invented value must fail as loudly as a missing one (SC-011)
- [X] T022 [P] [US1] Add a test asserting each of the four address groups is referenced by the rules that name it — six references total (SC-012)
- [X] T023 [P] [US1] Add a test asserting all six interfaces carry the file's description and MTU `9192` (SC-013)
- [X] T024 [US1] Load `objects/` into `fw-render` twice and confirm counts are unchanged. The CLI prints "Created node" for an upsert, so the log is not evidence — only the counts are (SC-014)
- [X] T025 [US1] Re-capture `tests/unit/fixtures/junos/fw1.json` from the corrected graph, so everything downstream is built against real data

**Checkpoint**: the seed is a transcription. Nothing after this can be right until it is.

---

## Phase 3a: the address-book ordering attribute — DONE

SC-001's byte-for-byte parity was at risk because **the address book's order is authoring
order** and nothing derives it. The requester chose an ordering attribute over relaxing the
criterion, so this cycle now spans **three** artifact types — schema, objects, transform.

- [X] T025a Add `book_index` (Number, optional) to `SecurityGenericAddress` in `schemas/security_extensions.yml`. On the **generic**, so one attribute covers all six concrete address kinds
- [X] T025b Seed `book_index` on all 13 addresses in the file's order; `any` gets none
- [X] T025c Update `tests/unit/test_security_schema_contract.py`, which correctly failed on "extensions touch only the two intended kinds" — updated to three, not loosened
- [X] T025d Fetch `book_index` in the query on all three concrete kinds, reload the schema into `main` so `export-schema` sees it, regenerate the types, re-capture the fixture
- [X] T025e Add tests: the order reproduces the file, only `any` is unindexed, indexes are unique

**An absent index is also the exclusion rule.** `any` is the one address with no position in the
rendered book, so FR-017 and `book_index` turn out to be the same fact.

## Phase 4: User Story 2 — The zones and the address book render (Priority: P2) — DONE

**The address book's order is authoring order.** Junos writes it infrastructure-first then
per-tenant; the graph returns it grouped by concrete kind, so `access-portal` — a `/32`, and the
only `SecurityIPAMIPAddress` — lands last instead of fourth. No rule reproduces the file's order:
not alphabetical, not by network address, not by prefix length. Infrahub stores no authoring
order.

Junos does not care — address-book entries are name-keyed definitions and their order is
cosmetic, unlike policies within a zone pair, which are first-match and whose order the model
*does* carry in `index`. So the render would be semantically identical and textually different in
one stanza. That collides with SC-001's byte-for-byte parity.

Three ways out, in research.md R11: relax SC-001 for that one stanza (recommended), add an
ordering attribute via `security_extensions.yml` (a schema change this cycle does not have), or
hardcode the order (rejected — violates SC-007).

**The address groups are unaffected**: the file's order is alphabetical, so `sorted()` reproduces
it.

## Phase 4: User Story 2 — The zones and the address book render (Priority: P2)

**Goal**: interfaces, address book and zones render, and the golden-diff harness exists.

**Independent Test**: render `fw1`; diff the `interfaces`, `address-book` and `zones` stanzas
against the oracle.

### Implementation for User Story 2

- [X] T026 [US2] Write `transforms/junos_config.py` with the `JunosConfig` class, `query = "junos_config"`, wrapping `data` in the generated `JunosConfigQuery` model as `transforms/frr_config.py` does
- [X] T027 [US2] Build the Jinja2 environment with all five settings: `undefined=StrictUndefined`, `trim_blocks=True`, `lstrip_blocks=True`, `keep_trailing_newline=True`, `autoescape=False` with a justifying comment and a targeted `noqa`
- [X] T028 [US2] Add a shared bracket-form helper: one member bare, several as `[ a b ]`. Every list site in every template MUST use it (FR-016)
- [X] T029 [US2] Assemble the address book through each entry's concrete kind, and **exclude the entry named `any`** (FR-017)
- [X] T030 [US2] Write `transforms/templates/junos/interfaces.j2`
- [X] T031 [P] [US2] Write `transforms/templates/junos/address-book.j2` — 13 addresses then 4 address-sets, reproducing the file's `/* … */` comments
- [X] T032 [P] [US2] Write `transforms/templates/junos/zones.j2` — six zones with their bound interfaces and `host-inbound-traffic`
- [X] T033 [US2] Raise a named error when a required value is absent rather than rendering an empty statement (FR-014)

### Tests for User Story 2

- [X] T034 [US2] Create `tests/unit/test_junos_config.py` with a helper that loads the fixture, renders, and extracts a named stanza. **This is the harness the later stories depend on**
- [X] T035 [US2] Add golden-file equality tests for the `interfaces`, `address-book` and `zones` stanzas. Equality, not substring matching
- [X] T036 [P] [US2] Add a test asserting `any` appears in no address-book entry, and the book has exactly 13 entries and 4 address-sets
- [X] T037 [P] [US2] Add a test asserting single-member lists render bare and multi-member lists bracketed

**Checkpoint**: `interfaces`, `address-book` and `zones` match the device **byte for byte** —
187 of the 573 in-scope lines. 8 tests in `tests/unit/test_junos_config.py`, harness in place.

The only diff on the way was the file's three `/* … */` comment blocks, which FR-021 requires.
The per-tenant one is anchored on the first entry it describes rather than on a line number, so
adding an infrastructure address above cannot detach it.

---

## Phase 5: User Story 3 — The zone-pair policies render (Priority: P3)

**Goal**: eleven zone pairs, rules in evaluation order, `deny-spoofed-infra` at the head of six.

**Independent Test**: diff the `policies` stanza; assert the six anti-spoofing rules render
identically.

### Implementation for User Story 3

- [X] T038 [US3] Group rules into zone pairs by `(source_zone, destination_zone)` — pairs are derived, not stored (R1)
- [X] T039 [US3] Sort rules within each pair by `index`. Junos evaluates first-match, so a wrong order loads cleanly and enforces something different (FR-012)
- [X] T040 [US3] Pin the zone-pair sequence to the golden file's order
- [X] T041 [US3] Write `transforms/templates/junos/policies.j2`, using the T028 helper for every address and application list
- [X] T042 [US3] Render the `then` block from `action` and `log`, including `session-close` where the file has it
- [X] T043 [US3] Emit `any` wherever a rule references it, though the book never declares it

### Tests for User Story 3

- [X] T044 [US3] Add a golden-file equality test for the whole `policies` stanza
- [X] T045 [US3] Add a test asserting rule order within every zone pair matches the oracle, pair by pair
- [X] T046 [P] [US3] Add a test asserting `deny-spoofed-infra` renders exactly six times with byte-identical bodies. It does **not** assert deduplication — the adopted schema forbids it, and R2 explains why
- [X] T047 [P] [US3] Add a test asserting 11 zone pairs and 19 policy statements

**Checkpoint**: roughly 470 of 573 lines.

---

## Phase 6: User Story 4 — The configuration is loadable as a whole (Priority: P4)

- [X] T048 [US4] Write `transforms/templates/junos/junos.j2` — the outer document in the golden file's stanza order
- [X] T049 [US4] Open with a provenance line naming Infrahub and the device (FR-022)
- [X] T050 [US4] Ensure brace nesting is balanced and the file ends with a newline (FR-023)
- [X] T051 [P] [US4] Add a test asserting brace depth returns to zero, never goes negative, and the file ends with a newline
- [X] T052 [P] [US4] Add a whole-file equality test against the in-scope stanzas
- [X] T053 [US4] Add a test asserting **no credential appears** — no `encrypted-password`, no key material, no private key header (FR-043, SC-005)

**Checkpoint**: all 573 in-scope lines render.

---

## Phase 7: Registration and Live Verification

- [X] T054 Add the `junos_firewalls` `CoreStandardGroup` to `objects/00_groups.yml` with `fw1` as its only member
- [X] T055 Register the query, transform and artifact definition in `.infrahub.yml` — `content_type: text/plain`, `targets: junos_firewalls`, `parameters: {device: name__value}`
- [X] T056 Verify programmatically that `transformation`, the `python_transforms` name and the class's `query` all match. A mismatch fails silently
- [X] T057 Render live against `fw-render` and diff against the in-scope stanzas ([quickstart.md](./quickstart.md) §3)
- [X] T058 Run the count checks — 6 zones, 13 addresses, 4 address-sets, 11 pairs, 19 rules, 6 anti-spoofing
- [X] T059 Run the credential grep over the artifact **and the repository** ([quickstart.md](./quickstart.md) §5)
- [X] T060 Run the brace-balance check
- [X] T061 Confirm the artifact definition generates exactly one artifact (SC-008)

---

## Phase 8: Documentation and Close-Out

- [X] T062 [P] Add the transform to the inventory in `AGENTS.md`, beside `frr_config`
- [X] T063 [P] Document the render in `docs/docs/developer-guide/transforms.md`, including what it does **not** cover: the credentials permanently, the static routes pending a schema cycle
- [X] T064 [P] Record in the developer guide that a polymorphic relationship needs a fragment per concrete kind — three distinct places in three cycles now
- [X] T065 Write [acceptance-evidence.md](./acceptance-evidence.md): the seed parity result, the diff, the counts, the credential grep, the brace check and the SC-010 arithmetic
- [X] T066 Run the SC-010 arithmetic ([quickstart.md](./quickstart.md) §9) — the exclusions must total 104
- [X] T067 Run `uv run invoke test` and `uv run invoke lint`
- [~] T068 Run `$infrahub-run-integration-tests`. If not installed, say so explicitly in the pull request as the constitution's documented exception — do not omit it silently
- [X] T069 Note the two follow-ups R2 identified: a check asserting the six anti-spoofing rules stay identical, and a schema cycle for device-level static routes so `routing-options` can join the artifact
- [X] T070 Merge to `main` and delete the `fw-render` Infrahub branch — on the requester's instruction, T068 named as the documented exception in the merge commit

---

## Dependencies & Execution Order

### Phase dependencies

- **Phases 1–2**: done
- **Phase 3 (US1, the seed)**: **blocks everything.** No rendering task can be correct until the
  data is a transcription. T025 re-captures the fixture and is the handoff
- **Phase 4 (US2)**: after US1. Builds the transform class, the bracket helper and the harness
- **Phase 5 (US3)**: after US2 — extends the same transform, reuses the same harness
- **Phase 6 (US4)**: after US2 and US3, because the outer document includes their stanzas
- **Phase 7**: after all stories
- **Phase 8**: after Phase 7

### Story dependencies

```text
US1 (seed) ──► US2 (class + helper + harness) ──► US3 (policies) ──► US4 (document)
```

Strictly sequential, unusually for this template, and the reason is real: US1 changes the data
every later story renders, and US2 builds the harness US3 and US4 assert through. US2, US3 and
US4 all edit `transforms/junos_config.py` and one test module, so they are **not** parallel;
their templates are separate files and can be written in parallel.

### Parallel opportunities

- T022 and T023 — seed assertions, different fields
- T031 and T032 — two templates
- T036, T037, T046, T047, T051, T052 — assertion tasks, if the test module is not being edited
- T062, T063, T064 — documentation

---

## Implementation Strategy

**MVP**: Phases 1–3 (US1). The seed becoming a transcription is worth shipping alone — it makes
`objects/32_nfd41_security.yml` a faithful description of the firewall, which is valuable whether
or not anything renders from it, and it is the blocker for everything else.

**Full cycle**: all four stories. US1 without the render leaves 010's assumption 8 unmet; the
render without US1 is impossible.

**What would make this cycle wrong**:

- A task that changes a schema. `security/security.yml` is marketplace-adopted; if something is
  unrepresentable it belongs in a schema cycle first.
- A task that models, queries or renders a credential. Permanent exclusion.
- **A seed value that is not in the oracle.** The repair is transcription. An invented value is
  worse than the paraphrase it replaces, because it looks deliberate.
- A test that checks substrings instead of stanza equality, or an oracle parser that does not
  handle the bracket form — that parser is what overstated the gap in the first place.
