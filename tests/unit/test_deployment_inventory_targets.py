"""The reconciler's reach is unchanged by telemetry addresses (cycle 034).

Cycle 034 gave the FRR routers, the firewall and the k3s nodes an address on the
management network, so a collector in a pod can observe them. It must never
change how a configuration reaches them. The reconciler picks a route per
family -- eAPI at `mgmt_ip` for a switch, the container name for everything
else -- and a router that suddenly had a `mgmt_ip` would be one widened query
away from being pushed to as a switch.

Two independent things keep that true, and this holds both:

* the new field is called `telemetry_address`, and the deployment package never
  reads it;
* the discovery query asks for `mgmt_ip` on `DcimFabricSwitch` alone, so the
  `Target` built for a router or the firewall has no address to prefer over its
  container name.
"""

from __future__ import annotations

import re
from pathlib import Path

from solution_arista_avd.deployment import devices

DEPLOYMENT = Path(devices.__file__).parent


def test_the_deployment_package_never_reads_telemetry_addresses() -> None:
    offenders = [
        path.name for path in sorted(DEPLOYMENT.glob("*.py")) if "telemetry_address" in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"the reconciler must not reach devices by their telemetry address: {offenders}"


def test_only_the_switch_fragment_asks_for_an_address() -> None:
    fragments = dict(re.findall(r"\.\.\. on (\w+) \{([^\n]*)\}", devices.DISCOVERY_QUERY))
    assert set(fragments) == {"DcimFabricSwitch", "DcimDevice", "SecurityFirewall"}
    assert "mgmt_ip" in fragments["DcimFabricSwitch"]
    for kind in ("DcimDevice", "SecurityFirewall"):
        assert "mgmt_ip" not in fragments[kind], kind
        assert "address" not in fragments[kind], kind
