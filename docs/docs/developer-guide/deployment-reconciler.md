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

Every 600 seconds by default, matching Vidra's `requeueResourcesAfter` so both reconcilers in
the environment drift at the same rate and you learn one number.

```bash
uv run invoke reconcile --converge                  # cycle until every device is confirmed
uv run invoke reconcile --once                      # one cycle, then stop
uv run invoke reconcile --dry-run --branch my-work  # report, change nothing
uv run invoke reconcile                             # the loop
```

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
| `DcimDevice` (FRR) | `frr-reload.py --test` | nothing; staging dir only |
| `SecurityFirewall` | `load replace` + `show \| compare` | candidate rolled back |

Nothing in the comparison path commits.

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

**Two of the three families report a difference against an artifact the device already
matches.** Measured against this lab:

| Family | An in-sync device reports |
| --- | --- |
| EOS | nothing |
| FRR | `neighbor <addr> activate`, `service integrated-vtysh-config`, `line vty` |
| Junos | zone-pair ordering and comment round-tripping |

FRR states things in the artifact that `show running-config` never echoes back — `activate` is
the default for IPv4 unicast, the other two are file directives rather than running state.
Junos reports the eleven zone-pair blocks in a different order (no object carries their order,
and Junos matches on zone rather than position) and its comment blocks round-tripping.

Read raw, all of that means "this device differs." A reconciler acting on it replaces the
configuration of every FRR router and the firewall **on every cycle, forever**, while every log
line says success.

`differs` is therefore computed from normalised output, never raw text. Three rules govern
`deployment/normalise.py`:

1. **Allowlist, never denylist.** Only named patterns are suppressed.
2. **Every suppression carries its reason.**
3. **Fail noisy.** Anything unrecognised counts as a difference — a gap causes an unnecessary
   push, never a missed one.

That third rule earns its keep. The first live dry run reported `isp-pe1` as differing: the
scaffold rule matched `router bgp <asn>` but not `router bgp <asn> vrf <NAME>`, so on a
provider edge each customer VRF left an unsuppressed wrapper behind. The rule surfaced it
instead of hiding it.

:::note A suppression that turned out to be a bug

This layer used to suppress the `fxp0` management interface. `load replace` on the
`interfaces` hierarchy deletes everything the artifact omits, and the model owned only the data
interfaces — so every push deleted the firewall's management interface, and vrnetlab, running
as root inside the container, restored it seconds later. An in-sync firewall reported
`- fxp0 {...}` forever. The device's commit log showed the pair every time:

```text
16:49:01 admin via cli commit confirmed   ← the artifact loads, fxp0 goes
16:51:03 root via other                   ← vrnetlab restores it
16:51:10 admin via cli                    ← the confirm
```

The suppression was right about the diff and wrong about the cause: the push was the bug.
`fxp0` is now modelled, so the artifact carries it, the hierarchy can be replaced wholesale
without deleting it, and the diff — along with the suppression — went away.

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
  than clamping.
- `--dry-run` reports differences and changes nothing, on a device or in Infrahub.
- **Least privilege does not bound it. None applies here.** The service authenticates as the
  same lab admin `invoke provision` uses.

For a lab that is the same trust level as running `invoke provision` from a shell. Anywhere
else it is not. Scoped per-family service accounts and a read-only credential for the compare
pass are the obvious next step, and neither changes the device layer or the state model.

Credentials are supplied by environment variable only — never baked into an image, committed,
or written into Infrahub.

The compose service additionally needs `network_mode: host` (the switches are on the
ContainerLab management network) and the Docker socket (the FRR routers and the firewall have
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
