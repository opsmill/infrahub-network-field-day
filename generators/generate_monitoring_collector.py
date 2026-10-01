"""Keep a collector's rendered configuration fresh (cycle 034).

THIS GENERATOR WRITES NOTHING. It exists because of how artifacts regenerate:
when their *target* changes. The `Telemetry Collector Configuration` artifact's
target is the collector, and almost nothing that changes what it should collect
is a change to the collector -- a device joining `avd_devices`, a profile
gaining a measurement, a router gaining a BGP neighbour. Without this, the
proposed change for any of those shows the data and no configuration diff, and
after the merge Telegraf goes on collecting what the old intent said.

It is `generate-app-access`'s `_rerender_firewall` again, for the same reason:
the thing that changed is not the artifact's target, and Infrahub's trigger
rules cannot render an artifact.

It runs in the proposed-change pipeline and after merge, and on NO event rule.
Monitoring intent is the input to what is observed; a trigger on it would let
an edit to what is watched regenerate something watched.
tests/unit/test_deployment_schema_contract.py holds that.
"""

from __future__ import annotations

from typing import Any

from infrahub_sdk.generator import InfrahubGenerator

from .artifact_render import request_artifact_render
from .generate_monitoring_collector_query import GenerateMonitoringCollectorQuery

COLLECTOR_ARTIFACT = "Telemetry Collector Configuration"


class MonitoringCollectorGenerator(InfrahubGenerator):
    """Request a re-render of one collector's configuration artifact, on its branch."""

    async def generate(self, data: dict[str, Any]) -> None:
        """Ask for the artifact; never create, update or delete a node."""
        parsed = GenerateMonitoringCollectorQuery(**data)
        collector = parsed.target.edges[0].node if parsed.target.edges else None
        if collector is None:
            msg = "no MonitoringCollector matched the requested name"
            raise ValueError(msg)
        name = collector.name.value if collector.name and collector.name.value else collector.id
        await self._rerender(collector.id, name)

    async def _rerender(self, collector_id: str, name: str) -> None:
        """POST /api/artifact/generate/{definition}?branch=..., naming the artifact.

        `?branch=` because the SDK's `artifact_generate` omits it and the
        endpoint then regenerates against `main` -- the no-op on a branch that
        generate-app-access measured. `nodes` names the ARTIFACT, not its
        target; before the first render there is no artifact, and an empty list
        asks for every member of the definition's group, which is the first
        render.

        Best effort: a failed request is logged, because raising would mark a
        generator that changed nothing as failed and block a proposed change on
        a render the artifact check performs anyway.
        """
        branch = self.branch_name
        try:
            await request_artifact_render(
                self._init_client,
                artifact_name=COLLECTOR_ARTIFACT,
                target_id=collector_id,
                branch=branch,
                first_render=True,
            )
        except Exception as exc:  # noqa: BLE001 - see the docstring; never fatal here
            self.logger.warning("Could not re-render %r for %s (%s)", COLLECTOR_ARTIFACT, name, exc)
            return
        self.logger.info("Requested a re-render of %r for %s on %s", COLLECTOR_ARTIFACT, name, branch or "main")
