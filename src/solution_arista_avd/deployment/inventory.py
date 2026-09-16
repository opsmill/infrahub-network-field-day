"""The Nornir layer: one inventory from Infrahub, device work in parallel.

**Where the thread boundary sits is the whole design of this module.**

Nornir runs hosts in a `ThreadPoolExecutor`. The Infrahub SDK is async, and its
client context is a contextvar bound to the running task -- so anything that
touches Infrahub from inside a Nornir task would have to hand-propagate that
context into worker threads. The design review measured exactly this and
recorded it: a per-host heartbeat written from inside a Nornir task "does not
survive contact".

So nothing here touches Infrahub. A Nornir task does device I/O only, using the
functions in `devices` and `compare`, all of which are synchronous already --
`httpx.post` and `subprocess.run`, never `await`. Results come back as plain
data, and the caller writes deployment state afterwards, in its own async
context, one device at a time. The thread pool is used for the part that is
genuinely I/O-bound against fourteen boxes, and for nothing else.

Two things this does NOT parallelise, both deliberately:

* **The firewall.** Comparing it takes an exclusive configuration lock, so it
  runs on its own, after everything else.
* **Writing state.** Ordering the writes costs nothing next to the device I/O,
  and keeping them sequential keeps them in one async context.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from nornir import InitNornir
from nornir.core.filter import F
from nornir.core.task import Result, Task

from solution_arista_avd.deployment import compare as cmp
from solution_arista_avd.deployment import devices as dv

if TYPE_CHECKING:
    from nornir.core import Nornir

# The group every AVD-rendered switch belongs to, and the two the rest use.
# `objects/00_groups.yml` seeds all three, so `nornir-infrahub` builds them from
# each node's `member_of_groups` with nothing extra to configure.
GROUP_EOS = "avd_devices"
GROUP_FRR = "frr_routers"
GROUP_JUNOS = "junos_firewalls"

DEFAULT_WORKERS = 10
"""Enough to cover the fabric in one pass without opening a session on every
switch at once. The firewall is excluded from this entirely."""


@dataclass
class DeviceOutcome:
    """What one device's turn produced. Plain data, safe to cross a thread."""

    device: str
    differs: bool = False
    pushed: bool = False
    failed: bool = False
    error: str | None = None
    diff: str = ""
    checksum: str = ""


def build_inventory(branch: str = "", workers: int = DEFAULT_WORKERS) -> Nornir:
    """An inventory of every device Infrahub models, grouped as Infrahub groups it.

    `host_node` is `DcimGenericDevice` rather than a concrete kind. The four
    device kinds are siblings, so naming one would silently return only that
    kind -- the same failure that hid the cabling plan's missing cables for
    months. `mgmt_ip__address` is a legal single-hop schema mapping, and is the
    only address any of these devices carries.
    """
    return InitNornir(
        runner={"plugin": "threaded", "options": {"num_workers": workers}},
        inventory={
            "plugin": "InfrahubInventory",
            "options": {
                "address": dv.INFRAHUB_ADDRESS,
                "token": dv.INFRAHUB_API_TOKEN,
                "branch": branch or "main",
                "host_node": {"kind": "DcimGenericDevice"},
                # No `schema_mappings`, and the absence is the interesting part.
                #
                # The design review's groundwork asserted both that the host kind
                # is `DcimGenericDevice` and that `mgmt_ip.address` is a legal
                # single-hop mapping. Those cannot both be true, and the plugin
                # says so: "schema_mapping 'mgmt_ip.address' references
                # 'mgmt_ip', which is not a relationship on DcimGenericDevice".
                # `mgmt_ip` lives on `DcimFabricSwitch` alone -- the discovery
                # query in `devices` already carries that scar, with per-kind
                # fragments because asking the other kinds for it is a GraphQL
                # error rather than an empty result.
                #
                # Nothing is lost. This inventory supplies hosts and groups; the
                # address each device is reached by comes from `Target`, which
                # the artifact discovery resolves correctly per kind. A mapping
                # here would either be dead config or force the host kind down
                # to one family and lose the other three.
                "group_mappings": ["member_of_groups__name"],
                "defaults_file": os.devnull,
                "group_file": os.devnull,
            },
        },
        logging={"enabled": False},
    )


def reconcile_host(task: Task, targets: dict[str, dv.Target], branch: str, dry_run: bool) -> Result:
    """One device's compare-and-maybe-push. Runs in a Nornir worker thread.

    **Nothing in here touches Infrahub.** It reads the artifact over HTTP and
    talks to the device, both synchronously, and returns plain data. Writing
    deployment state is the caller's job, in the caller's async context.
    """
    target = targets.get(task.host.name)
    if target is None:
        # A modelled device with no rendered configuration artifact is not this
        # service's business.
        return Result(host=task.host, result=None, changed=False)

    outcome = DeviceOutcome(device=target.device, checksum=target.checksum)
    try:
        config = cmp.read_intent(target, branch)
        comparison = cmp.compare(target, config)
    except Exception as error:  # noqa: BLE001 - one device must not stop the run
        outcome.failed = True
        outcome.error = str(error)
        return Result(host=task.host, result=outcome, failed=True)

    outcome.differs = comparison.differs
    outcome.diff = "\n".join(comparison.normalised)
    if not comparison.differs or dry_run:
        return Result(host=task.host, result=outcome, changed=False)

    try:
        dv.PUSHERS[target.artifact_name](target, config)
    except Exception as error:  # noqa: BLE001 - one device must not stop the run
        outcome.failed = True
        outcome.error = str(error)
        return Result(host=task.host, result=outcome, failed=True)

    outcome.pushed = True
    return Result(host=task.host, result=outcome, changed=True)


def run_over(
    nr: Nornir,
    targets: dict[str, dv.Target],
    *,
    branch: str = "",
    dry_run: bool = False,
) -> list[DeviceOutcome]:
    """Run the reconcile task across an inventory and collect plain outcomes."""
    results = nr.run(task=reconcile_host, targets=targets, branch=branch, dry_run=dry_run)
    outcomes: list[DeviceOutcome] = []
    for host, multi in results.items():
        value: Any = multi[0].result
        if isinstance(value, DeviceOutcome):
            outcomes.append(value)
        elif multi[0].failed:
            # A task that raised before returning an outcome still has to be
            # reported against its device rather than vanishing.
            outcomes.append(DeviceOutcome(device=host, failed=True, error=str(multi[0].exception or "unknown failure")))
    return outcomes


def split_firewalls(nr: Nornir) -> tuple[Nornir, Nornir]:
    """The fabric and the firewalls, separately.

    The firewall's comparison takes an exclusive configuration lock, so it is
    never run alongside anything and never alongside another firewall.
    """
    return nr.filter(~F(groups__contains=GROUP_JUNOS)), nr.filter(F(groups__contains=GROUP_JUNOS))
