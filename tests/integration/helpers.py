"""Shared helpers for the integration tests.

A bounded-wait poller with diagnostic failure messages, plus the generator and
artifact name constants sourced from ``.infrahub.yml`` so the tests and the
repository definition cannot drift apart.
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, TypeVar

from infrahub_sdk.exceptions import GraphQLError
from infrahub_sdk.task.models import TaskFilter, TaskState

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from infrahub_sdk import InfrahubClient

T = TypeVar("T")

# --- Generator definition names (from .infrahub.yml `generator_definitions`) ---
GENERATOR_FABRIC = "generate-fabric"
GENERATOR_POD = "generate-pod"
GENERATOR_RACK = "generate-rack"
GENERATOR_SERVER_CABLING = "generate-server-cabling"
GENERATOR_AVD_HOSTVAR = "generate-avd-device-hostvar"
GENERATOR_AVD_STRUCTURED_CONFIG = "generate-avd-device-structured-config"
GENERATOR_BACKFILL = "backfill-structured-config"

# --- Artifact instance names (from .infrahub.yml `artifact_definitions` -> `artifact_name`) ---
ARTIFACT_CABLING_PLAN = "Cabling Plan"
ARTIFACT_AVD_EOS_CONFIG = "AVD EOS Configuration"
ARTIFACT_AVD_FABRIC_DOC = "AVD Fabric Documentation"
ARTIFACT_AVD_DEVICE_DOC = "AVD Device Documentation"
ARTIFACT_AVD_ANTA_CATALOG = "AVD ANTA Catalog"
ARTIFACT_CONTAINERLAB_TOPOLOGY = "ContainerLab Topology"

ALL_ARTIFACT_NAMES = [
    ARTIFACT_CABLING_PLAN,
    ARTIFACT_AVD_EOS_CONFIG,
    ARTIFACT_AVD_FABRIC_DOC,
    ARTIFACT_AVD_DEVICE_DOC,
    ARTIFACT_AVD_ANTA_CATALOG,
    ARTIFACT_CONTAINERLAB_TOPOLOGY,
]

# Marker the ANTA transform emits when the fabric has ANTA disabled
# (transforms/avd_anta_catalog.py). Used to assert the catalog is *populated*.
ANTA_DISABLED_MARKER = "# ANTA disabled"

# Default bounded-wait budgets (seconds). Kept generous for CI runners.
SCHEMA_TIMEOUT = 120
OBJECT_LOAD_TIMEOUT = 300
GROUP_TIMEOUT = 60
REPO_SYNC_INTERVAL = 10
REPO_SYNC_RETRIES = 60  # 10s * 60 = 600s
GENERATOR_TIMEOUT = 600
ARTIFACT_TIMEOUT = 600
POLL_INTERVAL = 10


def _summarize(value: Any) -> str:
    """Render an observed value compactly for a diagnostic failure message."""
    if isinstance(value, (list, tuple, set)):
        return f"{type(value).__name__} of length {len(value)}"
    if isinstance(value, dict):
        compact = repr(value)
        if len(compact) <= 500:
            return compact
        return f"dict with keys {sorted(value)[:10]}"
    text = repr(value)
    return text if len(text) <= 200 else f"{text[:200]}..."


async def wait_until(
    fetch: Callable[[], Awaitable[T]],
    ready: Callable[[T], bool],
    *,
    timeout: int,  # noqa: ASYNC109 (deliberate polling budget, not an asyncio.timeout scope)
    interval: int,
    describe: str,
) -> T:
    """Poll ``fetch`` until ``ready`` is satisfied or ``timeout`` elapses.

    Returns the observed value once ``ready(value)`` is truthy. On timeout raises
    ``AssertionError`` including the last observed value, so the failing stage is
    diagnosable without a rerun.
    """
    deadline = time.monotonic() + timeout
    last: Any = None
    while True:
        try:
            last = await fetch()
        except GraphQLError as exc:
            last = exc
        else:
            if ready(last):
                return last
        if time.monotonic() >= deadline:
            msg = f"{describe}: timed out after {timeout}s; last observed: {_summarize(last)}"
            raise AssertionError(msg)
        await asyncio.sleep(interval)


# Task states that mean "not finished yet".
ACTIVE_TASK_STATES = [
    TaskState.SCHEDULED,
    TaskState.PENDING,
    TaskState.RUNNING,
    TaskState.PAUSED,
    TaskState.CANCELLING,
]

# Prefect workflow that turns CoreNodeTriggerRule/CoreAction objects into live
# automations. One run per saved trigger object, so loading triggers.yml queues
# well over a hundred of them.
WORKFLOW_CONFIGURE_ACTION_RULES = "configure-action-rules"
TRIGGER_SETUP_TIMEOUT = 300
TRIGGER_SETUP_STABLE_SAMPLES = 3


async def wait_for_workflow_quiet(
    client: InfrahubClient,
    *,
    workflow: str,
    timeout: int,  # noqa: ASYNC109 (deliberate polling budget, not an asyncio.timeout scope)
    interval: int,
    stable_samples: int,
    describe: str,
) -> int:
    """Wait until ``workflow`` has run at least once and has nothing left in flight.

    Both halves matter. "Nothing active" alone succeeds at t=0, before the first
    run has even been queued. So this requires at least one run, no active run,
    and an unchanged total over ``stable_samples`` consecutive samples -- a run
    queued between two samples resets the count. Returns the total observed.
    """
    deadline = time.monotonic() + timeout
    previous_total: int | None = None
    stable = 0
    last: dict[str, int] = {}
    while True:
        total = await client.task.count(filters=TaskFilter(workflow=[workflow]))
        active = await client.task.count(filters=TaskFilter(workflow=[workflow], state=ACTIVE_TASK_STATES))
        last = {"total": total, "active": active}
        if total > 0 and active == 0 and total == previous_total:
            stable += 1
            if stable >= stable_samples:
                return total
        else:
            stable = 0
        previous_total = total
        if time.monotonic() >= deadline:
            msg = f"{describe}: timed out after {timeout}s; last observed: {last}"
            raise AssertionError(msg)
        await asyncio.sleep(interval)
