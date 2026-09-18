"""Render the OTTERNET host_vars with PyAVD and diff against the deployed lab.

This is the fast half of the parity claim. ``tests/integration/test_otternet_fabric.py``
proves Infrahub *produces* these host_vars; this test proves the host_vars
*render* to the configuration the lab is running, in about a second and with no
containers.

Its real job is guarding the PyAVD pin. A version bump that changes a default,
renames a key, or reorders a stanza shows up here immediately rather than in a
15-minute testcontainer run -- see `docs/docs/how-to/upgrade-avd-version.md`.

The fixtures are the host_vars the AVD hostvar generator emits for each switch,
in the same shape and with the same types (stringified ASNs, bare next hops).
Regenerate them only alongside a deliberate change to the generator's output.
"""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest
from pyavd import get_avd_facts, get_device_config, get_device_structured_config, validate_inputs

FIXTURES = Path(__file__).parent / "fixtures" / "otternet"
GOLDEN = Path(__file__).parent.parent / "integration" / "golden" / "otternet"

# Hostnames come from the pod and rack generators' default naming:
# `spine-{pod}-{index}` and `leaf-{pod}-{rack_index}-{index}`.
DEVICES = [
    "spine-otternet-pod1-1",
    "spine-otternet-pod1-2",
    "leaf-otternet-pod1-1-1",
    "leaf-otternet-pod1-1-2",
    "leaf-otternet-pod1-2-1",
    "leaf-otternet-pod1-2-2",
    "leaf-otternet-pod1-3-1",
]


def _hostvars() -> dict[str, dict]:
    return {device: json.loads((FIXTURES / f"{device}.json").read_text()) for device in DEVICES}


def test_every_switch_has_a_hostvars_fixture_and_a_golden_config() -> None:
    assert sorted(path.stem for path in FIXTURES.glob("*.json")) == sorted(DEVICES)
    assert sorted(path.stem for path in GOLDEN.glob("*.cfg")) == sorted(DEVICES)


@pytest.mark.parametrize("device", DEVICES)
def test_hostvars_pass_pyavd_input_validation(device: str) -> None:
    """PyAVD accepts every key the generator emits.

    A key PyAVD does not know is rejected outright and fails the whole device,
    so this catches an unsupported input before it reaches the pipeline.
    """
    violations = list(validate_inputs(_hostvars()[device]).validation_result.violations)
    detail = [
        f"{'.'.join(str(part) for part in (getattr(item, 'path', []) or []))}: {getattr(item, 'message', item)}"
        for item in violations
    ]
    assert not violations, f"{device} host_vars rejected by PyAVD:\n  " + "\n  ".join(detail)


def test_rendered_configs_match_the_deployed_lab() -> None:
    """All seven switches render byte for byte to the lab's configuration."""
    hostvars = _hostvars()
    facts = get_avd_facts(hostvars)

    diffs: dict[str, str] = {}
    for device in DEVICES:
        rendered = get_device_config(get_device_structured_config(device, hostvars[device], avd_facts=facts))
        expected = (GOLDEN / f"{device}.cfg").read_text()
        if rendered != expected:
            diffs[device] = "\n".join(
                difflib.unified_diff(
                    expected.splitlines(),
                    rendered.splitlines(),
                    fromfile=f"deployed-lab/{device}.cfg",
                    tofile=f"pyavd/{device}.cfg",
                    lineterm="",
                )
            )

    if diffs:
        summary = "\n\n".join(f"=== {device} ===\n{diff}" for device, diff in sorted(diffs.items()))
        msg = f"{len(diffs)} of {len(DEVICES)} switches differ from the deployed lab:\n\n{summary}"
        raise AssertionError(msg)
