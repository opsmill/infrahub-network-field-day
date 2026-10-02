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
