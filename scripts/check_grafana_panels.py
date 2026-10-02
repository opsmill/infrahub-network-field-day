"""Run every OTTERNET dashboard panel THROUGH Grafana and fail on any that shows nothing.

`verify_bootstrap.sh` used to query Prometheus directly, and passed "every organisation
dashboard panel returns data" while every panel on the live lab read "No data": Grafana
13.2.1's Prometheus plugin was not registered, so `/api/ds/query` answered
`plugin.notRegistered` for every query while Prometheus held all of it. A check that goes
round Grafana cannot see Grafana failing. This one asks what a user's browser asks:

1. the datasource's own health check, `GET /api/datasources/uid/<uid>/health`;
2. every dashboard in the folder, fetched from Grafana rather than from the committed JSON
   (so a dashboard that failed to provision is missing, not silently checked from disk),
   with every committed dashboard required to be there;
3. every template variable resolved the way Grafana resolves it on load -- the saved
   selection, `All` becoming the variable's `allValue` -- and every query variable required
   to list at least one value, because an empty dropdown is its own "No data";
4. every visible query of every panel, executed through `POST /api/ds/query` over the last
   30 minutes, and required to return at least one non-null value.

A query may be empty only if it is named in `ALLOWED_EMPTY`, with a reason. Even then it may
not ERROR, and some other query in the same panel must return data, so an allowlisted
breakout cannot hide a panel that is blank. An entry that matches nothing fails too, so the
list cannot outlive the panel it excuses.

Usage:  uv run python scripts/check_grafana_panels.py [--url http://127.0.0.1:13000]
Env:    GRAFANA_ADMIN_PASSWORD   read from --env-file (default .env) when unset
        GRAFANA_USER             default admin

Exits 0 when every panel has data, 1 otherwise. `--record FILE` also writes every exchange
(responses trimmed to a few points) for use as a unit-test fixture.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode

REPO = Path(__file__).resolve().parent.parent
DASHBOARD_DIR = REPO / "payloads" / "dashboards"
FOLDER = "OTTERNET"
DATASOURCE_UID = "prometheus"
RANGE = "30m"
MAX_DATA_POINTS = 300


@dataclass(frozen=True)
class Allowed:
    """A query that is legitimately empty while the lab is healthy."""

    dashboard_uid: str
    panel_title: str
    ref_id: str
    reason: str


# THE ONE PLACE A PANEL QUERY MAY BE EMPTY. Each is a per-port breakout filtered with `> 0`,
# drawn beside a total in the same panel: a healthy lab has no erroring port, so the breakout
# has no series, while the total is a flat zero that does. The total is still required.
ALLOWED_EMPTY: tuple[Allowed, ...] = (
    Allowed(
        "otternet-fabric-telemetry",
        "Errors and discards",
        "B",
        "per-port breakout, `> 0`: one line only for a port that is erroring; the total (A) must have data",
    ),
    Allowed(
        "otternet-perimeter",
        "Interface errors",
        "B",
        "per-port breakout, `> 0`: one line only for a port that is erroring; the total (A) must have data",
    ),
    # Not a breakout: a probe the seed never renders. The collector probes an application only
    # where its pod gate admits an in-cluster source, and every seeded exposed application is
    # gated -- measured, a probe from Telegraf's pod is dropped at otternet-demo and at Grafana.
    # A (how many ports are probed, 0 here) must still have data.
    Allowed(
        "otternet-services",
        "Probed ports answering",
        "B",
        "no seeded application admits the collector at its pod gate, so no probe renders; the count (A) must have data",
    ),
)


class Transport(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]: ...


class HttpTransport:
    def __init__(self, url: str, user: str, password: str) -> None:
        import httpx

        self._client = httpx.Client(base_url=url, auth=(user, password), timeout=30)

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        import httpx

        # One retry: a kubectl port-forward occasionally drops a single connection.
        # A second failure is reported as the panel's failure, never swallowed.
        for attempt in range(2):
            try:
                response = self._client.request(method, path, json=body)
                break
            except httpx.TransportError as exc:
                if attempt:
                    return 0, {"message": f"{type(exc).__name__}: {exc}"}
        try:
            return response.status_code, response.json()
        except ValueError:
            return response.status_code, {"message": response.text[:500]}


def _exchange_key(method: str, path: str, body: dict[str, Any] | None) -> str:
    # The time range moves on every run, so it is not part of what identifies a request.
    route, _, query = path.partition("?")
    params = sorted((k, v) for k, v in parse_qsl(query) if k not in {"start", "end"})
    stable = {k: v for k, v in (body or {}).items() if k not in {"from", "to"}}
    return json.dumps([method, route, params, stable], sort_keys=True)


def _trim(path: str, payload: Any) -> Any:
    """Keep a recorded `/api/ds/query` response small: three frames, three rows each.

    Rows are chosen where some value is non-null, so trimming never turns data into none.
    """
    if not path.startswith("/api/ds/query") or not isinstance(payload, dict):
        return payload
    for result in payload.get("results", {}).values():
        frames = result.get("frames", [])[:3]
        for frame in frames:
            values = frame.get("data", {}).get("values", [])
            if not values:
                continue
            rows = [i for i in range(len(values[0])) if any(col[i] is not None for col in values[1:])][:3]
            rows = rows or list(range(min(3, len(values[0]))))
            frame["data"]["values"] = [[col[i] for i in rows] for col in values]
        result["frames"] = frames
    return payload


class RecordingTransport:
    def __init__(self, inner: Transport) -> None:
        self._inner = inner
        self.exchanges: list[dict[str, Any]] = []

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        status, payload = self._inner.request(method, path, body)
        self.exchanges.append(
            {
                "method": method,
                "path": path,
                "body": body,
                "status": status,
                "response": _trim(path, json.loads(json.dumps(payload))),
            }
        )
        return status, payload

    def write(self, target: Path) -> None:
        target.write_text(json.dumps({"exchanges": self.exchanges}, indent=1) + "\n", encoding="utf-8")


class ReplayTransport:
    """Answers from recorded exchanges, for the unit tests."""

    def __init__(self, exchanges: list[dict[str, Any]]) -> None:
        self._answers = {_exchange_key(e["method"], e["path"], e["body"]): e for e in exchanges}

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        key = _exchange_key(method, path, body)
        if key not in self._answers:
            raise KeyError(f"no recorded exchange for {method} {path}")
        e = self._answers[key]
        return e["status"], e["response"]


@dataclass
class Report:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.failures.append(message)


# --- template variables -----------------------------------------------------------------

_LABEL_VALUES = re.compile(
    r"^\s*label_values\(\s*(?:(?P<metric>.+?)\s*,\s*)?(?P<label>[A-Za-z_][A-Za-z0-9_]*)\s*\)\s*$"
)
_VAR_REF = re.compile(r"\$\{(?P<braced>\w+)(?::[^}]*)?\}|\[\[(?P<bracket>\w+)\]\]|\$(?P<plain>\w+)")


def _regex_escape(value: str) -> str:
    # Grafana's prometheusSpecialRegexEscape, applied to multi-value and All selections.
    return re.sub(r"([\\^$*+?.()|{}\[\]])", r"\\\\\1", value)


def interpolate(text: str, values: dict[str, str]) -> str:
    """Replace dashboard variables; leave Grafana's own `$__…` built-ins for the backend."""

    def repl(match: re.Match[str]) -> str:
        name = match.group("braced") or match.group("bracket") or match.group("plain")
        return values.get(name, match.group(0))

    return _VAR_REF.sub(repl, text)


def _now_range() -> tuple[int, int]:
    end = int(time.time())
    return end - 30 * 60, end


def _variable_options(var: dict[str, Any], values: dict[str, str], grafana: Transport) -> list[str]:
    kind = var.get("type")
    query = var.get("query")
    if isinstance(query, dict):
        query = query.get("query", "")
    query = interpolate(str(query or ""), values)
    if kind == "query":
        match = _LABEL_VALUES.match(query)
        if not match:
            raise ValueError(f"unsupported variable query {query!r}")
        start, end = _now_range()
        params: dict[str, Any] = {"start": start, "end": end}
        if match.group("metric"):
            params["match[]"] = match.group("metric")
        ds_uid = (var.get("datasource") or {}).get("uid", DATASOURCE_UID)
        path = f"/api/datasources/uid/{ds_uid}/resources/api/v1/label/{match.group('label')}/values?{urlencode(params)}"
        status, payload = grafana.request("GET", path)
        if status != 200 or not isinstance(payload, dict) or payload.get("status") != "success":
            raise ValueError(f"listing values failed: HTTP {status} {_message(payload)}")
        options = [str(v) for v in payload.get("data", [])]
        regex = var.get("regex")
        if regex:
            pattern = re.compile(regex.strip("/"))
            options = [o for o in options if pattern.search(o)]
        return options
    if kind in {"custom", "interval"}:
        return [o.strip() for o in query.split(",") if o.strip()]
    if kind in {"constant", "textbox"}:
        return [query]
    return []


def resolve_variables(dashboard: dict[str, Any], grafana: Transport, report: Report, title: str) -> dict[str, str]:
    """Each variable's value as Grafana interpolates it into a Prometheus query on load."""
    values: dict[str, str] = {}
    for var in dashboard.get("templating", {}).get("list", []):
        name = var["name"]
        try:
            options = _variable_options(var, values, grafana)
        except ValueError as exc:
            report.fail(f"{title}: variable ${name}: {exc}")
            options = []
        else:
            if var.get("type") == "query" and not options:
                report.fail(f"{title}: variable ${name} lists no values (an empty dropdown)")
        current = (var.get("current") or {}).get("value")
        selected = current if isinstance(current, list) else [current] if current not in {None, ""} else []
        if "$__all" in selected:
            if var.get("allValue"):
                values[name] = var["allValue"]
                continue
            selected = options
        elif not selected:
            selected = options[:1]  # no saved selection: Grafana takes the first option
        if var.get("multi") or var.get("includeAll"):
            escaped = [_regex_escape(s) for s in selected]
            values[name] = escaped[0] if len(escaped) == 1 else "(" + "|".join(escaped) + ")"
        else:
            values[name] = str(selected[0]) if selected else ""
    return values


# --- panels -----------------------------------------------------------------------------


def iter_panels(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every panel, including those inside a collapsed row."""
    out: list[dict[str, Any]] = []
    for panel in panels:
        out.append(panel)
        out.extend(iter_panels(panel.get("panels", [])))
    return out


def _message(payload: Any) -> str:
    if isinstance(payload, dict):
        bits = [str(payload[k]) for k in ("messageId", "message", "error") if payload.get(k)]
        if bits:
            return ": ".join(bits)
    return str(payload)[:200]


def has_data(result: dict[str, Any]) -> bool:
    """True when any frame holds a non-null value outside its time column."""
    for frame in result.get("frames", []):
        fields = frame.get("schema", {}).get("fields", [])
        columns = frame.get("data", {}).get("values", [])
        for index, column in enumerate(columns):
            if index < len(fields) and fields[index].get("type") == "time":
                continue
            if any(v is not None for v in column):
                return True
    return False


def query_panel(panel: dict[str, Any], values: dict[str, str], grafana: Transport) -> dict[str, tuple[str, str]]:
    """{refId: (outcome, detail)} with outcome one of data, empty, error."""
    targets = [t for t in panel.get("targets", []) if not t.get("hide")]
    queries = []
    for target in targets:
        query = dict(target)
        query["datasource"] = target.get("datasource") or panel.get("datasource")
        if "expr" in query:
            query["expr"] = interpolate(query["expr"], values)
        query["maxDataPoints"] = MAX_DATA_POINTS
        queries.append(query)
    if not queries:
        return {}
    body = {"from": f"now-{RANGE}", "to": "now", "queries": queries}
    status, payload = grafana.request("POST", "/api/ds/query", body)
    results = payload.get("results", {}) if isinstance(payload, dict) else {}
    outcomes: dict[str, tuple[str, str]] = {}
    for query in queries:
        ref = query.get("refId", "A")
        result = results.get(ref)
        if result is None:
            outcomes[ref] = ("error", f"HTTP {status}: {_message(payload)}")
        elif result.get("error"):
            outcomes[ref] = ("error", str(result["error"]))
        elif has_data(result):
            outcomes[ref] = ("data", "")
        else:
            outcomes[ref] = ("empty", "")
    return outcomes


def check_dashboard(
    uid: str, grafana: Transport, report: Report, allowed: tuple[Allowed, ...], used: set[Allowed]
) -> None:
    status, payload = grafana.request("GET", f"/api/dashboards/uid/{uid}")
    if status != 200:
        report.fail(f"dashboard {uid}: HTTP {status}: {_message(payload)}")
        return
    dashboard = payload["dashboard"]
    title = dashboard.get("title", uid)
    values = resolve_variables(dashboard, grafana, report, title)
    checked = bad = 0
    for panel in iter_panels(dashboard.get("panels", [])):
        outcomes = query_panel(panel, values, grafana)
        if not outcomes:
            continue
        checked += 1
        ptitle = panel.get("title", f"panel {panel.get('id')}")
        excused = {a.ref_id: a for a in allowed if a.dashboard_uid == uid and a.panel_title == ptitle}
        panel_failures = []
        for ref, (outcome, detail) in sorted(outcomes.items()):
            if ref in excused:
                used.add(excused[ref])
            if outcome == "error":
                panel_failures.append(f"[{ref}] error: {detail}")
            elif outcome == "empty" and ref in excused:
                report.notes.append(f"{title} / {ptitle} [{ref}]: empty, allowed -- {excused[ref].reason}")
            elif outcome == "empty":
                panel_failures.append(f"[{ref}] no data")
        if not panel_failures and not any(o == "data" for o, _ in outcomes.values()):
            # Every query was excused, so the panel as a whole is blank: that is never allowed.
            panel_failures.append("no query in the panel returns data")
        for failure in panel_failures:
            report.fail(f"{title} / {ptitle} {failure}")
        bad += bool(panel_failures)
    report.notes.append(f"{title}: {checked - bad}/{checked} panels with data")


def run(
    grafana: Transport,
    expected_uids: set[str],
    folder: str = FOLDER,
    datasource_uid: str = DATASOURCE_UID,
    allowed: tuple[Allowed, ...] = ALLOWED_EMPTY,
) -> Report:
    report = Report()
    status, health = grafana.request("GET", f"/api/datasources/uid/{datasource_uid}/health")
    if status != 200 or not isinstance(health, dict) or health.get("status") != "OK":
        report.fail(f"datasource {datasource_uid} health: HTTP {status}: {_message(health)}")
    else:
        report.notes.append(f"datasource {datasource_uid} health: OK ({health.get('message', '')})")

    status, folders = grafana.request("GET", "/api/search?" + urlencode({"type": "dash-folder", "query": folder}))
    folder_uid = next(
        (f["uid"] for f in folders if f.get("title") == folder) if status == 200 and isinstance(folders, list) else (),
        None,
    )
    if folder_uid is None:
        report.fail(f"folder {folder!r} not found in Grafana (HTTP {status})")
        return report
    status, found = grafana.request("GET", "/api/search?" + urlencode({"type": "dash-db", "folderUIDs": folder_uid}))
    uids = sorted(d["uid"] for d in found) if status == 200 and isinstance(found, list) else []
    for missing in sorted(expected_uids - set(uids)):
        report.fail(f"committed dashboard {missing} is not in Grafana's {folder} folder")
    if not uids:
        report.fail(f"no dashboards in Grafana's {folder} folder")

    used: set[Allowed] = set()
    for uid in uids:
        check_dashboard(uid, grafana, report, allowed, used)
    checked = set(uids)
    for entry in allowed:
        if entry.dashboard_uid in checked and entry not in used:
            report.fail(
                f"allowlist entry matches no query: {entry.dashboard_uid} / {entry.panel_title} [{entry.ref_id}]"
            )
    return report


def committed_uids(directory: Path = DASHBOARD_DIR) -> set[str]:
    return {json.loads(p.read_text(encoding="utf-8"))["uid"] for p in sorted(directory.glob("*.json"))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://127.0.0.1:13000")
    parser.add_argument("--record", type=Path, help="write every exchange to this file (a test fixture)")
    parser.add_argument("--env-file", type=Path, default=REPO / ".env", help="where GRAFANA_ADMIN_PASSWORD is kept")
    args = parser.parse_args()

    password = os.environ.get("GRAFANA_ADMIN_PASSWORD", "")
    if not password:
        from solution_arista_avd.envfile import read_env

        password = read_env(args.env_file, "GRAFANA_ADMIN_PASSWORD")
    if not password:
        print("FAIL  GRAFANA_ADMIN_PASSWORD is neither set nor in .env", file=sys.stderr)
        return 1

    transport: Transport = HttpTransport(args.url, os.environ.get("GRAFANA_USER", "admin"), password)
    recorder = RecordingTransport(transport) if args.record else None
    report = run(recorder or transport, committed_uids())
    if recorder and args.record:
        recorder.write(args.record)

    for note in report.notes:
        print(f"      {note}")
    for failure in report.failures:
        print(f"      FAIL {failure}")
    return 1 if report.failures else 0


if __name__ == "__main__":
    sys.exit(main())
