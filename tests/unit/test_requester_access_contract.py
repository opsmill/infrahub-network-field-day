"""Contract tests for the only role `Infrahub Users` holds.

A person such as `alice` signs in through Dex and lands in the built-in `Infrahub Users`
group. `scripts/provision_requester_access.py` makes `Requester Access` its only role and
detaches the built-in `General Access` and `Proposed Change Reviewer`. The role must stay small:
a person who may open a proposed change must not gain a way to approve, load a schema or
administer accounts, and must not write to `main`.

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


def test_the_role_holds_exactly_these_permissions() -> None:
    module = _provisioner()
    assert module.OBJECT_PERMISSIONS == [
        {"namespace": "*", "name": "*", "action": "view", "decision": 6},
        {"namespace": "Service", "name": "*", "action": "any", "decision": 4},
        {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
    ]
    assert module.GLOBAL_PERMISSIONS == [{"action": "edit_default_branch", "decision": 6}]
    assert module.expected_permissions() == {
        ("object", "*", "*", "view", 6),
        ("object", "Service", "*", "any", 4),
        ("object", "Core", "ProposedChange", "create", 2),
        ("global", "edit_default_branch", 6),
    }


def test_the_view_permission_is_kept_for_every_kind() -> None:
    module = _provisioner()
    assert {"namespace": "*", "name": "*", "action": "view", "decision": 6} in module.OBJECT_PERMISSIONS


def test_writes_are_limited_to_service_kinds_on_branches_other_than_the_default() -> None:
    # decision 4 = allow on branches other than the default; 2 = the default branch only.
    module = _provisioner()
    writes = [item for item in module.OBJECT_PERMISSIONS if item["action"] != "view"]
    for item in writes:
        if item["action"] == "any":
            assert item["namespace"] == "Service"
            assert item["decision"] == 4
        else:
            assert (item["namespace"], item["name"], item["action"], item["decision"]) == (
                "Core",
                "ProposedChange",
                "create",
                2,
            )
    assert not [item for item in module.OBJECT_PERMISSIONS if item["decision"] == 6 and item["action"] != "view"]


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
    assert not {"delete", "update", "*"} & {item["action"] for item in module.OBJECT_PERMISSIONS}


def test_the_built_in_roles_are_detached_and_never_deleted() -> None:
    module = _provisioner()
    assert set(module.DETACHED_ROLES) == {"General Access", "Proposed Change Reviewer"}
    source = (REPO / "scripts/provision_requester_access.py").read_text(encoding="utf-8")
    assert "group.roles.remove(" in source
    assert "role.delete" not in source
    assert ".delete(" not in source


def test_the_script_touches_only_infrahub_users_and_not_super_administrators() -> None:
    source = (REPO / "scripts/provision_requester_access.py").read_text(encoding="utf-8")
    assert "group.roles.add(role)" in source
    body = source.split('"""', 2)[2]
    for other in ("Super Administrators", "Agents", "Portal Services", "Metrics Readers"):
        assert other not in body
    assert 'GROUP = "Infrahub Users"' in source


def test_invoke_mcp_runs_the_script_after_the_agent_provisioning() -> None:
    body = (REPO / "tasks.py").read_text(encoding="utf-8").split("def mcp(", 1)[1].split("@task", 1)[0]
    assert "provision_requester_access.py" in body
    assert body.index("provision_mcp_agent.py") < body.index("provision_requester_access.py")
