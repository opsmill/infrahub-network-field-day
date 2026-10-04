"""Contract tests for the MCP server's compose service and its account.

The MCP server is how an agent works with the platform, and the demo's claim is
that it gets no shortcut: same branch, same checks, same review as a human. Two
properties carry that claim, and neither fails loudly when broken.

* **It must hold no credential and never use `agent`.** The server runs in
  ``token-passthrough`` mode: each client sends its own ``mcp-agent`` API token.
  The upstream sidecar example passes ``INFRAHUB_INITIAL_AGENT_TOKEN``, and here that token belongs to a Super
  Administrator the task workers run as -- one that can write to ``main``, load a
  schema and merge. Copying the example would work, look tidy, and quietly hand
  that to a model. ``test_the_mcp_server_runs_in_token_passthrough_mode_with_no_credential`` pins it.

* **The port is bound to loopback.** Anyone who reaches the port can try a token,
  and the transport answers 200 without one, so ``0.0.0.0`` would extend that to the lab's
  networks.

``test_the_agent_role_cannot_merge_or_manage_the_schema`` holds the role's
permission list to what was measured: no global permission beyond
``edit_default_branch``, which only admits a request to the default branch, and
no object permission that allows a write there except creating a proposed change.

This file reads only ``docker-compose.override.yml``, ``.mcp.json`` and
``scripts/provision_mcp_agent.py``; it needs no running Infrahub.
"""

from __future__ import annotations

import importlib.util
import json
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


def test_the_mcp_server_runs_in_token_passthrough_mode_with_no_credential() -> None:
    environment = _mcp_service()["environment"]
    assert environment["INFRAHUB_MCP_AUTH_MODE"] == "token-passthrough"
    for name in ("INFRAHUB_API_TOKEN", "INFRAHUB_USERNAME", "INFRAHUB_PASSWORD", "INFRAHUB_INITIAL_AGENT_TOKEN"):
        assert name not in environment, f"{name} would be a credential shared by every client of the server"
    assert "AGENT_TOKEN" not in str(environment)
    assert "INFRAHUB_MCP_TOKEN" not in str(_mcp_service()), (
        "the client token belongs in .env for clients, not the server"
    )


def test_the_client_sends_the_mcp_agent_token_from_the_environment() -> None:
    server = json.loads((REPO / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["infrahub-lab"]
    assert server["type"] == "http"
    assert server["headers"] == {"Authorization": "Bearer ${INFRAHUB_MCP_TOKEN}"}


def test_the_token_is_minted_for_mcp_agent_and_no_admin_token_is_referenced() -> None:
    provisioner = _provisioner()
    assert provisioner.ACCOUNT == "mcp-agent"
    assert provisioner.TOKEN_VAR == "INFRAHUB_MCP_TOKEN"  # noqa: S105
    assert "INITIAL_ADMIN_TOKEN" not in (REPO / ".mcp.json").read_text(encoding="utf-8")
    assert "INITIAL_AGENT_TOKEN" not in (REPO / ".mcp.json").read_text(encoding="utf-8")
    environment = _mcp_service()["environment"]
    assert not any("INITIAL_" in name for name in environment)


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
