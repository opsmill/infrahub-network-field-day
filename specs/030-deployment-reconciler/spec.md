# Feature Specification: Deployment reconciler

**Feature Branch**: `030-deployment-reconciler`

**Created**: 2026-09-15

**Status**: Draft

**Input**: User description: "move onto the next stage"

## What this cycle is

Cycle 029 built the place to record deployment state and nothing that writes to it. Right
now there are zero `DeploymentState` records, nothing reads a device, and the gap between a
merge landing on `main` and the devices matching it is still closed by a human typing
`uv run invoke provision`.

This cycle closes that gap. It builds the reconciler the design review in
[../029-deployment-executor/grilling-decision-log.md](../029-deployment-executor/grilling-decision-log.md)
settled on: **a loop, Nornir, and Infrahub as the source of truth.** No webhook receiver, no
approval gate, no separate state store — all three were removed under challenge, and the
reasons are recorded there rather than re-litigated here.

It is not an Infrahub artifact. It adds no generator, transform or check. The
`infrahub-speckit` router matched schema/transform/generator keywords in the description, but
every one of them is *referential* — this feature reads artifacts that already exist and writes
to kinds that already exist.

> **This paragraph used to claim the cycle added no schema and no menu, and both turned out to
> be wrong during implementation.** FR-015 requires `pending` to be distinguishable from
> `drifted`, and there was nowhere to remember the previous artifact, so `DeploymentState`
> gained `last_artifact_checksum`. Cycle 029's queued menu handoff was also closed here: a
> curated `menus/menu.yml` entry, with `include_in_menu` flipped to `false`. Both are recorded
> where they happened rather than left as a tidier claim in the introduction.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A merge reaches the devices without anyone typing a command (Priority: P1)

An engineer merges a proposed change. Within one cycle, every device whose rendered
configuration changed has been brought into line with it, and no one ran anything. Today that
step is `uv run invoke provision`, which means a merge at 6pm on a Friday reaches the fabric
on Monday, or whenever somebody remembers.

**Why this priority**: it is the entire feature. Everything else in this spec either makes
this safe or makes it visible.

**Independent Test**: change one device's intent on `main`, wait one cycle, and confirm the
device's own comparator reports no difference afterwards — without running `invoke provision`.

**Acceptance Scenarios**:

1. **Given** a device matches its rendered configuration, **When** a cycle runs, **Then** the
   device is compared and nothing is pushed.
2. **Given** a device's rendered configuration has changed, **When** a cycle runs, **Then**
   the change is pushed and the device afterwards reports no difference.
3. **Given** a fabric switch, an FRR router and the firewall all need a change, **When** a
   cycle runs, **Then** all three are brought into line — the loop covers every family the
   lab has, not only the AVD-rendered switches.
4. **Given** one device fails to accept its configuration, **When** the cycle finishes,
   **Then** the other devices were still reconciled and the failure is recorded against that
   device alone.

---

### User Story 2 - An operator can see whether their merge reached the fabric (Priority: P1)

The engineer from story 1 wants to know it worked. They look in Infrahub — the same UI they
raised the proposed change in — and see, per device, whether it has been **confirmed to match**
and when.

**Why this priority**: decision log item 9 is why deployment state lives in Infrahub at all,
and cycle 029 built the model for exactly this. A reconciler that silently does the right
thing is indistinguishable from one that has crashed.

**Independent Test**: run one cycle against an unchanged fabric and confirm every device has a
record whose confirmation timestamp moved, without any device having been written to.

**Acceptance Scenarios**:

1. **Given** no records exist, **When** the first cycle runs, **Then** every device in scope
   has exactly one `DeploymentState`, and its `name` is the device's name.
2. **Given** a device was compared and found to match, **When** the record is read, **Then**
   `status` is `in_sync` and `last_confirmed_at` has moved to this cycle.
3. **Given** a device was compared and found to differ, **When** the record is read, **Then**
   `last_checked_at` moved but `last_confirmed_at` did **not** — confirmation means the device
   matched, never that a push was sent.
4. **Given** a push failed, **When** the record is read, **Then** `status` is `failed`,
   `last_error` carries the detail, and the next cycle tries again.
5. **Given** a device was removed from the model, **When** a cycle runs, **Then** its record is
   swept rather than left pointing at nothing.

---

### User Story 3 - One device can be taken out of the loop without stopping the service (Priority: P1)

Someone is working on the perimeter firewall at 3am during an incident and has added a rule
by hand. They set `suspend` on that device's record. The reconciler leaves it alone and keeps
reconciling everything else.

**Why this priority**: drift is corrected automatically and without asking (decision log item
15), so this is the mitigation that decision required in the same breath. **Auto-push must not
ship before this works.** Without it the only break-glass is `docker stop`, which suspends
reconciliation for the whole fabric.

**Independent Test**: suspend one device, change its intent, run a cycle, and confirm the
device was not touched while another changed device was.

**Acceptance Scenarios**:

1. **Given** a device's record has `suspend` set, **When** a cycle runs, **Then** that device
   is not connected to, not compared, and not pushed.
2. **Given** a suspended device, **When** its record is read after a cycle, **Then** its
   status still shows what it was doing when it was suspended — suspension does not overwrite
   the last observation.
3. **Given** suspension is cleared, **When** the next cycle runs, **Then** the device is
   reconciled normally.

---

### User Story 4 - Drift is corrected, not just intent changes (Priority: P2)

Someone changed a switch by hand and did not tell anyone. The artifact has not moved; the
device has. The reconciler notices and puts it back.

**Why this priority**: this is what makes it a reconciler rather than a deployment trigger,
and decision log item 6 is explicit that comparing checksums detects a change in *intent* and
would miss this entirely. It is P2 only because story 1 is shippable without it.

**Independent Test**: change a device by hand without touching Infrahub, run a cycle, and
confirm the device is returned to its rendered configuration.

**Acceptance Scenarios**:

1. **Given** a device was changed outside Infrahub, **When** a cycle runs, **Then** the
   difference is detected even though the rendered artifact has not changed.
2. **Given** drift is detected, **When** the record is read, **Then** `status` is `drifted`,
   distinguishing it from `pending` — the two have different causes and an operator reading
   the record needs to know which.
3. **Given** drift is detected on a device that is **not** suspended, **When** the cycle
   continues, **Then** the device is corrected without anyone being asked.
4. **Given** a difference was found, **When** the record is read, **Then** the device's own
   diff output is attached as evidence.

---

### User Story 5 - Each cycle cleans up after the last one (Priority: P2)

A cycle that died badly left a configuration session open on a switch or a lock held on the
firewall. The next cycle clears its own leftovers before it starts work.

**Why this priority**: decision log item 14 puts cleanup in scope from day one, and the reason
is specific — **EOS holds a finite number of configuration sessions, so a checker that dies
often enough removes the ability to deploy at all.** `try/finally` does not survive SIGKILL,
which is exactly how a container gets stopped.

**Independent Test**: leave a session open on a switch by hand, run a cycle, and confirm the
session is gone and the device still reconciles.

**Acceptance Scenarios**:

1. **Given** a switch has configuration sessions left by earlier cycles, **When** a cycle
   starts, **Then** those sessions are aborted before any comparison begins.
2. **Given** sessions exist that this service did not create, **When** cleanup runs, **Then**
   they are left alone — only this service's own sessions are swept.
3. **Given** the firewall holds a configuration lock from an earlier cycle, **When** a cycle
   starts, **Then** the lock is released.

---

### User Story 6 - A change can be checked against the devices before it is merged (Priority: P2)

Before merging, an engineer asks what a branch would do to the fabric, and gets back the
devices' own diffs — without anything being pushed and without any state being written.

**Why this priority**: it falls out of the same machinery as story 1 (decision log item 12
notes the dry run "comes free"), and it is the answer to "auto-push makes me nervous". P2
because story 1 delivers value without it.

**Independent Test**: run a dry run against a branch with a known change and confirm the diff
is reported, no device changed, and no `DeploymentState` was written.

**Acceptance Scenarios**:

1. **Given** a branch with a changed configuration, **When** a dry run is requested against
   it, **Then** the per-device differences are reported.
2. **Given** a dry run completes, **When** the devices are inspected, **Then** none of them
   changed.
3. **Given** a dry run completes, **When** deployment records are read, **Then** none was
   created or modified — deployment state is a fact about `main`, never about a branch.

---

### User Story 7 - The push path is covered by tests (Priority: P3)

The knowledge that makes pushing safe — stripping the trailing `end`, checking the management
lifeline survives, tagging Junos stanzas for `load replace` — is currently in a 678-line
script with **no tests at all**. Lifting it into an importable module is the moment to add
them.

**Why this priority**: it protects stories 1 to 6 rather than delivering anything itself. But
the reconciler will call this code every ten minutes instead of when a human chooses to, so a
regression in it now has a much larger blast radius than it does today.

**Independent Test**: the guards can be exercised in `tests/unit` with no devices and no
Infrahub instance.

**Acceptance Scenarios**:

1. **Given** a rendered EOS configuration ending in `end`, **When** it is prepared for a
   session, **Then** the trailing `end` is removed and blank lines are dropped.
2. **Given** an EOS configuration missing the management lifeline, **When** a push is
   attempted, **Then** it is refused before anything is sent.
3. **Given** a Junos configuration that contains a `system` stanza, **When** a push is
   attempted, **Then** it is refused — that stanza carries credentials that are never
   modelled.
4. **Given** the lift is complete, **When** `uv run invoke provision` is run, **Then** it
   behaves exactly as before — the command stays, its implementation moves.

---

### Edge Cases

- **A cycle takes longer than the interval.** The firewall wait alone can block for up to ten
  minutes. Cycles must not overlap and must not queue up behind each other.
- **The artifact exists, reports `Ready`, and is empty.** This repository documents twice that
  `Ready` is not evidence of anything. The current script trusts it
  (`provision_lab.py:614` skips anything not `Ready` and pushes anything that is), and an
  empty artifact pushed as a replace would erase a device.
- **Infrahub is unreachable.** A cycle that cannot read intent must change nothing, rather
  than treating "no artifact" as "empty configuration".
- **A device is unreachable.** One unreachable device must not stop the other fourteen.
- **The service restarts mid-cycle.** A half-applied cycle must be recoverable by the next
  one, with no manual repair.
- **Two instances are started by accident.** Two reconcilers pushing replacements to the same
  device is the worst failure mode available here.
- **A device is renamed.** Its record's `name` is a copy; cycle 029 made keeping it in step
  the reconciler's job, and a rename must converge rather than strand a record and create a
  second one.
- **The firewall is mid-commit-confirmed when a cycle starts.** Rolling back under a new push
  is a way to lose both changes.
- **A device has no rendered artifact at all.** Not every device modelled is one this service
  should push to.

## Requirements *(mandatory)*

### Functional Requirements

#### The loop

- **FR-001**: The service MUST run continuously, reconciling on a fixed interval, with no
  external trigger. It MUST NOT receive webhooks.
- **FR-002**: The interval MUST default to **600 seconds**, matching Vidra's
  `requeueResourcesAfter`, so both reconcilers in the environment drift at the same rate and
  an operator learns one number.
- **FR-003**: The interval MUST be configurable, and the service MUST **refuse to start**
  below a floor of **60 seconds** rather than silently clamping.
- **FR-004**: The perimeter firewall MUST be checked only on every **fourth** cycle. Checking
  it takes an exclusive configuration lock, and at the default interval a per-cycle check
  would take that lock 144 times a day on the device someone needs during an incident.
- **FR-005**: Cycles MUST NOT overlap. A cycle still running when the next is due MUST cause
  the next to be skipped, not queued.
- **FR-006**: Only one instance MUST reconcile a given fabric at a time.
- **FR-007**: The service MUST reconcile against `main` only.

#### Deciding what to do

- **FR-010**: The comparison MUST be computed **by the device**, not by comparing checksums.
  Each family already offers this and two already do it inside the existing push path.
- **FR-011**: A device reporting no difference MUST NOT be pushed to.
- **FR-011a**: "No difference" MUST be evaluated **after per-family normalisation**. Measured
  against the running lab (research R2, R3), two of the three families report a permanent
  non-empty difference against an artifact the device already matches — FRR because the
  artifact states defaults and file-directives that `show running-config` never echoes back,
  Junos because of zone-pair ordering and comment round-tripping, both already documented in
  `AGENTS.md` as differences the model cannot close. Without normalisation this service
  replaces the configuration of every FRR router and the firewall on every cycle, forever.
  The normalisation MUST be:
  - **explicit** — each suppressed pattern named, in one place, with its reason;
  - **tested against captured real device output**, so the set cannot rot unnoticed;
  - **fail-noisy** — anything unrecognised counts as a difference, so an unknown line causes an
    unnecessary push and never a missed one.
- **FR-011b**: Exit status MUST NOT be used to decide whether a device differs. `frr-reload.py
  --test` returns `0` both when the configuration matches and when it does not (research R2).
- **FR-012**: The service MUST NOT treat an artifact's `Ready` status as evidence that it has
  content. It MUST download the artifact and MUST refuse to push an empty or truncated one.
- **FR-013**: Failure to read intent MUST result in no change to any device.
- **FR-014**: A device with `suspend` set MUST be skipped entirely — not connected to, not
  compared, not pushed.
- **FR-015**: Drift MUST be corrected without asking, and MUST be distinguishable in the
  record from a change in intent.
- **FR-016**: Every push MUST be a full replace, so that deleting something from the model
  deletes it from the device.
- **FR-017**: A failed device MUST NOT stop the cycle. The loop itself is the retry: every
  push is a replace and the next cycle recomputes the difference from scratch.

#### Recording what happened

- **FR-020**: The service MUST write per-device state into the `DeploymentState` kind from
  cycle 029, and MUST NOT keep its own state store. It MUST be able to restart with no local
  state and behave correctly.
- **FR-021**: `last_confirmed_at` MUST move **only** when the device itself reported no
  difference. It MUST NOT move because a push was sent.
- **FR-022**: `last_checked_at` MUST move on every comparison, including ones that find a
  difference and ones that fail, so that a stale confirmation is distinguishable from a dead
  reconciler.
- **FR-023**: The service MUST own the record's `name`, setting it on creation and refreshing
  it from the device, so a rename converges.
- **FR-024**: The service MUST create at most one record per device, upserting rather than
  creating. The graph enforces uniqueness on `name`, not on the device relationship, so this
  is the service's responsibility (cycle 029, FR-050).
- **FR-025**: Records whose device no longer resolves MUST be swept.
- **FR-026**: When a difference is found, the device's own diff output MUST be stored as a
  `DeploymentDiffFile` against that record.
- **FR-027**: The service MUST NOT cause regeneration. Nothing it writes may be a generator
  input, artifact target, or trigger source.
- **FR-028**: The write cadence MUST be decided explicitly and stated. Cycle 029 left this
  open deliberately: writing every cycle shows the loop is alive; writing only on change
  costs fewer versioned mutations but makes a stale record ambiguous between "fine" and "the
  loop died". At the default interval across roughly fifteen devices, writing every cycle is
  about 2,000 versioned writes a day.

#### Cleaning up

- **FR-030**: Each cycle MUST begin by sweeping leftovers from earlier cycles: configuration
  sessions on EOS devices matching this service's own prefix, and a firewall lock it owns.
- **FR-031**: Cleanup MUST NOT touch sessions or locks this service did not create.
- **FR-032**: Cleanup MUST NOT depend on orderly shutdown. `try/finally` does not survive
  SIGKILL, which is how a container is stopped.

#### The dry run

- **FR-040**: A dry run against a branch MUST report per-device differences without changing
  any device.
- **FR-041**: A dry run MUST write no deployment state.

#### The device layer

- **FR-050**: The push logic in `scripts/provision_lab.py` MUST be **lifted into an importable
  module, not rewritten**. Those 678 lines already encode the expensive knowledge, most of it
  learned by measurement against the running lab.
- **FR-051**: `uv run invoke provision` MUST continue to work unchanged after the lift.
- **FR-052**: The guards MUST gain unit tests — the trailing-`end` strip, the management
  lifeline check, and the Junos scope assertion. There are currently none.
- **FR-053**: The inventory MUST be built from Infrahub, keyed on the generic device kind so
  that all four device kinds are visible. A query naming a concrete kind sees only that kind.

#### Operating it

- **FR-060**: The service MUST log each cycle in a form that says which devices were compared,
  which differed, which were pushed, and which failed.
- **FR-061**: Credentials MUST NOT be written to logs, to Infrahub, or to any artifact.
- **FR-062**: The service MUST start reconciling without manual priming after a restart.

### Key Entities

- **DeploymentState** (exists, cycle 029): one record per device — `name`, `status`,
  `last_confirmed_at`, `last_checked_at`, `last_attempt_at`, `last_error`, `suspend`,
  `suspend_reason`, and an optional device relationship. This service is its only writer.
- **DeploymentDiffFile** (exists, cycle 029): the device-computed difference, stored as a
  file against a record.
- **Device families**: `DcimFabricSwitch` reached by management address over its API;
  `DcimDevice` (FRR) and `SecurityFirewall` reached by container name. The names do not match
  between Infrahub and the lab, which is why the route in differs by family.
- **Rendered artifacts** (exist): the AVD EOS configuration, the FRR configuration, and the
  Junos configuration. This service reads them and never produces them.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A merge to `main` is reflected on every affected device within two cycles, with
  no human action.
- **SC-002**: A fabric already matching its intent produces **zero** device changes across ten
  consecutive cycles, while still confirming every device.
- **SC-003**: A hand-made change to a device is reverted within two cycles.
- **SC-004**: A suspended device is untouched across ten consecutive cycles while other
  devices continue to be reconciled.
- **SC-005**: An operator can answer "has this device been confirmed to match since my merge?"
  from the Infrahub UI alone, with no shell access.
- **SC-006**: Killing the service mid-cycle and restarting it leaves no device unreconcilable —
  in particular, no switch accumulates configuration sessions across ten kill/restart rounds.
- **SC-007**: One unreachable device does not prevent any other device from being reconciled
  in the same cycle.
- **SC-008**: A dry run against a branch changes no device and writes no record.
- **SC-009**: The reconciler and Vidra can both act on the same merge without either
  preventing the other from reaching its steady state.
- **SC-010**: `uv run invoke provision` produces the same result after the lift as before it.
- **SC-011**: The push-path guards are covered by tests that run in `tests/unit` with no lab
  and no Infrahub instance.

## Assumptions

- **The device layer is Nornir.** Phase 0 dropped it (research R5) and it was reinstated
  afterwards (R5a): a full sweep goes from ~10 s to 3.3 s, and the ceiling moves with worker
  count rather than device count. The contextvar hazard the review recorded is designed around
  rather than avoided — Nornir tasks do device I/O only and return plain data, and every state
  write happens in the caller's coroutine afterwards. The firewall is still never parallelised,
  because its comparison takes an exclusive lock.
- **The orchestrator is a plain loop, not Temporal.** The decision log's item 16 left this
  open, and answered it in the same breath: the webhook went at item 5 and the approval gate
  at item 15, so what remained for Temporal was scheduling, retry and history — and a
  600-second loop *is* the retry, history now lives in Infrahub, and concurrency control is
  one loop with one lock. The remaining case for Temporal is multi-fabric scale or an external
  operational standard. Neither applies to one lab fabric. If either appears later, the device
  layer and the state model are unchanged by the switch.
- **Ordering against Vidra is not enforced.** Both act on the same merge with nothing
  sequencing them, so a `FabricPeering` can land before a leaf has its BGP configuration.
  Both are reconcilers, so the fabric converges anyway — the transient is a few minutes of
  peering pointing at a device that is not ready. `invoke bootstrap` remains the sequencer for
  a cold build. This is worth stating rather than discovering, and is the assumption most
  likely to need revisiting.
- **Nothing alerts.** The record's status is the signal, and an operator or a dashboard reads
  it. Adding an alert destination is a later decision; a reconciler that corrects the problem
  is a poor source of pages.
- **Devices in scope are those with a rendered configuration artifact.** A modelled device
  with nothing rendered for it is not this service's business.
- **The lab's three front doors stay as they are.** Switches by management address, FRR and
  the firewall by container name, because Infrahub's names and ContainerLab's names do not
  match and there is no renaming layer.
- **`Ready` is never trusted.** This is assumed rather than discovered because the repository
  has already documented it twice and `scripts/verify_bootstrap.sh` was written around it.

## Decisions taken on the review's open items

Two of the decision log's open items were decisions this spec could not make unilaterally.
Both are now settled.

- **FR-070**: The service **lives in this repository**, beside `scripts/provision_lab.py`
  whose push logic it lifts and beside the `Deployment` schema it writes to. This keeps the
  lift (FR-050) a file move within one checkout and one test suite, rather than a change that
  crosses a repository boundary and versions independently.

  The cost is accepted knowingly and is editorial rather than technical: this repository is
  the published Arista AVD reference design, synced to `opsmill/infrahub-docs` and live at
  `docs.infrahub.app/arista-avd`, so a bespoke lab executor becomes part of what the reference
  design appears to offer. Two things follow from that and are requirements, not notes:

- **FR-072**: The service MUST be documented as what it is — a reference implementation of the
  reconciler pattern for this lab — rather than as a supported component of the AVD reference
  design.
- **FR-073**: Adding the service MUST NOT change the behaviour of any existing documented
  workflow. `invoke provision`, `invoke bootstrap` and the artifact chain MUST work exactly as
  they do today whether or not the reconciler is running.

- **FR-071**: The service **reuses the existing environment variables**,
  `NFD41_EOS_PASSWORD` and `NFD41_VSRX_PASSWORD`, exactly as `invoke provision` does today. No
  new credential machinery is built in this cycle.

  This is a deliberate acceptance of a real change in blast radius, and stating it is the
  point: today those credentials exist in a human's shell for the duration of one command;
  afterwards they sit in a long-running service that can replace the configuration of every
  device in the fabric on a timer. What makes it acceptable is that this is a lab, and that
  three controls already in this spec bound it — the per-device `suspend` flag (FR-014), the
  60-second floor (FR-003), and the dry run that changes nothing (FR-040, FR-041). What does
  **not** bound it is anything to do with least privilege, because there is none here. Two
  requirements follow:

- **FR-074**: Credentials MUST be supplied to the service by environment variable only. They
  MUST NOT be baked into an image, committed, or written into Infrahub.
- **FR-075**: The blast radius MUST be stated in the service's own documentation, so that
  anyone lifting this pattern into an environment that is not a lab meets the decision rather
  than inherits it.

  Scoped per-family service accounts and a read-only compare pass were both considered and
  deferred, not rejected. They are the obvious next step if this ever runs anywhere real, and
  neither changes the device layer or the state model.
