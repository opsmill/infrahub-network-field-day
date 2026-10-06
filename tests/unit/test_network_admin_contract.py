"""Contract tests for the local `network-admin` account and its role.

`scripts/provision_network_admin.py` creates a password-based account in one group with one role:
it edits network data on a branch and opens, reviews and merges a proposed change, and holds no
schema, repository, account or permission management. The role must stay that small.

This file reads the script and `tasks.py`; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts/provision_network_admin.py"


def _provisioner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_network_admin", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_names() -> None:
    module = _provisioner()
    assert module.ACCOUNT == "network-admin"
    assert module.LABEL == "Network Admin"
    assert module.GROUP == "Network Admins"
    assert module.ROLE == "Network Admin Access"
    assert module.PASSWORD_VAR == "INFRAHUB_NETWORK_ADMIN_PASSWORD"  # noqa: S105


def test_the_role_holds_exactly_these_permissions() -> None:
    module = _provisioner()
    assert module.OBJECT_PERMISSIONS == [
        {"namespace": "*", "name": "*", "action": "view", "decision": 6},
        {"namespace": "*", "name": "*", "action": "any", "decision": 4},
        {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 2},
    ]
    assert module.GLOBAL_PERMISSIONS == [
        {"action": "edit_default_branch", "decision": 6},
        {"action": "merge_proposed_change", "decision": 6},
        {"action": "review_proposed_change", "decision": 6},
    ]
    assert len(module.expected_permissions()) == 6


def test_every_write_on_an_object_is_limited_to_branches_other_than_the_default() -> None:
    # decision 4 = branches other than the default; 2 = the default branch only (the proposed change itself).
    module = _provisioner()
    writes = [item for item in module.OBJECT_PERMISSIONS if item["action"] != "view"]
    assert [(w["namespace"], w["name"], w["action"], w["decision"]) for w in writes] == [
        ("*", "*", "any", 4),
        ("Core", "ProposedChange", "create", 2),
    ]
    assert not [item for item in module.OBJECT_PERMISSIONS if item["decision"] == 6 and item["action"] != "view"]


def test_no_schema_repository_account_permission_or_super_admin_action_is_granted() -> None:
    module = _provisioner()
    granted = {item["action"] for item in module.GLOBAL_PERMISSIONS} | {
        item["action"] for item in module.OBJECT_PERMISSIONS
    }
    for action in ("manage_schema", "manage_repositories", "manage_accounts", "manage_permissions", "super_admin"):
        assert action in module.FORBIDDEN_ACTIONS
        assert action not in granted
    assert not granted & set(module.FORBIDDEN_ACTIONS)
    assert {"merge_proposed_change", "review_proposed_change", "edit_default_branch"} <= granted


def test_the_account_is_never_a_super_administrator_or_a_dex_user() -> None:
    module = _provisioner()
    assert set(module.FORBIDDEN_GROUPS) == {"Super Administrators", "Infrahub Users"}
    source = SCRIPT.read_text(encoding="utf-8")
    body = source.split('"""', 2)[2]
    assert 'account_type="User"' in body
    assert "password=password" in body
    assert not {"oauth", "oidc", "keycloak"} & set(re.findall(r"[a-z0-9]+", body.lower()))
    assert "Super Administrators" not in re.sub(r"FORBIDDEN_GROUPS = .*", "", body)


def test_the_script_uses_no_admin_or_agent_token_and_no_account_token() -> None:
    body = SCRIPT.read_text(encoding="utf-8").split('"""', 2)[2]
    assert "INFRAHUB_INITIAL_ADMIN_TOKEN" not in body
    assert "INFRAHUB_INITIAL_AGENT_TOKEN" not in body
    assert "InfrahubAccountTokenCreate" not in body
    assert "print(password" not in body
    assert 'print(f"{password' not in body


def test_the_script_deletes_nothing_and_writes_the_password_only_to_env() -> None:
    body = SCRIPT.read_text(encoding="utf-8")
    assert ".delete(" not in body
    assert "upsert_env(" in body
    assert "ENV_FILE = envfile.env_file(REPO)" in body


def test_the_password_variable_is_one_of_the_generated_credentials() -> None:
    from solution_arista_avd import envfile

    assert envfile.GENERATED_CREDENTIAL.match("INFRAHUB_NETWORK_ADMIN_PASSWORD")


class _Peers:
    def __init__(self, labels: list[str]) -> None:
        self.peers = [SimpleNamespace(display_label=label) for label in labels]

    def fetch(self) -> None:
        return None


def _client(module: ModuleType, *, groups: list[str], held: set[tuple], role_groups: list[str] | None = None) -> Any:
    perms = []
    for item in held:
        if item[0] == "global":
            node = SimpleNamespace(
                get_kind=lambda: "CoreGlobalPermission",
                action=SimpleNamespace(value=item[1]),
                decision=SimpleNamespace(value=item[2]),
            )
        else:
            node = SimpleNamespace(
                get_kind=lambda: "CoreObjectPermission",
                namespace=SimpleNamespace(value=item[1]),
                name=SimpleNamespace(value=item[2]),
                action=SimpleNamespace(value=item[3]),
                decision=SimpleNamespace(value=item[4]),
            )
        perms.append(SimpleNamespace(peer=node))
    permissions = SimpleNamespace(peers=perms, fetch=lambda: None)
    role = SimpleNamespace(permissions=permissions, groups=_Peers(role_groups or [module.GROUP]))
    account = SimpleNamespace(account_type=SimpleNamespace(value="User"), member_of_groups=_Peers(groups))
    group = SimpleNamespace(roles=_Peers([module.ROLE]))
    by_kind = {"CoreAccount": account, "CoreAccountRole": role, "CoreAccountGroup": group}
    return SimpleNamespace(get=lambda kind, **_kw: by_kind[kind])


def test_check_passes_for_the_defined_state(monkeypatch: Any) -> None:
    module = _provisioner()
    monkeypatch.setattr(module, "signs_in", lambda _p: True)
    client = _client(module, groups=[module.GROUP], held=module.expected_permissions())
    assert module.check(client, "x") == []


def test_check_reports_membership_in_super_administrators(monkeypatch: Any) -> None:
    module = _provisioner()
    monkeypatch.setattr(module, "signs_in", lambda _p: True)
    client = _client(module, groups=[module.GROUP, "Super Administrators"], held=module.expected_permissions())
    problems = module.check(client, "x")
    assert any("Super Administrators" in p for p in problems)


def test_check_reports_an_extra_permission_a_missing_password_and_a_failed_sign_in(monkeypatch: Any) -> None:
    module = _provisioner()
    monkeypatch.setattr(module, "signs_in", lambda _p: False)
    extra = module.expected_permissions() | {("global", "manage_schema", 6)}
    client = _client(module, groups=[module.GROUP], held=extra)
    problems = module.check(client, "x")
    assert any("manage_schema" in p for p in problems)
    assert any("cannot sign in" in p for p in problems)
    assert any("is not set" in p for p in module.check(client, ""))


def test_check_reports_a_role_attached_to_another_group(monkeypatch: Any) -> None:
    module = _provisioner()
    monkeypatch.setattr(module, "signs_in", lambda _p: True)
    client = _client(
        module, groups=[module.GROUP], held=module.expected_permissions(), role_groups=[module.GROUP, "Infrahub Users"]
    )
    assert any("attached to" in p for p in module.check(client, "x"))


def test_invoke_network_admin_runs_the_script_and_bootstrap_calls_it() -> None:
    text = (REPO / "tasks.py").read_text(encoding="utf-8")
    body = text.split("def network_admin(", 1)[1].split("@task", 1)[0]
    assert "provision_network_admin.py" in body
    assert "_use_dotenv_credentials()" in body
    assert "network_admin(ctx)" in text.split("def bootstrap(", 1)[1].split("def _wait_for_infrahub", 1)[0]
