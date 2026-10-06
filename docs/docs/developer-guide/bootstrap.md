---
title: Running the AVD chain, bootstrapping and bringing up the lab
description: The AVD chain, the one-command bootstrap, its verification, and the lab bring-up with the provisioning mechanics for each device family.
audience: developer
sidebar_position: 34
---

# Running the AVD chain, bootstrapping and bringing up the lab

## Running the AVD chain

`invoke load` seeds objects and runs **no generators**. A freshly loaded instance
therefore has no spine-to-leaf cabling, and PyAVD renders switches with no
uplinks and no underlay or overlay BGP — about 155 lines for a spine instead of
239 — while every artifact still reports `Ready`. Nothing errors. Use
`invoke avd --topology` once after a fresh load to build the fabric.

Thereafter use `invoke avd`, which runs only the two idempotent stages:

| Stage | Idempotent | When |
| --- | --- | --- |
| `generate-fabric`, `generate-pod`, `generate-rack` | **No — destructive on re-run** | `--topology`, build time only |
| `generate-avd-device-hostvar`, `generate-avd-device-structured-config` | Yes | every run |

The topology generators must not be re-run against a fabric that already has
cabling. `generate-pod` takes each spine from nine interfaces to four, deleting
the leaf-role ports racks 1 and 2 are cabled to, and `generate-rack` then fails
on rack 3 with an `IndexError` because its slice of spine ports is empty. That
is why they are behind a flag rather than in the default path.

**Use `--branch` for anything you intend to review.** The chain writes a great
deal of derived data, and doing that straight onto `main` leaves nowhere to see
what changed first. Artifact regeneration passes the branch through to
`POST /api/artifact/generate/{id}`; omit it and the endpoint regenerates against
`main`, which produces the confusing result that
`infrahubctl transform --branch X` renders your change while the stored artifact
never moves.

## Bootstrapping the whole environment

```bash
uv run invoke bootstrap            # everything, in one command
uv run invoke bootstrap --fresh    # ... destroying the stack and the lab first
```

That runs `build` → `start` → `load` → `avd` (on a branch, then merged) → `lab` →
`reconcile --converge` → `tooling` → `mcp` → `mcp-tokens` → `metrics-exporter` → `cluster`, starts
the reconciler loop, and ends with the readiness checks. Each step is still available on its own;
`bootstrap` only removes the need to remember the order and the flags.

Since cycle 033 it also builds the portal image and runs `tooling` before `cluster`, so a
finished bootstrap has a branch user able to sign in and ask for something.

### A read-write bootstrap, and what it does for demo-main

The demonstration runs against a read-write repository on `demo-main`
([builder demo](../demo-builder.md)). Export these four settings, then bootstrap:

```bash
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
export INFRAHUB_REPOSITORY_MODE=readwrite
export INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES='["demo/.*"]'
export NFD_GITHUB_TOKEN=...          # a token with write access to the repository; never commit it
export INFRAHUB_API_TOKEN=...        # the token infrahubctl uses; for a local stack, INFRAHUB_INITIAL_ADMIN_TOKEN
uv run invoke bootstrap --fresh
```

- **The settings are checked first.** Bootstrap stops before it destroys anything if `INFRAHUB_API_TOKEN`, the URL, the
  token or the import setting is missing. Measured from a shell that held only `HOME`, `PATH`, `USER` and
  `NFD_GITHUB_TOKEN`: without `INFRAHUB_API_TOKEN` the stack was destroyed and rebuilt for five minutes, and then the step
  that uploads application payloads stopped with `INFRAHUB_API_TOKEN is not set`. The check now refuses at the start. Bootstrap also stops if a dry-run push with the token is refused. These used
  to be found out after the teardown.
- **`--fresh` recreates `demo-main`.** After the stack and the lab are destroyed, bootstrap deletes
  `demo-main` on the remote and creates it again at the tip of `main`. Before this, an existing
  `demo-main` was kept, so a new stack registered the tree that earlier demonstrations had left, which
  was behind `main`. Recreating it is safe at that point, and only at that point: the rule against it
  in the builder demo exists because a running Infrahub has already pulled the merge commit.
  Bootstrap without `--fresh` leaves `demo-main` alone, and the readiness check reports a `demo-main`
  that differs from `main`.
- **A stale local staged branch is rebuilt.** At the end of a read-write bootstrap, if
  `stage/internet-access` exists and was cut from an older `main`, bootstrap runs
  `demo-stage --force`. It does so only when the local `main` equals `origin/main`, because
  `demo-stage` cuts from the local `main`; otherwise it prints the two commands to run.

### The two MCP accounts, and the order they are made in

`mcp` creates `mcp-agent` and mints `INFRAHUB_MCP_TOKEN` into the **main checkout's** `.env` (only the demo rehearsal uses it; Claude Code does not), makes
`Requester Access` the only role of the built-in `Infrahub Users` group (it detaches `General Access` and `Proposed Change Reviewer`), and starts the MCP server in
token-passthrough mode. `mcp-tokens` then mints `INFRAHUB_MCP_TOKEN_ALICE`. It runs after `tooling` and
after `mcp` because `.mcp.json` sends her token, and alice has no password in Infrahub: her account exists once she has signed in through
Dex, and her token is minted with the access token that sign-in returns. Before this wiring, only
`invoke mcp` ran, and nothing in bootstrap minted her token.

`--fresh` destroys the database, so every token in `.env` stops authenticating. Both scripts replace a
token that no longer authenticates and keep one that still does, so a re-run changes nothing. Bob has a
Dex account but no MCP token, because nothing registers him with the MCP server.

**A shell that loaded `.env` before `--fresh` holds the old tokens, and they win over `.env`.** `docker compose`
and `scripts/deploy_tooling.sh` both prefer a variable in the process environment to the file. Measured on a
`bootstrap --fresh` run from such a shell: the portal was deployed with the previous stack's token, answered 401 to
every request, ingested no catalogue entry, and its picker was empty. The readiness check for the picker found it.
`bootstrap`, `tooling`, `mcp`, `mcp-tokens` and `metrics-exporter` now drop every generated credential variable
(`INFRAHUB_MCP_*`, `INFRAHUB_PORTAL_*`, `INFRAHUB_EXPORTER_*` tokens and passwords) whose value differs from `.env`,
print the names without the values, and read `.env` instead. `invoke ready` warns when the shell it runs in holds such
a variable, because a Claude Code started from that shell would send the old token: open a new shell after a bootstrap.

### The local `network-admin` account

`network-admin` runs after `mcp-tokens`, and `uv run invoke network-admin` runs it alone. It needs only the loaded stack,
because it is a local Infrahub account: it does not use Dex, the MCP server or a token. It creates the account
`network-admin` (label `Network Admin`, type `User`), the group `Network Admins` and the role `Network Admin Access`, and puts the
generated password into the main checkout's `.env` as `INFRAHUB_NETWORK_ADMIN_PASSWORD`. Nothing prints the password. A password that
still signs in is kept, so a re-run changes nothing, and after `--fresh` the same password is used to create the account again.
No API token is minted for it: a person signs in to the UI with the username and the password. What it can and cannot do is in
[the network-admin account](./mcp-server.md#the-network-admin-account).

### What a finished bootstrap checks

The last step is `invoke ready`, which runs by itself at the end of bootstrap and can be run at any time.
It prints one line per check, a count, and what a person still has to do. It exits 1, and bootstrap
exits 1, if any check fails. `invoke doctor` runs the same checks after its own.

| Check | What it asserts |
| --- | --- |
| Application catalogue | Seven entries; `whoami`, `podinfo`, `grafana` and `argo-cd` are requestable and the three `lab-*` entries are not |
| `triggers.yml` objects | Every action and rule the file declares exists, including the group rules such as `add-app-access-to-its-generator-group` |
| Menus | Every entry in `menus/` exists |
| Seeded applications | `otternet-demo`, `otternet-metrics` and `otternet-telemetry` have a catalogue entry and are pinned |
| MCP server | The container runs and `/health` reports `token-passthrough` |
| `mcp-agent` | The account and its role exist; a tool call with `INFRAHUB_MCP_TOKEN` (used by the demo rehearsal, not by Claude Code) returns `AccountProfile` `mcp-agent` |
| Requester Access | `Infrahub Users` holds only `Requester Access` (view, write service objects on a branch, open a proposed change); the two built-in roles are detached |
| `network-admin` | The account exists, is only in `Network Admins` (not `Super Administrators`, not `Infrahub Users`), the role holds exactly the six permissions defined, the role is attached to no other group, and the password in `.env` signs in |
| alice cannot write to main | A scratch tag created on `main` with her token is refused |
| Portal accounts | Every Dex user has an Infrahub account |
| alice | A tool call with `INFRAHUB_MCP_TOKEN_ALICE` returns `alice`, and she opens a proposed change on a throw-away branch that the check deletes |
| Repository | Read-write on `demo-main`, `in-sync`, two task workers, and `demo-main` equal to `main` (same commit, or same tree). After a merge to `main` it differs until `uv run invoke demo-advance` brings it level through Infrahub |
| Leftover branches | Warns about any Infrahub branch besides `main`, such as an `mcp/session-*` branch |
| Staged branch | Warns when `stage/internet-access` was cut from an older `main` |
| Portal picker | The portal's catalogue lists exactly the requestable entries, asked from the branch desktop as alice |
| `.mcp.json` | One server, `infrahub-lab`, sends `INFRAHUB_MCP_TOKEN_ALICE`; any other entry fails the check |
| `claude mcp list` | `infrahub-lab` connects, from a process that has `.env` loaded |
| Shell environment | Warns when this shell holds a generated credential that differs from `.env` |

The repository check is skipped on a stack that is not read-write unless
`INFRAHUB_REPOSITORY_MODE=readwrite` is exported, in which case it fails. A check that cannot run, such as
the picker with the lab down, is reported as `SKIP` with the reason.

**What a person still has to do.** Start Claude Code from a shell that has loaded `.env`, because
`.mcp.json` takes alice's token from the environment:

```bash
cd /home/ubuntu/dev/nfd41/infrahub
set -a; source .env; set +a
claude
```

and approve the `infrahub-lab` server the first time Claude Code asks. Claude Code then acts as alice. Claude
Code reads `.mcp.json` at start, so restart it after a bootstrap that mints new tokens.

**The bootstrap ends by starting the reconciler LOOP**, not just by converging
once. Without it a merge reaches no device and `DeploymentState` keeps reporting
the green it recorded during the build — a reading identical whether the loop is
running or was never started, which is the worst kind of wrong. Measured before
this was added: every device `in_sync`, `last_checked_at` nine hours old, no
container. `scripts/verify_bootstrap.sh` now asserts the container is up.

`OTTERNET_RECONCILE_FIREWALL_EVERY` makes the firewall's cadence tunable. The
default of one cycle in four is a steady-state economy — its comparison takes an
exclusive lock on the vSRX — and a demo wants `1`, because the firewall is the
payoff and nobody else is on the box.

**Bootstrap runs `invoke build` itself, before it starts the stack.** `destroy` keeps images, and `invoke doctor` once showed the reconciler's image 14 hours behind the source commits after a pull.

**A rename means `invoke build`.** The reconciler runs the image's installed copy
of `solution_arista_avd`, not the bind-mounted source, so after the rename it
looked for `clab-nfd41-*` containers and reported `failed=7` against a healthy
lab. The bind mount cannot stand in for the install.

**The device step is the reconciler, not `invoke provision`.** Cycle 030 swapped
it so the bootstrap exercises the same code path that keeps the fabric correct
afterwards, which also means `scripts/verify_bootstrap.sh` validates that path
rather than a second one. `invoke provision` remains as the manual command and
is unchanged.

`--converge` rather than a single cycle, because of a semantic that matters: a
cold device differs, so the first cycle **pushes** it — and `last_confirmed_at`
deliberately does not move on a push. Confirmation needs a later comparison that
finds no difference, so one cycle would leave a freshly built fabric correct but
unconfirmed. Converge also compares the firewall on every cycle rather than one
in four; the cadence is a steady-state economy and during a build nobody else is
using the box.

**The AVD chain runs on a branch and `--merge` merges it, rather than you
running `infrahubctl branch merge` by hand.** That is not ceremony. The topology
generators write a great deal of derived data, and running them onto `main`
leaves nowhere to see what changed — and no way back if they damage a fabric
that already has cabling. The merge then **waits for the artifacts to render**,
because generation is asynchronous: the REST endpoint returns 200 and the
rendering happens afterwards. Without that wait `provision` can read an artifact
that exists, reports `Ready`, and is empty — and push nothing onto a switch.

**That wait requires the artifacts to be non-empty AND stable over a window**, and both
halves were added after being measured, in that order:

- An artifact still holding its *pre-merge* content is populated, so a merge that REMOVED
  something returned from the wait immediately. A reconcile cycle run straight afterwards
  compared every device against stale output, printed `compared=14 differed=0`, and left the
  deleted interface on both leaves. Nothing errored, and the next cycle ten minutes later
  cleaned it up — so the only symptom was a deletion that appeared not to take.
- Requiring two consecutive agreeing checksum samples **did not fix it**, because the two
  samples agreed on the *old* checksums: the post-merge render had not begun ten seconds after
  the merge, so the wait settled on exactly the stale values it was meant to exclude. Same
  `differed=0`, same interface left behind.

`_wait_for_artifacts` therefore asserts stability over `STABLE_SAMPLES` samples rather than one,
and any movement resets the count. That is an empirical floor, not a guarantee, which is why the
timeout path says what it could not establish rather than claiming success. Waiting instead for
every checksum to **move** would be exact and would never terminate — an artifact whose content
genuinely did not change never moves, which is most of them on most merges.

`invoke avd --branch X --merge` does the same thing outside a bootstrap.

**After the wait, `--merge` deletes the branch it merged** — `build-fabric`, in a bootstrap.
Left behind it sat in every branch picker with all of its content already on `main`, reading as
unfinished work. The delete is idempotent (a branch already gone is skipped), never touches the
default branch, and is skipped rather than guessed at when Infrahub cannot list branches; a
failed merge raises before it is reached. `tests/unit/test_merged_branch_cleanup.py` pins all
four.

### Showing a check catch something

```bash
scripts/demo_break_isolation.sh            # break it, open the proposed change
scripts/demo_break_isolation.sh --revert   # delete the branch and the change
```

Every validator is green on every proposed change this lab produces, so the
review step reads as decoration. This adds one tenant's circuit to another
tenant's `ServiceL3vpn` on a branch — the routing domain, not a label, so it
joins two tenants directly across the provider edge — and lets
`wan-service-consistency` say so. Nothing renders wrong; the check is what
notices. It never merges, and `--revert` removes the branch and the change.

**It re-runs the checks, and that is not belt-and-braces.** Creating a proposed
change starts its validators immediately, and that first pass raced the edit:
measured 62 checks, all green, over data that was already wrong. Asking again
gave 67 checks with one red.

### Verifying a bootstrap

```bash
scripts/verify_bootstrap.sh          # ~20 minutes, destroys and rebuilds everything
SKIP_SMOKE=1 scripts/verify_bootstrap.sh   # without the act-level smoke
```

Tears the environment down, rebuilds it with `invoke bootstrap --fresh`, and
asserts the result stage by stage — seed data, artifacts, the devices, the
cluster, the tooling cluster and signing in, then `invoke ready` and `invoke doctor`, then an act-level
smoke: `invoke demo-run --acts one,two`, `invoke demo-restore` and `make -C lab verify`, which has to report
121 passed. For a read-write repository, export the four settings above first. Use it after changing anything in
the bootstrap path; "it worked" and "it is stable" are different claims, and only
a full teardown distinguishes them. (This said "sixteen things" for several
cycles after it stopped being sixteen, which is why the count is no longer
stated: the stages are what stays true.)

Several checks are deliberately about **state rather than exit status**, because
every bug this found was quiet:

- It counts **established BGP sessions**, not artifact size. An AVD artifact can
  be 239 lines, contain `router bgp`, report `Ready`, and describe a fabric that
  does not exist — which is exactly what a half-run topology chain produces.
- It **downloads** every configuration artifact. Generation is asynchronous, and
  an empty artifact still reports `Ready`.
- It checks the **delivered resources**, not `syncState`. A sync over an empty
  set is still `Succeeded`.
- It asks **fw1's running configuration**, not `DeploymentState`, whether the full
  configuration was applied: no `plain-text-password-value`, and the newest commit by
  `admin` (the reconciler) rather than vrnetlab's `root via other`. `in_sync` once came
  from a comparison that could not see cleartext.
- It counts every **SR Linux WAN router's established BGP sessions** per network instance
  against the `neighbor` statements of that router's own `lab/wan/rendered/<n>/config.cli`,
  so the expected count comes from the artifact rather than from a number in the script.
- It runs **every OTTERNET dashboard panel through Grafana**, not against Prometheus.
  The direct check passed while every panel read "No data," because Grafana's
  Prometheus plugin was not registered. `scripts/check_grafana_panels.py` checks the
  datasource's health, then sends each visible query to `/api/ds/query` over the last
  30 minutes, with the dashboard's own variables, and names each panel that returns
  no data or an error. Its `ALLOWED_EMPTY` is the one place a query may be empty, with
  a reason per entry. An allowed query may still not error, its panel's other query
  must have data, and an entry that matches nothing fails.

Six runs of it found the tolerated-502, the topology double-run and the CoreDNS
race, none of which failed in a way that pointed at its cause.

**Two more races live in `invoke cluster`, and both are timing-dependent rather
than deterministic.** Seen on a cycle-030 rebuild, one after the other:

- **Vidra can beat the lab's installer to a resource.** Vidra goes up before
  Crossplane, so once the XRDs land its next retry may create
  `fabricpeering/otternet` in the window between the lab installer's
  `kubectl apply` reading the resource and creating it. Apply then fails
  `AlreadyExists` — from `apply`, not `create` — and the script `die`s, leaving
  the lab's two FabricApps unapplied and the handover unrun. Re-running
  `invoke cluster` clears it, because by then `apply` finds the resource and
  updates instead.
- **The lab's Crossplane installer preflights in-cluster networking itself.**
  `invoke cluster` already waits for the CoreDNS rollout, but
  `install-crossplane.sh` separately runs a busybox pod checking API ClusterIP,
  external DNS and egress. A Cilium that is up but still settling fails it. The
  same preflight run by hand a few minutes later passes, so the failure says
  "too early," not "broken."

Neither is caused by the device step, whichever command runs it: both parties to
each race are inside `invoke cluster`, which starts only after the devices are
done.

**Compose commands are pinned to the real project directory.** `docker compose`
derives its project name from the working directory, so from a git worktree
`invoke destroy` used to address a project that does not exist and silently do
nothing, while `invoke start` raised a second stack fighting for port 8000.
`compose_root()` resolves the main checkout through
`git rev-parse --git-common-dir`, which also matters because
docker-compose.override.yml mounts `./:/upstream` and Infrahub clones that path
over git — a worktree's `.git` is a file pointing into the main repository, so a
clone of it fails outright.

## Bringing the lab up from Infrahub

Two tasks, in order. The topology belongs to the lab under `lab/`; the
configuration belongs to Infrahub.

```bash
uv run invoke lab          # deploy lab/otternet.clab.yml, wait for eAPI
uv run invoke provision    # push every rendered artifact onto the devices
```

`invoke lab` deploys the lab's committed topology **as-is**. Nothing
renders a topology from Infrahub. The fabric comes up unconfigured on purpose:
the cEOS nodes are given no `startup-config`, only `CLAB_MGMT_VRF` and a
management address, so they boot reachable and empty. The lab resolves to
`lab/` in the **main** checkout, even from a git worktree, because there is one
lab and its runtime state (`clab-otternet/`, the kubeconfigs) lives under its
directory; set `OTTERNET_LAB_DIR` to override. It renders `lab/wan/render.py`
first, because every SR Linux router boots from that gitignored output
(`wan/rendered/<node>/config.cli`) and ContainerLab refuses a missing file.

`invoke provision` then makes each device match its artifact. Three families,
three routes in, because the lab gives them three different front doors:

| Kind | Artifact | Route | Mechanism |
| --- | --- | --- | --- |
| `DcimFabricSwitch` | AVD EOS Configuration | `mgmt_ip`, eAPI | config session + `rollback clean-config` |
| `DcimDevice` | SR Linux Configuration | container name | `sr_cli` candidate: `delete /`, set, `commit confirmed`, check, accept |
| `SecurityFirewall` | Junos Configuration | container name | `load override` + `commit confirmed` + login check |

**The switches are reached by address and the rest by name, deliberately.**
Infrahub calls a switch `leaf-otternet-pod1-1-1` and ContainerLab calls the same box
`k8s-leaf1`; there is no renaming layer, so names cannot match them. Their
`mgmt_ip` does equal the lab's management address, so eAPI needs no name. The SR
Linux routers and the firewall are not pushed by address (theirs is the
collector's), and their Infrahub names *are* their ContainerLab node names.

Every push is a replace, not a merge, so deleting something from the model
deletes it from the device. Three things are worth knowing before changing
`scripts/provision_lab.py`:

- **The EOS artifact ends with `end`.** Left in place it returns the CLI to
  enable mode and the commit that follows is rejected as an invalid command, so
  the session is abandoned and the switch silently keeps its old configuration.
  `_eos_config_lines` strips it and appends its own.
- **The firewall uses `load override`, and only because the artifact is complete.**
  `load override` and `load update` were once measured deleting the `system`
  stanza -- including `services { ssh; netconf; }`, the management path this
  script arrives on -- because the artifact then had none, which is why the push
  was `load replace` with `replace:` tags until cycle 035. The artifact now
  renders `system`, fxp0 and `mgmt_junos`, `_assert_junos_lifeline` refuses one
  that lacks them, and the confirming commit waits for a fresh login. Measured
  on a vSRX booted like `fw1`: the first full replace changed exactly two
  `display set` lines -- it removed `init.conf`'s two cleartext
  `plain-text-password-value` entries -- and added none.
- **Junos re-serialises `## SECRET-DATA` with a fresh salt on load**, so a
  diff showing the password hashes changing is Junos, not a credential rewrite.
  The comparison proves it rather than assuming it -- see the normaliser above.
