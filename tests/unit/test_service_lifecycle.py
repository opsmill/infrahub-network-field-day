"""The service-lifecycle exporter: where every request is in the pipeline (cycle 035).

Each stage is a claim the Services dashboard and the demo rehearsal rely on, and
each one was got wrong once while measuring it against the live lab:

* a service unchanged on a branch was reported as an UPDATE, because
  ``node_metadata.updated_at`` disagrees between main and a branch for a node
  neither changed -- so a branch's request is compared on status only;
* a deletion carries no attributes, and events arrive newest first, so a removed
  grant was reported nameless until events were folded oldest first;
* a grant created and deleted between two polls is of a kind no live service
  has, and was dropped until a creation carrying `name` and `status` was taken
  as declaring a service kind.

No running lab: the GraphQL responses are built here, in the shapes measured.
"""

from __future__ import annotations

from typing import Any

from solution_arista_avd.service_lifecycle import (
    SERVICES_QUERY,
    Exporter,
    State,
    absorb_events,
    build,
    parse_time,
    render,
    services_from,
    validation_of,
)

T0 = "2026-10-02T10:00:00+00:00"
T1 = "2026-10-02T10:05:00+00:00"
T2 = "2026-10-02T10:10:00+00:00"
NOW = parse_time("2026-10-02T10:20:00+00:00") or 0.0


def _svc(
    sid: str, kind: str, name: str, status: str = "active", updated: str = T0, requester: str | None = None
) -> dict[str, Any]:
    node: dict[str, Any] = {
        "id": sid,
        "__typename": kind,
        "name": {"value": name},
        "status": {"value": status},
        "owner": {"node": {"display_label": "branch"}},
    }
    if requester is not None:
        node["requester"] = {"value": requester}
    return {
        "node_metadata": {"created_at": T0, "updated_at": updated, "created_by": {"display_label": "Admin"}},
        "node": node,
    }


def _services(*edges: dict[str, Any]) -> dict[str, Any]:
    return {"ServiceGeneric": {"edges": list(edges)}}


def _record(name: str, status: str = "in_sync", confirmed: str = T2, suspend: bool = False) -> dict[str, Any]:
    return {
        "node": {
            "name": {"value": name},
            "status": {"value": status},
            "suspend": {"value": suspend},
            "last_confirmed_at": {"value": confirmed},
        }
    }


def _pc(branch: str, *verdicts: tuple[str, str]) -> dict[str, Any]:
    return {
        "node_metadata": {"created_at": T1},
        "node": {
            "id": f"pc-{branch}",
            "name": {"value": f"Implement {branch}"},
            "source_branch": {"value": branch},
            "destination_branch": {"value": "main"},
            "validations": {
                "edges": [{"node": {"state": {"value": s}, "conclusion": {"value": c}}} for s, c in verdicts]
            },
        },
    }


def _stages(samples: list[Any]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (dict(s.labels)["service"], dict(s.labels)["stage"]): dict(s.labels)
        for s in samples
        if s.metric == "otternet_service_stage"
    }


MAIN = services_from(
    _services(
        _svc("a", "ServiceFabricApp", "otternet-demo"),
        _svc("b", "ServiceL3vpn", "acme-l3vpn", updated=T2),
        _svc("c", "ServiceAppAccess", "old-grant", status="decommissioning", requester="alice@otternet.lab"),
    )
)


def test_a_service_is_deployed_only_once_every_device_is_confirmed_since_it_changed() -> None:
    samples = build(
        main=MAIN,
        branches={},
        open_changes=[],
        deployment=[_record("leaf1", confirmed=T1), _record("fw1", confirmed=T2)],
        state=State(),
        now=NOW,
    )
    stages = _stages(samples)
    assert ("otternet-demo", "deployed") in stages, "changed at T0, every device confirmed after"
    assert ("acme-l3vpn", "merged") in stages, "changed at T2, leaf1 last confirmed at T1"
    pending = {
        dict(s.labels)["service"]: s.value for s in samples if s.metric == "otternet_service_deploy_pending_devices"
    }
    assert pending == {"otternet-demo": 0, "acme-l3vpn": 1}


def test_a_device_not_in_sync_holds_every_service_at_merged_unless_suspended() -> None:
    held = _stages(
        build(
            main=MAIN,
            branches={},
            open_changes=[],
            deployment=[_record("fw1", status="drifted")],
            state=State(),
            now=NOW,
        )
    )
    assert ("otternet-demo", "merged") in held
    suspended = [_record("fw1", status="drifted", suspend=True)]
    assert ("otternet-demo", "deployed") in _stages(
        build(main=MAIN, branches={}, open_changes=[], deployment=suspended, state=State(), now=NOW)
    )


def test_decommissioning_is_its_own_stage_and_requester_is_the_grants_own() -> None:
    stages = _stages(build(main=MAIN, branches={}, open_changes=[], deployment=[], state=State(), now=NOW))
    assert stages["old-grant", "decommissioning"]["requester"] == "alice@otternet.lab"
    assert stages["otternet-demo", "deployed"]["requester"] == "Admin", "elsewhere, who created it"


def test_a_request_is_a_branch_with_an_open_change_compared_with_main_on_status() -> None:
    branch = services_from(
        _services(
            # unchanged, but the branch's metadata disagrees with main's (measured)
            _svc("a", "ServiceFabricApp", "otternet-demo", updated=T2),
            _svc("b", "ServiceL3vpn", "acme-l3vpn", status="decommissioning", updated=T2),
            _svc("d", "ServiceAppAccess", "grafana-x", requester="alice@otternet.lab"),
            # "c" is absent: deleted on the branch
        )
    )
    samples = build(
        main=MAIN,
        branches={"implement_grafana-x": branch},
        open_changes=[_pc("implement_grafana-x", ("completed", "success"), ("in_progress", "unknown"))],
        deployment=[],
        state=State(),
        now=NOW,
        branch_created={"implement_grafana-x": NOW - 60},
    )
    requested = {k[0]: v for k, v in _stages(samples).items() if k[1] == "requested"}
    assert {name: r["change"] for name, r in requested.items()} == {
        "grafana-x": "create",
        "acme-l3vpn": "update",
        "old-grant": "delete",
    }
    assert {r["validation"] for r in requested.values()} == {"running"}
    assert requested["grafana-x"]["proposed_change"] == "Implement implement_grafana-x"
    assert requested["grafana-x"]["requester"] == "alice@otternet.lab"
    since = {
        dict(s.labels)["service"]: s.value
        for s in samples
        if s.metric == "otternet_service_stage_since_timestamp_seconds" and dict(s.labels)["stage"] == "requested"
    }
    assert since["grafana-x"] == parse_time(T1), "a request is as old as its proposed change"


def test_a_service_created_on_main_after_the_branch_is_not_a_deletion() -> None:
    samples = build(
        main=MAIN,
        branches={"late": {}},
        open_changes=[_pc("late")],
        deployment=[],
        state=State(),
        now=NOW,
        branch_created={"late": (parse_time(T0) or 0) - 1},
    )
    assert not [k for k in _stages(samples) if k[1] == "requested"]


def test_validators_reduce_to_one_word() -> None:
    def pc(*v: tuple[str, str]) -> dict[str, Any]:
        return _pc("x", *v)["node"]

    assert validation_of(pc()) == "pending"
    assert validation_of(pc(("completed", "success"), ("completed", "failure"))) == "failed"
    assert validation_of(pc(("completed", "success"), ("in_progress", "unknown"))) == "running"
    assert validation_of(pc(("completed", "success"))) == "passed"


def _event(eid: str, verb: str, kind: str, node: str, when: str, **attrs: Any) -> dict[str, Any]:
    names = ("name", "status") if verb == "infrahub.node.deleted" else tuple(attrs)
    return {
        "node": {
            "id": eid,
            "event": verb,
            "occurred_at": when,
            "primary_node": {"id": node, "kind": kind},
            "attributes": [{"name": n, "value": attrs.get(n)} for n in names],
        }
    }


def test_a_grant_created_and_removed_between_polls_is_reported_by_name() -> None:
    """Newest first, as the API returns them; a kind no live service has."""
    state = State()
    edges = [
        _event("e3", "infrahub.node.deleted", "ServiceAppAccess", "g", T2),
        _event("e2", "infrahub.node.updated", "ServiceAppAccess", "g", T1, status="decommissioned"),
        _event("e1", "infrahub.node.created", "ServiceAppAccess", "g", T0, name="grafana-x", status="active"),
        _event("e0", "infrahub.node.created", "ServiceFabricAppValuesFile", "v", T0, name="values.yaml"),
        _event("eu", "infrahub.node.updated", "ServiceFabricApp", "a", T1, description="unrelated"),
    ]
    absorb_events(state, edges, {"ServiceFabricApp"})
    samples = build(main=MAIN, branches={}, open_changes=[], deployment=[], state=state, now=NOW)
    events = sorted(
        (dict(s.labels)["event"], dict(s.labels)["service"], dict(s.labels)["status"])
        for s in samples
        if s.metric == "otternet_service_event_timestamp_seconds"
    )
    assert events == [
        ("created", "grafana-x", "active"),
        ("deleted", "grafana-x", ""),
        ("status", "grafana-x", "decommissioned"),
    ]
    assert ("grafana-x", "removed") in _stages(samples)


def test_the_scrape_filters_service_series_by_kind_and_says_which_it_asked_for() -> None:
    samples = build(main=MAIN, branches={}, open_changes=[], deployment=[], state=State(), now=NOW)
    text = render(samples, {"ServiceL3vpn"}, True, NOW, 0)
    assert 'service="acme-l3vpn"' in text
    assert 'service="otternet-demo"' not in text
    assert 'otternet_service_lifecycle_kinds{service_kind="ServiceL3vpn"} 1' in text
    every = render(samples, {"ServiceGeneric"}, True, NOW, 0)
    assert 'service="otternet-demo"' in every
    assert "# TYPE otternet_service_lifecycle_poll_errors_total counter" in every


def test_a_failed_poll_keeps_the_last_snapshot_and_says_so() -> None:
    """The Infrahub exporter empties a kind's series when a fetch fails, which reads
    exactly like every service being deleted. This one does not."""
    calls = {"n": 0}

    def gql(query: str, _variables: dict[str, Any], _branch: str) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] > 3:
            raise RuntimeError("Infrahub went away")
        if query == SERVICES_QUERY:
            return _services(_svc("a", "ServiceFabricApp", "otternet-demo"))
        return {}

    exporter = Exporter(gql)
    exporter.poll_safely()
    assert exporter.up
    assert 'service="otternet-demo"' in exporter.metrics(None)
    exporter.poll_safely()
    assert not exporter.up
    assert exporter.errors == 1
    text = exporter.metrics(None)
    assert 'service="otternet-demo"' in text
    assert "otternet_service_lifecycle_up 0" in text


def test_an_edit_on_the_branch_that_leaves_status_alone_is_still_a_request() -> None:
    """Act four's broken isolation adds a circuit to an L3VPN and touches nothing
    else: the branch's timestamp is later than the branch and than main's."""
    edited = "2026-10-02T10:19:30+00:00"
    branch = services_from(_services(_svc("b", "ServiceL3vpn", "acme-l3vpn", updated=edited)))
    samples = build(
        main={"b": MAIN["b"]},
        branches={"demo-broken-isolation": branch},
        open_changes=[_pc("demo-broken-isolation", ("completed", "failure"))],
        deployment=[],
        state=State(),
        now=NOW,
        branch_created={"demo-broken-isolation": NOW - 60},
    )
    row = _stages(samples)["acme-l3vpn", "requested"]
    assert (row["change"], row["validation"]) == ("update", "failed")
