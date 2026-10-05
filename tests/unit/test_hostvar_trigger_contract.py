"""The rule that puts a service's change to a switch's custom hostvars onto the branch.

`generate-app-access` writes the border leaf's `avd_custom_hostvars`. A proposed change opened by a
client that does not wait for the generators (the MCP server) chose its generators before that write,
so the border leaf configuration was missing until every check was run again. The rule below runs the
hostvar generator for the switch that changed. It is safe only while the hostvar generator never
writes the field it watches, which would feed each run into the next.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
RULE = "trigger-avd-hostvar-generator-update-custom-hostvars"
ACTION = "run-avd-device-hostvar-generator"


def _documents() -> list[dict]:
    return [d for d in yaml.safe_load_all((ROOT / "triggers.yml").read_text(encoding="utf-8")) if d]


def _rows(kind: str) -> list[dict]:
    return [row for doc in _documents() if doc["spec"]["kind"] == kind for row in doc["spec"]["data"]]


def test_the_hostvar_generator_runs_for_a_switch_whose_custom_hostvars_changed_on_a_branch() -> None:
    rule = next(row for row in _rows("CoreNodeTriggerRule") if row["name"] == RULE)

    assert rule["branch_scope"] == "other_branches"
    assert rule["node_kind"] == "DcimFabricSwitch"
    assert rule["mutation_action"] == "updated"
    assert rule["action"] == ACTION
    assert rule["matches"]["data"] == [{"attribute_name": "avd_custom_hostvars", "value_match": "any"}]


def test_the_action_runs_a_generator_that_is_registered() -> None:
    action = next(row for row in _rows("CoreGeneratorAction") if row["name"] == ACTION)
    registered = {
        g["name"] for g in yaml.safe_load((ROOT / ".infrahub.yml").read_text(encoding="utf-8"))["generator_definitions"]
    }

    assert action["generator"] == "generate-avd-device-hostvar"
    assert action["generator"] in registered


def test_the_hostvar_generator_never_writes_the_field_the_rule_watches() -> None:
    source = (ROOT / "generators" / "generate_avd_device_hostvar.py").read_text(encoding="utf-8")

    assert "avd_custom_hostvars.value =" not in source
    assert "avd_custom_hostvars = " not in source
