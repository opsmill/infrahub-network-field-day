#!/usr/bin/env python3
"""Give the MCP server its own least-privilege Infrahub account.

WHY NOT THE `agent` ACCOUNT. The MCP docs' sidecar example authenticates with
`INFRAHUB_INITIAL_AGENT_TOKEN`, and here that token belongs to `agent`, which is a
Super Administrator -- and which the task workers run as, so every generator,
transform and check depends on it. Handing it to a model would give the model a
back door past the review gate: write straight to `main`, load a schema, merge.
Demoting it instead would break the pipeline. So the MCP server gets `mcp-agent`.

WHAT `mcp-agent` MAY DO, and each line was measured against 1.10.6:

- read everything;
- write anything, but only on a branch -- a write on `main` is refused naming
  `object:<Kind>:create:allow_default`;
- open a proposed change. A proposed change is stored on `main`, so this needs
  two grants that look broader than they are: the global `edit_default_branch`,
  which admits the request to the default branch at all, and `create` on
  `CoreProposedChange` there. Object permissions still narrow everything else,
  which is why the write on `main` above is refused with both in place.

What it may NOT do: approve, merge a branch, change the schema, or delete or
update a proposed change.

ONE GAP THIS CANNOT CLOSE. On 1.10.6 the `CoreProposedChangeMerge` mutation never
checks `merge_proposed_change` -- the rule exists in `action_checker.py` and that
mutation does not consult it -- so any account that can open a proposed change can
also merge it, and `infrahub-mcp`'s `mutate_graphql` does not block that mutation.
Measured: this account merged its own proposed change. Until upstream fixes it, the
review gate against an agent is a convention, not an enforcement.

The password lives in `.env` (gitignored) as `INFRAHUB_MCP_PASSWORD`, which is where
docker compose reads it from; one is generated on first run.

    uv run python scripts/provision_mcp_agent.py
    uv run python scripts/provision_mcp_agent.py --check   # report only
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.exceptions import GraphQLError

from solution_arista_avd import envfile
from solution_arista_avd.envfile import read_env, upsert_env

REPO = Path(__file__).resolve().parents[1]
# The MAIN checkout's `.env`, not one beside this file: from a git worktree that
# would be a file docker compose never reads. See `envfile.main_checkout`.
ENV_FILE = envfile.env_file(REPO)

ACCOUNT = "mcp-agent"
GROUP = "Agents"
ROLE = "Agent Access"
PASSWORD_VAR = "INFRAHUB_MCP_PASSWORD"  # noqa: S105 -- the variable's name, not a password

# decision values: 6 = allow everywhere, 4 = allow on branches other than the default
OBJECT_PERMISSIONS = [
    {"namespace": "*", "name": "*", "action": "view", "decision": 6},
    {"namespace": "*", "name": "*", "action": "any", "decision": 4},
    {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 6},
]
GLOBAL_PERMISSIONS = [
    {"action": "edit_default_branch", "decision": 6},
]


def read_env_password() -> str:
    return read_env(ENV_FILE, PASSWORD_VAR)


def write_env_password(password: str) -> None:
    upsert_env(
        ENV_FILE,
        PASSWORD_VAR,
        password,
        "The MCP server's Infrahub account, written by scripts/provision_mcp_agent.py.",
    )


def admin_client() -> InfrahubClientSync:
    """The provisioning client, with ONE credential.

    `tasks.py` sets INFRAHUB_USERNAME and INFRAHUB_PASSWORD as defaults, and the
    shell usually carries INFRAHUB_API_TOKEN too, so under `invoke` a bare
    `InfrahubClientSync()` sees both and refuses to choose.
    """
    address = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
    token = os.getenv("INFRAHUB_API_TOKEN")
    if token:
        return InfrahubClientSync(config=Config(address=address, api_token=token))
    return InfrahubClientSync(
        config=Config(
            address=address,
            username=os.getenv("INFRAHUB_USERNAME", "admin"),
            password=os.getenv("INFRAHUB_PASSWORD", "infrahub"),
        )
    )


def provision(client: InfrahubClientSync, password: str) -> None:
    permissions = []
    for data in OBJECT_PERMISSIONS:
        node = client.create("CoreObjectPermission", **data)
        node.save(allow_upsert=True)
        permissions.append(node)
    for data in GLOBAL_PERMISSIONS:
        node = client.create("CoreGlobalPermission", **data)
        node.save(allow_upsert=True)
        permissions.append(node)

    role = client.create("CoreAccountRole", name=ROLE, permissions=permissions)
    role.save(allow_upsert=True)

    account = client.create("CoreAccount", name=ACCOUNT, label="MCP agent", account_type="User", password=password)
    account.save(allow_upsert=True)

    group = client.create("CoreAccountGroup", name=GROUP, roles=[role], members=[account])
    group.save(allow_upsert=True)


def check(client: InfrahubClientSync, password: str) -> list[str]:
    problems = []
    account = client.get("CoreAccount", name__value=ACCOUNT, raise_when_missing=False, include=["member_of_groups"])
    if account is None:
        return [f"{ACCOUNT} does not exist"]
    account.member_of_groups.fetch()
    names = sorted(group.display_label or "" for group in account.member_of_groups.peers)
    if GROUP not in names:
        problems.append(f"{ACCOUNT} is not in {GROUP!r} (groups: {names or 'none'})")
    if "Super Administrators" in names:
        problems.append(f"{ACCOUNT} is a Super Administrator, which defeats the point of it")
    if not password:
        problems.append(f"{PASSWORD_VAR} is not set in {ENV_FILE}")
        return problems
    try:
        own = InfrahubClientSync(config=Config(address=client.config.address, username=ACCOUNT, password=password))
        own.execute_graphql("query { AccountProfile { name { value } } }")
    except (GraphQLError, Exception) as exc:  # noqa: BLE001 -- any failure here means the container cannot sign in
        problems.append(f"{ACCOUNT} cannot sign in with the password in {ENV_FILE}: {exc}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report only; change nothing")
    args = parser.parse_args()

    client = admin_client()
    password = read_env_password()

    if not args.check:
        if not password:
            password = secrets.token_urlsafe(24)
            write_env_password(password)
            print(f"Generated {PASSWORD_VAR} in {ENV_FILE}")
        provision(client, password)
        print(f"{ACCOUNT} is in {GROUP!r} with role {ROLE!r}")

    problems = check(client, password)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(f"{ACCOUNT} signs in and holds only the {ROLE!r} role.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
