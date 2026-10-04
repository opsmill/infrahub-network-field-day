# Feature Specification: Application Catalogue

**Feature Branch**: `feat/application-catalogue` (spec directory `035-application-catalogue`; the branch name does not follow the numbering, by instruction)
**Created**: 2026-10-04
**Status**: Draft
**Input**: Replace the typed chart repository, chart name, chart version, namespace, address-block size, ports, service selector and chart values of the portal template `exposed-app-with-access-request` with an application catalogue modelled in Infrahub. A requester picks an entry such as "Who am I" and supplies only what is theirs.

> **Routing note.** The `infrahub-speckit` pre-specify hook classifies this feature as spanning Schema, Objects, Generator, Menu and Transform artifacts and would start with the Schema template. Its connectivity step needs a live Infrahub (`infrahubctl info`), which this offline run does not have, so that step was skipped and the `infrahub-managing-schemas` skill was loaded by hand. The whole chain is specified in this one cycle at the owner's request, not one artifact type per cycle. See `RUN-NOTES.md`.

## Decisions already made

These were fixed before this specification and are recorded, not reopened.

- **D1. A new kind `ServiceApplicationDefinition`** is a catalogue entry. It is not a service instance and not a generator target. Attributes: `name` (unique), `title`, `description`, `chart_repository`, `chart_name`, `chart_version`, `default_values` (YAML text, never a JSON attribute: Infrahub 1.10.6 returns HTTP 500 for JSON keys containing a dot or a slash, which every Kubernetes label has), default advertised services, default address block size, default service selector, `requestable` (boolean) and `status` (`active` or `deprecated`). Only an `active` entry is requestable. It appears in the Infrahub menu under the Services group.
- **D2. `ServiceFabricApp` gains an optional relationship `definition`.** Never mandatory (Infrahub refuses a mandatory attribute against existing data). An application with no definition keeps working exactly as today with its inline chart fields. The seeded `otternet-demo`, `otternet-metrics` and `otternet-telemetry` become non-requestable catalogue entries and point at them, with identical rendered output.
- **D3. Pin at request time.** When an application with a definition is created, the effective chart fields and values are snapshotted onto the instance, so a later change to the catalogue never silently upgrades a running application. An upgrade is its own reviewed change. Where the snapshot is made, and how the values attachment is produced, is a plan decision.
- **D4. No user overrides in this version.** The requester cannot change chart values or the chart version. Name, namespace, owner, cluster, VRF, source site, justification and request reference remain requester-supplied, with the template's existing defaults.
- **D5. The portal template** replaces the chart, values, ports, block-size and selector fields with one picker of catalogue entries (active and requestable only), keeps the rest, and still creates the application and its access grant the same way.
- **D6. Event rules stay finite.** The watched-fields contract of `triggers.yml` is respected and every write-back is guarded.
- **D7. Seed data** goes in a new objects file in the right numeric order: `whoami` (requestable) plus one non-requestable entry per seeded application.
- **D8. Demo scripts and documentation** move to the picker's value.

## Clarifications

### Session 2026-10-04

Questions were raised by the clarify pass and answered by the author from decisions D1 to D8 and the repository's existing contracts. Six were asked, more than the skill's default five, because the author supplied them as a list; the cap is noted in `RUN-NOTES.md`.

- Q: Where is the pin made, given the schema keeps `chart_repository`, `chart_name` and `chart_version` mandatory (an existing contract test asserts it and must not be weakened)? -> A: Both ends. The portal template reads the chosen entry at request time and sends the three chart fields in the create, because the schema requires them. `generate-fabric-app` then pins once, on the request branch, from the entry: chart fields, values attachment from `default_values`, and the service selector and advertised services when the request left them empty. A new optional Boolean write-back attribute `definition_pinned` (default false) on `ServiceFabricApp` is the once-only marker, set in the same save as the chart fields. Seeded applications carry `definition_pinned: true`.
- Q: Is `definition` a watched input of the application's event rules? -> A: No. Re-pointing an application at another entry is an upgrade and its own reviewed change. `definition` and `definition_pinned` are both unwatched. The generator reads the entry through the SDK, so `generate_fabric_app.gql` and its generated query model do not change.
- Q: How is the values file produced? -> A: The generator creates a `ServiceFabricAppValuesFile` for the application and uploads `default_values` as its content, using the same checksum-guarded save the seeding script uses. The portal does not upload values for a catalogue request.
- Q: Who decides the block size? -> A: The portal reads the entry's default and sends it in the create. The generator never writes `vip_block_size`, because the application's rules watch it.
- Q: Where do the non-requestable entries get their values? -> A: From the payload files the seeded applications already attach, applied by `scripts/seed_app_payloads.py`, so git holds one source. `whoami`'s `default_values` is inline in the objects file. A unit test holds `whoami`'s values to what the transform requires of an exposed application.
- Q: How does the portal filter the picker to active, requestable entries? -> A: The kind is ingested into the portal catalogue as a Resource of type `application-definition`. The provider tags an entry `requestable` only when that attribute is true and its status is active (one derived tag, because a catalogue filter ORs the values of one key). The picker filters on kind, type and that tag. A template step then re-reads the entry from Infrahub and refuses a non-requestable or non-active one, so the filter is convenience and the step is the control.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Request an application by picking it from a catalogue (Priority: P1)

A requester opens "Exposed application, with access", picks "Who am I", names their application, chooses a namespace, owner, cluster, VRF and source site, gives a reference and submits. They never see a chart repository, chart version, values or block size. The request opens one proposed change carrying the application, its pinned chart, its VIP block and the access grant.

**Why this priority**: This is the whole point: chart choice is the platform team's decision, not the requester's.

**Independent Test**: With the catalogue seeded, parse the template: it asks for a catalogue entry and none of the five removed field groups; its create mutation sends the entry's chart coordinates and defaults read from Infrahub, not form values.

**Acceptance Scenarios**:

1. **Given** the seeded catalogue, **When** the portal picker lists entries, **Then** it lists `whoami` and no infrastructure entry, and no deprecated entry.
2. **Given** a requester picked `whoami`, **When** the application is created on the request branch, **Then** the application carries `chart_repository`, `chart_name`, `chart_version`, its advertised services, its service selector and its block size from the entry, plus a values attachment holding the entry's default values.
3. **Given** the same request, **When** the Crossplane artifact renders, **Then** it names chart `whoami` 6.0.0 and carries the values.

---

### User Story 2 - A catalogue change never upgrades a running application (Priority: P1)

A platform engineer raises `whoami`'s chart version in the catalogue. Applications already created from it keep their chart, version and values. Moving one to the new version is a separate, reviewed change to that application.

**Why this priority**: Without pinning, editing a catalogue entry is an unreviewed production change.

**Independent Test**: A unit test builds an application already pinned from an entry, changes the entry, runs the generator, and asserts the application is untouched and nothing is written.

**Acceptance Scenarios**:

1. **Given** a pinned application, **When** its definition's `chart_version` changes and the generator runs again, **Then** the application's chart fields and values file are unchanged.
2. **Given** an application created with a definition and not yet pinned, **When** its generator runs, **Then** it is pinned exactly once and the run after it writes nothing.

---

### User Story 3 - Platform team maintains the catalogue in Infrahub (Priority: P2)

A platform engineer sees "Application Catalogue" in the Infrahub menu under Services, creates an entry, marks it requestable, and later marks it deprecated so it leaves the portal picker without deleting it or touching applications built from it.

**Why this priority**: The catalogue is data, so it is maintained where the rest of the model is.

**Independent Test**: Schema contract tests: the kind exists, has the attributes of D1, is not a generator target, is reachable in the menu, and `ServiceFabricApp.definition` is optional.

**Acceptance Scenarios**:

1. **Given** the schema is loaded, **When** the menu is opened, **Then** the catalogue appears under Services.
2. **Given** an entry whose status is `deprecated`, **When** the portal catalogue refreshes, **Then** it is not offered, and applications already built from it are unaffected.

---

### User Story 4 - The seeded applications keep rendering identically (Priority: P1)

After the change, `otternet-demo`, `otternet-metrics` and `otternet-telemetry` point at catalogue entries, and every Crossplane artifact they render is byte-for-byte what it was.

**Why this priority**: The lab runs on these. A regression here is a live outage.

**Independent Test**: The existing rendered-artifact unit tests stay green and unchanged; a new test asserts each seeded application's chart fields equal its definition's.

**Acceptance Scenarios**:

1. **Given** the seed data, **When** it is loaded in filename order, **Then** every definition exists before the application that references it.
2. **Given** the seeded applications, **When** their definitions are compared with their inline chart fields, **Then** they agree.
3. **Given** an application with no definition, **When** it is created or rendered, **Then** behaviour is as before.

---

### User Story 5 - The demo still runs act one (Priority: P2)

The rehearsal and full-run scripts submit act one with the picker's value, and their checks still prove the rendered artifact shows chart `whoami` 6.0.0 and its values.

**Independent Test**: Unit tests over the scripts' act-one inputs; lab phase runs them for real.

### Edge Cases

- A request names an entry that is deprecated or not requestable (a stale form, or a hand-written request): the template must fail before the application is created.
- A definition has empty `default_values`: the application is pinned with no values attachment, and is not re-pinned on every run.
- An application with a definition is decommissioned: nothing is pinned, and nothing about the catalogue is changed.
- A definition is deleted while applications reference it: the relationship must not cascade into the applications.
- An application is created through the Infrahub UI with a definition and typed chart fields that disagree: the definition wins at pin time, and says so in the run log.
- An entry's `default_values` contains Kubernetes labels (dots and slashes): it must survive object load, since it is text and not JSON.
- The generator's own write-back to the application must not re-fire it unboundedly.

## Requirements *(mandatory)*

### Functional Requirements

#### Catalogue entry

- **FR-001**: The schema MUST define `ServiceApplicationDefinition` with the attributes in D1, a unique `name`, a human friendly id on `name`, and a display label that reads as the entry's title.
- **FR-002**: `default_values` MUST be a text attribute, never JSON.
- **FR-003**: `status` MUST offer `active` and `deprecated`, default `active`. `requestable` MUST be a boolean defaulting to false, so an entry is never user-facing by accident.
- **FR-004**: The kind MUST NOT inherit the service generic, MUST NOT be a generator target and MUST NOT be a member of a generator group.
- **FR-005**: The kind MUST appear in the Infrahub menu under the Services group, exactly once.
- **FR-006**: Default advertised services MUST be a relationship to the named service objects the access grant already derives ports from. Default service selector MUST be a list of `key=value` strings. Default block size MUST be a number bounded like the application's own.

#### Application link and pinning

- **FR-010**: `ServiceFabricApp` MUST gain an optional relationship `definition` to the entry, which MUST NOT cascade a delete in either direction.
- **FR-011**: An application with no `definition` MUST behave exactly as before: the generator, transform and portal paths for it are unchanged.
- **FR-012**: An application that has a definition and has not yet been pinned MUST be pinned on its request branch: `chart_repository`, `chart_name`, `chart_version` set from the entry, a values attachment produced from `default_values`, and its service selector and advertised services filled from the entry when the request left them empty.
- **FR-013**: Pinning MUST happen once. The generator MUST record that it has happened with the optional write-back Boolean `definition_pinned`, in the same write as the chart fields, and MUST NOT touch the pinned fields or the values attachment on any later run, whatever the entry says.
- **FR-014**: Pinning MUST NOT run for an application being withdrawn.
- **FR-015**: The mandatory-together rule for the chart fields MUST still hold for every application: the renderer MUST refuse an incomplete chart.
- **FR-016**: The rendered Crossplane artifact MUST read the instance's pinned fields only, never the entry.

#### Event rules

- **FR-020**: `definition` and `definition_pinned` MUST NOT be watched inputs (see Clarifications), and the trigger-contract test MUST hold that. No field the generator writes back may be watched, and the run after a pin MUST write nothing.
- **FR-021**: The generator MUST NOT write `vip_block_size`. The portal supplies the entry's default block size in the create.

#### Portal

- **FR-030**: The curated template MUST drop the chart repository, chart name, chart version, ports, block-size, service-selector and chart-values fields and gain one catalogue-entry picker offering only active, requestable entries.
- **FR-031**: The picker's entries MUST come from Infrahub through the portal's existing catalogue configuration, so a new entry needs no portal change.
- **FR-034**: The provider MUST ingest the kind as a Resource of type `application-definition` and tag an entry `requestable` only when it is requestable and active; the picker MUST filter on type and that one tag.
- **FR-032**: Before creating anything, the template MUST read the chosen entry from Infrahub and refuse the run if it is not active and requestable, so a stale or hand-edited form cannot request an infrastructure entry.
- **FR-033**: The application and the grant MUST still be created by the same steps, in the same order, as today; every existing template contract test MUST still pass.

#### Seed data

- **FR-040**: A new objects file MUST declare `whoami` (requestable) and three non-requestable entries, one per seeded application, loading before `36_otternet_app_services.yml`.
- **FR-041**: Each seeded application MUST carry a `definition` link and already hold the pinned fields, so its rendered output does not move and `invoke load` stays idempotent. Seeded applications are created on `main`, where no event rule fires, so the seed carries the pin.
- **FR-042**: The non-requestable entries' values MUST come from the same payload files the seeded applications already attach, so there is one source in git; `whoami`'s are inline in the objects file.
- **FR-043**: Seeded applications MUST carry `definition_pinned: true`.

#### Demo and documentation

- **FR-050**: `scripts/demo_rehearsal.py` and `scripts/demo_full_run.py` act one MUST submit the picker's value and MUST still assert chart `whoami` 6.0.0 and the values in the rendered artifact.
- **FR-051**: `docs/docs/demo-builder.md`, `docs/docs/demo-runbook.md`, `docs/docs/service-portal.md`, the schemas page and the generator and transform inventory MUST describe the catalogue.

### Key Entities

- **Application definition (catalogue entry)**: A platform-owned description of an application: where its chart is, which version, its default values, how it is advertised, and whether people may ask for it.
- **Fabric application**: The instance a requester asks for. Optionally points at the definition it came from; always carries its own pinned chart.
- **Values attachment**: The file attached to an application holding its chart values; produced from the entry's default values text when the application is pinned.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A requester completes the application request by filling in at most the ten fields the template keeps (name, description, namespace, cluster, VRF, owner, definition, source site, justification, request reference), none of them about charts.
- **SC-002**: 100 percent of the portal picker's entries are active and requestable; 0 infrastructure entries appear.
- **SC-003**: Editing a catalogue entry changes 0 existing applications.
- **SC-004**: The Crossplane artifacts rendered for the three seeded applications are unchanged, shown by the existing rendered-artifact tests passing without edit.
- **SC-005**: `uv run invoke lint` and `uv run invoke test` exit 0.
- **SC-006**: A creation costs the same number of generator runs as before plus at most one no-op.
- **SC-007**: Items that cannot be proven offline (live schema load, file attachment creation, portal build, a real request) are listed for the lab phase, not claimed.

## Assumptions

- The catalogue is edited on a branch and merged, like all other seed data; the portal refreshes within its existing interval.
- The generated Backstage form for `ServiceFabricApp` keeps working and gains the optional `definition` field through the same schema-driven path.
- Only `whoami` is requestable in this version; a second entry is added only if it renders without special handling, and none is.
