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
- **A user with no Infrahub account cannot request anything.** The account is
  created by their first Infrahub sign-in, so a fresh environment fails the first
  request *after* creating its branch. `invoke tooling` provisions them; the
  `--check` above tells you if any are missing.
- **Stale branches in the selector** are the first thing on screen in Infrahub
  and invite the one question you do not want.

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

## If you want the review step to bite

```bash
scripts/demo_break_isolation.sh            # then open the proposed change
scripts/demo_break_isolation.sh --revert
```

Adds one tenant's circuit to another tenant's L3VPN — the routing domain, not a
label — and `wan-service-consistency` fails naming both tenants while everything
else stays green. Nothing renders wrong, which is the point.

## Timings, measured

| Step | Wall clock |
| --- | --- |
| Portal request, start to proposed change | ~75s |
| Merge to the resource existing in Kubernetes | under a minute |
| Merge to the firewall carrying the rule | next reconcile cycle |
| Whole-fabric AVD regeneration (7 switches) | ~21s |

## Recovery

- **A request fails half way** — change the request reference and resubmit;
  `BranchCreate` is not idempotent, so the same reference dies on step 1. Delete
  the orphan branch afterwards.
- **`Unable to set context for account that doesn't exist`** — that user has
  never signed in to Infrahub. Run `scripts/provision_portal_accounts.py`.
- **The cluster resource never appears** — check the `VidraResource`, not the
  sync: a sync reports `Succeeded` over an empty or rejected set.
