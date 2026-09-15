# Phase 0 research: deployment reconciler

**Feature**: `specs/030-deployment-reconciler` | **Date**: 2026-09-15

Every finding below was measured against the **running lab** — 40 ContainerLab nodes, Infrahub
1.10.6 — not reasoned about. The feature rests on one assumption inherited from the design
review, that each device family can compute its own diff, and that assumption turns out to be
true in a much more qualified way than the review supposed.

**The headline: two of the three families report a permanent, non-empty difference against an
artifact the device already matches.** A naive "non-empty diff ⇒ push" reconciler would
replace the configuration of every FRR router and the perimeter firewall **on every cycle,
forever**. That is R2 and R3, and it is the single most important thing in this document.

---

## R1. EOS: the device computes a true diff, and an unchanged device reports nothing

**Decision**: use a configuration session — `configure session <name>` → `rollback clean-config`
→ artifact lines → `show session-config named <name> diffs` → `abort`. No normalisation needed.

**Measured**, against `leaf-nfd41-pod1-1-1` (366 artifact lines after the trailing `end` is
stripped):

| Case | Result |
| --- | --- |
| Unchanged artifact | **0 characters of diff** |
| Control: one line injected (`ip host probe-marker-does-not-exist 10.255.255.254`) | **133 characters**, correctly attributed |

The control output is the device's own comparison, not ours:

```text
--- system:/running-config
+++ session:/infrahub-probe-1789490201-session-config
+ip host probe-marker-does-not-exist 10.255.255.254
```

Afterwards, `show running-config | include probe-marker` was **empty** — the candidate was
never committed — and `show configuration sessions` returned `{}` on all seven switches.

**Why the control matters.** An empty diff on its own is worth nothing: it is indistinguishable
from a command that silently returns nothing, which is the same failure shape as an artifact
that reports `Ready` while empty. The injected line is what proves the comparison is live.

**Alternatives considered**: comparing artifact checksum to a last-applied checksum — rejected
by decision log item 6, because it detects a change in *intent* and cannot see drift in the
*device*, which is the whole point of user story 4.

---

## R2. FRR: an unchanged device reports lines to add, permanently

**Decision**: `frr-reload.py --test` is the right mechanism, but its output **must be
normalised** before it can be read as "differs or not". The normalisation is an explicit,
tested allowlist — not a fuzzy heuristic.

**Measured**, against `branch-rtr`, staging the artifact exactly as `push_frr` does:

```text
Lines To Add
============
router bgp 65030
 address-family ipv4 unicast
  neighbor 10.250.70.1 activate
 exit
exit
service integrated-vtysh-config
line vty
exit
```

That is the output for the device's **own unmodified artifact**. The control (one extra
`ip route 10.255.255.0/24 Null0`) produced the same block plus that route, and the device was
confirmed unchanged afterwards.

**Why it happens** — checked line by line against the device:

| Reported line | In `show running-config`? | Why |
| --- | --- | --- |
| `neighbor 10.250.70.1 activate` | **No** — only `remote-as`, `description`, `route-map` appear | Activation for IPv4 unicast is FRR's default, so the running config omits it while the artifact states it |
| `service integrated-vtysh-config` | No | A configuration-file directive, not running state |
| `line vty` | No | Same |

So the delta is **structural and permanent**. It is not drift and it will never converge.

**Two further traps measured at the same time:**

- **`rc` is not a signal.** `frr-reload.py --test` returned `0` for both the unchanged and the
  control run. Exit status cannot be used to decide whether to push.
- **The output format is `Lines To Add` / `Lines To Delete` sections, not `+`/`-` prefixes.** A
  first parser written against diff-style prefixes returned "0 differences" for the control as
  well as the baseline — a false negative that looks exactly like success. Noted because it is
  the obvious way to write this and it is wrong.

**Alternatives considered**:

- *Treat any output as drift.* **Rejected** — this is the defect: every FRR router replaced
  every cycle.
- *Compare artifact checksums for FRR only.* **Rejected** — it gives up drift detection for
  that family, which is user story 4, and it makes one family behave unlike the others.
- *Diff the delta against a stored baseline delta.* **Rejected as the primary mechanism** —
  it is stateful, it drifts silently when FRR's defaults change between versions, and nothing
  would tell you it had gone stale.
- *An explicit normalisation allowlist, asserted by unit tests.* **Chosen.** The set is small,
  structural, and explainable; a test over a captured real `--test` output fails the moment the
  set changes, rather than the reconciler quietly starting to churn.

---

## R3. Junos: an unchanged device reports 55 changed lines

**Decision**: `configure exclusive` → `load replace` → `show | compare` → `rollback 0` is the
right mechanism, and it too **must be normalised**, for two causes that are already documented
in this repository.

**Measured**, against `fw1`, staged exactly as `push_junos` does (including the `scp -O` flag —
omitting it fails with `problem checking file: No such file or directory`, and the resulting
empty compare looks like success):

| Case | Result |
| --- | --- |
| Unchanged artifact | **55 changed lines** |
| Control: one comment injected into `security` | **68 changed lines**, the marker clearly attributed |

Nothing was committed: `show configuration | compare rollback 1` came back empty.

**The 55 lines are two known categories:**

1. **Zone-pair ordering.** Eight lines of the form
   `!    from-zone acme-cloud to-zone wan { ... }`. `AGENTS.md` already documents this as the
   one difference the model cannot close: a zone pair is derived from each rule's source and
   destination zone, so no object carries an order, and Junos matches on zone rather than
   position. It is presentation, and it is permanent.
2. **Comments.** Junos does not retain the artifact's comment blocks in the committed
   configuration in the same form, so re-loading the identical artifact shows them as removed
   and re-added. The repository's own note that Junos re-serialises `## SECRET-DATA` with a
   fresh salt on any load is the same phenomenon in a different guise.

**Consequence**: identical in shape to R2. Without normalisation the firewall is
`load replace`-ed and `commit confirmed`-ed on every fourth cycle forever — on the device the
spec singles out as the one someone needs during an incident.

**Alternatives considered**: closing the zone-pair ordering gap in the model — **rejected**,
`AGENTS.md` explains why no object exists to carry that order, and inventing one to satisfy a
comparator is the tail wagging the dog. Suppressing comments in the renderer — **rejected**,
`AGENTS.md` is explicit that the comments are most of the teaching value of those configs.

---

## R4. What the normalisation layer has to be

**Decision**: a per-family `normalise(raw_diff) -> list[str]` step sitting between the device
and the decision to push, with three properties:

1. **Explicit.** Each suppressed pattern is named, with the reason, in one place.
2. **Tested against captured real output.** `tests/unit` holds the actual `--test` and
   `show | compare` text measured above; the tests fail if a suppressed pattern stops matching
   or an unsuppressed one starts being ignored.
3. **Fail-noisy.** Anything the allowlist does not recognise counts as a difference. The
   failure mode of an unknown line must be an unnecessary push, never a missed one.

**Rationale**: this is the difference between the feature working and the feature being a
fabric-wide config churn generator, and it is not visible from the design review — the review
concluded all three families "compute the diff themselves", which is true, and drew from that
the conclusion that an empty diff means in-sync, which is false for two of the three.

**Consequence for the spec**: FR-010 and FR-011 stand, but they are incomplete as written. The
plan adds FR-011a (normalisation, with the fail-noisy rule) and the spec should be amended to
match rather than leaving the implementer to discover R2 and R3 at 3am.

---

## R5. Is Nornir justified?

**Decision**: **No, not in this cycle.** Reconcile sequentially, reusing the existing code
path. Revisit if cycle wall-clock becomes a problem.

**Rationale**: Nornir buys concurrency and an inventory abstraction. Against that:

- **The inventory is already solved.** `provision_lab.discover()` returns every device with a
  rendered artifact and the identifier it can actually be reached by, in one GraphQL query,
  keyed on the artifact rather than the device kind — which sidesteps the sibling-kinds problem
  entirely. `nornir-infrahub`'s `InfrahubInventory` would be a second way to do something the
  repository already does correctly.
- **Concurrency is not the bottleneck and is not free.** Fifteen devices at the default
  600-second interval have ample headroom sequentially. Meanwhile the review already recorded a
  concurrency casualty: a per-host heartbeat "does not survive contact" because Nornir runs
  hosts in a `ThreadPoolExecutor` while the surrounding async context is a contextvar bound to
  the task.
- **Two new direct dependencies** (`nornir`, `nornir-infrahub`) need constitutional
  justification, and "we might parallelise later" is not one.

**Alternatives considered**: adopting Nornir now for the inventory alone — rejected, it
replaces working code with a dependency. Adopting it for concurrency — deferred; if wall-clock
becomes the constraint, `concurrent.futures` over the existing per-device functions is a
smaller step than a framework, and the firewall must stay serialised regardless because it
takes an exclusive lock.

**Spec impact**: the spec's framing assumed Nornir (inherited from the review). It is not a
requirement in the spec's FR list, so nothing there needs amending — but the assumption should
be corrected so the next reader does not treat it as settled.

---

## R6. Cleanup: what a cycle has to sweep

**Decision**: sweep EOS configuration sessions whose name carries this service's prefix, and
release a Junos exclusive lock this service holds. Measured surfaces:

- **EOS**: `show configuration sessions` returns a JSON object keyed by session name, so
  matching the `infrahub-` prefix is exact rather than textual. `configure session <name> abort`
  clears one. Verified: after the R1 probes, all seven switches reported `{}`.
- **Junos**: `configure exclusive` holds the lock for the life of the CLI session; `rollback 0`
  then `exit` releases it, verified by the R3 probe leaving the device committable.
- **FRR**: nothing to sweep. `--test` holds no lock and writes only into a staging directory
  this service owns.

**Rationale for doing it at cycle start rather than only in `finally`**: the spec's FR-032 is
right that `try/finally` does not survive SIGKILL, and the R1 probe shows why it matters — EOS
keeps one completed session per name, and `provision_lab.py` already carries a comment
recording that a fixed session name works exactly once per device and fails on every later run.

---

## R7. Not trusting `Ready`

**Decision**: download every artifact and refuse to push an empty one. Do **not** skip on
status.

**Rationale**: `provision_lab.py:614` currently does the opposite — it skips anything whose
status is not `Ready` and pushes anything that is. This repository documents twice that
`Ready` is not evidence of content, and `scripts/verify_bootstrap.sh` was written around that
fact. For a human-triggered command the risk is a wasted run; for a loop that pushes replaces
every ten minutes, an empty artifact treated as intent erases a device.

Measured incidentally during R1–R3: every artifact downloaded had content, and the EOS one was
366 lines. The guard is for the case that is rare, not the case observed.

---

## R8. The write cadence (spec FR-028)

**Decision**: write **only on change**, plus a heartbeat on `last_checked_at` **once per
cycle per device**, which is the same thing as writing every cycle for that one field.

Honest statement of the trade, since FR-028 exists to force it rather than inherit it:

- Writing every field every cycle: ~2,000 versioned mutations a day across fifteen devices.
- Writing nothing unless something changed: a stale record is ambiguous between "fine" and
  "the loop died a week ago".

`last_checked_at` is the field cycle 029 added precisely to resolve that ambiguity, so it is
the one that must move every cycle; `status`, `last_confirmed_at`, `last_error` and the diff
file move only when they change. That keeps the ambiguity closed at roughly one write per
device per cycle rather than seven.

---

## R9. Single instance (spec FR-006) and non-overlapping cycles (FR-005)

**Decision**: one process, one loop, no internal concurrency; overlap prevented by construction
rather than by a lock, because a sequential loop cannot overlap itself. Two instances are
prevented operationally — the service runs as a single compose service with no replicas.

**Rationale**: the review's own conclusion was "concurrency control is one loop with one lock",
and with R5 removing Nornir there is no internal parallelism left to guard. This is worth
stating rather than assuming, because the edge case in the spec — two reconcilers pushing
replacements to the same device — is the worst failure mode available here, and "we only start
one" is a weaker guarantee than it sounds. A cheap belt-and-braces option, deferred: take a
short-lived marker in Infrahub at cycle start so a second instance refuses to run.

---

## Summary of what changed relative to the spec

| Spec statement | Research outcome |
| --- | --- |
| FR-010 device computes the diff | **True for all three, but insufficient.** R1 clean; R2 and R3 need normalisation |
| FR-011 no difference ⇒ no push | **Needs FR-011a**: "no difference" must be defined after normalisation, fail-noisy |
| Nornir device layer (assumption) | **Dropped for this cycle** (R5). No new dependency |
| FR-028 write cadence undecided | **Decided** (R8): `last_checked_at` every cycle, everything else on change |
| FR-030 cleanup surfaces | **Confirmed and measured** (R6) |

No `NEEDS CLARIFICATION` items remain.
