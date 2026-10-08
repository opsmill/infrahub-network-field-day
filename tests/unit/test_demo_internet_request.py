"""The second part of the builder demonstration: the request file and the evidence command's expectations."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
REQUEST = ROOT / "demo" / "requests" / "acme-internet.yml"
OBJECTS = ROOT / "objects" / "37_otternet_wan_services.yml"


def _documents(path: Path) -> list[dict]:
    return [doc for doc in yaml.safe_load_all(path.read_text(encoding="utf-8")) if doc]


def test_request_is_one_internet_access_node_for_acme() -> None:
    (doc,) = _documents(REQUEST)
    assert doc["kind"] == "Object"
    assert doc["spec"]["kind"] == "ServiceInternetAccess"
    (node,) = doc["spec"]["data"]
    assert node["name"] == "acme-internet"
    assert node["l3vpn"] == "acme-l3vpn"
    assert node["peering"] == "isp-to-internet"
    assert node["status"] == "active"


def test_request_has_no_node_for_globex() -> None:
    assert "globex" not in REQUEST.read_text(encoding="utf-8").replace("globex has no node", "")


def test_the_service_is_not_seed_data() -> None:
    """On main the kind does not exist, so no seed file may name it, and `invoke load` never loads the request."""
    kinds = {doc["spec"]["kind"] for doc in _documents(OBJECTS)}
    assert "ServiceInternetAccess" not in kinds
    assert "objects" not in REQUEST.relative_to(ROOT).parts


def _evidence_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("internet_evidence", ROOT / "scripts" / "internet_evidence.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["internet_evidence"] = module
    spec.loader.exec_module(module)
    return module


def test_evidence_phases_expect_acme_only_after_the_request() -> None:
    phases = _evidence_module().PHASES
    assert phases["before"][0] == "none"
    assert phases["capability"][0] == "none"
    assert phases["request"][0] == "acme"


def test_evidence_verdicts() -> None:
    evidence = _evidence_module().Evidence
    assert evidence(tenant="acme").verdict == "no internet"
    full = evidence("acme", True, True, True, True, "200", "0.01")
    assert full.verdict == "internet"
    partial = evidence("acme", True, True, False, True, "000", "5.00")
    assert partial.verdict == "INCONSISTENT"
    assert not partial.consistent


def test_route_parsing_reads_prefix_rows_only() -> None:
    module = _evidence_module()
    raw = "Flags: > (best)\n0.0.0.0/0            static       1        5       >        discard\n10.1.0.0/24  local 0 0 > x\n"
    assert module.has_prefix(raw, "0.0.0.0/0")
    assert not module.has_prefix(raw, "10.2.0.0/24")
