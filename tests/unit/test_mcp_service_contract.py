"""Contract tests for the MCP server's compose service and its account.

The MCP server is how an agent works with the platform, and the demo's claim is
that it gets no shortcut: same branch, same checks, same review as a human. Two
properties carry that claim, and neither fails loudly when broken.

* **It must not sign in as `agent`.** The upstream sidecar example passes
  ``INFRAHUB_INITIAL_AGENT_TOKEN``, and here that token belongs to a Super
  Administrator the task workers run as -- one that can write to ``main``, load a
  schema and merge. Copying the example would work, look tidy, and quietly hand
  that to a model. ``test_the_mcp_server_signs_in_as_mcp_agent`` pins the account.

* **The port is bound to loopback.** Auth mode ``none`` means whoever reaches the
  port acts as ``mcp-agent``, so ``0.0.0.0`` would extend that to the lab's
  networks.

``test_the_agent_role_cannot_merge_or_manage_the_schema`` holds the role's
permission list to what was measured: no global permission beyond
``edit_default_branch``, which only admits a request to the default branch, and
no object permission that allows a write there except creating a proposed change.

This file reads only ``docker-compose.override.yml`` and
``scripts/provision_mcp_agent.py``; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from types import ModuleType

REPO = Path(__file__).resolve().parents[2]


def _mcp_service() -> dict:
    compose = yaml.safe_load((REPO / "docker-compose.override.yml").read_text(encoding="utf-8"))
    return compose["services"]["infrahub-mcp"]


def _provisioner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("provision_mcp_agent", REPO / "scripts/provision_mcp_agent.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_mcp_server_signs_in_as_mcp_agent() -> None:
    environment = _mcp_service()["environment"]
    assert environment["INFRAHUB_USERNAME"] == "mcp-agent"
    assert "INFRAHUB_API_TOKEN" not in environment, (
        "an API token here is almost certainly INFRAHUB_INITIAL_AGENT_TOKEN, a Super Administrator"
    )
    assert "AGENT_TOKEN" not in str(environment)


def test_the_mcp_port_is_bound_to_loopback() -> None:
    ports = _mcp_service()["ports"]
    assert ports, "the MCP server must be reachable from the host"
    for port in ports:
        assert str(port).startswith("127.0.0.1:"), f"{port} exposes mcp-agent beyond this host"


def test_the_agent_role_cannot_merge_or_manage_the_schema() -> None:
    provisioner = _provisioner()
    allow_all, allow_other = 6, 4

    assert [p["action"] for p in provisioner.GLOBAL_PERMISSIONS] == ["edit_default_branch"]

    writes_on_main = [p for p in provisioner.OBJECT_PERMISSIONS if p["action"] != "view" and p["decision"] == allow_all]
    assert writes_on_main == [{"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": 6}]

    assert {"namespace": "*", "name": "*", "action": "any", "decision": allow_other} in provisioner.OBJECT_PERMISSIONS
