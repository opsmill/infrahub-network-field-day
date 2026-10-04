#!/usr/bin/env python3
"""Let members of the built-in `Infrahub Users` group open a proposed change.

WHY THIS EXISTS. A person such as `alice` signs in through Dex and lands in
`Infrahub Users`. Infrahub creates that group with two roles, `General Access` and
`Proposed Change Reviewer`, and neither lets her OPEN a proposed change: the request
is refused naming `object:Core:ProposedChange:create:allow_default`. An agent that
works with her API token (the MCP server in token passthrough mode) is refused the
same way on `propose_changes`. `mcp-agent` and `backstage-portal` can, because their
own roles carry it.

WHAT THIS ADDS. One role, `Requester Access`, attached to `Infrahub Users` next to
the two it already has. It holds exactly:

- `object:Core:ProposedChange:create:allow_default` -- create a proposed change. A
  proposed change is stored on `main`, which is why the decision is `allow_default`;
- the global `edit_default_branch`, which admits a request to the default branch at
  all. Measured on 1.10.6: the group already holds it through the built-in
  `Proposed Change Reviewer` role, so granting it here changes nothing today. The
  refusal named only the object permission, and that permission was the only one that
  was missing (see docs/docs/developer-guide/mcp-server.md). It is listed so the grant does not depend
  on a built-in role that an administrator may edit.

It grants no merge, approve, schema, repository or delete permission, and puts nobody in
`Super Administrators`. It does NOT narrow what the group's other roles already allow;
see docs/docs/developer-guide/mcp-server.md for what members could already do.

Idempotent: it never removes a role from the group. Run `--check` to report only.

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
    {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
]
GLOBAL_PERMISSIONS = [
    {"action": "edit_default_branch", "decision": 6},
]

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
    if role.id not in {peer.id for peer in group.roles.peers}:
        group.roles.add(role)
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
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report only; change nothing")
    args = parser.parse_args()

    client = admin_client()
    if not args.check:
        provision(client)
        print(f"{GROUP!r} now holds the role {ROLE!r}")

    problems = check(client)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(f"{GROUP!r} holds {ROLE!r}: open a proposed change, nothing else.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
