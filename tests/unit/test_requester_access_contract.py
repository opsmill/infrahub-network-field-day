"""Contract tests for the role that lets `Infrahub Users` open a proposed change.

A person such as `alice` signs in through Dex and lands in the built-in `Infrahub Users`
group. `scripts/provision_requester_access.py` gives that group one extra role,
`Requester Access`. The role must stay small: a person who may open a proposed change
must not gain a way to merge, approve, load a schema or administer accounts through it.

This file reads only the script and `tasks.py`; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]


def _provisioner() -> ModuleType:
    path = REPO / "scripts/provision_requester_access.py"
    spec = importlib.util.spec_from_file_location("provision_requester_access", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_role_and_group_names() -> None:
    module = _provisioner()
    assert module.ROLE == "Requester Access"
    assert module.GROUP == "Infrahub Users"


def test_the_role_holds_exactly_the_two_permissions() -> None:
    module = _provisioner()
    assert module.OBJECT_PERMISSIONS == [
        {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
    ]
    assert module.GLOBAL_PERMISSIONS == [{"action": "edit_default_branch", "decision": 6}]
    assert module.expected_permissions() == {
        ("object", "Core", "ProposedChange", "create", 2),
        ("global", "edit_default_branch", 6),
    }


def test_the_object_permission_allows_the_default_branch_only() -> None:
    # decision 2 = allow on the default branch only. A proposed change is stored on main.
    module = _provisioner()
    assert all(item["decision"] == 2 for item in module.OBJECT_PERMISSIONS)


def test_no_merge_approve_schema_repository_or_account_action_is_granted() -> None:
    module = _provisioner()
    granted = {item["action"] for item in module.GLOBAL_PERMISSIONS} | {
        item["action"] for item in module.OBJECT_PERMISSIONS
    }
    for action in (
        "merge_branch",
        "merge_proposed_change",
        "review_proposed_change",
        "manage_schema",
        "manage_repositories",
        "manage_accounts",
        "manage_permissions",
        "super_admin",
    ):
        assert action in module.FORBIDDEN_ACTIONS, f"{action} must stay on the forbidden list"
        assert action not in granted
    assert not granted & set(module.FORBIDDEN_ACTIONS)
    assert not {"delete", "update", "any", "*"} & {item["action"] for item in module.OBJECT_PERMISSIONS}


def test_the_script_attaches_the_role_to_infrahub_users_without_super_administrators() -> None:
    source = (REPO / "scripts/provision_requester_access.py").read_text(encoding="utf-8")
    assert "group.roles.add(role)" in source
    assert "Super Administrators" not in source.split('"""', 2)[2]
    assert "roles.remove" not in source


def test_invoke_mcp_runs_the_script_after_the_agent_provisioning() -> None:
    body = (REPO / "tasks.py").read_text(encoding="utf-8").split("def mcp(", 1)[1].split("@task", 1)[0]
    assert "provision_requester_access.py" in body
    assert body.index("provision_mcp_agent.py") < body.index("provision_requester_access.py")
