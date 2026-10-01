---
title: Demo runbook
---

# Demo runbook

The order below is not preference. It is what the measured timings make sensible:
a merge reaches the **cluster** in under a minute and a **device** on the
reconciler's next cycle, so showing the cluster first fills the gap the fabric
would otherwise leave you standing in.

## Before anyone is watching

```bash
docker compose ps | grep deployment-reconciler   # must be running
uv run infrahubctl branch list                   # main, and nothing stale
uv run python scripts/provision_portal_accounts.py --check
```

Three things go wrong if you skip these:

- **No reconciler, no device changes.** It is behind a compose profile. Without
  it a merge reaches nothing, and the deployment view still shows green from
  whenever it last ran — a reading identical to a healthy one. Start it with
  `docker compose --profile reconcile up -d deployment-reconciler`, and for a
  demo set `OTTERNET_RECONCILE_FIREWALL_EVERY=1` so the firewall is compared
  every cycle rather than one in four, and `OTTERNET_RECONCILE_INTERVAL=120`.
  Put both in `.env` at the repository root (gitignored) so they survive a
  restart; the defaults, 600s and one cycle in four, leave a merge up to forty
  minutes from the firewall. `docker exec infrahub-deployment-reconciler-1 env
  | grep RECONCILE` shows what the running container has.
- **A user with no Infrahub account cannot request anything.** The account is
  created by their first Infrahub sign-in, so a fresh environment fails the first
  request *after* creating its branch. `invoke tooling` provisions them; the
  `--check` above tells you if any are missing.
- **Stale branches in the selector** are the first thing on screen in Infrahub
  and invite the one question you do not want. Infrahub mirrors the git branches
  of the repository it clones, so a local git branch reappears in Infrahub after
  its Infrahub branch is deleted. Remove or push aside the git branch first.

The branch user's screen is the branch desktop, through Guacamole on the host's
port 8080 (`http://<host>:8080/`, over Tailscale for a remote laptop). The
portal itself is reachable only from the branch side, so a browser on the
presenter's laptop cannot open it directly.

## The arc

**1. Ask for something.** [https://10.90.0.11:32001](https://10.90.0.11:32001), sign in as
`alice@otternet.lab` / `password`, choose **Exposed application, with access**.
Every field is a dropdown or prefilled; the chart values default to a working
exposure block. About **75 seconds**, most of it two generator waits.

What to say while it runs: the request creates a branch, an application and an
access grant, waits for the VIP to be allocated before the grant is built, and
regenerates the fabric — so the proposed change carries consequences, not just a
request.

**2. Read the proposed change.** This is the point of the whole thing. It
contains the service objects, the firewall rule, the address-book entry, the
source prefix added to the application's own policy, the regenerated host vars
and the **rendered configuration diff** for the border leaf — one line,
`seq <n> permit <vip>`, inside `PL-DC-ADVERTISED-BRANCH`.

Merging is the approval. There is no second gate, deliberately: two gates can
only disagree.

**3. Merge, and show the cluster first.** Vidra delivers within about a minute
and the application deploys. `kubectl get fabricapp` and `kubectl -n <app> get
svc` show the VIP arriving.

**4. Then the device.** On the next reconcile cycle the firewall is pushed. Show
the rule landing:

```bash
docker exec -i clab-otternet-fw1 sshpass -p 'admin@123' ssh -o StrictHostKeyChecking=no \
  admin@localhost "show configuration security policies | display set | match <app>"
```

**5. The packet.** From the branch desktop, curl the VIP — and then curl one it
was not granted:

```bash
docker exec clab-otternet-branch-desktop curl -s -m 10 http://<granted vip>/     # answers
docker exec clab-otternet-branch-desktop curl -s -m 8 http://10.112.240.0/       # refused
```

The second one matters more than the first. It is what shows the firewall is the
control rather than an open path.

**6. Revoke it.** **Revoke access** in the portal, pick the grant, merge. The
rule, the address-book entry and the source prefix the grant opened are removed —
and a rule written by hand in the same zone pair is left alone, because removal
is keyed on provenance rather than on shape.

## Act two: a branch user asks for Grafana

Grafana is already running when the demo starts. It is `otternet-metrics`, a seeded application
that Infrahub delivered through Vidra like any other. Nobody at the branch can use it yet.

**1. Show the gate.** On the branch desktop, the toolbar bookmark **Grafana (needs access)** opens
`http://10.112.240.81/`, and nothing answers. The branch has no route to the VIP and no firewall
permit, and Grafana's own pod policy names no branch source.

**2. Ask.** In the portal, as `alice@otternet.lab`, request access to `otternet-metrics` from site
`branch`. It is the ordinary access request; Grafana needs nothing special.

**3. Read the proposed change.** The rule `branch → k8s-prod` on `junos-http`, the address-book
entry for `10.112.240.81`, `10.70.0.0/24` added to the application's allowed sources, and the
border leaf's `PL-DC-ADVERTISED-BRANCH` gaining the VIP. The Junos and EOS artifacts re-render
alongside.

**4. Merge, and sign in.** Once the reconciler has pushed fw1 and the leaf, reload the bookmark.
Grafana redirects to the same Dex sign-in page the portal uses. `alice` signs in and lands as a
**Viewer** in the OTTERNET folder.

**5. Show the dashboards, in this order:**

- **Organisation**: what Infrahub says the lab is, counted from the graph by the exporter.
- **Fabric telemetry**: streaming telemetry from every switch. Point at **Intended sessions not
  established**, which is empty, and say why that panel exists: Infrahub knows which sessions
  should be up, so it can say which ones are missing.
- **Monitoring is intent too.** In Infrahub, open the `fabric-core` profile and remove
  `bgp-neighbor-state` on a branch. The proposed change shows the collector's configuration losing
  its BGP subscriptions, and nothing else.

**6. Revoke.** Set the grant to `decommissioning` and merge. After the next reconcile the bookmark
stops answering again, and anyone already signed in loses the page with it.

A grant made **outside the portal** -- over the API or an SDK -- must also be added to the
`service_app_accesses` group. The generator runs only for members of its target group: the event
rule fires, and the run fails "Target … is not part of the group" with nothing visible on the
grant. The portal adds the membership itself.

## If you want the review step to bite

```bash
scripts/demo_break_isolation.sh            # then open the proposed change
scripts/demo_break_isolation.sh --revert
```

Adds one tenant's circuit to another tenant's L3VPN — the routing domain, not a
label — and `wan-service-consistency` fails naming both tenants while everything
else stays green. Nothing renders wrong, which is the point.

## The agent, through the MCP server

```bash
uv run invoke mcp                                   # account, then container
uv run python scripts/provision_mcp_agent.py --check
curl -s http://127.0.0.1:8001/health                # {"status":"healthy"}
```

Claude Code picks the server up from `.mcp.json` as `infrahub-lab` and asks you to
approve it the first time. It signs in as `mcp-agent`, which reads everything,
writes only on a branch — the server creates one per session, named
`mcp/session-<date>-<hex>` — and can open a proposed change. A write aimed at
`main` is refused by Infrahub, not by the prompt. `find_reachable` answers
"what depends on this": from `otternet-demo` it returns 24 connected objects,
its VIP block first.

**Do not claim the agent cannot merge.** On Infrahub 1.10.6 the
`CoreProposedChangeMerge` mutation does not check `merge_proposed_change`, and
the MCP server's `mutate_graphql` does not block it, so `mcp-agent` merged its
own proposed change when tested. Say instead that every change the agent makes
lands on a branch as a proposed change, and that merging is where the human
decides.

## Timings, measured

| Step | Wall clock |
| --- | --- |
| Portal request, start to proposed change | ~75s |
| Merge to the resource existing in Kubernetes | under a minute |
| Merge to the firewall carrying the rule | next reconcile cycle |
| Whole-fabric AVD regeneration (7 switches) | ~21s |
| Revocation, merge to the rule leaving the device | next reconcile cycle |
| Grafana grant, merge to Grafana answering the branch | ~2.3 minutes, one reconcile cycle |

Measured on this lab: a granted VIP answered `HTTP 200` from the branch desktop,
the seeded application's VIP and an unpermitted port on the granted one were both
refused, and after revoking, the same VIP stopped answering once the reconciler
pushed — two devices on one cycle, the firewall and the border leaf.

## What is already there

Only `otternet-demo` is seeded, and it is **not** reachable from the branch: an
application with no grant. It is a ready-made target if you would rather
demonstrate granting access to something that already exists than create an
application first — the generated **Request application access** item does that
in one step.

Anything else was requested through the portal and lives only in that
environment's database, so a rebuild removes it. An earlier runbook named
`otter-bakery` here; it was portal-created and does not survive a fresh
bootstrap. Request it again during rehearsal if the demo wants a second
ungranted application.

## Recovery

- **A request fails half way** — change the request reference and resubmit;
  `BranchCreate` is not idempotent, so the same reference dies on step 1. Delete
  the orphan branch afterwards.
- **`Unable to set context for account that doesn't exist`** — that user has
  never signed in to Infrahub. Run `scripts/provision_portal_accounts.py`.
- **The cluster resource never appears** — check the `VidraResource`, not the
  sync: a sync reports `Succeeded` over an empty or rejected set.
