#!/usr/bin/env python3
"""Give the network team a local Infrahub account that is neither Dex nor an administrator.

WHY THIS EXISTS. A person who signs in through Dex lands in `Infrahub Users`, whose only role,
`Requester Access`, writes Service kinds on a branch and opens a proposed change. A network
engineer who must change devices, interfaces, links, addresses or locations, and who must
merge the proposed change, needs more. The built-in answer is the `admin` account, which is a
Super Administrator. This script creates the middle: `alex`, an account with a local
password (no Dex), in one group, `Network Admins`, with one role, `Network Admin Access`.

WHAT `alex` MAY DO (each line measured on Infrahub 1.10.6; see
docs/docs/developer-guide/mcp-server.md, section "The network-admin account"):

- view every kind, everywhere;
- any action on every kind on a branch other than the default branch (decision 4), so network
  data can be edited on a branch;
- create a proposed change, which is stored on the default branch
  (`object:Core:ProposedChange:create:allow_default`), and the global `edit_default_branch`,
  which admits the request to the default branch at all;
- the global `merge_branch`, `merge_proposed_change` and `review_proposed_change`.

WHAT IT MAY NOT DO: `manage_schema`, `manage_repositories`, `manage_accounts`,
`manage_permissions`, `super_admin`, and any write on the default branch other than the
proposed-change merge. It is not in `Super Administrators` and not in `Infrahub Users`.

WHAT THIS CANNOT BLOCK. On 1.10.6 `CoreProposedChangeMerge` does not check
`merge_proposed_change`, so the permission documents who is meant to merge; it does not stop
another account that can open a proposed change. Nor does Infrahub stop this account from
approving and merging a change it opened itself.

THE PASSWORD is generated the first time (random, 24 bytes, URL-safe) and kept in the
gitignored `.env` as INFRAHUB_NETWORK_ADMIN_PASSWORD. It is never printed. A password that
still signs in is kept, so a re-run changes nothing. No API token is minted: the account is for
signing in to the UI, and the checks sign in with the password.

    uv run python scripts/provision_network_admin.py
    uv run python scripts/provision_network_admin.py --check   # report only; exit 1 on a problem
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

from infrahub_sdk import Config, InfrahubClientSync

from solution_arista_avd import envfile
from solution_arista_avd.envfile import read_env, upsert_env

REPO = Path(__file__).resolve().parents[1]
# The MAIN checkout's `.env`, not one beside this file: see `envfile.main_checkout`.
ENV_FILE = envfile.env_file(REPO)

ACCOUNT = "alex"
LABEL = "Alex"
GROUP = "Network Admins"
ROLE = "Network Admin Access"
PASSWORD_VAR = "INFRAHUB_NETWORK_ADMIN_PASSWORD"  # noqa: S105 -- the variable's name, not a password

# decision values: 2 = allow on the default branch only, 4 = allow on branches other than
# the default, 6 = allow everywhere
OBJECT_PERMISSIONS = [
    {"namespace": "*", "name": "*", "action": "view", "decision": 6},
    {"namespace": "*", "name": "*", "action": "any", "decision": 4},
    {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
]
GLOBAL_PERMISSIONS = [
    {"action": "edit_default_branch", "decision": 6},
    {"action": "merge_branch", "decision": 6},
    {"action": "merge_proposed_change", "decision": 6},
    {"action": "review_proposed_change", "decision": 6},
]

# Groups the account must never be in.
FORBIDDEN_GROUPS = ("Super Administrators", "Infrahub Users")

# Actions this role must never carry, whatever else changes. Pinned by
# tests/unit/test_network_admin_contract.py.
FORBIDDEN_ACTIONS = (
    "manage_schema",
    "manage_repositories",
    "manage_accounts",
    "manage_permissions",
    "super_admin",
)


def _address() -> str:
    return os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")


def admin_client() -> InfrahubClientSync:
    """The provisioning client, with ONE credential (see provision_mcp_agent.admin_client)."""
    token = os.getenv("INFRAHUB_API_TOKEN")
    if token:
        return InfrahubClientSync(config=Config(address=_address(), api_token=token))
    return InfrahubClientSync(
        config=Config(
            address=_address(),
            username=os.getenv("INFRAHUB_USERNAME", "admin"),
            password=os.getenv("INFRAHUB_PASSWORD", "infrahub"),
        )
    )


def expected_permissions() -> set[tuple]:
    objects = {("object", d["namespace"], d["name"], d["action"], d["decision"]) for d in OBJECT_PERMISSIONS}
    globals_ = {("global", d["action"], d["decision"]) for d in GLOBAL_PERMISSIONS}
    return objects | globals_


def signs_in(password: str) -> bool:
    """True when the account authenticates with `password`. The password is never reported."""
    if not password:
        return False
    try:
        own = InfrahubClientSync(config=Config(address=_address(), username=ACCOUNT, password=password))
        result = own.execute_graphql("query { AccountProfile { name { value } } }")
    except Exception:  # noqa: BLE001 -- any failure means the account cannot sign in
        return False
    return str(result["AccountProfile"]["name"]["value"]) == ACCOUNT


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

    account = client.create("CoreAccount", name=ACCOUNT, label=LABEL, account_type="User", password=password)
    account.save(allow_upsert=True)

    group = client.create("CoreAccountGroup", name=GROUP, roles=[role], members=[account])
    group.save(allow_upsert=True)


def check(client: InfrahubClientSync, password: str) -> list[str]:
    problems: list[str] = []
    account = client.get("CoreAccount", name__value=ACCOUNT, raise_when_missing=False, include=["member_of_groups"])
    if account is None:
        return [f"{ACCOUNT} does not exist"]
    if account.account_type.value != "User":
        problems.append(f"{ACCOUNT} has account type {account.account_type.value!r}, expected 'User'")
    account.member_of_groups.fetch()
    names = sorted(group.display_label or "" for group in account.member_of_groups.peers)
    if names != [GROUP]:
        problems.append(f"{ACCOUNT} is in {names or 'no group'}, expected only {GROUP!r}")
    problems += [f"{ACCOUNT} is in {g!r}, which defeats the point of it" for g in FORBIDDEN_GROUPS if g in names]

    role = client.get("CoreAccountRole", name__value=ROLE, raise_when_missing=False, include=["permissions", "groups"])
    if role is None:
        problems.append(f"the role {ROLE!r} does not exist")
    else:
        role.permissions.fetch()
        held = set()
        for peer in role.permissions.peers:
            node = peer.peer
            if node.get_kind() == "CoreGlobalPermission":
                held.add(("global", node.action.value, node.decision.value))
            else:
                held.add(("object", node.namespace.value, node.name.value, node.action.value, node.decision.value))
        if held != expected_permissions():
            problems.append(
                f"{ROLE!r} holds {sorted(map(str, held))}, expected {sorted(map(str, expected_permissions()))}"
            )
        role.groups.fetch()
        role_groups = sorted(peer.display_label or "" for peer in role.groups.peers)
        if role_groups != [GROUP]:
            problems.append(f"{ROLE!r} is attached to {role_groups or 'no group'}, expected only {GROUP!r}")

    group = client.get("CoreAccountGroup", name__value=GROUP, raise_when_missing=False, include=["roles"])
    if group is None:
        problems.append(f"the group {GROUP!r} does not exist")
    else:
        group.roles.fetch()
        roles = sorted(peer.display_label or "" for peer in group.roles.peers)
        if roles != [ROLE]:
            problems.append(f"{GROUP!r} holds {roles or 'no role'}, expected only {ROLE!r}")

    if not password:
        problems.append(f"{PASSWORD_VAR} is not set in {ENV_FILE}")
    elif not signs_in(password):
        problems.append(f"{ACCOUNT} cannot sign in with the password in {ENV_FILE}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report only; change nothing")
    args = parser.parse_args()

    client = admin_client()
    password = read_env(ENV_FILE, PASSWORD_VAR)

    if not args.check:
        if not password:
            password = secrets.token_urlsafe(24)
            upsert_env(
                ENV_FILE,
                PASSWORD_VAR,
                password,
                "The alex account's password (local Infrahub account, not Dex); written by scripts/provision_network_admin.py.",
            )
            print(f"Generated {PASSWORD_VAR} in {ENV_FILE}")
        provision(client, password)
        print(f"{ACCOUNT} is in {GROUP!r} with role {ROLE!r}")

    problems = check(client, password)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(
            f"{ACCOUNT} signs in with {PASSWORD_VAR} from {ENV_FILE}, is only in {GROUP!r}, "
            f"and holds only the {ROLE!r} role."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
