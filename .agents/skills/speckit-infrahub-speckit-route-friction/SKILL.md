---
name: speckit-infrahub-speckit-route-friction
description: Hook command — runs after the active integration's speckit implement command in Infrahub projects. Scans the finished cycle for evidence that an Infrahub skill's guidance had a gap, and offers to draft a skill-friction report. Detection is automatic; drafting and filing are not.
compatibility: Requires spec-kit project structure with .specify/ directory
metadata:
  author: opsmill
  source: infrahub-speckit:commands/speckit.infrahub-speckit.route-friction.md
---

# Infrahub Routing — post-implement friction hook

This command is fired as an `after_implement` hook by the `infrahub-speckit` extension. It runs every time the active integration finishes the core implement workflow, for example `/speckit-implement` in Codex skills or `/speckit.implement` in Claude Code slash commands, after its completion validation. If `.infrahub.yml` is not present, this command is a no-op.

Infrahub skills fail quietly. A missing or unclear rule does not crash the run; it produces extra round trips and repeated user nudges until the model works the answer out on its own. That friction is invisible by the time the cycle ends, which is why this hook looks for it while the session still holds the evidence.

**This hook detects. It does not draft, and it does not file.** Its entire output on the positive path is a one-line offer. Loading `infrahub-reporting-skill-gaps`, searching the tracker, and drafting anything happen only if the user accepts. Filing happens only after `infrahub-reporting-issues` takes the user through its own content-review and submission-method gates.

## Hook return semantics

Throughout this file, **"return"** means: stop emitting hook-command output and let control flow back to the calling core skill. Do NOT terminate the session or abort the parent command.

Unlike the `before_*` hooks in this extension, **this hook has no halt case**. It runs after implementation has already succeeded, so nothing it discovers may fail, retry, or roll back a finished run. Every path through this file ends in a return:

- emit a no-op line and return (not an Infrahub project, reporting skill absent, or no qualifying evidence), OR
- emit the Step 4 friction offer and return (positive case).

If any step of this hook errors, is ambiguous, or cannot be completed, emit a no-op line and return. A missed friction report costs nothing. A hook that disrupts a completed implementation cycle costs the user real work.

## Step 1 — Detect Infrahub project

If the repository has no `.infrahub.yml`, emit:

```
[infrahub-speckit] No .infrahub.yml detected. No friction check applied.
```

Then return.

## Step 2 — Check the reporting skill is available

Confirm `infrahub-reporting-skill-gaps` appears in your available-skills inventory.

**If it is missing**, emit this line and return:

```
[infrahub-speckit] infrahub-reporting-skill-gaps not installed. Friction check skipped.
```

Do NOT halt. Do NOT print install guidance. Do NOT block the completed run. This differs deliberately from Step 2 of the `route-specify`, `route-plan`, and `route-implement` hooks, which halt when the mandatory `infrahub-managing-*` skills are absent. Those skills are load-bearing for the work itself, and running without them is the silent-failure mode this extension exists to close. This one is load-bearing for nothing: implementation is already done, and an absent reporting skill means only that a report cannot be offered.

## Step 3 — Evidence gate

Scan **this session only** for evidence that an Infrahub skill's guidance had a gap. This is a cheap in-session read, not an investigation.

**Do not, in this hook:** run `gh` or search any issue tracker, read rule file contents, diff anything against git history, fetch documentation, or draft any part of a report. All of that belongs to `infrahub-reporting-skill-gaps` and happens only after the user accepts the offer.

The gate opens on any one of these three **closing** probes, drawn from the skill's detection ladder:

| Probe | What to look for | Notes |
|-------|------------------|-------|
| **Verifier verdict** | A red-to-green transition on the same target within this session: `infrahubctl schema load`, `infrahubctl object load`, `infrahubctl check run`, `infrahubctl transform run`, or a `pytest` run that failed and then passed against the same artifact. | Strongest evidence there is, because no self-assessment produced it. It only counts when the relevant `infrahub-managing-*` skill was loaded (by an earlier hook in this cycle) BEFORE the first failing attempt. |
| **Coverage read** | `ls` the implicated skill's `rules/` directory and check whether any filename covers the topic the model struggled with. An absence is a positive result. | Names the file, or names the gap. An `ls` is in scope here; reading the file contents is not. |
| **Correction delta** | The user rejected or rewrote an artifact the agent authored during this cycle, and the accepted version differs in a way a rule could have prevented. | The delta itself is the proposed rule change, so it must be visible in-session. Do not reconstruct it from git. |

**These do NOT open the gate**, on their own or in combination:

- retry counts and round-trip counts
- edit churn on the same file
- the user asking the same thing more than once
- a docs escape to `docs.infrahub.app`

These are session-shape counters. They rise for reasons that have nothing to do with a skill's guidance: an unclear request, a slow instance, a user changing their mind. Per the skill's own ladder, counters open an investigation and never close one. A hook that fired on a retry count would offer a report on most cycles and train the user to ignore it.

**If no closing probe is present**, emit this line and return:

```
[infrahub-speckit] No skill-guidance friction detected this cycle.
```

This is the expected outcome for most cycles.

## Step 4 — Emit the friction offer and return

If the gate opened, emit exactly this block, then return:

```
[infrahub-speckit — friction offer, post-implement]

Skill:        <IMPLICATED-SKILL-NAME>
Evidence:     <ONE-LINE-SUMMARY-OF-THE-CLOSING-PROBE>
Rule coverage: <RULE-FILENAME> | no rule file covers this topic

An Infrahub skill's guidance may have a gap here. Reply "report it" to draft a
skill-friction report for review. Nothing is filed without your approval.
```

Substitute the placeholders with the values from Step 3. Keep `Evidence` to one line and state what actually happened, for example `schema load failed on relationship cardinality, passed after correction` or `no rule covers CoreFileObject attribute kinds`.

**Do NOT invoke `infrahub-reporting-skill-gaps` here.** The offer above is the trigger that skill already declares ("accepting a friction offer"), so a user reply routes into it through its own description with no further wiring from this extension. Invoking it from this hook would load its full rule set and begin the tracker search on a cycle where the user never asked for either.

Then return. The implement command is complete, and any remaining `after_implement` hooks run next.

## What happens if the user accepts

Recorded here so the boundary is clear; none of it is this hook's work.

`infrahub-reporting-skill-gaps` runs its own detection ladder, searches `opsmill/infrahub-skills` for an existing report, triages skill defect vs. product defect, and drafts a redacted report from its template. It is explicitly forbidden from filing. It hands `{type, title, body, searched, issue?}` to `infrahub-reporting-issues`, which resolves the destination repo and owns the two remaining gates:

1. **Content review** (mandatory): target repo, title, and full body shown to the user, iterated until they approve.
2. **Submission method**: `gh` CLI, a GitHub MCP server, or manual copy-paste markdown plus the `issues/new` URL. The manual path sends nothing from this machine.

The user can stop at either gate.