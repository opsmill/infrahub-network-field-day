"""Where every service request is in the pipeline, as Prometheus series (cycle 035).

A request moves through stages nothing else reports together:

    requested     a service on a branch whose proposed change is open -- new,
                  changed, or deleted relative to main -- with its validators'
                  verdict (running, passed, failed)
    merged        on main, live, and not yet deployed
    deployed      on main, live, and every device the reconciler tracks has been
                  confirmed in sync SINCE the service last changed
    decommissioning  on main with status decommissioning or decommissioned
    removed       deleted from main within the last day

HEALTHY is not a stage this module decides: it is ``deployed`` and every check
the collector's artifact renders for the service passing, which only Prometheus
can join. The Services dashboard does that join.

**Why a purpose-built exporter rather than the Infrahub exporter.** The
Infrahub exporter reads one branch, configured once, and exports attributes of
one kind's nodes. A request lives on a branch that did not exist when anything
was configured, its verdict is on the proposed change's validators, its
deployment is in ``DeploymentState`` timestamps, and its removal is visible only
in ``InfrahubEvent``. None of those is a node attribute on main.

**It has no configuration of its own.** Which kinds it reports is the scrape's
``?kinds=`` parameter, and that scrape is rendered into the collector's artifact
from the ``service-lifecycle`` monitoring profile -- so turning lifecycle
reporting on for a kind is an Infrahub change, reviewed as an artifact diff,
like everything else the lab watches. It reports every kind it is asked for,
including a kind added after it was written: kinds are read from the graph.

**It reads as ``metrics-exporter``**, the view-only account the Infrahub
exporter already uses. It writes nothing, and nothing generates from what it
reports.

**"Deployed" is deliberately fleet-wide.** Which devices a service changes is
known only to the generators beneath it, so this asks the stronger question the
graph can answer: has every device been confirmed matching its artifact since
the service last changed? One device stuck unconfirmed holds every service at
``merged``, which is the honest reading -- the change may be on that device.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

WITHDRAWN = frozenset({"decommissioning", "decommissioned"})
ALL_KINDS = "ServiceGeneric"
REMOVED_WINDOW = 24 * 3600
EVENT_PAGE = 50  # the API's ceiling for InfrahubEvent

STAGE_LABELS = (
    "service_kind",
    "service",
    "owner",
    "requester",
    "stage",
    "status",
    "branch",
    "proposed_change",
    "change",
    "validation",
)

SERVICES_QUERY = """
query {
  ServiceGeneric {
    edges {
      node_metadata { created_at updated_at created_by { display_label } }
      node {
        id
        __typename
        name { value }
        status { value }
        owner { node { display_label } }
        ... on ServiceAppAccess { requester { value } }
      }
    }
  }
}
"""

MAIN_QUERY = """
query {
  Branch { name created_at }
  CoreProposedChange(state__value: "open") {
    edges {
      node_metadata { created_at }
      node {
        id
        name { value }
        source_branch { value }
        destination_branch { value }
        validations { edges { node { state { value } conclusion { value } } } }
      }
    }
  }
  DeploymentState {
    edges { node { name { value } status { value } suspend { value } last_confirmed_at { value } } }
  }
}
"""

EVENTS_QUERY = """
query ($since: DateTime, $offset: Int) {
  InfrahubEvent(
    limit: 50, offset: $offset, since: $since, branches: ["main"],
    event_type: ["infrahub.node.created", "infrahub.node.updated", "infrahub.node.deleted",
                 "infrahub.proposed_change.merged"]
  ) {
    edges {
      node {
        id
        event
        occurred_at
        primary_node { id kind }
        ... on NodeMutatedEvent { attributes { name value } }
      }
    }
  }
}
"""

PROPOSED_CHANGES_QUERY = """
query ($ids: [ID]) {
  CoreProposedChange(ids: $ids) { edges { node { id name { value } source_branch { value } } } }
}
"""

HELP: dict[str, str] = {
    "otternet_service_stage": "1 for each service at each stage of the request pipeline it is in.",
    "otternet_service_stage_since_timestamp_seconds": "When the service entered the stage.",
    "otternet_service_deploy_pending_devices": "Devices not yet confirmed in sync since the service last changed.",
    "otternet_service_event_timestamp_seconds": "When a service was created, changed status or was deleted on main.",
    "otternet_proposed_change_merged_timestamp_seconds": "When a proposed change merged into main.",
    "otternet_service_lifecycle_kinds": "The service kinds this scrape asked for.",
    "otternet_service_lifecycle_up": "1 when the last poll of Infrahub succeeded.",
    "otternet_service_lifecycle_poll_timestamp_seconds": "When the last successful poll finished.",
    "otternet_service_lifecycle_poll_errors_total": "Polls of Infrahub that failed since the exporter started.",
}


def parse_time(value: Any) -> float | None:
    """An Infrahub timestamp as epoch seconds, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.timestamp()


@dataclass(frozen=True)
class Service:
    id: str
    kind: str
    name: str
    status: str
    owner: str
    requester: str
    changed_at: float | None
    created_at: float | None


@dataclass(frozen=True)
class Sample:
    metric: str
    labels: tuple[tuple[str, str], ...]
    value: float

    def kind(self) -> str | None:
        return dict(self.labels).get("service_kind")


def services_from(data: dict[str, Any]) -> dict[str, Service]:
    """Service id -> Service, from a SERVICES_QUERY response."""
    found: dict[str, Service] = {}
    for edge in (data.get("ServiceGeneric") or {}).get("edges") or []:
        node, meta = edge.get("node") or {}, edge.get("node_metadata") or {}
        if not node.get("id"):
            continue
        requester = ((node.get("requester") or {}).get("value")) or (
            ((meta.get("created_by") or {}).get("display_label")) or ""
        )
        found[node["id"]] = Service(
            id=node["id"],
            kind=str(node.get("__typename") or ""),
            name=str((node.get("name") or {}).get("value") or ""),
            status=str((node.get("status") or {}).get("value") or ""),
            owner=str(((node.get("owner") or {}).get("node") or {}).get("display_label") or ""),
            requester=str(requester),
            changed_at=parse_time(meta.get("updated_at")),
            created_at=parse_time(meta.get("created_at")),
        )
    return found


def validation_of(pc: dict[str, Any]) -> str:
    """One word for a proposed change's validators: failed, running, passed or pending."""
    validators = [e["node"] for e in (pc.get("validations") or {}).get("edges") or [] if e.get("node")]
    if not validators:
        return "pending"
    if any((v.get("conclusion") or {}).get("value") == "failure" for v in validators):
        return "failed"
    if any((v.get("state") or {}).get("value") != "completed" for v in validators):
        return "running"
    return "passed"


@dataclass
class State:
    """What the exporter remembers between polls: names of the departed, and when stages began."""

    names: dict[str, tuple[str, str]] = field(default_factory=dict)  # id -> (kind, name)
    # event id -> (time, kind, name, event, status, node id)
    events: dict[str, tuple[float, str, str, str, str, str]] = field(default_factory=dict)
    merged: dict[str, tuple[float, str, str]] = field(default_factory=dict)  # event id -> (t, pc, branch)
    first_seen: dict[tuple[str, str, str], float] = field(default_factory=dict)  # (id, stage, branch) -> t
    pc_names: dict[str, tuple[str, str]] = field(default_factory=dict)  # pc id -> (name, branch)
    kinds: set[str] = field(default_factory=set)
    events_since: float | None = None


def absorb_events(state: State, edges: list[dict[str, Any]], kinds: set[str]) -> list[str]:
    """Fold InfrahubEvent edges into the state; returns proposed-change ids whose names are unknown.

    OLDEST FIRST, whatever order they arrive in: the API returns newest first,
    and a deletion carries no attributes -- its name is known only from the
    creation that preceded it. A kind is a service kind if it is one the graph
    reported, or if its creation carried a `status` and a `name`, which is how a
    grant created and deleted between two polls is still reported.
    """
    unknown_pcs: list[str] = []
    ordered = sorted(edges, key=lambda e: parse_time((e.get("node") or {}).get("occurred_at")) or 0.0)
    for edge in ordered:
        node = edge.get("node") or {}
        present = {a.get("name") for a in node.get("attributes") or [] if a.get("value") is not None}
        kind = str((node.get("primary_node") or {}).get("kind") or "")
        if (
            node.get("event") == "infrahub.node.created"
            and kind.startswith("Service")
            and {"name", "status"} <= present
        ):
            kinds.add(kind)
            state.kinds.add(kind)
    kinds |= state.kinds
    for edge in ordered:
        event = edge.get("node") or {}
        primary = event.get("primary_node") or {}
        when = parse_time(event.get("occurred_at"))
        if when is None or not event.get("id"):
            continue
        if event.get("event") == "infrahub.proposed_change.merged":
            pc_id = str(primary.get("id") or "")
            name, branch = state.pc_names.get(pc_id, ("", ""))
            if not name:
                unknown_pcs.append(pc_id)
            state.merged[event["id"]] = (when, pc_id, branch)
            continue
        kind = str(primary.get("kind") or "")
        if kind not in kinds:
            continue
        attrs = {a.get("name"): a.get("value") for a in event.get("attributes") or []}
        node_id = str(primary.get("id") or "")
        if attrs.get("name"):
            state.names[node_id] = (kind, str(attrs["name"]))
        name = state.names.get(node_id, (kind, f"id:{node_id[:8]}"))[1]
        verb = {"infrahub.node.created": "created", "infrahub.node.deleted": "deleted"}.get(event["event"], "status")
        status = str(attrs.get("status") or "")
        if verb == "status" and not status:
            continue  # an update that did not touch status is not a lifecycle event
        state.events[event["id"]] = (when, kind, name, verb, status, node_id)
    return unknown_pcs


def build(  # noqa: C901 - one snapshot from four sources
    *,
    main: dict[str, Service],
    branches: dict[str, dict[str, Service]],
    open_changes: list[dict[str, Any]],
    deployment: list[dict[str, Any]],
    state: State,
    now: float,
    branch_created: dict[str, float] | None = None,
) -> list[Sample]:
    """Every series, for every kind; the scrape filters by kind afterwards."""
    samples: list[Sample] = []

    def stage(service: Service, stage_name: str, since: float | None, **extra: str) -> None:
        labels = {
            "service_kind": service.kind,
            "service": service.name,
            "owner": service.owner,
            "requester": service.requester,
            "stage": stage_name,
            "status": service.status,
            "branch": extra.get("branch", "main"),
            "proposed_change": extra.get("proposed_change", ""),
            "change": extra.get("change", ""),
            "validation": extra.get("validation", ""),
        }
        key = (service.id, stage_name, labels["branch"])
        first = state.first_seen.setdefault(key, now)
        samples.append(Sample("otternet_service_stage", tuple((k, labels[k]) for k in STAGE_LABELS), 1))
        samples.append(
            Sample(
                "otternet_service_stage_since_timestamp_seconds",
                (
                    ("service_kind", service.kind),
                    ("service", service.name),
                    ("stage", stage_name),
                    ("branch", labels["branch"]),
                ),
                since if since is not None else first,
            )
        )

    for service in main.values():
        state.names[service.id] = (service.kind, service.name)

    records = [e["node"] for e in deployment if e.get("node")]
    tracked = [r for r in records if not (r.get("suspend") or {}).get("value")]
    # When each service last changed on main: its metadata, or the latest event
    # about it, whichever is later. The metadata alone can lag -- see below.
    last_event: dict[str, float] = {}
    for when, _kind, _name, _verb, _status, node_id in state.events.values():
        last_event[node_id] = max(last_event.get(node_id, 0.0), when)
    main = {
        sid: Service(
            **{**service.__dict__, "changed_at": max(service.changed_at or 0.0, last_event.get(sid, 0.0)) or None}
        )
        for sid, service in main.items()
    }
    for service in sorted(main.values(), key=lambda s: (s.kind, s.name)):
        if service.status in WITHDRAWN:
            stage(service, "decommissioning", service.changed_at)
            continue
        pending = 0
        for record in tracked:
            confirmed = parse_time((record.get("last_confirmed_at") or {}).get("value"))
            in_sync = (record.get("status") or {}).get("value") == "in_sync"
            if not in_sync or confirmed is None or (service.changed_at is not None and confirmed < service.changed_at):
                pending += 1
        samples.append(
            Sample(
                "otternet_service_deploy_pending_devices",
                (("service_kind", service.kind), ("service", service.name)),
                pending,
            )
        )
        if pending:
            stage(service, "merged", service.changed_at)
        else:
            stage(service, "deployed", None)

    for edge in open_changes:
        pc, meta = edge.get("node") or {}, edge.get("node_metadata") or {}
        branch = str((pc.get("source_branch") or {}).get("value") or "")
        if (pc.get("destination_branch") or {}).get("value") not in (None, "main") or branch not in branches:
            continue
        pc_name = str((pc.get("name") or {}).get("value") or "")
        state.pc_names[str(pc.get("id"))] = (pc_name, branch)
        verdict = validation_of(pc)
        opened = parse_time(meta.get("created_at"))
        ours = branches[branch]
        cut = (branch_created or {}).get(branch)
        for service_id, service in sorted(ours.items(), key=lambda kv: (kv[1].kind, kv[1].name)):
            before = main.get(service_id)
            if before is None:
                change = "create"
            elif before.status != service.status or _changed_on_branch(service, before, cut):
                change = "update"
            else:
                continue
            stage(
                service, "requested", opened, branch=branch, proposed_change=pc_name, change=change, validation=verdict
            )
        # A deletion only if the service predates the branch: one created on
        # main afterwards is simply not visible from a branch cut before it.
        for service_id, service in main.items():
            if service_id not in ours and (cut is None or (service.created_at or 0) < cut):
                stage(
                    service,
                    "requested",
                    opened,
                    branch=branch,
                    proposed_change=pc_name,
                    change="delete",
                    validation=verdict,
                )

    live_names = {(s.kind, s.name) for s in main.values()}
    for event_id, (when, kind, name, verb, status, _node) in sorted(state.events.items(), key=lambda kv: kv[1][0]):
        if now - when > REMOVED_WINDOW:
            del state.events[event_id]
            continue
        samples.append(
            Sample(
                "otternet_service_event_timestamp_seconds",
                (("service_kind", kind), ("service", name), ("event", verb), ("status", status)),
                when,
            )
        )
    removed: dict[tuple[str, str], float] = {}
    for when, kind, name, verb, _status, _node in state.events.values():
        if verb == "deleted" and (kind, name) not in live_names:
            removed[kind, name] = max(removed.get((kind, name), 0.0), when)
    for (kind, name), when in sorted(removed.items()):
        gone = Service(id=f"removed:{kind}:{name}", kind=kind, name=name, status="", owner="", requester="",
                       changed_at=when, created_at=None)  # fmt: skip
        stage(gone, "removed", when)
    for event_id, (when, pc_id, branch) in list(state.merged.items()):
        if now - when > REMOVED_WINDOW:
            del state.merged[event_id]
            continue
        name, known_branch = state.pc_names.get(pc_id, (f"id:{pc_id[:8]}", branch))
        samples.append(
            Sample(
                "otternet_proposed_change_merged_timestamp_seconds",
                (("proposed_change", name), ("branch", known_branch or branch)),
                when,
            )
        )
    return samples


def _changed_on_branch(ours: Service, main: Service, cut: float | None) -> bool:
    """Whether a service was edited on the branch, not merely visible from it.

    NOT a comparison of the two `node_metadata.updated_at` values: they disagree
    for a node neither side changed (measured: main still reporting an L3VPN's
    creation time while the branch reported the update 93 s later, which made
    every service on a fresh branch an "update"). The branch's own timestamp is
    trusted only when it is later than the branch itself, and later than the
    last change main knows of -- main's metadata or its last event, whichever is
    later, which is what `main.changed_at` already is.
    """
    if cut is None or ours.changed_at is None:
        return False
    return ours.changed_at > cut and ours.changed_at > (main.changed_at or 0.0) + 1


def render(samples: list[Sample], kinds: set[str] | None, up: bool, polled_at: float, errors: int) -> str:
    """Prometheus text format, keeping service series only for the kinds asked for."""
    wanted = None if not kinds or ALL_KINDS in kinds else kinds
    selected = [s for s in samples if s.kind() is None or wanted is None or s.kind() in wanted]
    selected += [
        Sample("otternet_service_lifecycle_kinds", (("service_kind", k),), 1) for k in sorted(kinds or {ALL_KINDS})
    ]
    selected += [
        Sample("otternet_service_lifecycle_up", (), 1 if up else 0),
        Sample("otternet_service_lifecycle_poll_timestamp_seconds", (), polled_at),
        Sample("otternet_service_lifecycle_poll_errors_total", (), errors),
    ]
    lines: list[str] = []
    for metric, help_text in HELP.items():
        rows = [s for s in selected if s.metric == metric]
        kind = "counter" if metric.endswith("_total") else "gauge"
        lines += [f"# HELP {metric} {help_text}", f"# TYPE {metric} {kind}"]
        for sample in sorted(set(rows), key=lambda s: s.labels):
            body = ",".join(f'{k}="{_escape(v)}"' for k, v in sample.labels)
            value = int(sample.value) if float(sample.value).is_integer() else sample.value
            lines.append(f"{metric}{{{body}}} {value}" if body else f"{metric} {value}")
    return "\n".join(lines) + "\n"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class Exporter:
    """Polls Infrahub on a timer and holds the latest snapshot for the HTTP handler."""

    def __init__(self, gql: Any, poll_seconds: float = 15) -> None:
        self.gql = gql
        self.poll_seconds = poll_seconds
        self.state = State()
        self.samples: list[Sample] = []
        self.up = False
        self.polled_at = 0.0
        self.errors = 0
        self.last_error = ""
        self.lock = threading.Lock()

    def poll(self, now: float | None = None) -> None:
        now = time.time() if now is None else now
        main = services_from(self.gql(SERVICES_QUERY, {}, "main"))
        rest = self.gql(MAIN_QUERY, {}, "main")
        open_changes = (rest.get("CoreProposedChange") or {}).get("edges") or []
        branches: dict[str, dict[str, Service]] = {}
        for edge in open_changes:
            branch = str(((edge.get("node") or {}).get("source_branch") or {}).get("value") or "")
            if branch and branch != "main" and branch not in branches:
                try:
                    branches[branch] = services_from(self.gql(SERVICES_QUERY, {}, branch))
                except RuntimeError:
                    continue  # a branch deleted between the two queries
        kinds = {s.kind for s in main.values()} | {s.kind for b in branches.values() for s in b.values()}
        kinds |= {kind for kind, _ in self.state.names.values()}
        since = self.state.events_since if self.state.events_since is not None else now - REMOVED_WINDOW
        collected: list[dict[str, Any]] = []
        for page in range(200):
            edges = (self.gql(EVENTS_QUERY, {"since": _iso(since - 5), "offset": page * EVENT_PAGE}, "main")
                     .get("InfrahubEvent") or {}).get("edges") or []  # fmt: skip
            collected += edges
            if len(edges) < EVENT_PAGE:
                break
        unknown = absorb_events(self.state, collected, kinds)
        if unknown:
            found = self.gql(PROPOSED_CHANGES_QUERY, {"ids": sorted(set(unknown))}, "main")
            for edge in (found.get("CoreProposedChange") or {}).get("edges") or []:
                node = edge.get("node") or {}
                self.state.pc_names[str(node.get("id"))] = (
                    str((node.get("name") or {}).get("value") or ""),
                    str((node.get("source_branch") or {}).get("value") or ""),
                )
        self.state.events_since = now
        samples = build(
            main=main,
            branches=branches,
            open_changes=open_changes,
            deployment=(rest.get("DeploymentState") or {}).get("edges") or [],
            state=self.state,
            now=now,
            branch_created={
                str(b.get("name")): created
                for b in rest.get("Branch") or []
                if (created := parse_time(b.get("created_at"))) is not None
            },
        )
        with self.lock:
            self.samples, self.up, self.polled_at = samples, True, now

    def poll_safely(self) -> None:
        """A failed poll keeps the last snapshot and says so, rather than reporting every service gone."""
        try:
            self.poll()
        except Exception as exc:  # noqa: BLE001 - any failure is a failed poll, reported as a series
            with self.lock:
                self.up = False
                self.errors += 1
                self.last_error = f"{type(exc).__name__}: {exc}"

    def metrics(self, kinds: set[str] | None) -> str:
        with self.lock:
            return render(self.samples, kinds, self.up, self.polled_at, self.errors)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()
