#!/usr/bin/env python3
"""Limit members of the built-in `Infrahub Users` group to what a requester needs.

WHY THIS EXISTS. A person such as `alice` signs in through Dex and lands in
`Infrahub Users`. Infrahub creates that group with two roles, `General Access` and
`Proposed Change Reviewer`. Between them they allow `merge_proposed_change`,
`review_proposed_change`, `manage_schema`, `manage_repositories` and `edit_default_branch`,
and any action on any kind on a branch. A requester needs none of the first four. An
agent that works with her API token (the MCP server in token passthrough mode) holds
whatever her group holds.

WHAT A MEMBER MAY DO AFTER THIS SCRIPT, through one role, `Requester Access`:

- view every kind, so people can read the data (`view` on every namespace and kind,
  everywhere);
- create and edit service objects on a branch other than the default branch: every
  kind in the `Service` namespace, decision 4. A write on `main` is refused;
- create a proposed change. A proposed change is stored on `main`, so this is
  `object:Core:ProposedChange:create:allow_default` plus the global `edit_default_branch`,
  which admits a request to the default branch at all. Object permissions still narrow
  every other write on `main`.

Creating a branch needs no permission that appears in a role; see
docs/docs/developer-guide/mcp-server.md for what was measured.

WHAT IT REMOVES. The roles `General Access` and `Proposed Change Reviewer` are detached
from `Infrahub Users`. They are not deleted and no other group is touched, so
`Super Administrators` and the `Agents`, `Portal Services` and `Metrics Readers` groups
keep what they have. Nobody is put in `Super Administrators`.

WHAT THIS CANNOT BLOCK. On Infrahub 1.10.6 `CoreProposedChangeMerge` does not appear to
check `merge_proposed_change`; see docs/docs/developer-guide/mcp-server.md for the
measurement of whether a member can still merge.

Idempotent. Run `--check` to report only.

    uv run python scripts/provision_requester_access.py
    uv run python scripts/provision_requester_access.py --check   # report only; exit 1 on a problem
"""

from __future__ import annotations

import argparse
import os
import sys

from infrahub_sdk import Config, InfrahubClientSync

GROUP = "Infrahub Users"
ROLE = "Requester Access"

# decision values: 2 = allow on the default branch only, 4 = allow on branches other
# than the default, 6 = allow everywhere
OBJECT_PERMISSIONS = [
    {"namespace": "*", "name": "*", "action": "view", "decision": 6},
    {"namespace": "Service", "name": "*", "action": "any", "decision": 4},
    {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
]
GLOBAL_PERMISSIONS = [
    {"action": "edit_default_branch", "decision": 6},
]

# Built-in roles that `Infrahub Users` must not hold. Detached from the group, never deleted.
DETACHED_ROLES = ("General Access", "Proposed Change Reviewer")

# Actions this role must never carry, whatever else changes. Pinned by
# tests/unit/test_requester_access_contract.py.
FORBIDDEN_ACTIONS = (
    "merge_branch",
    "merge_proposed_change",
    "review_proposed_change",
    "manage_schema",
    "manage_repositories",
    "manage_accounts",
    "manage_permissions",
    "super_admin",
)


def admin_client() -> InfrahubClientSync:
    """The provisioning client, with ONE credential (see provision_mcp_agent.admin_client)."""
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


def expected_permissions() -> set[tuple]:
    objects = {("object", d["namespace"], d["name"], d["action"], d["decision"]) for d in OBJECT_PERMISSIONS}
    globals_ = {("global", d["action"], d["decision"]) for d in GLOBAL_PERMISSIONS}
    return objects | globals_


def provision(client: InfrahubClientSync) -> None:
    group = client.get("CoreAccountGroup", name__value=GROUP, raise_when_missing=False, include=["roles"])
    if group is None:
        msg = f"the built-in group {GROUP!r} does not exist"
        raise SystemExit(msg)

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

    group.roles.fetch()
    held = {peer.id for peer in group.roles.peers}
    changed = False
    if role.id not in held:
        group.roles.add(role)
        changed = True
    for peer in list(group.roles.peers):
        if (peer.display_label or "") in DETACHED_ROLES:
            group.roles.remove(peer.id)
            changed = True
    if changed:
        group.save()


def check(client: InfrahubClientSync) -> list[str]:
    problems: list[str] = []
    role = client.get("CoreAccountRole", name__value=ROLE, raise_when_missing=False, include=["permissions"])
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

    group = client.get("CoreAccountGroup", name__value=GROUP, raise_when_missing=False, include=["roles"])
    if group is None:
        problems.append(f"the group {GROUP!r} does not exist")
    else:
        group.roles.fetch()
        names = sorted(peer.display_label or "" for peer in group.roles.peers)
        if ROLE not in names:
            problems.append(f"{GROUP!r} does not hold {ROLE!r} (roles: {names or 'none'})")
        problems.extend(f"{GROUP!r} still holds the built-in role {name!r}" for name in DETACHED_ROLES if name in names)
        extra = [name for name in names if name not in (ROLE, *DETACHED_ROLES)]
        if extra:
            problems.append(f"{GROUP!r} holds roles this script does not manage: {extra}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report only; change nothing")
    args = parser.parse_args()

    client = admin_client()
    if not args.check:
        provision(client)
        print(f"{GROUP!r} now holds the role {ROLE!r} and not {', '.join(DETACHED_ROLES)}")

    problems = check(client)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(
            f"{GROUP!r} holds only {ROLE!r}: view everything, write service objects on a branch, open a proposed change."
        )
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
