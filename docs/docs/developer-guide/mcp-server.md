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

**What an agent holding alice's token can and cannot do.** `Infrahub Users` holds one role,
`Requester Access`, set by `scripts/provision_requester_access.py`. The built-in roles
`General Access` and `Proposed Change Reviewer` are detached from the group (not deleted, and no other group
is changed). The measurements below were taken on Infrahub 1.10.6 with alice's own token, before and after
the change, with scratch objects on scratch branches that were deleted afterwards.

| Action with alice's token | Before (built-in roles) | After (`Requester Access` only) |
| --- | --- | --- |
| View nodes of any kind | Allowed | Allowed |
| Create a branch | Allowed | Allowed |
| Write a `BuiltinTag` on her branch | Allowed | Refused: `object:Builtin:Tag:create:allow_other` |
| Write a `Service` kind on her branch | Not measured | Allowed (a `ServiceApplicationDefinition`) |
| Open a proposed change | Allowed | Allowed |
| Write a `BuiltinTag` on `main` | Refused: `object:Builtin:Tag:create:allow_default` | Refused: the same permission |
| Merge her own proposed change with `CoreProposedChangeMerge` | **Succeeded** (permission held) | **Succeeded** (permission not held) |

- **Merging is not blocked by the role change.** After `General Access` (which holds `merge_proposed_change`)
  was detached, alice's token still merged a scratch proposed change into `main`, and its scratch node
  appeared on `main`. This agrees with the reading of the source recorded below: `CoreProposedChangeMerge`
  does not consult `merge_proposed_change` on 1.10.6. No permission in this repository can stop alice, or
  any account that can open a proposed change, from merging it.
- **What could stop a merge is not known.** It was not measured whether the MCP server's `mutate_graphql`
  tool refuses `CoreProposedChangeMerge`; the `mcp-agent` notes in `scripts/provision_mcp_agent.py` say it does
  not. The remaining control is the instruction in the skill
  [infrahub-requesting-app-access](https://github.com/opsmill/infrahub-network-field-day/blob/main/.agents/skills/infrahub-requesting-app-access/SKILL.md),
  which tells the agent never to merge. That is an instruction to the model, not a permission. A guarantee
  needs an Infrahub fix, or a proxy in front of the server that rejects the mutation; neither exists here.
- **A write to `main` is refused.** Her only write permission on objects is decision 4 (branches other than
  the default branch), restricted to the `Service` namespace. The one exception is the proposed change, which
  is stored on `main`.
- **Other actions are no longer granted.** Review, `manage_schema` and `manage_repositories` came from the
  detached roles. Whether a given tool call would have used them was not measured; the absence of the grants
  is read from the role definitions, and a schema load or an approval by her token was not tried.
- **A grant of access through `ServiceAppAccessCreate` with `member_of_groups` was not measured after the
  change** because the lab held no `ServiceFabricApp` at the time (the demo creates it in act one). With a
  non-existent application the mutation passed the permission check and failed on the missing application,
  while a `BuiltinTag` write was refused for permission. Re-run act two to confirm it end to end.
- **A write to any kind outside the `Service` namespace through alice's token is now
  refused.** The portal is not affected: it writes with its own `backstage-portal` account and attributes the
  write to the signed-in user through the mutation `context`.

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
- **Restarting the container keeps alice's token valid and ends open sessions.** Measured on 2026-10-05 with
  `docker restart infrahub-infrahub-mcp-1`: `/health` answered again after about 4 s, a new session with
  `INFRAHUB_MCP_TOKEN_ALICE` returned `alice`, and a request that still carried the session id of before the restart
  was answered `404` with `Session not found`. The token lives in Infrahub, not in the server. That Claude Code starts a
  new session after that answer, as the MCP specification says a client must, was not tested; if tool calls keep failing,
  restart Claude Code from a shell that has loaded `.env`.

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
- **She can open a proposed change through `Requester Access`.** Before the role existed, `propose_changes`
  was refused with
  `You do not have one of the following permissions: object:Core:ProposedChange:create:allow_default`.
  `mcp-agent` has that permission through its own role; the built-in `Infrahub Users` group did not.
  `scripts/provision_requester_access.py` (run by `uv run invoke mcp`) creates the role `Requester Access`,
  attaches it to `Infrahub Users` and detaches `General Access` and `Proposed Change Reviewer` from that
  group. `--check` reports a problem if a built-in role is attached again or if the role holds any other
  permission. The role holds four permissions:
  - `view` on every namespace and kind, everywhere, so she can read the data;
  - `any` on every kind in the `Service` namespace, on branches other than the default branch only;
  - the object permission `object:Core:ProposedChange:create:allow_default`;
  - the global permission `edit_default_branch`, which admits a request to the default branch at all.
- **The global permission `edit_default_branch` was held through the built-in role `Proposed Change Reviewer`
  before.** That role is now detached, and opening a proposed change still works with the permission held
  in `Requester Access`, so the measurement after the change is the evidence that it is needed or at least
  sufficient. It was not measured with the permission removed and the object permission kept.
- **Her roles before.** `General Access`: `manage_repositories`, `manage_schema`, `merge_proposed_change`,
  view on every kind, and any action on branches other than the default branch. `Proposed Change Reviewer`:
  `edit_default_branch`, `review_proposed_change` and update on `CoreProposedChange`. After: `Requester
  Access` only.
- **Creating a branch needs no permission that appears in the role.** She created a branch with only
  `Requester Access`. Which Infrahub check allows it was not looked up.
- **Her token is a credential for requests she made.** It can no longer write most kinds or load a schema through her
  roles, and it can still merge (see above). Use `INFRAHUB_MCP_TOKEN_ALICE` only for a request she made,
  and never merge.
- **A fresh Infrahub install may attach the built-in roles again.** Whether Infrahub re-attaches them on a
  restart or an upgrade is not known. `uv run invoke ready` runs `provision_requester_access.py --check`, which
  reports it, and `uv run invoke mcp` repairs it.

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

- **`propose_changes` opens the proposed change while the grant is still being built, and the
  border leaf configuration was missing from it.** Measured on 2026-10-05 with the grant created
  through the MCP server as `alice`. The proposed change is created about 0.6 seconds after the grant.
  The grant's own generator (`generate-app-access`) is still writing, and its last write, the
  `permit <vip>` sequence in the border leaf's `avd_custom_hostvars`, lands about 5 seconds after the
  change opens. Infrahub chooses the generators and artifact checks of a proposed change from the
  branch's differences at the moment the pipeline starts, so that pipeline ran only
  `generate-app-access` and the telemetry collector artifact check. Nothing in `triggers.yml` ran
  `generate-avd-device-hostvar` on the branch, so no border leaf hostvars or structured config were
  written and the proposed change showed the firewall rule and no EOS diff for 300 seconds
  (the longest wait). A second `CoreProposedChangeRunCheck` with `check_type: ALL` selected all of the
  generators, and the diff arrived about 90 seconds later. The portal avoids this because its template
  waits for the grant's generator and then runs the two AVD generators on the branch before it opens
  the proposed change.
  Fix: the rule `trigger-avd-hostvar-generator-update-custom-hostvars` in `triggers.yml` runs
  `generate-avd-device-hostvar` for a switch whose `avd_custom_hostvars` changed on a branch, and
  that run fires the existing structured config rule. With the rule loaded, the border leaf diff was
  in the proposed change 42 seconds after `propose_changes`, with no second run of the checks. The
  checks must be re-run with `CoreProposedChangeRunCheck` and `check_type: ALL` before the
  proposed change is read or merged (next item).

- **The proposed change that `propose_changes` opens holds 9 validators, and a merge at 9 is not safe.**
  Measured on 2026-10-05 in two runs as `alice` with the hostvar rule loaded. The nine are Data Integrity,
  Schema Integrity, the five `Check:` validators, the Generator Validator `generate-app-access` and the
  Artifact Validator `telemetry_collector_config`. They concluded green 27 to 33 seconds after the change
  opened. The count then stayed at 9 for 240 seconds while the border leaf diff appeared at 38 seconds,
  because Infrahub selects the validators when the change opens and nothing repeats that selection when the
  AVD generators write to the branch. Missing at 9 are the Artifact Validators for artifacts that did change
  (`avd_eos_configuration`, `avd_device_documentation`, `junos_config`, and `crossplane_fabric_app` when the
  allowed sources of the application changed) and the Generator Validators `generate-avd-device-hostvar` and
  `generate-avd-device-structured-config`. Nothing had judged the border leaf configuration or the firewall
  configuration that the merge would deploy. `CoreProposedChangeRunCheck` with `check_type: ALL` raised the count
  to 24 in 56 seconds, all green, the same 24 validators the portal's proposed change holds.
  `check_type: ARTIFACT` raised it to 17 in 10 seconds in one run on a second grant for the same source (the
  Crossplane artifact did not change in that run) and added no generator validator.
  The condition to wait for before a human merges: after the `ALL` re-run, every validator is `completed`, the
  count is 24 and has not changed on two reads, and every conclusion is `success`. The portal's template avoids
  all of this because it opens the proposed change only after its own AVD generator run. No change to
  `triggers.yml` or to a generator was made for this: a rule can run a generator or write a node, and none was
  found that starts a proposed change's checks again (not exhaustively searched).

How long the generators take on a given stack is not recorded here. Measured elsewhere in this
documentation, a generator pass is 15 to 21 seconds, and artifacts settle in about a minute after a
merge ([AGENTS.md](https://github.com/opsmill/infrahub-network-field-day/blob/main/AGENTS.md)).
