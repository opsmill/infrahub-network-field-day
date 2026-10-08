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

The agent reaches Infrahub as `alice`: the MCP server forwards the API token the client sends in the `Authorization: Bearer` header (`INFRAHUB_MCP_TOKEN_ALICE` in `.env`), and `.mcp.json` has no other server. Her token holds `merge_proposed_change`, `review_proposed_change`, `manage_schema` and `manage_repositories` through her built-in roles, so nothing in Infrahub stops the agent from merging or loading a schema. **Never merge a proposed change, never review or approve one, and never load or change a schema.** Write only on the session branch the MCP server creates (`mcp/session-<date>-<hex>`).
A human merges the proposed change. Do not tell the requester the agent cannot merge: it can, and the only control is this instruction. Sources:
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
2. Wait for the AVD generators. The rule `trigger-avd-hostvar-generator-update-custom-hostvars` in
   `triggers.yml` runs `generate-avd-device-hostvar` for the border leaf once the grant's generator has
   written its custom hostvars, and the structured config follows. The border leaf diff arrived 42 seconds
   after `propose_changes` in a run on 2026-10-05 with that rule loaded, and 40 seconds after it on a stack whose bootstrap had loaded `triggers.yml` by itself. Without the rule, nothing ran the AVD
   generators on the branch, and the diff had not arrived 300 seconds after `propose_changes`; it arrived
   about 90 seconds after the re-run in the next step
   ([act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana),
   [the cause](../../../docs/docs/developer-guide/mcp-server.md#requesting-application-access-through-the-mcp-server)).
3. Re-run the checks with `mutate_graphql`. **Do this even when the border leaf diff is already present.**

   ```graphql
   mutation {
     CoreProposedChangeRunCheck(data: { id: "<proposed change id>", check_type: ALL }) {
       ok
     }
   }
   ```

   Measured on 2026-10-05 (two runs, rule loaded): the proposed change that `propose_changes` opens holds
   **9 validators** (Data Integrity, Schema Integrity, five `Check:` validators, the Generator Validator
   `generate-app-access` and the Artifact Validator `telemetry_collector_config`). All 9 concluded green
   within 27 to 33 seconds, and the count stayed at 9 for the 240 seconds that were watched, although the
   border leaf diff had appeared at 38 seconds. Infrahub chose the validators when the change opened, before
   the AVD generators had written anything, and nothing starts that choice again. A merge at 9 validators is
   **not safe**: no validator has judged the artifacts that changed afterwards (`avd_eos_configuration`,
   `avd_device_documentation`, `junos_config` and, when the application's allowed sources changed,
   `crossplane_fabric_app`), nor the generators `generate-avd-device-hostvar` and
   `generate-avd-device-structured-config` that ran on the branch.
   `check_type: ALL` raised the count to **24** in 56 seconds, the same 24 that the portal's proposed change
   holds. `check_type: ARTIFACT`, measured once on a second grant for the same source (so the application's
   Crossplane artifact did not change), raised it to 17 in 10 seconds: eight more artifact validators, and none
   of the six generator validators that `ALL` adds (`generate-avd-device-hostvar`,
   `generate-avd-device-structured-config`, `generate-fabric-app`, `generate-fabric-peering`,
   `generate-network-segment`, `generate-tenant-onboarding`). Use `ALL`.
4. **Wait for this exact condition before telling a human the change can be merged**, measured after the
   `ALL` re-run was started:
   - every validator of the proposed change has `state` `completed`, and the number of validators has not
     changed on two reads 10 seconds apart;
   - the count is 24 (the portal's count; it grows if the repository gains a generator, artifact definition or
     check, so compare with a portal change if unsure); and
   - every validator's `conclusion` is `success`, including `Artifact Validator: avd_eos_configuration`,
     `Artifact Validator: junos_config`, `Generator Validator: generate-avd-device-hostvar` and
     `Generator Validator: generate-avd-device-structured-config`.

   If the count is below 24, or any of those four is missing, the checks have not judged the final branch:
   run the mutation again and wait again. Do not report the change as ready.
5. If the grant never reaches `active`, see "Failure modes" and do not re-run the checks repeatedly.

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
the approval. The human who merges signs in to the Infrahub UI as the local account `alex`
(its password is in `.env` as `INFRAHUB_NETWORK_ADMIN_PASSWORD`; never read, print or use it as the agent).
That account holds `merge_proposed_change` and `review_proposed_change`; no agent identity does.

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
| The proposed change has the firewall rule but no border leaf EOS diff | The stack lacks the rule `trigger-avd-hostvar-generator-update-custom-hostvars`, so no AVD generator ran on the branch after the grant's generator wrote the border leaf's hostvars | Load `triggers.yml` (`invoke load`), then run `CoreProposedChangeRunCheck` with `check_type: ALL`. See step 5 |
| `Writes to the default branch 'main' are not allowed` or `PERMISSION_DENIED` | The write was aimed at `main` | Write on the session branch. This is intended |
| `Node must have at least one identifier (ID or HFID) to query it` on every proposed change | A deleted grant left its `CoreGeneratorInstance` behind | An operator deletes the instance. See [Recovery](../../../docs/docs/demo-runbook.md#recovery) |
| Every tool says `Authentication required: no Infrahub API token in request header.` or `Invalid token` | `INFRAHUB_MCP_TOKEN_ALICE` was not in the environment of the shell that started Claude Code, or the token was re-minted | Run `uv run invoke mcp`, source `.env`, restart Claude Code. `claude mcp list` still shows `Connected` |
| `INFRAHUB_MCP_PASSWORD is not set` from `provision_mcp_agent.py --check` | The script was run from a git worktree | Run it from the main checkout |
| The change merged but the application still does not answer | The reconciler, Vidra or the firewall has not converged | Step 8 |

## Acting as alice

Every tool call from Claude Code here acts as `alice`: `.mcp.json` has one server, `otternet-infrahub`, and it sends her API token
(`INFRAHUB_MCP_TOKEN_ALICE`, minted by `scripts/provision_mcp_user_token.py --user alice`). Measured on
Infrahub 1.10.6: the grant's attributes then show `updated_by: alice`, and `requester` stays a separate
free-text value. Her group `Infrahub Users` holds one role, `Requester Access`, set by
`scripts/provision_requester_access.py` (run by `uv run invoke mcp`). The role allows: view of every kind,
any action on `Service` kinds on a branch other than `main`, and creating a proposed change. It does not
allow writing to `main`, other kinds on a branch, approving a change, loading a schema or managing
repositories. If a write to a `Service` kind or `propose_changes` is refused naming a permission, run
that script. Do not retry on `main`.

**Her token can still merge.** On Infrahub 1.10.6 `CoreProposedChangeMerge` succeeded with her token after
`merge_proposed_change` was removed from her group, so no permission stops a merge. Never merge: a person
reviews and merges. That is an instruction to you, not an enforced limit. Details:
[acting as a named user](../../../docs/docs/developer-guide/mcp-server.md#acting-as-a-named-user-such-as-alice).

## Related

- [The MCP server and the account it must not use](../../../docs/docs/developer-guide/mcp-server.md)
- [Services expand on their branch by event rule](../../../docs/docs/developer-guide/service-triggers.md)
- [AppAccessGenerator](../../../docs/docs/developer-guide/generators.md)
- [Demo runbook, act two](../../../docs/docs/demo-runbook.md#act-two-a-branch-user-asks-for-grafana)
