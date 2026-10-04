---
title: The MCP server and the account it must not use
description: How infrahub-mcp runs beside Infrahub, why it signs in as mcp-agent, and the measured facts about its role.
audience: developer
sidebar_position: 22
---

# The MCP server and the account it must not use

`infrahub-mcp` runs beside Infrahub in the compose stack (profile `mcp`, pinned
`registry.opsmill.io/opsmill/infrahub-mcp:v1.1.7`, `http://127.0.0.1:8001/mcp`),
and `.mcp.json` registers it for Claude Code. `uv run invoke mcp` provisions its
account and starts it; the bootstrap does both after `tooling`.

**It signs in as `mcp-agent`, never as `agent`.** The upstream sidecar example
uses `INFRAHUB_INITIAL_AGENT_TOKEN`, and here `agent` is a Super Administrator
**the task workers run as** — so it cannot be demoted without breaking every
generator, and it cannot be handed to a model without a back door past review.
`scripts/provision_mcp_agent.py` creates `mcp-agent` in the `Agents` group with
the `Agent Access` role, and keeps its password in `.env`.
`tests/unit/test_mcp_service_contract.py` pins both.

Three measured facts about that role:

- **Opening a proposed change needs `edit_default_branch`.** A proposed change is
  stored on `main`, and without the global permission the request is refused
  before object permissions are consulted. With it, object permissions still
  narrow the rest: a write to any other kind on `main` is refused.
- **Nothing stops it merging its own proposed change.** On 1.10.6
  `CoreProposedChangeMerge` never checks `merge_proposed_change` — the rule is in
  `proposed_change/action_checker.py` and that mutation does not consult it — and
  `infrahub-mcp` does not block the mutation. Approving, merging a branch and
  loading a schema are refused.
- **PyPI's `infrahub-mcp` 1.1.7 does not start.** It resolves against fastmcp 4 and
  mcp 2 and fails at import with `cannot import name 'McpError' from 'mcp'`. The
  published image carries the versions it was built with.

`invoke stop` and `invoke destroy` pass `--profile '*'`. Without it `down` skips
profiled services, and this one, being on the compose network, then holds that
network open so it cannot be removed.

## Requesting application access through the MCP server

A person who asks an agent for access to an application is creating a `ServiceAppAccess` node on a
branch. The agent works as `mcp-agent`, so the change lands on a session branch and a human merges
it. The step-by-step process is the project skill
[infrahub-requesting-app-access](https://github.com/opsmill/infrahub-network-field-day/blob/main/.agents/skills/infrahub-requesting-app-access/SKILL.md).
Two facts from a live run (act two, Grafana, requested as `mcp-agent`) shape it. Both come from
how `infrahub-mcp` works. The server is the published image
`registry.opsmill.io/opsmill/infrahub-mcp:v1.1.7`, not code in this repository, so this repository
cannot change them and documents the way around each.

- **`node_upsert` cannot create a `ServiceAppAccess`.** The tool takes scalar attribute values only.
  A grant needs two relationships, `application` and `owner`, and `source_site` or another source
  peer as well. Create the grant with the `mutate_graphql` tool and a `ServiceAppAccessCreate`
  mutation on the session branch. The portal sends the same mutation, as the `create_grant` step in
  [`backstage/catalog/exposed-app-with-access.yaml`](https://github.com/opsmill/infrahub-network-field-day/blob/main/backstage/catalog/exposed-app-with-access.yaml):

  ```graphql
  mutation {
    ServiceAppAccessCreate(
      data: {
        name: { value: "grafana-agent" }
        requester: { value: "alice@otternet.lab" }
        justification: { value: "Dashboards for the branch office" }
        application: { id: "<ServiceFabricApp id>" }
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

  `member_of_groups` is not required since the group rules in `triggers.yml` add the membership
  (see [service triggers](./service-triggers.md#a-grant-made-by-any-client-joins-its-generator-group)),
  but sending it does no harm and is what the portal does. On a stack that has not yet loaded those
  rules (`invoke load` loads `triggers.yml`), a grant without the membership is never built.

- **`propose_changes` opens the proposed change before the generators finish.** The proposed change
  is created in well under a second, before the generators the grant triggers
  (`generate-app-access`, then the AVD generators) have finished. The first set of checks therefore
  ran against a branch that did not yet hold the border leaf configuration, and the proposed change showed no EOS diff for the border
  leaf. Re-running the checks after the generators finished fixed it: the `CoreProposedChangeRunCheck`
  mutation with `check_type: ALL`, sent through `mutate_graphql`. Which check types the mutation
  accepts other than `ALL` was not tested.

How long the generators take on a given stack is not recorded here. Measured elsewhere in this
documentation, a generator pass is 15 to 21 seconds, and artifacts settle in about a minute after a
merge ([AGENTS.md](https://github.com/opsmill/infrahub-network-field-day/blob/main/AGENTS.md)).
