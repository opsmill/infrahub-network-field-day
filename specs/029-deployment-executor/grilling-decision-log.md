# Deployment executor — grilling and decision log

**Date**: 2026-09-15
**Status**: design settled in outline, three items open
**Context**: closing the gap between "a merge lands on `main`" and "the devices match it".
Today that gap is a human typing `uv run invoke provision`.

This document records an adversarial design review. Each section states the challenge, the
answer given, and what the answer settled. It exists so that nobody re-litigates the webhook
in three months without first reading why it was dropped.

## The proposal that went in

FastAPI receiver on `infrahub.proposed_change.merged`, Temporal for orchestration, Nornir for
the device pass, `scripts/provision_lab.py` lifted into an importable module.

## The design that came out

| | Opening proposal | After the review |
| --- | --- | --- |
| Trigger | `proposed_change.merged` webhook | poll loop, 600s default, floor enforced |
| Receiver | FastAPI | **gone** — nothing to receive |
| State | unspecified | Infrahub, separate deployment kind related to `DcimGenericDevice`, `main` only |
| Comparison | artifact checksum | **device-computed diff** |
| Semantics | "last checksum sent" | **"last time the device was confirmed to match"** |
| Drift | out of scope | detected, and corrected automatically |
| Approval gate | Temporal signal | **gone** — auto-push |
| Orchestrator | Temporal | **open** — see [Open items](#open-items) |
| Device layer | Nornir | unchanged |

Every change came from a decision made under challenge, not from the original design.

## The exchange

### 1. Has anyone ever received an Infrahub custom webhook?

**Challenge**: the whole trigger rests on a mechanism nobody here has exercised.
**Answer**: yes, it retries.
**Settled**: delivery is at-least-once, which is a hazard rather than a comfort — see 3.

### 2. What makes a second delivery of the same merge a no-op?

**Challenge**: every push is a replace; at-least-once delivery plus a slow push (`_wait_for_vsrx`
blocks up to 600s) means a retry can arrive while the first push is still on the wire.
**Answer**: the merge information is in the webhook payload — key on it.
**Settled**: the proposed-change ID in the body is the idempotency key. Correctly *not* the
`webhook-id` header: Infrahub's retry "runs as a new delivery", so that header is unstable across
exactly this case.

### 3. How do you tell an intentional replay from a duplicate?

**Challenge**: an operator who fixes a switch and hits retry means it. The dedupe key cannot see
the difference.
**Answer**: ignore retries.
**Settled**: delivery becomes **at-most-once**. If the receiver is down when the merge fires, the
merge is never deployed and nothing surfaces it. Recovery is a human running `invoke provision`.
Acceptable for a lab, but it must be stated rather than emergent.

### 4. What guarantees the artifacts exist on `main` when the trigger fires?

**Challenge**: this repository already documents that generation is asynchronous, that an empty
artifact reports `Ready`, and that `provision` can therefore push nothing. `invoke avd --merge`
carries `_wait_for_artifacts` for this reason; `scripts/verify_bootstrap.sh` downloads every
artifact rather than trusting status.
**Answer**: poll artifacts for a checksum change, the way Vidra does.
**Settled**: polling — with the consequences in 5 and 6.

### 5. Vidra's polling works because it has no deadline. Yours has one.

**Challenge**: at the deadline, an unchanged checksum is ambiguous — regeneration may not have
reached that artifact, or this merge legitimately changed nothing for that device (the common
case, and near-universal in Infrahub 1.11, where a merge regenerates only what it affected).
Push anyway and you push an unproven artifact as a replace; skip and a device silently misses a
change it needed.
**Answer**: maybe don't wait for a webhook at all — poll all the time.
**Settled**: **the webhook is dropped.** The FastAPI receiver has nothing to receive. The design
becomes a reconciler, which also resolves the coherence objection that Kubernetes delivery was
declarative while network delivery was event-driven.

### 6. What do you compare against what?

**Challenge**: comparing artifact checksum to last-applied checksum detects a change in *intent*,
not drift in the *device*. That is precisely why a resource deleted under Vidra stays missing for
ten minutes while the sync reports `Succeeded`.
**Answer at the time**: checksum.
**Revised at 12**: device state. See below.

### 7. Where does "the checksum I last applied" live?

**Challenge**: three edges — partial failure (five switches take it, two fail; recording
artifact-level state strands the failures forever), cold start (empty state means a
fabric-wide simultaneous replace triggered by a container restart), and the fact that the store
becomes a claim about device state that nothing can ever correct.
**Answer**: somewhere in the FastAPI app.
**Note**: the FastAPI app had been deleted two answers earlier.

### 8. In-process memory or a database — and why not the source of truth?

**Challenge**: memory makes every restart a fabric-wide config event; a database makes a third
one in the environment. And the deeper question: you built a product around a single source of
truth — why is "what is on this device" the one fact living in a sidecar?
**Answer**: SQLite.
**Note**: answers *which* database, not *why* a separate one. The file then needs a named volume,
and an unmounted volume is indistinguishable from "nothing was ever applied" — which by this
design means push everything, everywhere, at once.

### 9. Where does an operator look to see whether their merge reached the fabric?

**Challenge**: a SQLite file in a container is not a place a network engineer looks. A UI on the
executor is a fourth service; exposing it through Infrahub means writing it to Infrahub anyway;
Temporal history is engine detail with finite retention.
**Answer**: use Infrahub as the data store, and track state and deployment progress there.
**Settled**: **state lives in Infrahub.** The executor becomes stateless. Cold start is a
non-event, partial failure is recorded per device by construction, and deployment state is
visible in the UI everything else uses.

### 10. What stops the feedback loop, and what does the write volume do to the graph?

**Challenge**: writing state onto a device emits an event; `triggers.yml` turns node events into
generator runs; a generator run regenerates artifacts; a moved checksum is what the poller acts
on. Today the loop does not close only because no trigger watches a switch — **by accident, not by
design**. Separately, Infrahub versions every mutation, so a heartbeat-per-cycle is tens of
thousands of versioned writes a day.
**Answer**: a separate schema for the deployment objects, related back to the device.
**Settled**: a separate kind, in the shape of `AvdHostvarFile` / `AvdStructuredConfigFile` hanging
off `AvdArtifact`. **Still required**: a stated rule that nothing generates from deployment kinds,
and a test that fails when someone adds a trigger on one.

### 11. Branch-aware or branch-agnostic?

**Challenge**: deployment state is a fact about the physical world, not about a branch. Modelled
branch-aware, a branch created Monday and merged Friday carries Monday's deployment state into
`main`, and every proposed change shows deployment records as proposed intent.
**Answer**: deploy only on `main`, but allow a dry run against a branch.
**Settled**: deploys are `main`-only; a branch dry run is read-only and writes no state. The
deployment kind can be `main`-scoped without the merge-overwrite hazard.

### 12. "Sent" or "confirmed"?

**Challenge**: the comparator objection from 6 mostly dissolves, because all three device families
compute the diff themselves and two already have the machinery in the existing code path —
`show session-config diffs` inside the `configure session` that `push_eos` already opens,
`show | compare` between the `load replace` and `commit` that `push_junos` already does, and
`frr-reload.py --test`. Junos's own comparator also solves the `## SECRET-DATA` re-salting problem,
because the device knows which changes are semantic.
**Answer**: **confirmed.**
**Settled**: the deployment record is a claim about the network, not about the executor's past
behaviour. Drift is detectable. The branch dry run comes free from the same mechanism.

### 13. What interval, what cleans up, and does the firewall participate?

**Challenge**: "confirmed" means the read path takes locks and leaves state on devices. EOS holds
a finite number of configuration sessions, so a checker that dies badly enough removes the ability
to deploy. `push_junos` uses `configure exclusive`, so a per-cycle check takes the exclusive lock
on the perimeter firewall — at 60s, 1,440 times a day, on the box someone needs during an incident.
**Answer**: the user can configure an interval.

### 14. What number ships, and who writes the cleanup?

**Answer**: recommendation accepted.
**Settled**:

- **600 seconds default**, matching Vidra's `requeueResourcesAfter`, so both reconcilers in the
  environment drift at the same rate and an operator learns one number.
- **Enforce a floor** (refuse under 60s) rather than trusting configuration.
- **Firewall on a multiple** — every fourth cycle — because checking it costs an exclusive lock.
- **Cleanup is in scope from day one.** Each cycle starts by sweeping its own leftovers: list
  configuration sessions on each EOS device and abort any matching the `infrahub-` prefix, detect
  and clear a Junos lock it owns. `try/finally` does not survive SIGKILL.

### 15. Drift is found. What do you do?

**Challenge**: the artifact checksum has not moved — intent did not change, the device did. That is
a structurally different reason to push, and the one that can fight a person. Auto-correction on a
leaf at 3pm is fine; on the perimeter firewall at 3am it silently reverts the emergency rule
someone added to stop an incident, with `commit confirmed` making it stick.
**Answer**: push automatically.
**Settled**: drift is corrected without asking. **Required mitigation**: a per-device `suspend`
attribute on the deployment kind that the reconciler honours, so an operator can exempt one device
without stopping the service. Without it the only break-glass is `docker stop`, which suspends
reconciliation for the whole fabric.

### 16. What is Temporal for now?

Raised but not answered. Temporal was carrying two things: durable handling of a one-shot webhook,
and the human approval park. The webhook went at 5 and the approval gate at 15. What remains is
scheduling a loop, retrying a device, and keeping history — but a 600-second loop *is* the retry,
because every push is a replace and the next cycle recomputes the diff from scratch; history now
lives in Infrahub; and concurrency control is one loop with one lock.

The remaining case for Temporal is multi-fabric scale or an external operational standard. Both are
legitimate. Absent one, the honest shape of this design is a single container: a loop, Nornir, and
Infrahub as the source of truth.

## Two defects found along the way

1. **`repository_checks.yml:138` sets `branch_scope: other_branches` on a
   `infrahub.proposed_change.merged` webhook.** Proposed changes are branch-agnostic objects, so
   their lifecycle events are emitted on the **default branch**. Infrahub's documentation is
   explicit: scoping them to other branches means the webhook will never fire. Combined with its
   `https://placeholder.invalid/...` URL, the CloudVision webhook is doubly dead.

2. **`docs/docs/supported-capabilities.md:116` overstates what exists.** It publishes
   *"Deploy configurations to devices — Through the bundled Ansible runner or CloudVision"*, but
   `ansible/deploy.yml` fetches the EOS artifact and copies it to `/tmp`; it configures nothing and
   knows one of three device families. The thing that actually deploys is
   `scripts/provision_lab.py`, which the page does not mention. That page syncs to
   `opsmill/infrahub-docs` and is live at `docs.infrahub.app/arista-avd`.

## Corrections to claims made during the review

- The merge webhook was described as "already proven here". It is not: the only
  `CoreCustomWebhook` in the repository points at `placeholder.invalid` and has never fired.
- Webhook delivery as an inspectable, retryable task is **Infrahub 1.11.0**. The compose files
  default to 1.10.6, and 1.10.1's release note says it *"restores webhook delivery"*.
- A proposed "heartbeat per host from inside a Nornir task" does not survive contact: Nornir runs
  hosts in a `ThreadPoolExecutor` while Temporal's activity context is a contextvar bound to the
  async activity, so it requires hand-propagating context into worker threads.

## Open items

- **Ordering against Vidra.** Both reconcilers act on the same merge with nothing sequencing them.
  A `FabricPeering` can land before the leaf has its BGP configuration. `invoke bootstrap` is the
  sequencer today and there is no equivalent in a steady-state loop.
- **Credentials and blast radius.** `NFD41_EOS_PASSWORD` and `NFD41_VSRX_PASSWORD` move from a
  human's shell for the duration of one command into a long-running service that can replace the
  configuration of every device in the fabric.
- **What CI can test.** `tests/unit` is fast and hermetic, and there are currently **no tests at
  all** for `scripts/provision_lab.py`. Lifting it into a module is the moment to add them against
  the guards (`_assert_eos_lifeline`, `_assert_junos_scope`, `_eos_config_lines`).
- **Where this lives.** This repository is the published Arista AVD reference design. Whether a
  bespoke executor belongs here, in the lab repository, or on its own is undecided.
- **Where an alert goes**, if anything ever alerts rather than correcting.

## Groundwork that is true regardless

- `nornir-infrahub` 1.2.0's `InfrahubInventory` builds Nornir groups from each node's
  `member_of_groups`, so `avd_devices`, `frr_routers` and `junos_firewalls` — already seeded in
  `objects/00_groups.yml` — become the inventory's grouping with no extra work. Host kind is
  `DcimGenericDevice`, because the four device kinds are siblings and `DcimDevice` sees no fabric
  switch. `mgmt_ip.address` is a legal single-hop schema mapping.
- `scripts/provision_lab.py` is 678 lines that already encode the expensive knowledge: the `end`
  stripping, the management lifeline check, `load replace` with `replace:` tags, the vSRX wait.
  It should be lifted, not rewritten.
- `--dry-run` today prints `would <device> -> <address>` and downloads nothing. There is no
  comparison machinery in this repository to build on.
- `provision_lab.py:614` skips any artifact whose status is not `Ready` — trusting the exact signal
  this repository documents twice as not being evidence of anything.
