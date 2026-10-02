---
title: Demo runbook
---

# Demo runbook

This is the script for showing the lab to an audience. It assumes a finished
`uv run invoke bootstrap`, and every command below is run from the repository
root unless it says otherwise.

The order is not preference. It follows from the measured timings: a merge
reaches the **cluster** in under a minute and a **device** once the reconciler
sees the merged artifacts hold still. Showing the cluster first, then the
**Deployment state** dashboard, fills the gap the fabric would otherwise leave
you standing in.

:::note Timings marked "expected after the early-wake change"
The reconciler used to sleep its whole interval between cycles, so a merge
waited up to two minutes for a push and two more for confirmation. It now polls
the artifacts' checksums every 10 seconds, starts a cycle once the moved ones
hold still for two polls, and confirms a push 60 seconds later rather than an
interval later. Numbers marked *expected* below are derived from the measured
cycle lengths (about 11 s for a cycle that pushes nothing, about 25 s for one
that pushes the firewall and a leaf) and have not yet been timed end to end on
this lab. Replace them when they have been.
:::

| Act | What the audience sees | Changes state |
| --- | --- | --- |
| [Preflight](#before-anyone-is-watching) | Nothing. You do this alone. | No |
| [One](#act-one-ask-for-an-application) | A branch user asks for an application and can reach it after one merge | Yes: a branch, then a merge |
| [Two](#act-two-a-branch-user-asks-for-grafana) | The same request against Grafana, then monitoring as intent | Yes |
| [Three](#act-three-revoke-it) | Access withdrawn through the same workflow | Yes |
| [Four](#act-four-the-review-step-bites) | A check catching a mistake nothing else would notice | A branch only, never merged |
| [Five](#act-five-the-agent-through-the-mcp-server) | An agent working through the MCP server, on a branch | A branch only |

:::note What was checked, and how
Everything up to each merge was rehearsed against a freshly bootstrapped lab:
the preflight, act four, act five, and acts one and two submitted through the
portal as `alice` and read in their proposed changes. The merges themselves, and
what follows them on the devices and in the cluster, were not re-run for this
page; those timings come from measurements recorded in this repository's
documentation.

Rehearse before an audience does, with a request reference you do not plan to use live:

```bash
uv run python scripts/demo_rehearsal.py          # every act up to its merge, about ten minutes
uv run python scripts/demo_rehearsal.py --only four,five
```

It creates branches and proposed changes, deletes them afterwards even when an
act fails, merges nothing, and touches no device. It prints a timing for every
step, so the numbers below can be checked against the lab in front of you.
:::

## Before anyone is watching

Allow ten minutes. Each check guards against something that goes wrong quietly.

### 1. The reconciler loop is running, at demo cadence

```bash
docker compose ps deployment-reconciler
docker exec infrahub-deployment-reconciler-1 env | grep RECONCILE
docker logs --tail 3 infrahub-deployment-reconciler-1 | grep cycle
```

You want the container `Up`, and these two values:

```text
OTTERNET_RECONCILE_INTERVAL=120
OTTERNET_RECONCILE_FIREWALL_EVERY=1
```

and a recent line ending `compared=14 differed=0 pushed=0 failed=0 suspended=0 not-due=0`.
The start-up line should read `interval=120s (the maximum) poll=10s`; one
without `poll=` is an image built before the early-wake change, which waits the
whole interval after every merge. `uv run invoke build`, then recreate the
container.

The interval is now a maximum. To start a cycle over every device, firewall
included, without waiting for anything, for example after editing a device by
hand to show drift being put back:

```bash
uv run invoke reconcile --now
```

**Without the loop, a merge reaches no device**, and the deployment view still
shows the green it recorded during the build. That reading is identical whether
the loop is running or was never started. The defaults are a 600-second cycle and
the firewall compared one cycle in four, which can leave a merge up to forty
minutes from the firewall. Put both values in `.env` at the repository root
(gitignored) so they survive a restart, then
`docker compose --profile reconcile up -d deployment-reconciler`.

### 2. Infrahub is clean

```bash
uv run infrahubctl repository list    # Sync status: in-sync
uv run infrahubctl branch list        # main, and nothing you would rather not explain
```

The branch selector is the first thing on screen in Infrahub. **Infrahub
mirrors the git branches of the repository it clones**, which here is your own
checkout, so every local git branch, including each `worktree-*` branch an agent
created, appears as an Infrahub branch. Deleting the Infrahub branch is not
enough: delete or push aside the git branch first, or it comes back.

In the Infrahub UI, **Deployment → Device Sync State** should list fourteen
devices, all `in_sync`, with `last_checked_at` inside the last couple of minutes.

### 3. Every portal user has an Infrahub account

```bash
uv run python scripts/provision_portal_accounts.py --check
# Every portal user already has an account.
```

An Infrahub account is created by its owner's first Infrahub sign-in. A user
without one fails at the create step **after** the request has already made its
branch: a red run and an orphan branch, mid-demo. `invoke tooling` provisions
them; this tells you whether it did.

### 4. The network is up

```bash
make -C lab fabric-bgp     # underlay and EVPN sessions on all seven switches
make -C lab wan-bgp        # every SR Linux WAN router's BGP neighbours, all `established`
export KUBECONFIG=lab/k8s/.kubeconfig/kubeconfig.yaml
kubectl get fabricapp,fabricpeering    # otternet-demo, -metrics, -telemetry and the peering: READY True
kubectl get infrahubsync -o custom-columns=NAME:.metadata.name,STATE:.status.syncState
```

`syncState: Succeeded` alone proves nothing, because a sync over an empty set
also succeeds. The `READY True` claims are the evidence that Vidra delivered.

### 5. The "before" picture is what you expect

Nothing is granted on a fresh lab, so the branch reaches neither application VIP:

```bash
docker exec clab-otternet-branch-desktop curl -s -m 8 -o /dev/null -w '%{http_code}\n' http://10.112.240.81/   # 000, timed out
docker exec clab-otternet-branch-desktop curl -s -m 8 -o /dev/null -w '%{http_code}\n' http://10.112.240.0/    # 000, timed out
```

`10.112.240.81` is Grafana (`otternet-metrics`) and `10.112.240.0` is the
seeded `otternet-demo`. The firewall's `branch → k8s-prod` zone pair carries
only the hand-written rules:

```bash
docker exec -i clab-otternet-fw1 sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR admin@127.0.0.1 \
  "show configuration security policies from-zone branch to-zone k8s-prod | display set" | grep -c svc-
# 0
```

### Screens to have open

| Screen | Address | Sign in |
| --- | --- | --- |
| The branch desktop, through Guacamole | `http://<host>:8080/` (over Tailscale from a remote laptop) | `branch` / `branch` |
| Infrahub, as the operator | `http://<host>:8000/` | the local `admin` account |
| A terminal on the host | | |
| Grafana, as the operator | `make -C lab grafana-forward`, then `http://localhost:13000/` | `admin`, password `GRAFANA_ADMIN_PASSWORD` in `.env` |

The operator's Grafana is for act one, before the branch can reach Grafana at
all: it crosses no firewall, so showing it proves nothing about a grant. Open
**OTTERNET / Deployment state** there before the first merge.

The portal (`https://10.90.0.11:32001`) and Dex are reachable **only from the
branch side**, so open the portal inside the branch desktop. Guacamole opens its
one connection, **OTTERNET branch office desktop**, straight after sign in. The
desktop shows two icons, **Service Portal** and **Start here**, and the same two
sit in the top panel. Start here is a one-page note naming who to sign in as.
Firefox opens on the portal, with no first-run or sponsored pages, and its
toolbar carries four bookmarks in the order the demo uses them:

| Bookmark | Address | Before any grant |
| --- | --- | --- |
| **Service Portal** | `https://10.90.0.11:32001/` | answers |
| **Proposed changes** | `http://10.90.0.1:8000/proposed-changes`, Infrahub signed in with Dex | answers |
| **Demo app (locked)** | `http://10.112.240.0/`, `otternet-demo` | times out |
| **Grafana (locked)** | `http://10.112.240.81/`, `otternet-metrics` | times out |

`(locked)` means the address answers only after a grant, and `make -C lab verify` holds
each bookmark to its label from inside the desktop. The portal's certificate is
trusted without a click: `invoke tooling` signs it with a throwaway CA and installs
the CA on the desktop. If the portal shows a certificate warning, Firefox was
already open when `invoke tooling` ran. Close Firefox and open it again from the
Service Portal icon.

A preflight of the desktop, read-only, from the host:

```bash
make -C lab verify 2>&1 | grep -E "bookmark|launcher|portal|policies"
```

Every line should read `PASS`. A `the desktop runs the committed Firefox policies`
failure means the desktop image predates the bookmarks in this runbook.

An operator signs in to Infrahub with the local `admin` account on the same
login page as the Dex button. The Dex issuer is unreachable from an operator's
laptop on purpose.

## Act one: ask for an application

**1. Ask.** On the branch desktop, open **Service Portal**, sign in with Dex as
`alice@otternet.lab` / `password`, open the portal's template list, and choose
**Exposed application, with access**. Fill in what has no default:

| Field | Value |
| --- | --- |
| Application name | `otter-shop` |
| What it is | anything a stranger would understand |
| Kubernetes namespace | `otter-shop` |
| Chart repository / name / version | `https://cowboysysop.github.io/charts/` / `whoami` / `6.0.0` (the seeded application's chart) |
| Request reference | `demo1`, or anything not used before |

Leave the rest. The defaults are the cluster `otternet`, VRF `K8S_PROD`, ports
`junos-http`, a `/28` VIP block, source site `branch-office`, and chart values
carrying a working exposure block: a LoadBalancer Service with the
`otternet.lab/advertise: "true"` label the service selector names.

The run takes **70 to 85 seconds**, most of it two waits. What to say while it
runs, step by step, because the step list is on screen:

- It creates a branch, `implement_otter-shop_demo1`, and the application on it,
  **as `alice`**. The write carries her account through the mutation's `context`,
  so the events are attributed to her, not to the portal's service account.
- It **waits for the VIP block to be allocated** before it creates the grant.
  Both generators fire on creation and nothing else orders them; a grant that
  loses that race is stamped `error` and nothing retries it on its own.
- It **regenerates the fabric**: host vars for all seven switches, then their
  structured configs, 21 to 25 seconds. Without that the border leaf's change
  would be a JSON attribute rather than configuration.
- Only then does it open the proposed change, so the change's own checks render
  from current data.

**2. Read the proposed change.** Follow the run's **Review the proposed change**
link, or open **Proposed Changes** in Infrahub. This is the point of the whole
thing. It contains:

- the `ServiceFabricApp`, and the `ServiceAppAccess` with `alice@otternet.lab`
  as its requester;
- the VIP block taken from the cluster's pool;
- the firewall rule `svc-otter-shop-access` (`branch → k8s-prod`, `junos-http`),
  its address-book entry for the VIP, and `10.70.0.0/24` added to the
  application's own allowed sources, which is the pod-level gate;
- the regenerated host vars, and the **rendered configuration diff** for the border
  leaf, `leaf-otternet-pod1-3-1`: one line, `seq <n> permit <vip block>`, in
  `PL-DC-ADVERTISED-BRANCH`, and the same line in its device documentation; the
  other six switches are unchanged;
- the re-rendered **Junos Configuration** artifact for `fw1`, and the
  **Crossplane FabricApp** artifact for the new application.

Point at the checks: `wan-service-consistency`, `zone-advertisement`,
`allocation-consistency`, `peering-consistency` and `fabric-pool-validation`
are green, which only means something once [act four](#act-four-the-review-step-bites)
has shown one going red.

Merging is the approval. The grant has no second gate, deliberately:
two gates can only disagree.

**3. Merge, and show the cluster first.** Merge the proposed change in Infrahub.
Vidra delivers within about a minute:

```bash
kubectl get fabricapp otter-shop                 # SYNCED True, READY True
kubectl -n otter-shop get svc                    # EXTERNAL-IP is the VIP, inside the allocated block
```

**4. Then the devices.** Once the merged artifacts have re-rendered and held
still for two polls, the reconciler starts a cycle without waiting out its
interval, pushes two devices, `fw1` and the border leaf, and confirms them about
a minute later. Expected after the early-wake change: the push lands 30 to
90 seconds after the merge, and confirmation about a minute after that. If
nothing has moved after two minutes, `uv run invoke reconcile --now`.

```bash
docker logs -f infrahub-deployment-reconciler-1 2>&1 | grep --line-buffered cycle
# ... starting cycle N (artifacts, intent moved on fw1, leaf-otternet-pod1-3-1)
# ... compared=14 differed=2 pushed=2 ...
# ... starting cycle N (confirmation)
# ... compared=14 differed=0 pushed=0 ...
```

Fill the wait with **OTTERNET / Deployment state** in the operator's Grafana.
It draws the `DeploymentState` records the reconciler writes: **Deployment state
per device** lists the fourteen devices and their status, and **Not in sync**
counts the ones that are not `in_sync`. Between the push and the confirming
comparison the two pushed devices read `pending`, and they return to `in_sync`
only when a later comparison finds no difference. That is the point to make:
green means the device *said* it matches, never that something was sent to it.

The dashboard lags the log. The exporter reads Infrahub once a minute and
Prometheus scrapes it once a minute, so a status reaches the panel up to two
minutes late. The `pending` window is now about a minute, so the panel can skip
it and go straight to green. Narrate from the log and use the dashboard to show
the end state.

Show the rule and the advertisement landing:

```bash
docker exec -i clab-otternet-fw1 sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR admin@127.0.0.1 \
  "show configuration security policies from-zone branch to-zone k8s-prod | display set | match svc-"
docker exec clab-otternet-border-leaf1 Cli -c "show ip prefix-list PL-DC-ADVERTISED-BRANCH"
```

Both pushes are full replaces, never merges. The leaf's runs in an EOS
configuration session that starts from `rollback clean-config`. The firewall
loads the whole artifact with `load override` and commits it with `commit
confirmed`, and the reconciler sends the confirmation only once the device still
answers, so a push that cut the reconciler off rolls itself back.

**5. The packet.** From the branch desktop, the granted VIP answers, and the one
nobody granted does not:

```bash
docker exec clab-otternet-branch-desktop curl -s -m 10 http://<otter-shop vip>/     # whoami answers
docker exec clab-otternet-branch-desktop curl -s -m 8 http://10.112.240.0/          # times out
```

The second one matters more than the first. `otternet-demo` is running,
advertised, and healthy. The branch still cannot reach it, which shows the
firewall and the pod policy are the control, and not an open path. In the
desktop's Firefox, the **Demo app (locked)** bookmark makes the same point.

## Act two: a branch user asks for Grafana

Grafana is already running when the demo starts. It is `otternet-metrics`, a
seeded application that Infrahub delivered through Vidra like any other, on the
pinned VIP `10.112.240.81`. Nobody at the branch can use it yet.

**1. Show the gate.** On the branch desktop, the toolbar bookmark **Grafana
(locked)** opens `http://10.112.240.81/`, and nothing answers. Two gates
are shut: the firewall has no permit, and Grafana's own pod policy names no
branch source. The route is **not** a gate here, and it is worth not claiming it
is: `PL-DC-ADVERTISED-BRANCH` already permits the whole VIP range
(`seq 10 permit 10.112.240.0/24 le 32`), so `branch-rtr` holds
`10.112.240.0/24` before anyone asks. The grant still adds its own block's line,
which is the record of what it opened, and revoking removes that line.

**2. Ask.** In the portal, as `alice@otternet.lab`, choose **Application Access
Grant (generated)**, the template the portal derives from the schema, and leave
**What do you want to do?** on *Request a new service*. Four fields matter, and
three of them the form requires:

| Field | Value |
| --- | --- |
| Name | `grafana-alice`, or anything not used before; the branch is `implement_<name>` |
| Application | `otternet-metrics` |
| Owner | `branch` |
| Source Site | `branch-office` |

Leave the rest empty: the ports come from the application's advertised services,
and the zone and source address from the site. Grafana needs nothing special;
this is the ordinary access request. It takes **20 to 40 seconds**.

**3. Read the proposed change.** The rule `svc-<name>` (`branch → k8s-prod`,
`junos-http`), the address-book entry for Grafana's block `10.112.240.80/28`,
`10.70.0.0/24` added to the application's allowed sources (the **Crossplane
FabricApp** artifact for `otternet-metrics` gains it under `allowFrom`), and the
border leaf's `PL-DC-ADVERTISED-BRANCH` gaining `seq <n> permit 10.112.240.80/28`.
The Junos artifact re-renders alongside.

The generated templates stop at the service's own generator, unlike the
hand-written one. The fabric consequence still appears because
`generate-avd-device-hostvar` runs in every proposed change's pipeline, and it
arrives **last**: about a minute after the change opens, once the pipeline's
host vars and structured configs are written and the border leaf's artifacts
re-render. Open the change, talk through the firewall rule, then show the leaf.
If the leaf's diff is still missing after two minutes, retry the artifact
checks from the **Checks** tab (the API equivalent is
`CoreProposedChangeRunCheck` with `check_type: ARTIFACT`); that re-renders it from
the files the pipeline wrote, in about fifteen seconds.

**4. Merge, and sign in.** Once the reconciler has pushed `fw1` and the border
leaf, reload the bookmark. That took about 2.3 minutes from the merge when the
loop slept its whole interval; expected after the early-wake change, 30 to
90 seconds. Watch for `pushed=2` in the reconciler log rather than the clock.
Grafana redirects to the same Dex sign-in page the portal uses. `alice` signs in
and lands on the **Organisation** dashboard as a **Viewer**: the sign-in path
can never make anyone an administrator.

**5. Show the dashboards, in this order.** They are in the `OTTERNET` folder.

- **OTTERNET / Organisation**: what Infrahub says the lab is, counted from the
  graph by the exporter. Devices by kind, services by status, and open and
  merged proposed changes.
- **OTTERNET / Fabric telemetry**: gNMI from every switch. Point at **Intended
  but not established**, which is empty, and say why that panel exists:
  Infrahub knows which sessions *should* be up, so it can say which ones are
  missing. **Established but never intended** is the converse.
- **OTTERNET / WAN routing**: the SR Linux routers, also over gNMI. They answer
  the same OpenConfig paths as the switches, so their series carry the same names
  and labels.
- **OTTERNET / Perimeter firewall**: `fw1` over SNMP, its zone handoffs named
  by their modelled descriptions. **Zone handoffs down** should read 0;
  **Flow sessions** and **Throughput per handoff** are the traffic the rule the
  grant created now lets through, alice's browser session among it. The
  firewall the proposed change configured is the firewall this dashboard reads.
- **OTTERNET / Deployment state**: every device's `DeploymentState`. The two
  devices this grant pushed are `in_sync` again, which means the confirming
  comparison found no difference, not merely that a push was sent. If a step
  above leaves you waiting on the reconciler, open this one first; it is the
  dashboard about the wait.

**6. Monitoring is intent too.** In Infrahub, on a new branch, open
**Monitoring → Profiles → `fabric-core`** and remove the measurement
`bgp-neighbor-state`. Open a proposed change. About a minute later it shows the
collector's **Telemetry Collector Configuration** artifact losing its BGP
subscriptions for each fabric switch, and no other artifact moves. Do not merge
it; delete the branch afterwards.

## Act three: revoke it

In the portal, choose **Revoke access**, pick the `otter-shop-access` grant (or
the Grafana one), give a request reference, and submit. It sets the grant to
`decommissioning` on a branch, waits for the generator to remove what the grant
created, regenerates the fabric, and opens the proposed change.

The change removes the rule, the address-book entry, the source prefix the grant
added, and the border leaf's advertisement line. A rule written by hand in the
same zone pair is left alone. `branch-to-access-portal` is one, and it sits in
the same zone pair the grant's rule left, because removal is keyed on provenance
(`managed_by_service`) rather than on shape. A source prefix that another live
grant still relies on is also left in place.

Merge it. Once the merged artifacts hold still, the reconciler pushes both devices again (expected after the early-wake change: 30 to 90 seconds), and the VIP
stops answering from the branch. Anyone already signed in to Grafana loses the
page with it.

A grant can also be withdrawn without the portal by setting its `status` to
`decommissioning` in the Infrahub UI, on a branch: the event rule on `status`
fires the generator, and the proposed change shows the same withdrawal.
Rehearsed on a grant's own branch, the generator had the grant `decommissioned`,
its rule gone and `fw1`'s configuration back to main's byte for byte about
twelve seconds after the status changed.

The **Revoke access** picker lists only grants that exist on `main`, so it can
only be rehearsed after a real merge. Before one, it offers nothing.

## Act four: the review step bites

Every check is green on every proposed change the demo produces, so the
review step can read as decoration. This makes one go red:

```bash
scripts/demo_break_isolation.sh            # needs INFRAHUB_API_TOKEN in the environment
scripts/demo_break_isolation.sh --revert   # afterwards: deletes the branch and the change
```

It adds `globex-hq`'s circuit to `acme-l3vpn` on the branch
`demo-broken-isolation` and opens a proposed change. A circuit in an L3VPN is the
routing domain, not a label, so this joins two tenants directly across the
provider edge. `wan-service-consistency` fails naming both tenants while every
other check stays green. Nothing renders wrong, which is the point: the check is
what notices.

The script takes 35 to 45 seconds and `--revert` about 4. It re-runs the checks
after the edit, on purpose. The first pass starts when the proposed change is
created and has been measured racing the edit, all green over data that was
already wrong. It never merges.

Because of that re-run, the **Checks** tab lists `wan-service-consistency`
twice, both red, and the other global checks twice, both green. A check with no
`targets` gets a new entry on every pass. That is one fault reported by two
passes, not two faults. The message reads:

```text
L3VPN 'acme-l3vpn' belongs to 'acme' but carries circuit 'globex-hq', which belongs
to 'globex'. Membership of this list is the routing domain, so the two tenants
would reach each other directly across the provider edge.
```

## Act five: the agent, through the MCP server

```bash
uv run python scripts/provision_mcp_agent.py --check
# mcp-agent signs in and holds only the 'Agent Access' role.
curl -s http://127.0.0.1:8001/health
# {"status":"healthy"}
```

Claude Code picks the server up from `.mcp.json` as `infrahub-lab` and asks you
to approve it the first time. It signs in as `mcp-agent`, never as the
Super Administrator `agent` the task workers run as. It reads everything, writes
only on a branch (the server creates one per session, named
`mcp/session-<date>-<hex>`), and can open a proposed change. A write aimed at
`main` is refused by Infrahub, not by the prompt.

`provision_mcp_agent.py --check` reads the password from the `.env` beside the
script, so run it from the main checkout. From a git worktree it reports
`INFRAHUB_MCP_PASSWORD is not set` against a server that is working.

Good questions to ask it: "what depends on `otternet-demo`?" (`find_reachable`
from `ServiceFabricApp__otternet-demo` reaches its `ClusterKubernetes`
`otternet`, its VIP block `10.112.240.0/28` and onward; the cluster kind is
`ClusterKubernetes`, and naming it `KubernetesCluster` is refused as an unknown
kind), or "which switches would a change to `K8S_PROD` touch?" (from
`IpamVRF__K8S_PROD` it reaches the leaves through the VRF's BGP peers).

Two refusals are worth showing, because they come from different places:

- Ask it to work on `main` and the **MCP server** refuses:
  `Writes to the default branch 'main' are not allowed`.
- Its account is refused by **Infrahub** too, which is what makes that more
  than a prompt: `mcp-agent` writing to `main` directly gets `PERMISSION_DENIED`
  (`object:Service:FabricApp:update:allow_default`).

A write it is allowed lands on its session branch, and `propose_changes` opens
the proposed change from there in well under a second.

**Do not claim the agent cannot merge.** On Infrahub 1.10.6 the
`CoreProposedChangeMerge` mutation does not check `merge_proposed_change`, and
the MCP server does not block it, so `mcp-agent` merged its own proposed change
when tested. Say instead that every change the agent makes lands on a branch as
a proposed change, and that merging is where the human decides.

## Timings

| Step | Wall clock |
| --- | --- |
| Portal request **Exposed application, with access**, start to proposed change | 70 to 85 s |
| Of that, the whole-fabric AVD regeneration (7 switches) | 21 to 25 s (15 to 19 s host vars, 6 s structured configs) |
| Its proposed change, opened to every check finished | 60 to 80 s |
| A single access grant through the portal | 20 to 40 s |
| Its proposed change, opened to the border leaf's diff | about 60 s |
| Act four, break to red check / `--revert` | 35 to 45 s / about 4 s |
| Merge to the resource existing in Kubernetes | under a minute |
| Merge to `fw1` and the border leaf carrying the change | 30 to 90 s, expected after the early-wake change (was up to 120 s plus the cycle) |
| Push to both devices confirmed `in_sync` | about 70 s, expected after the early-wake change (was a further 120 s) |
| Grafana grant, merge to Grafana answering the branch | 30 to 90 s, expected after the early-wake change (measured about 2.3 minutes before it) |
| Revocation, merge to the rule leaving the device | 30 to 90 s, expected after the early-wake change |
| `uv run invoke reconcile --now` to the cycle starting | under a second; the cycle itself about 11 s, or about 25 s when it pushes |
| A reconcile cycle with nothing to push / pushing `fw1` and a leaf | about 11 s / about 25 s (measured from the loop's own log) |

Measured on this lab: a granted VIP answered `HTTP 200` from the branch desktop,
the seeded application's VIP and an unpermitted port on the granted one were
both refused, and after revoking, the same VIP stopped answering once the
reconciler pushed two devices on one cycle: the firewall and the border leaf.

## What is already there

Three applications are seeded, and none is reachable from the branch:

| Application | VIP | Purpose |
| --- | --- | --- |
| `otternet-demo` | `10.112.240.0` | a `whoami` workload, the ready-made target for a grant on something that already exists |
| `otternet-metrics` | `10.112.240.81` | Grafana and Prometheus, for act two |
| `otternet-telemetry` | none, not exposed | Telegraf, configured entirely from the monitoring profiles |

No grant is seeded, and a test keeps it that way. Anything else was requested
through the portal and lives only in that environment's database, so a rebuild
removes it. Rehearse with a different request reference from the one you plan to
use live.

## Recovery

- **A request fails half way.** Change the request reference and resubmit:
  `BranchCreate` is not idempotent, so the same reference dies on the first step.
  Delete the orphan branch afterwards, in Infrahub and, if it was mirrored, in git.
- **`Unable to set context for account that doesn't exist`.** That user has never
  signed in to Infrahub. Run `uv run python scripts/provision_portal_accounts.py`.
- **A grant made outside the portal never builds.** Over the API or an SDK, it must
  also be added to the `service_app_accesses` group. The event rule fires, and the
  run fails `Target … is not part of the group` with nothing visible on the grant.
  The portal adds the membership itself.
- **The cluster resource never appears.** Check `kubectl get vidraresource -A`, not
  the sync: a sync reports `Succeeded` over an empty or rejected set. A deleted
  resource is not redelivered until the `InfrahubSync` is deleted and re-applied
  from `vidra/infrahub-syncs.yaml`.
- **The merge reached no device.** Check the reconciler is running and look at
  `docker logs infrahub-deployment-reconciler-1`; a device the operator suspended
  shows as `suspended=1` and is left alone by design. A loop that is running
  but has not started a cycle since the merge is still waiting for the
  artifacts to hold still; `uv run invoke reconcile --now` starts one at once.
