---
name: infrahub-requesting-app-access
description: >-
  Requests access to an exposed application in this repository's Infrahub through the Infrahub MCP server — creates a ServiceAppAccess grant on a branch, opens the proposed change, waits for the generators, re-runs the checks and confirms the firewall, pod and fabric changes before a human merges.
  TRIGGER when: someone asks an agent to give a user, site or source network access to an application (for example Grafana), to grant, request or open access to a ServiceFabricApp, to run act two through the MCP server, or to debug a grant that built nothing or a proposed change with no border leaf diff.
  DO NOT TRIGGER when: revoking or decommissioning a grant, requesting access through the Backstage portal, only querying data (use infrahub-analyzing-data), or changing the schema, generators or triggers.
allowed-tools:
  - Read
  - Bash
  - Grep
argument-hint: "[application] [requester or source site]"
metadata:
  version: 1.0.0
  author: OpsMill
---

# Requesting application access with the Infrahub MCP server

## Overview

A grant is a `ServiceAppAccess` node. It names an application (a `ServiceFabricApp`), the requester, an
owner and where the traffic comes from. Creating it on a branch fires `generate-app-access`, which
builds the firewall rule and the address and service objects, adds the source to the application's
allowed sources and advertises the destination VIP toward the source zone. A proposed change then
carries those results before anyone merges.

The agent signs in to Infrahub as `mcp-agent`. That account writes only on a branch, which the MCP
server creates for the session (`mcp/session-<date>-<hex>`), and Infrahub refuses its writes to `main`.
A human merges the proposed change. Do not tell the requester the agent cannot merge: on Infrahub
1.10.6 the merge mutation does not check the permission, so the account can merge its own change.
Never do so. Sources:
[the MCP server](../../../docs/docs/developer-guide/mcp-server.md),
[act five of the demo runbook](../../../docs/docs/demo-runbook.md#act-five-the-agent-through-the-mcp-server).

The Infrahub MCP server is the published image `infrahub-mcp`, not code in this repository. The tool
names below (`search_nodes`, `get_nodes`, `node_upsert`, `mutate_graphql`, `propose_changes`) are the
ones used in a live run. If a tool is missing, say so and stop. Do not fall back to the admin or
`agent` token.

## Process

Follow the steps in order. Each ends with a result to state to the requester before moving on.

### 1. Identify the application and the source of the request

1. Find the application with `search_nodes` or `get_nodes` on kind `ServiceFabricApp`. Record its `id`,
   `name`, `status`, `exposed` and `vip_block`. If the application is not `active`, or not exposed,
   stop and report it. Whether a grant to such an application builds is not documented.
2. Find where the request comes from. The portal asks for a **Source Site**, for example
   `branch-office` (a `LocationSite`), and the generator derives the zone and source address from the
   site. A grant may instead name `source_zone` or `source_address`. If the requester gave no site,
   zone or address, ask. Do not guess one.
3. Find the owner. The portal passes `branch` as the owner. Confirm that node exists with `get_nodes`
   and do not invent another.
4. Find the requester. This is the requester's identity as the portal records it (for example
   `alice@otternet.lab`). Do not use the agent's own name.
5. Read existing grants for the same application and site with `search_nodes` on `ServiceAppAccess`.
   If one is `active`, report it. A second grant for the same source is not needed.

### 2. Check current reachability

State what is open before changing anything, so the result can be compared afterwards.

- Read the application's `allowed_source_prefixes` and its `vip_block` with `get_nodes`.
- Read the firewall's rules with `get_nodes` on `SecurityPolicyRule` for the application's zone, and
  look for a rule for the source.
- The MCP server cannot run a request from the requester's desktop. Reachability is therefore a fact
  the requester confirms, or one that `make -C lab verify` and the lab dashboards show. Say that it was
  not tested by the agent.

In the demo lab, before the grant, nothing answers at the Grafana VIP and the firewall has no permit,
and Grafana's pod policy names no branch source
([act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana)).

### 3. Create the grant

**`node_upsert` cannot create a grant.** It takes scalar values only, and a grant needs relationships.
Use `mutate_graphql` with a `ServiceAppAccessCreate` mutation, sent on the session branch the MCP
server created. The portal sends the same mutation (`create_grant` in
[`backstage/catalog/exposed-app-with-access.yaml`](../../../backstage/catalog/exposed-app-with-access.yaml)):

```graphql
mutation {
  ServiceAppAccessCreate(
    data: {
      name: { value: "grafana-alice" }
      requester: { value: "alice@otternet.lab" }
      justification: { value: "Dashboards for the branch office" }
      application: { id: "<ServiceFabricApp id from step 1>" }
      source_site: { hfid: ["branch-office"] }
      owner: { hfid: ["branch"] }
      member_of_groups: [{ hfid: ["service_app_accesses"] }]
    }
  ) {
    ok
    object { id }
  }
}
```

Rules for the fields:

- **Name.** Use a name that has not been used. The portal branch is named from it.
- **Required.** `name`, `requester`, `application` and `owner`. `justification` is optional but
  should say why. Leave `ports` empty so the ports come from the application's advertised services.
- **Source.** Send `source_site`. The generator derives the zone and source address from it. Send
  `source_zone` or `source_address` only when the requester gave one.
- **Group membership.** Send `member_of_groups: [{ hfid: ["service_app_accesses"] }]`. Infrahub refuses
  to run `generate-app-access` against a node that is not in that group, and fails
  `Target <id> is not part of the group <id>` with all validators green and no firewall rule in the
  proposed change. The portal sends the membership. A grant created without it is added to the group by
  the group rules in [`triggers.yml`](../../../triggers.yml) only once those rules are loaded on the
  stack. Whether they are loaded is not known from here, so send the membership either way
  ([service triggers](../../../docs/docs/developer-guide/service-triggers.md#a-grant-made-by-any-client-joins-its-generator-group)).
- **Do not write the generator's output.** `granted_rules` and `granted_source_prefixes` belong to
  the generator.
- **Never write to `main`.** The refusal `Writes to the default branch 'main' are not allowed` comes
  from the MCP server, and Infrahub refuses too.

Confirm the grant with `get_nodes` on the branch: `status` becomes `provisioning`, then `active` once
`granted_rules` holds a rule.

### 4. Open the proposed change

Call `propose_changes` for the session branch. It returns in well under a second. **The change opens
before the generators have finished**, so a first set of checks can run on a branch with no firewall
rule and no border leaf configuration. Do not read the first result as the answer.

### 5. Wait for the generators, then re-run the checks

1. Wait until the grant's `status` is `active` and its `granted_rules` holds a rule. The portal path
   takes 20 to 40 seconds for this.
2. Wait for the AVD generators that run in the proposed change's pipeline. The border leaf diff
   arrives last, about a minute after the change opens
   ([act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana)).
3. Re-run the checks with `mutate_graphql`:

   ```graphql
   mutation {
     CoreProposedChangeRunCheck(data: { id: "<proposed change id>", check_type: ALL }) {
       ok
     }
   }
   ```

   In the live run the border leaf EOS diff was missing until this mutation ran with `check_type: ALL`.
   The runbook names `ARTIFACT` for re-rendering only the artifacts. Which of the two is enough on every
   stack was not tested, so use `ALL`.
4. If the grant never reaches `active`, see "Failure modes" and do not re-run the checks repeatedly.

### 6. Confirm the results in the proposed change

Read the proposed change's diff and artifacts with `get_nodes`. All four must be present:

| What to confirm | Where | Expected for the Grafana demo |
| --- | --- | --- |
| A firewall rule | `SecurityPolicyRule` linked in the grant's `granted_rules`, and the re-rendered Junos artifact | `svc-<name>`, `branch` to `k8s-prod`, `junos-http`, with an address-book entry for the application's VIP block |
| The application's allowed sources | The application's Crossplane FabricApp artifact, `allowFrom` | The source prefix, for example `10.70.0.0/24`, is added |
| The border leaf EOS diff | The border leaf's configuration artifact | `PL-DC-ADVERTISED-BRANCH` gains `seq <n> permit <VIP block>` |
| The collector diff | The Telemetry Collector Configuration artifact | Present in the live run. Its content for a grant is not documented, so report what the diff shows |

Source: [act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana). If any row
is missing, report it. Do not call the request ready.

### 7. A human merges

Give the requester the proposed change link and say what it contains. `mcp-agent` cannot write to
`main`, and the agent must not merge its own proposed change. A human reviews and merges. Merging is
the approval.

### 8. Verify reachability after the merge

After the merge, the pod policy arrives through Vidra 40 to 70 seconds later, and the reconciler pushes
the border leaf and the firewall once the merged artifacts hold still (measured 41 and 55 seconds from
the merge). Grafana answered the branch desktop 75 seconds after the merge. Source:
[act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana).

- Read the `DeploymentState` of the border leaf and the firewall with `get_nodes`. Both should be
  `in_sync`.
- Ask the requester to reload the application. The agent cannot make the request from the requester's
  network.
- If it does not answer, check the reconciler log, `kubectl get vidraresource -A` and the firewall
  rule, in that order
  ([Recovery](../../../docs/docs/demo-runbook.md#recovery)).

### 9. Clean up

Delete the `mcp/session-*` branches the session created once the proposed change is merged or
abandoned. Use `infrahubctl branch delete <name>` from an operator account, because the MCP server's
own tools may not delete branches. That `mcp-agent` can delete them is not known. Do not delete a
branch that has an open proposed change. Do not create or delete a `CoreGeneratorInstance`
or a `ServiceAppAccess` on `main`.

## Failure modes

| Symptom | Cause | Action |
| --- | --- | --- |
| The grant stays `provisioning` or has no `granted_rules`, and the proposed change has no firewall rule, with green validators | The grant is not a member of `service_app_accesses`, so the generator run fails `Target ... is not part of the group` | Add the node to the group, or recreate the grant with `member_of_groups`. See step 3 |
| `node_upsert` refuses or drops the relationships | The tool takes scalar attribute values only | Use `mutate_graphql` and `ServiceAppAccessCreate`. See step 3 |
| The proposed change has the firewall rule but no border leaf EOS diff | `propose_changes` opened the change before the generators finished | Wait, then run `CoreProposedChangeRunCheck` with `check_type: ALL`. See step 5 |
| `Writes to the default branch 'main' are not allowed` or `PERMISSION_DENIED` | The write was aimed at `main` | Write on the session branch. This is intended |
| `Node must have at least one identifier (ID or HFID) to query it` on every proposed change | A deleted grant left its `CoreGeneratorInstance` behind | An operator deletes the instance. See [Recovery](../../../docs/docs/demo-runbook.md#recovery) |
| `INFRAHUB_MCP_PASSWORD is not set` from `provision_mcp_agent.py --check` | The script was run from a git worktree | Run it from the main checkout |
| The change merged but the application still does not answer | The reconciler, Vidra or the firewall has not converged | Step 8 |

## Related

- [The MCP server and the account it must not use](../../../docs/docs/developer-guide/mcp-server.md)
- [Services expand on their branch by event rule](../../../docs/docs/developer-guide/service-triggers.md)
- [AppAccessGenerator](../../../docs/docs/developer-guide/generators.md)
- [Demo runbook, act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana)
