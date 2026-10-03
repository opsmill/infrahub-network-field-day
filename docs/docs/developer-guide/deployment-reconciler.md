---
title: Deployment reconciler
description: A reference implementation of the reconciler pattern for this lab — how a merge reaches the devices without anyone typing a command, why each device computes its own diff, and what the normalisation layer is protecting you from.
audience: developer
sidebar_position: 7
---

# Deployment reconciler

`invoke provision` closes the gap between a merge landing on `main` and the devices matching
it, and it closes it when a human remembers to run it. The reconciler closes the same gap on a
timer.

:::warning What this is, and is not

This is a **reference implementation of the reconciler pattern for this lab**, not a supported
component of the Arista AVD reference design. It is here because the device knowledge and the
deployment state model are here, and because reading working code beats reading a description
of one. Treat it as a worked example to lift ideas from, not as a product to deploy.

It also **pushes device configuration without being asked**, including correcting drift someone
introduced by hand. Read [Blast radius](#blast-radius) before enabling it.

:::

## What a cycle does

```text
sweep leftovers → read intent → per device: compare → push if it differs → record → sweep orphans
```

At most every 600 seconds by default, matching Vidra's `requeueResourcesAfter` so both
reconcilers in the environment drift at the same rate and you learn one number.

```bash
uv run invoke reconcile --converge                  # cycle until every device is confirmed
uv run invoke reconcile --once                      # one cycle, then stop
uv run invoke reconcile --dry-run --branch my-work  # report, change nothing
uv run invoke reconcile                             # the loop
uv run invoke reconcile --now                       # ask the running loop for a cycle now
```

### When the next cycle starts

The interval is the **maximum** between cycles, not a fixed sleep. Without that, a merge waited
out the whole interval before any device changed, and a second interval before the push was
confirmed. `src/solution_arista_avd/deployment/wake.py` decides when the next cycle starts:

- **Intent moved.** Every `OTTERNET_RECONCILE_POLL` seconds (default 10) the loop runs the
  cycle's own discovery query and compares the configuration artifacts' checksums with the
  ones the last cycle read. It reaches no device. Once a moved set has been seen unchanged on
  two consecutive polls, a cycle starts, comparing the fabric and **forcing** the devices whose
  intent moved, the firewall included.
- **A push needs confirming.** After a cycle that pushed, the next comes after 60 seconds, the
  interval's floor, and compares the pushed devices. `last_confirmed_at` still moves only on a
  comparison that finds no difference. A device gets this once per push; one that is pushed
  again by the confirming cycle waits for the interval.
- **Someone asked.** `invoke reconcile --now` touches a trigger file inside the container
  (`OTTERNET_RECONCILE_TRIGGER`, default `/tmp/otternet-reconcile-now`) through `docker compose
  exec`. The loop checks it every second and answers with a cycle over every device.
- **The interval elapsed.** Only these cycles count towards the firewall's one-in-N cadence,
  so waking early for a leaf never takes the firewall's exclusive lock on its own account.

Two rules keep the early wake from pushing something half-rendered. A merge re-renders the
artifacts one after another, so any further movement resets the two-poll count. And the wake
fires only on movement **away from** what the last cycle read: two polls agreeing on the old
checksums, which is how `_wait_for_artifacts` was once fooled, is "nothing happened," and the
interval still applies. A render still moving when the interval runs out holds the cycle for up
to five minutes more. An empty artifact is refused where it always was, in
`compare.read_intent`.

Or as a service, which is deliberately behind a compose profile so `docker compose up` does not
start it:

```bash
docker compose --profile reconcile up -d deployment-reconciler
```

## Bootstrapping a cold fabric

`invoke bootstrap` uses `invoke reconcile --converge` as its device step, so the build
exercises the same code that keeps the fabric correct afterwards.

`--converge` exists because of one semantic: a cold device differs, so the first cycle
**pushes** it — and `last_confirmed_at` deliberately does not move on a push. Confirmation
needs a later comparison that finds no difference. A single cycle would therefore leave a
freshly built fabric correct but unconfirmed, which is exactly the ambiguity the record exists
to remove. Converge also compares the firewall every cycle rather than one in four: the cadence
is a steady-state economy, and during a build nobody else is using the box.

It gives up after six cycles and names the devices that never confirmed, rather than looping
forever.

## Each device computes its own diff

This is what makes it a reconciler rather than a deployment trigger. Comparing an artifact
checksum against a last-applied checksum detects a change in *intent*; it cannot see that
someone edited a switch by hand.

| Family | Mechanism | Leaves behind |
| --- | --- | --- |
| `DcimFabricSwitch` | `configure session` + `show session-config … diffs` | session aborted |
| `DcimDevice` (SR Linux) | private candidate: `delete /`, set the whole artifact, `diff flat`, `discard now` | candidate discarded; one stranded by an abort is cleared |
| `SecurityFirewall` | `load override` + `show \| compare` | candidate rolled back |

Nothing in the comparison path commits.

**An SR Linux push is a full replace with commit-confirm.** The same candidate ends `commit
confirmed timeout 120` instead of `discard now`. The reconciler then checks from inside the
container that `mgmt0.0` has an address and that gNMI (57400) and SSH (22) are listening. If
they are, it accepts the commit; if not, it rejects it, and SR Linux rolls back by itself if the
reconciler dies first. All three paths were measured on a prototype, alongside a lifeline that
refuses, before anything is sent, an artifact lacking the management interface and VRF, the gNMI
and SSH servers or an admin password hash. Unchanged and changed pushes left every BGP session
up, because the commit applies only the net difference.

## The firewall is replaced whole

The firewall push is `load override`, then `commit confirmed 3`, then a fresh login over the
reconciler's own path, then the confirming `commit` — the Junos counterpart of EOS's
`rollback clean-config`. Everything the artifact omits is deleted: a hand-added rule, a stray
application, the cleartext `plain-text-password-value` vrnetlab's `init.conf` leaves behind.

It is safe for two reasons, and both were measured on a throwaway vSRX booted exactly as the lab
boots `fw1`:

- **The lifeline.** `_assert_junos_lifeline` refuses, before anything is staged, an artifact
  missing an `fxp0` address, `services ssh`, `services netconf ssh`, a `super-user` login for the
  account the reconciler authenticates as, or root authentication. It reads statements, not
  substrings, so a comment mentioning `ssh` does not count and an `inactive:` `fxp0` is no
  `fxp0`. An empty artifact fails it — under `override`, an empty file is an instruction to
  erase the device.
- **The confirmation is earned.** After `commit confirmed`, a new session must log in through
  vrnetlab's forward to `fxp0` and NETCONF on 830 must answer a hello. Only then is the
  confirming `commit` sent. On the prototype, an artifact that passed the lifeline but moved
  `fxp0` off vrnetlab's guest address committed, failed the check, was never confirmed, and was
  rolled back by Junos itself (`root via other`) without anyone touching the device. A probe that
  answers within 30 seconds of the rollback is refused rather than raced, because a confirm
  issued after the rollback commits nothing and still prints `commit complete`.

`scp -O` stays load-bearing: without it the copy fails, the load does nothing, and
`show | compare` comes back empty.

The firewall is compared on **one cycle in four, and last**, because its comparison takes an
exclusive configuration lock — at the default interval a per-cycle check would take that lock
144 times a day on the device you need during an incident.

## The device layer

Nornir, with the inventory built from Infrahub: hosts are `DcimGenericDevice` so all four
device kinds appear, and groups come from each node's `member_of_groups`. A full sweep of the
lab takes about 3.3 seconds against roughly 10 sequentially, and the ceiling moves with worker
count rather than device count.

**The firewall is never parallelised.** Its comparison takes an exclusive configuration lock,
so it runs on its own after everything else.

Nothing in a Nornir task touches Infrahub. Its hosts run in a thread pool while the SDK's
client context is bound to the async task, so tasks do device I/O and return plain data, and
state is written afterwards in the caller's coroutine.

## The normalisation layer, and why it exists

**One of the three families reports a difference against an artifact the device already
matches.** Measured against this lab, and for SR Linux against a six-router prototype:

| Family | An in-sync device reports |
| --- | --- |
| EOS | nothing |
| SR Linux | nothing but `All changes have been discarded. Leaving candidate mode.` |
| Junos | zone-pair ordering, comment round-tripping, `version`, `uid`, re-salted password hashes |

SR Linux needs no suppression because the comparison is the router's own: the artifact is
loaded as a replace in a private candidate and `diff flat` compares it with running. The FRR
routers it replaced did need three suppressions, for lines the artifact stated and `show
running-config` never echoed back. A non-zero exit from `sr_cli` is never read as in sync: an
aborted candidate prints no diff at all, so the comparator raises instead.

Junos reports the zone-pair blocks in a different order (no object carries their order, and
Junos matches on zone rather than position), its comment blocks round-tripping, and two
statements it writes itself on every commit — `version` and a login's `uid` — which the artifact
never states.

**Re-salted hashes are the subtle one.** Compared against a freshly booted vSRX, both of the
lab's `$6$otternetlab$…` hashes come back as `$6$<random>$…`: the same password under a new salt,
on every load. A rule that ignored `encrypted-password` changes would hide a changed password; a
rule that reported them would push a freshly deployed firewall every cycle. The normaliser
hashes the reconciler's own password with each salt and suppresses the pair only when both
match. A hash no known password explains is a changed secret, and differs.

**A cleartext password is always a difference, and the comparison has to go looking for it.**
`show | compare` never prints the deletion of a `plain-text-password-value`, and a freshly
booted vSRX carries two from vrnetlab's `init.conf`. The re-salted pairs above were their only
visible trace, so the booted firewall's whole diff normalised to empty: a fresh bootstrap
recorded `fw1` as `in_sync` with cleartext credentials in its running configuration and never
pushed it. The comparator now reads the running configuration in the same session —
`show configuration | display set | match plain-text-password-value`, operational mode, changing
nothing — and appends each statement found as a deletion. The normaliser keeps any statement
naming that leaf before every other rule, with its value redacted, since the normalised diff is
stored in Infrahub. A probe that answers with an error raises instead of reading as clean.

Read raw, all of that means "this device differs." A reconciler acting on it replaces the
firewall's configuration **on every cycle, forever**, while every log
line says success.

`differs` is therefore computed from normalised output, never raw text. Three rules govern
`deployment/normalise.py`:

1. **Allowlist, never denylist.** Only named patterns are suppressed.
2. **Every suppression carries its reason.**
3. **Fail noisy.** Anything unrecognised counts as a difference — a gap causes an unnecessary
   push, never a missed one.

That third rule earned its keep while the WAN still ran FRR. The first live dry run reported
`isp-pe1` as differing: the scaffold rule matched `router bgp <asn>` but not `router bgp <asn> vrf <NAME>`, so on a
provider edge each customer VRF left an unsuppressed wrapper behind. The rule surfaced it
instead of hiding it.

:::note A suppression that turned out to be a bug

This layer used to suppress the `fxp0` management interface. The push was then `load replace`
on the `interfaces` hierarchy, which deleted everything the artifact omitted, and the model owned
only the data interfaces — so every push deleted the firewall's management interface, and vrnetlab, running
as root inside the container, restored it seconds later. An in-sync firewall reported
`- fxp0 {...}` forever. The device's commit log showed the pair every time:

```text
16:49:01 admin via cli commit confirmed   ← the artifact loads, fxp0 goes
16:51:03 root via other                   ← vrnetlab restores it
16:51:10 admin via cli                    ← the confirm
```

The suppression was right about the diff and wrong about the cause: the push was the bug.
`fxp0` is now modelled, so the artifact carries it, a replace no longer deletes it, and the
diff — along with the suppression — went away. The push is now a full `load override` of the
whole configuration, and `fxp0` is the first item in its lifeline.

The trade is stated rather than hidden: **the model is now authoritative for the firewall's
management address.** Its values come from an `init.conf` that vrnetlab generates inside the
container and that no repository holds, so if they ever drift, a push sets the wrong address
and nothing restores it.

Before adding a rule to the normaliser, ask whether the device is telling you something true.

:::

## What it records, and where you look

Per device, in `DeploymentState` — the same UI you raised the proposed change in.

| Field | Moves when |
| --- | --- |
| `last_confirmed_at` | the device itself reported **no difference**. Never because a push was sent |
| `last_checked_at` | every comparison, including failures |
| `status` | `in_sync`, `pending`, `drifted`, `failed`, `never_deployed` |
| `last_artifact_checksum` | used only to tell `pending` from `drifted` |

`last_checked_at` exists so that a stale `last_confirmed_at` is distinguishable from a dead
loop. Without it, "this device is fine" and "the reconciler stopped a week ago" read identically.

`pending` versus `drifted` is the only use of the artifact checksum in the whole design. It
never decides *whether* to push — the device's own diff does that — it records which of two
structurally different causes applies. Drift is the one that can be fighting a person.

## Taking one device out of the loop

```text
Set DeploymentState.suspend on that device, with a suspend_reason.
```

The reconciler skips it entirely: not connected to, not compared, not pushed. Its `status` and
`last_checked_at` stay exactly as they were, so you can still see what it was doing when it was
suspended — a moving timestamp on a device nobody looked at would be a lie.

**The service never writes `suspend` or `suspend_reason`.** A reconciler that can clear its own
break-glass is not a break-glass.

## Blast radius

The device credentials move from a human's shell for the duration of one command into a
long-running service that can replace the configuration of every device in the fabric on a
timer.

Three things bound that, and one thing does not:

- `suspend` exempts a single device without stopping the service.
- The interval has a hard floor of 60 seconds; the service **refuses to start** below it rather
  than clamping. The early wake does not get around it: a cycle starts early only when intent
  moved, once after a push, or on request, and the checksum poll (floor 5 seconds) reaches
  Infrahub only, never a device.
- `--dry-run` reports differences and changes nothing, on a device or in Infrahub.
- **Least privilege does not bound it. None applies here.** The service authenticates as the
  same lab admin `invoke provision` uses.

For a lab that is the same trust level as running `invoke provision` from a shell. Anywhere
else it is not. Scoped per-family service accounts and a read-only credential for the compare
pass are the obvious next step, and neither changes the device layer or the state model.

Credentials are supplied by environment variable only — never baked into an image, committed,
or written into Infrahub.

The compose service additionally needs `network_mode: host` (the switches are on the
ContainerLab management network) and the Docker socket (the SR Linux routers and the firewall have
no address modelled and are reached by container name). Mounting the Docker socket is
effectively root on the host.

## What it does not do

- **It does not sequence against Vidra.** Both act on the same merge with nothing ordering
  them, so a `FabricPeering` can land before a leaf has its BGP configuration. Both are
  reconcilers, so the fabric converges; the transient is a few minutes. `invoke bootstrap`
  remains the sequencer for a cold build.
- **It does not alert.** The record is the signal.
- **It does not run on a branch.** Deploys are `main`-only; a branch can be dry-run, which
  writes no state.
- **It does not change any existing workflow.** `invoke provision`, `invoke bootstrap` and the
  artifact chain behave identically whether or not it is running.

## Operational notes

Moved from the repository instruction file. Read these before changing the reconciler package.

`src/solution_arista_avd/deployment/` compares every device against its rendered artifact on a
timer and pushes the ones that differ — the loop half of what `invoke provision` does by hand.
It is behind a compose profile (`--profile reconcile`) so nothing starts it by accident, and
`invoke provision` is unchanged: cycle 030 **lifted** the push path out of
`scripts/provision_lab.py` into `deployment/devices.py` so both callers share one copy rather
than two that drift.

**Run `invoke build` before starting the profile if dependencies have moved.** The service runs
`python scripts/reconcile.py` with the *image's* interpreter, so it needs the project's runtime
dependencies baked in. An image built predating `nornir-infrahub` crash-loops on
`ModuleNotFoundError: No module named 'infrahub_sdk'` — the SDK arrives transitively through
`nornir-infrahub`, and the host virtualenv bind-mounted at `/source` cannot stand in for it:
the image is Python 3.13 and that virtualenv is 3.12.

The device layer is **Nornir** (`deployment/inventory.py`), with the inventory built from
Infrahub by `nornir-infrahub`: hosts are `DcimGenericDevice` so all four device kinds appear,
and groups come from each node's `member_of_groups`, which `objects/00_groups.yml` already
seeds. **No `schema_mappings` is configured, deliberately** — `mgmt_ip` is a relationship on
`DcimFabricSwitch` alone, so a mapping for it against the generic is rejected outright; the
address each device is reached by comes from `Target` instead.

**Where the thread boundary sits is the design.** Nornir runs hosts in a `ThreadPoolExecutor`
while the SDK's client context is a contextvar bound to the async task, so a Nornir task does
device I/O only and returns plain data; every Infrahub write happens afterwards in the caller's
coroutine. `test_the_nornir_layer_never_touches_infrahub` asserts that by walking the module's
imports rather than trusting the comment. The firewall is never parallelised — its comparison
takes an exclusive lock, so it runs alone after the fabric.

**Read `deployment/normalise.py` before changing anything in this package.** One of the three
device families reports a difference against an artifact the device already matches:

- **Junos** reports changed lines every time: zone-pair ordering and comment round-tripping.
- **SR Linux does not**, which is why its normaliser suppresses nothing: the comparison loads
  the artifact as a replace in a private candidate and asks for `diff flat`, so the router
  compares intent against running itself, and all six printed nothing but the status line
  after boot. (FRR, before it, reported three lines on every in-sync router.)

Read raw, Junos's output means "differs," and the reconciler would replace the firewall's
configuration on every cycle forever while logging success. `differs` is therefore computed
from normalised output, never raw text, and the rules are an **allowlist** — anything
unrecognised counts as a difference, so a gap causes an unnecessary push rather than a missed
one. `tests/unit/test_deployment_normalise.py` holds real captured device output for both the
in-sync and the changed case; an empty result is only evidence when a non-empty one is proven
beside it.

Worth knowing before debugging it:

- **The firewall is replaced whole: `load override`, `commit confirmed 3`, a fresh login, then
  the confirming `commit`.** The counterpart of EOS's `rollback clean-config`, since cycle 035.
  Two guards make it survivable, both proven on a throwaway vSRX booted exactly like `fw1`:
  `_assert_junos_lifeline` refuses, before staging, an artifact missing an `fxp0` address,
  `services ssh`, `services netconf ssh`, a `super-user` login for `VSRX_USERNAME` or root
  authentication (statements, not substrings; an `inactive:` fxp0 is no fxp0; an empty artifact
  fails it, and under `override` an empty file erases the device). And the confirmation is
  **earned**: `_assert_vsrx_reachable` logs in again through vrnetlab's forward and asks NETCONF
  for a hello before the confirm is sent. Measured: an artifact moving `fxp0` off vrnetlab's
  guest address passed the lifeline, committed, failed the check, was never confirmed, and was
  rolled back by Junos itself (`root via other`). A probe answering within 30 s of the rollback is
  refused rather than raced — a confirm issued after the rollback commits nothing and still
  prints `commit complete`.
- **`fxp0` is modelled, and the model is authoritative for the firewall's management
  address.** It was modelled first because `load replace` on `interfaces` deleted it on every
  push; under the full override it is the lifeline's first item. Its values, like the
  `mgmt_junos` gateways (constants in `junos_config.py`), come from an `init.conf` vrnetlab
  generates inside the container. If they drift from what vrnetlab assigns, a push now *fails
  the post-commit check and rolls back* rather than stranding the device.
  `FXP0_FROM_INIT_CONF` and its siblings in `tests/unit/test_junos_config.py` are hand-maintained;
  `fixtures/junos/vsrx_booted.conf` is the captured witness they are checked against.
  `SecurityZone` on a firewall interface became optional in `schemas/security/security.yml` to
  allow this: a deliberate change to the upstream contract, because a management interface is in
  no zone.
- **Junos re-salts password hashes on load, and only proof suppresses it.** Against a freshly
  booted vSRX, both `$6$otternetlab$…` hashes come back as `$6$<random>$…` on every load — the
  same password. `normalise.junos_same_secret` hashes the reconciler's own password with each
  salt (`sha_crypt`, because Python 3.13 removed `crypt`) and suppresses the pair only when both
  match; an unexplained hash is a changed password and differs. `version` and a login's `uid` are
  stamped by Junos on every commit and suppressed as deletions only, under the banner they were
  measured under. Every rule has a captured in-sync *and* drifted fixture, including drift inside
  `system`.
- **`show | compare` cannot see a cleartext password, so the comparator asks running.** A
  freshly booted vSRX carries `init.conf`'s two `plain-text-password-value "admin@123"` leaves.
  `load override` deletes them, but the compare never prints that deletion — its only trace is
  the two re-salted hash pairs, which the proof above rightly suppresses. The whole diff
  normalised to empty, and a fresh bootstrap recorded fw1 `in_sync` with cleartext credentials
  on it and never pushed; a manual `invoke provision --kind junos` removed exactly those two
  lines. `compare_junos` now runs `show configuration | display set | match
  plain-text-password-value` in the same session and appends what it finds as deletions, and
  `normalise_junos` keeps any statement naming the leaf **before every suppression**, redacted,
  because the normalised diff is stored in Infrahub. An unanswered probe raises rather than
  reading as clean. The re-salt proof is unchanged; the fix is that the leaf is now looked for,
  not that hashes became suspicious.
- **sr_cli stops at the first error, commits nothing, and leaves its candidate behind.** A
  parse error or a refused commit exits 1 with running untouched — measured both — but the
  named candidate survives the session and SR Linux holds ten. The pusher and comparator clear
  it on failure and `sweep_srl` clears any `infrahub-*` leftovers each cycle. An aborted
  comparison prints NO diff, so a non-zero exit raises rather than reading as in sync.
- **An empty SR Linux artifact is an instruction to erase the router**, because the push
  runs `delete /` before setting the file — management and the admin login included. Artifact
  generation is asynchronous and an unrendered artifact exists, reports `Ready`, and is empty.
  `_assert_srl_lifeline` refuses, before anything is sent, an artifact lacking any of: mgmt0
  and its DHCP client, the `mgmt` network instance holding `mgmt0.0`, the gNMI and SSH servers
  in it, and an admin password that is a crypt hash. Whole commands, so a comment never
  satisfies it.
- **Every push is `commit confirmed timeout 120`, and the reconciler confirms only what it can
  see survived.** After the commit it checks inside the container's `srbase-mgmt` namespace
  that `mgmt0.0` has an address and 57400 and 22 are listening, then `confirmed-accept`; else
  `confirmed-reject`. Measured: a lifeline-passing artifact that moved gNMI to another port was
  rejected and running went back to the artifact; a confirmed commit nobody accepted rolled
  itself back at its timeout. Unchanged and changed full replaces left every BGP session's
  uptime running — the commit applies only the net difference.
- **The routers are pushed with `docker exec sr_cli`, not a gNMI Set Replace on `/`**: both
  replace the whole tree atomically, but only sr_cli takes the artifact exactly as rendered and
  has commit-confirm, and it needs no credential and no address, which keeps `mgmt_ip` meaning
  eAPI and the collector's `telemetry_address` out of the reconciler. Nothing is saved to
  startup. A `docker restart`ed router came back in sync in 16 s **but without its data-plane
  links** — a plain restart drops a container's veths and only `containerlab deploy` restores
  them.
- **`scp -O` is load-bearing on the Junos path.** Without it the copy fails, `load override` does
  nothing, and `show | compare` comes back empty — which reads exactly like "in sync."

State goes to `DeploymentState` (cycle 029). `last_confirmed_at` moves only when the device
reported no difference, never because a push was sent; `last_checked_at` moves every cycle so a
stale confirmation is distinguishable from a dead loop. The service never writes `suspend` or
`suspend_reason` — those are the operator's break-glass.

**The interval is a maximum, not a sleep** (`deployment/wake.py`). Between cycles the loop polls
the configuration artifacts' checksums on `main` (the cycle's own discovery query, no device
I/O) and starts early once a moved set holds still for two polls, forcing the devices whose
intent moved; a cycle that pushed is confirmed 60 seconds later rather than an interval later,
once per push. Two things look loosenable and are not:

- **Only interval-started cycles advance the firewall's one-in-N cadence.** An early cycle
  compares `fw1` only when `fw1`'s own artifact moved or it was just pushed. Counting early
  cycles would take the exclusive lock as often as merges land.
- **The wake fires only on movement away from what the last cycle read, and only once it
  stops.** Waking on the first movement compares a half-rendered fabric; treating agreement as
  enough repeats `_wait_for_artifacts`' stale-checksum lesson. A snapshot equal to the
  baseline is "nothing happened" and the full interval applies.

`invoke reconcile --now` asks the running container for an immediate all-device cycle through a
trigger file. A changed `wake.py` reaches the loop only after `invoke build` and recreating the
container: `scripts/reconcile.py` comes from the bind mount and imports the image's package, so
a new script against an old image fails at import.
