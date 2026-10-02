"""Contract tests for the Backstage portal's own Infrahub account.

The portal used to hold the stack's Super Administrator token, committed in
`tooling/20-backstage.yaml`. It now authenticates as `backstage-portal`, created
by `scripts/provision_portal_account.py`, and its token is rendered into the
Secret by `scripts/deploy_tooling.sh` at deploy time. Two properties carry that,
and neither fails loudly when broken:

* **The permission set is exactly what the portal's steps were measured to
  need.** Adding a broad grant "to make something work" would look harmless and
  quietly restore most of what the admin token could do -- merging, the schema,
  accounts. `test_the_portal_role_is_exactly_what_was_measured` pins it.

* **The committed manifest carries no real token**, only the placeholder the
  deploy script substitutes. A token pasted back in by hand would deploy and
  work, which is precisely why nothing else would notice.

This reads only files; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "tooling/20-backstage.yaml"
DEPLOY = REPO / "scripts/deploy_tooling.sh"
PLACEHOLDER = "__INFRAHUB_PORTAL_TOKEN__"

ALLOW_ALL, ALLOW_OTHER_BRANCHES = 6, 4


def _provisioner() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "provision_portal_account", REPO / "scripts/provision_portal_account.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _secret() -> dict:
    for document in yaml.safe_load_all(MANIFEST.read_text(encoding="utf-8")):
        if document and document.get("kind") == "Secret" and document["metadata"]["name"] == "backstage-secrets":
            return document
    raise AssertionError("backstage-secrets is not in tooling/20-backstage.yaml")


def test_the_portal_role_is_exactly_what_was_measured() -> None:
    provisioner = _provisioner()

    assert provisioner.ACCOUNT == "backstage-portal"
    assert sorted((p["namespace"], p["name"], p["action"], p["decision"]) for p in provisioner.OBJECT_PERMISSIONS) == [
        # BranchCreate, the service creates and updates, generator runs and the
        # file upload -- all on the request's branch, never on main.
        ("*", "*", "any", ALLOW_OTHER_BRANCHES),
        # The catalogue reads everything.
        ("*", "*", "view", ALLOW_ALL),
        # Open the proposed change, which is an object on main.
        ("Core", "ProposedChange", "create", ALLOW_ALL),
    ]
    assert sorted((p["action"], p["decision"]) for p in provisioner.GLOBAL_PERMISSIONS) == [
        # Admits the proposed change to the default branch at all.
        ("edit_default_branch", ALLOW_ALL),
        # `context: { account: ... }` -- writes attributed to the signed-in user.
        ("override_context", ALLOW_ALL),
    ]


def test_the_portal_role_cannot_merge_review_or_administer() -> None:
    provisioner = _provisioner()
    actions = {p["action"] for p in provisioner.GLOBAL_PERMISSIONS}
    for forbidden in (
        "super_admin",
        "merge_branch",
        "merge_proposed_change",
        "review_proposed_change",
        "manage_schema",
        "manage_accounts",
        "manage_permissions",
        "manage_repositories",
        "delete_branch",
    ):
        assert forbidden not in actions, f"the portal must not hold {forbidden}"
    writes_on_main = [p for p in provisioner.OBJECT_PERMISSIONS if p["action"] != "view" and p["decision"] == ALLOW_ALL]
    assert writes_on_main == [
        {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": ALLOW_ALL}
    ]
    assert "Super Administrators" in provisioner.FORBIDDEN_GROUPS


def test_the_committed_manifest_carries_no_real_token() -> None:
    token = _secret()["stringData"]["INFRAHUB_API_TOKEN"]
    assert token == PLACEHOLDER, (
        "tooling/20-backstage.yaml must carry the placeholder; deploy_tooling.sh renders the real token"
    )
    text = MANIFEST.read_text(encoding="utf-8")
    uuid = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
    assert not uuid.search(text), "a token-shaped value is committed in tooling/20-backstage.yaml"


def test_the_deploy_renders_the_portal_token_and_refuses_without_one() -> None:
    script = DEPLOY.read_text(encoding="utf-8")
    assert f"s|{PLACEHOLDER}|${{PORTAL_TOKEN}}|g" in script
    assert "INFRAHUB_PORTAL_TOKEN" in script
    assert _provisioner().TOKEN_VAR == "INFRAHUB_PORTAL_TOKEN"  # noqa: S105 -- a variable name
    # Refuses rather than deploying the placeholder, and checks it did render.
    assert "provision_portal_account.py" in script
    assert f'grep -q "{PLACEHOLDER}"' in script
    # The admin token's default value appears nowhere in the deploy path.
    assert "06438eb2" not in script


def test_invoke_tooling_provisions_the_account_before_deploying() -> None:
    tasks = (REPO / "tasks.py").read_text(encoding="utf-8")
    body = tasks.split("def tooling(", 1)[1].split("\n@task", 1)[0]
    assert body.index("provision_portal_account.py") < body.index('"scripts/deploy_tooling.sh", pty')
