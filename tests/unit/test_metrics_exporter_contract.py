"""Contract tests for the Infrahub exporter's compose service and account (cycle 034).

The exporter is a long-running process holding an Infrahub credential, and it
only ever reads. Three properties carry that, and none fails loudly when broken:

* **It reads as `metrics-exporter`, holding view and nothing else.** The easy
  credential to reach for is the admin token in the shell, or
  ``INFRAHUB_INITIAL_AGENT_TOKEN`` -- both Super Administrators, one of them the
  account every task worker runs as.
* **The token is never committed.** The exporter's settings model *requires*
  ``infrahub.token`` in its YAML, so the obvious way to make it start is to put
  the token there. It arrives through one JSON environment variable instead.
* **Port 8002, not the exporter's default.** 8001 on this host is
  ``infrahub-mcp``; two services claiming it is a compose failure that names
  neither of them helpfully.

This file reads only committed files; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
PINNED_COMMIT = "80974dfca53a532126ee5945eed7c07dbbff93c4"


def _service() -> dict[str, Any]:
    compose = yaml.safe_load((REPO / "docker-compose.override.yml").read_text(encoding="utf-8"))
    return compose["services"]["infrahub-exporter"]


def _config() -> dict[str, Any]:
    return yaml.safe_load((REPO / "metrics" / "exporter.yml").read_text(encoding="utf-8"))


def _provisioner() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "provision_metrics_exporter", REPO / "scripts/provision_metrics_exporter.py"
    )
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_exporter_is_built_from_the_pinned_commit() -> None:
    build = _service()["build"]
    assert build["context"].endswith(f"#{PINNED_COMMIT}")
    assert build["dockerfile"] == "development/Dockerfile"


def test_the_exporter_is_published_on_8002_and_listens_on_8001_inside() -> None:
    assert _service()["ports"] == ["8002:8001"]
    assert _config()["listen_port"] == 8001


def test_the_token_reaches_the_exporter_from_env_and_never_from_git() -> None:
    assert "infrahub" not in _config(), (
        "an `infrahub:` block in exporter.yml would override the environment and is where a token gets committed"
    )
    raw = _service()["environment"]["INFRAHUB_SIDECAR_INFRAHUB"]
    assert "${INFRAHUB_EXPORTER_TOKEN" in raw
    # The value must be valid JSON once compose has interpolated it.
    parsed = json.loads(raw.replace("${INFRAHUB_EXPORTER_TOKEN:-}", "t"))
    assert parsed["branch"] == "main"
    assert parsed["address"] == "http://infrahub-server:8000"
    assert "AGENT_TOKEN" not in raw
    assert "INFRAHUB_API_TOKEN" not in raw


def test_service_discovery_is_off_and_the_contracted_kinds_are_exported() -> None:
    config = _config()
    assert config["service_discovery"]["enabled"] is False
    kinds = {entry["kind"] for entry in config["metrics"]["kind"]}
    assert kinds == {
        "DcimGenericDevice",
        "ServiceGeneric",
        "OrganizationTenant",
        "CoreProposedChange",
        "DeploymentState",
    }


def test_the_role_is_view_only() -> None:
    module = _provisioner()
    assert module.ACCOUNT == "metrics-exporter"
    assert [p["action"] for p in module.OBJECT_PERMISSIONS] == ["view"]
    assert not hasattr(module, "GLOBAL_PERMISSIONS") or not module.GLOBAL_PERMISSIONS
    assert "Super Administrators" in module.FORBIDDEN_GROUPS
