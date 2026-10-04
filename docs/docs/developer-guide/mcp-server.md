---
title: The MCP server and the account it must not use
description: How infrahub-mcp runs beside Infrahub, why Claude Code acts only as alice, and the measured facts about her token and the mcp-agent role.
audience: developer
sidebar_position: 22
---

# The MCP server and the account it must not use

`infrahub-mcp` runs beside Infrahub in the compose stack (profile `mcp`, pinned
`registry.opsmill.io/opsmill/infrahub-mcp:v1.1.7`, `http://127.0.0.1:8001/mcp`),
and `.mcp.json` registers it for Claude Code. `uv run invoke mcp` provisions its
account and starts it, and `uv run invoke mcp-tokens` mints alice's token. The bootstrap runs `mcp`
after `tooling` and `mcp-tokens` after that, because alice's token is minted through Dex. `uv run invoke ready`
checks the account and token that `.mcp.json` uses (see [bootstrap](./bootstrap.md#what-a-finished-bootstrap-checks)).

## Claude Code acts as alice only

`.mcp.json` has one server, `infrahub-lab`, and it sends alice's API token
(`INFRAHUB_MCP_TOKEN_ALICE`). It has no `mcp-agent` entry and no second entry, so every tool
call from Claude Code in this repository is recorded as `alice`. The `mcp-agent` account, its role
and its token (`INFRAHUB_MCP_TOKEN`) are still provisioned: `scripts/demo_rehearsal.py` act five
calls the server as `mcp-agent` on purpose, to show what that role can and cannot do. Claude Code
does not read that token.

**Security consequence: an agent using alice's token holds her permissions, which are wider than
`mcp-agent`'s.** Her built-in roles include `merge_proposed_change`, `review_proposed_change`,
`manage_schema` and `manage_repositories` (see the measured roles below). An agent using her token
can therefore merge a proposed change or load a schema if it chooses to. What is and is not known
on Infrahub 1.10.6:

- Recorded earlier in this page: on 1.10.6 the code of `CoreProposedChangeMerge` does not consult
  `merge_proposed_change` (the rule is in `proposed_change/action_checker.py`). That is a reading of
  the source, see "Three measured facts about that role" below. It was not tested by merging.
- Not known: what the merge does when alice's token calls it. She holds the permission, so it does
  not stop her either way, and it was not measured whether the mutation checks anything else.
- Not known: whether `manage_schema` lets her token load a schema through the MCP server's tools.
  The MCP server exposes the GraphQL mutation tools, and Infrahub, not the server, decides.
- Nothing in the server or in Infrahub prevents an agent from merging as alice. The only
  control is the instruction in the skill
  [infrahub-requesting-app-access](https://github.com/opsmill/infrahub-network-field-day/blob/main/.agents/skills/infrahub-requesting-app-access/SKILL.md),
  which tells the agent never to merge. That is an instruction to the model, not a permission.
- No permission or role was changed to compensate. This repository does not narrow alice's roles.

**Clients never act as `agent`.** The server runs in
`INFRAHUB_MCP_AUTH_MODE=token-passthrough` and holds no Infrahub credential. Each
client sends `Authorization: Bearer <API token>` and the server forwards
it to Infrahub, so Infrahub attributes each action to the account that owns the token. The upstream
sidecar example uses `INFRAHUB_INITIAL_AGENT_TOKEN`, and here `agent` is a Super
Administrator **the task workers run as** — so it cannot be demoted without
breaking every generator, and it cannot be handed to a model without a back door
past review. `scripts/provision_mcp_agent.py` creates `mcp-agent` in the `Agents`
group with the `Agent Access` role, then signs in as it with its password and mints
an API token (Infrahub 1.10.6 mints a token only for the account that asks). Both
values are kept in `.env` as `INFRAHUB_MCP_PASSWORD` and `INFRAHUB_MCP_TOKEN`; the
password is used only by the script. An existing token that still authenticates as
`mcp-agent` is kept on re-run.
`tests/unit/test_mcp_service_contract.py` pins the mode, the absence of a server-side
credential, and the single `.mcp.json` entry that sends alice's token.

## Connecting Claude Code to the server

`.mcp.json` registers `infrahub-lab` over HTTP and sends alice's token
from the environment:

```json
{
  "mcpServers": {
    "infrahub-lab": {
      "type": "http",
      "url": "http://127.0.0.1:8001/mcp",
      "headers": { "Authorization": "Bearer ${INFRAHUB_MCP_TOKEN_ALICE}" }
    }
  }
}
```

The variable must be in the environment of the shell that starts `claude`:

```bash
set -a; source .env; set +a   # from the main checkout
claude
```

Source: [Infrahub MCP authentication](https://docs.infrahub.app/mcp/getting-started/authentication)
and [installation, HTTP with authentication](https://docs.infrahub.app/mcp/guides/installation#streamable-http-with-authentication).

What was measured on `infrahub-mcp` v1.1.7 against Infrahub 1.10.6:

- **The transport answers 200 without a token.** `initialize` and `tools/list` return
  200 with no header and with a wrong token. The documentation does not state this and
  an HTTP 401 was expected. Authentication is enforced when a tool calls Infrahub:
  with no header the tool result is an error, `Authentication required: no Infrahub API
  token in request header.`, and with a wrong token it is `Invalid token`. A check that
  only looks at the HTTP status code therefore cannot tell whether authentication works.
- **A tool call with the `mcp-agent` token runs as `mcp-agent`.** `query_graphql` with
  `AccountProfile { name { value } }` returned `mcp-agent`.
- **`claude mcp list` reports `Connected` even when the variable is unset**, because
  the connection check does not call a tool. It adds the warning `Missing environment
  variables: INFRAHUB_MCP_TOKEN_ALICE`. Tool calls then fail with the error above.
- The loopback binding (`127.0.0.1`) therefore still matters: anyone who can reach the
  port can open a session, and only the token decides what the session can do.

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

## Acting as a named user, such as alice

A person who asks an agent for access wants the request recorded as theirs, not as `mcp-agent`. Claude Code in this repository always does that. In
token-passthrough mode Infrahub records the account that owns the token, so a second token gives a
second identity. `scripts/provision_mcp_user_token.py --user alice` obtains that token:

1. It signs in as `alice@otternet.lab` through Dex, the same OIDC flow as
   `scripts/provision_portal_accounts.py`, and receives an Infrahub access token (a JWT).
2. With that JWT it calls `InfrahubAccountTokenCreate`. Infrahub 1.10.6 mints a token only for the
   account that asks, so the operator token cannot do this for her.
3. It writes the API token to the git-ignored `.env` of the main checkout as
   `INFRAHUB_MCP_TOKEN_ALICE` (the variable is `INFRAHUB_MCP_TOKEN_<USER>`, upper case, `-` becomes `_`).
   A token already in `.env` that still authenticates as the user is kept, so a re-run mints nothing.

The script prints the token only with `--show`. Run it yourself when you need to paste the token
somewhere: `uv run python scripts/provision_mcp_user_token.py --user alice --show`. `--check` reports
without minting. `uv run invoke mcp-tokens` runs it for every user the bootstrap serves (alice) after making sure
the portal accounts exist, and bootstrap runs that task after `tooling`. The Dex sign-in needs the Dex address (`OTTERNET_DEX_ADDRESS`, default
`http://10.90.0.11:32556`) to be reachable from where the script runs.

`.mcp.json` registers the one server, `infrahub-lab`, with the header
`Authorization: Bearer ${INFRAHUB_MCP_TOKEN_ALICE}`, so tools in Claude Code act as `alice`. Before
this change `.mcp.json` also had a `mcp-agent` entry and an `infrahub-lab-alice` entry; both are gone.
Source the
`.env` in the shell that starts `claude`, as described above, and restart Claude Code after the first
run so it reads the variable.

What was measured on `infrahub-mcp` v1.1.7 against Infrahub 1.10.6:

- **The JWT from the Dex sign-in is not accepted by the MCP server.** Sent as the Bearer token it
  returns `Invalid token`, although Infrahub's own GraphQL endpoint accepts the same JWT. Only an API
  token works, which is why the script mints one.
- **A tool call with her token runs as `alice`.** `query_graphql` with `AccountProfile { name { value } }`
  returned `alice`. The `Authorization` header is read per request, not per server: a client
  that sends a different token gets a different identity on the same port.
- **A grant she creates is attributed to her.** `ServiceAppAccessCreate` through `mutate_graphql` on the
  session branch succeeded. Reading the grant back, `updated_by` on its `name` and `requester` attributes
  showed `alice`. A grant created with the `mcp-agent` token showed `MCPagent` (the account's label). The
  attribute `status`, which the generator writes, showed `Agent`, the account the task workers run as.
  Node-level `created_by` metadata is not available in this schema (`node_metadata` is an unknown
  field), so the per-attribute `updated_by` is the evidence.
- **`requester` is a separate, free-text attribute.** A grant created with the token of `alice` and
  `requester: someone-else@otternet.lab` kept that value. Infrahub does not set or check it against the
  token, so the account that wrote the node and the requester it names can differ.
- **She can open a proposed change once `Requester Access` is attached to her group.** Before that,
  `propose_changes` was refused with
  `You do not have one of the following permissions: object:Core:ProposedChange:create:allow_default`.
  `mcp-agent` has that permission through its own role; the built-in `Infrahub Users` group did not.
  `scripts/provision_requester_access.py` (run by `uv run invoke mcp`) creates the role `Requester Access`
  and attaches it to `Infrahub Users`. The role holds two permissions: the object permission
  `object:Core:ProposedChange:create:allow_default` and the global permission `edit_default_branch`.
  After the role was attached, a scratch node written on her session branch and `propose_changes` with her
  token succeeded, and the change was recorded with the session branch as source and `main` as destination.
- **The global permission in the role changes nothing on 1.10.6.** The group already holds
  `edit_default_branch` through the built-in role `Proposed Change Reviewer`. The refusal named only the
  object permission, so the object permission is the part that changed the result. It was not measured
  with `Proposed Change Reviewer` removed, because that would change the permissions of every member. The
  role lists `edit_default_branch` so the grant does not depend on a built-in role an administrator may edit.
- **Her roles before and after.** `General Access`: `manage_repositories`, `manage_schema`,
  `merge_proposed_change`, view on every kind, and any action on branches other than the default branch.
  `Proposed Change Reviewer`: `edit_default_branch`, `review_proposed_change` and update on
  `CoreProposedChange`. `Requester Access`: the two permissions above, and nothing else.
  `Requester Access` widens the group by one action only: creating a proposed change on the default branch.
- **Her token carries more power than `mcp-agent`'s.** She holds `manage_schema` and
  `merge_proposed_change`, which `mcp-agent` does not. A model working with her token can load a schema
  or merge a branch. Treat `INFRAHUB_MCP_TOKEN_ALICE` as her credential: use it only for a request she
  made, and never merge. `Requester Access` does not add to this and does not remove from it: the
  permissions that give her that power come from the built-in roles.
- **A write to `main` as her was not tried.** From her roles, `any:allow_other` allows object writes on
  branches other than the default branch only, and the MCP server writes on the session branch.
- **What `CoreProposedChangeMerge` does for her was not measured.** She holds `merge_proposed_change`
  through `General Access`, so the permission does not stop her. Whether 1.10.6 checks it at all is not
  known from this measurement. Her token must not be used to merge.

### Claude Desktop

Claude Desktop reads `claude_desktop_config.json` and does not expand environment variables in it, so
the literal token has to be in that file. The file is outside this repository. Never copy it into the
repository or commit it. Get the token with the `--show` command above.

The documented form of that file starts local servers as a command, so the safest entry is a stdio
bridge, `mcp-remote`, which forwards to the HTTP endpoint:

```json
{
  "mcpServers": {
    "infrahub_lab_alice": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "http://127.0.0.1:8001/mcp",
        "--header",
        "Authorization:${AUTH}"
      ],
      "env": { "AUTH": "Bearer <alice-api-token>" }
    }
  }
}
```

`mcp-remote` documents that `--header` values may refer to environment variables, which keeps a space out of
the argument (a known problem on Windows). Node.js must be installed.

A direct entry with `"transport": "streamable-http"` and a `url` was not tried and is not expected to
work: Claude Desktop's remote servers are added as connectors and are reached from the vendor's
servers, which cannot reach `127.0.0.1`. That reading comes from the product's documentation and is
unverified here.

Verified here without Claude Desktop (not installed): `npx -y mcp-remote@0.14.3 http://127.0.0.1:8001/mcp
--header "Authorization:${AUTH}"` run over standard input returned `alice` for the `AccountProfile` query.
Not verified: that Claude Desktop starts this entry and lists the tools.

## Requesting application access through the MCP server

A person who asks an agent for access to an application is creating a `ServiceAppAccess` node on a
branch. The agent works as `alice` (her token), so the change lands on a session branch and a human merges
it. The step-by-step process is the project skill
[infrahub-requesting-app-access](https://github.com/opsmill/infrahub-network-field-day/blob/main/.agents/skills/infrahub-requesting-app-access/SKILL.md).
Two facts from a live run (act two, Grafana, first measured with the `mcp-agent` token) shape it. Both come from
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
