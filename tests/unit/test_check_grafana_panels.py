"""`scripts/check_grafana_panels.py` proves what a user sees, not what Prometheus holds.

The bootstrap verification once passed "every organisation dashboard panel returns data"
while every panel on the lab read "No data": the check queried Prometheus directly, and
Grafana's Prometheus plugin was not registered. These tests replay Grafana API exchanges
recorded read-only from the live lab (`fixtures/grafana/live_pass.json`, written by the
helper's own `--record`), then break them the ways the lab has actually broken.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from types import ModuleType

FIXTURES = Path("tests/unit/fixtures/grafana")
DASHBOARDS = Path("payloads/dashboards")


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_grafana_panels", Path("scripts/check_grafana_panels.py"))
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve annotations through it
    spec.loader.exec_module(module)
    return module


m = _module()


@pytest.fixture
def exchanges() -> list[dict[str, Any]]:
    return json.loads((FIXTURES / "live_pass.json").read_text(encoding="utf-8"))["exchanges"]


@pytest.fixture
def failures() -> dict[str, Any]:
    return json.loads((FIXTURES / "failure_responses.json").read_text(encoding="utf-8"))


def _run(exchanges: list[dict[str, Any]], **kwargs: Any) -> Any:
    expected = kwargs.pop("expected", m.committed_uids(DASHBOARDS))
    return m.run(m.ReplayTransport(exchanges), expected, **kwargs)


def _panel_query(exchanges: list[dict[str, Any]], fragment: str) -> dict[str, Any]:
    """The one recorded /api/ds/query exchange whose first query contains `fragment`."""
    hits = [
        e for e in exchanges if e["path"] == "/api/ds/query" and fragment in e["body"]["queries"][0].get("expr", "")
    ]
    assert len(hits) == 1, f"{fragment!r} matched {len(hits)} panel queries"
    return hits[0]


def test_the_live_lab_passes(exchanges: list[dict[str, Any]]) -> None:
    report = _run(exchanges)
    assert report.failures == []
    # Every committed dashboard was checked, through Grafana.
    assert sum("panels with data" in n for n in report.notes) == len(m.committed_uids(DASHBOARDS))
    # Both allowlisted breakouts were empty on the recording, and said so.
    assert sum("allowed --" in n for n in report.notes) == len(m.ALLOWED_EMPTY)


def test_a_recording_queries_every_committed_panel(exchanges: list[dict[str, Any]]) -> None:
    queried = sum(e["path"] == "/api/ds/query" for e in exchanges)
    committed = 0
    for path in sorted(DASHBOARDS.glob("*.json")):
        panels = m.iter_panels(json.loads(path.read_text(encoding="utf-8"))["panels"])
        committed += sum(bool(p.get("targets")) for p in panels)
    assert queried == committed


def test_plugin_not_registered_fails_every_panel(exchanges: list[dict[str, Any]], failures: dict[str, Any]) -> None:
    broken = copy.deepcopy(exchanges)
    for e in broken:
        if e["path"] == "/api/ds/query":
            e["status"] = failures["plugin_not_registered"]["status"]
            e["response"] = failures["plugin_not_registered"]["response"]
    report = _run(broken)
    # The datasource health check alone does not catch this; the panels do.
    assert any(n.startswith("datasource prometheus health: OK") for n in report.notes)
    panel_failures = [f for f in report.failures if "plugin.notRegistered" in f]
    assert panel_failures
    assert all("HTTP 404" in f for f in panel_failures)
    assert any(f.startswith("OTTERNET / Organisation / Tenants [A] error") for f in report.failures)
    assert "OTTERNET / Organisation: 0/16 panels with data" in report.notes


def test_an_empty_panel_is_named(exchanges: list[dict[str, Any]], failures: dict[str, Any]) -> None:
    broken = copy.deepcopy(exchanges)
    _panel_query(broken, "infrahub_organizationtenant_info")["response"]["results"]["A"] = failures["empty_result"]
    report = _run(broken)
    assert report.failures == ["OTTERNET / Organisation / Tenants [A] no data"]


def test_one_empty_query_fails_a_panel_whose_other_query_has_data(
    exchanges: list[dict[str, Any]], failures: dict[str, Any]
) -> None:
    broken = copy.deepcopy(exchanges)
    exchange = _panel_query(broken, "rate(interface_ifHCInOctets")
    exchange["response"]["results"]["B"] = failures["empty_result"]
    report = _run(broken)
    assert report.failures == ["OTTERNET / Perimeter firewall / Throughput per handoff [B] no data"]


def test_a_query_error_is_reported_with_its_message(exchanges: list[dict[str, Any]], failures: dict[str, Any]) -> None:
    broken = copy.deepcopy(exchanges)
    _panel_query(broken, "infrahub_organizationtenant_info")["response"]["results"]["A"] = failures[
        "parse_error_result"
    ]
    report = _run(broken)
    assert len(report.failures) == 1
    assert report.failures[0].startswith("OTTERNET / Organisation / Tenants [A] error: bad_data")


def test_an_allowlisted_breakout_still_needs_its_total(
    exchanges: list[dict[str, Any]], failures: dict[str, Any]
) -> None:
    broken = copy.deepcopy(exchanges)
    _panel_query(broken, "sum(rate(interface_ifInErrors")["response"]["results"]["A"] = failures["empty_result"]
    report = _run(broken)
    assert report.failures == ["OTTERNET / Perimeter firewall / Interface errors [A] no data"]


def test_an_allowlisted_breakout_may_not_error(exchanges: list[dict[str, Any]], failures: dict[str, Any]) -> None:
    broken = copy.deepcopy(exchanges)
    _panel_query(broken, "sum(rate(interface_ifInErrors")["response"]["results"]["B"] = failures["parse_error_result"]
    report = _run(broken)
    assert len(report.failures) == 1
    assert report.failures[0].startswith("OTTERNET / Perimeter firewall / Interface errors [B] error")


def test_a_stale_allowlist_entry_fails(exchanges: list[dict[str, Any]]) -> None:
    stale = (*m.ALLOWED_EMPTY, m.Allowed("otternet-perimeter", "A panel since renamed", "B", "test"))
    report = _run(exchanges, allowed=stale)
    assert report.failures == ["allowlist entry matches no query: otternet-perimeter / A panel since renamed [B]"]


def test_an_unhealthy_datasource_fails(exchanges: list[dict[str, Any]]) -> None:
    broken = copy.deepcopy(exchanges)
    for e in broken:
        if e["path"] == "/api/datasources/uid/prometheus/health":
            e["status"] = 400
            e["response"] = {"status": "ERROR", "message": "Prometheus is not reachable"}
    report = _run(broken)
    assert report.failures == ["datasource prometheus health: HTTP 400: Prometheus is not reachable"]


def test_a_committed_dashboard_missing_from_grafana_fails(exchanges: list[dict[str, Any]]) -> None:
    report = _run(exchanges, expected={*m.committed_uids(DASHBOARDS), "otternet-unprovisioned"})
    assert report.failures == ["committed dashboard otternet-unprovisioned is not in Grafana's OTTERNET folder"]


def test_an_empty_variable_dropdown_fails(exchanges: list[dict[str, Any]]) -> None:
    broken = copy.deepcopy(exchanges)
    for e in broken:
        if "/label/device/values" in e["path"]:
            e["response"] = {"status": "success", "data": []}
    report = _run(broken)
    assert report.failures == ["OTTERNET / Kubernetes nodes: variable $device lists no values (an empty dropdown)"]


def test_variables_resolve_as_grafana_does() -> None:
    values = {"device": ".*", "one": "leaf1"}
    expr = 'rate(x{device=~"$device", d="${one}", n="[[one]]"}[$__rate_interval])'
    assert m.interpolate(expr, values) == 'rate(x{device=~".*", d="leaf1", n="leaf1"}[$__rate_interval])'

    class Labels:
        def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
            return 200, {"status": "success", "data": ["leaf-1.a", "leaf-2"]}

    def resolve(var: dict[str, Any]) -> str:
        report = m.Report()
        dashboard = {
            "templating": {"list": [{"name": "v", "type": "query", "query": "label_values(m, device)", **var}]}
        }
        return m.resolve_variables(dashboard, Labels(), report, "d")["v"]

    all_selected = {"current": {"value": ["$__all"]}, "includeAll": True, "multi": True}
    assert resolve({**all_selected, "allValue": ".*"}) == ".*"
    assert resolve(all_selected) == r"(leaf-1\\.a|leaf-2)"
    assert resolve({"current": {}}) == "leaf-1.a"
    assert resolve({"current": {"value": "leaf-2"}}) == "leaf-2"


def test_every_allowlist_entry_names_a_breakout_beside_a_total() -> None:
    committed = {}
    for path in sorted(DASHBOARDS.glob("*.json")):
        dashboard = json.loads(path.read_text(encoding="utf-8"))
        committed[dashboard["uid"]] = {p.get("title"): p for p in m.iter_panels(dashboard["panels"])}
    for entry in m.ALLOWED_EMPTY:
        assert entry.reason
        panel = committed[entry.dashboard_uid][entry.panel_title]
        targets = {t["refId"]: t for t in panel["targets"]}
        # A breakout (`> 0`, beside its total) or a subset of a count beside it (`== 0)`).
        expr = targets[entry.ref_id]["expr"].rstrip()
        assert expr.endswith(("> 0", "== 0)")), entry
        assert set(targets) - {entry.ref_id}, f"{entry} has no total to require data from"


def test_a_panel_blank_only_through_its_allowlist_still_fails(
    exchanges: list[dict[str, Any]], failures: dict[str, Any]
) -> None:
    broken = copy.deepcopy(exchanges)
    _panel_query(broken, "sum(rate(interface_ifInErrors")["response"]["results"]["A"] = failures["empty_result"]
    both = (*m.ALLOWED_EMPTY, m.Allowed("otternet-perimeter", "Interface errors", "A", "test: excusing the total"))
    report = _run(broken, allowed=both)
    assert report.failures == ["OTTERNET / Perimeter firewall / Interface errors no query in the panel returns data"]
