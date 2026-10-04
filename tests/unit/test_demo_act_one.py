"""Act one of the demo submits a catalogue pick (specs/035-application-catalogue).

`scripts/demo_rehearsal.py` act one used to type a chart repository, name, version,
ports, block size, selector and values into the curated template. It now submits
the picker's value, and these tests tie that to the two things it has to agree
with: the template's own form, and the catalogue entry it names. Whether the
lab then shows it is what the rehearsal itself checks, against a live lab.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = ROOT / "backstage/catalog/exposed-app-with-access.yaml"
CATALOGUE = ROOT / "objects/35a_otternet_app_catalogue.yml"


@pytest.fixture(scope="module")
def rehearsal() -> Any:
    spec = importlib.util.spec_from_file_location("demo_rehearsal", ROOT / "scripts/demo_rehearsal.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _whoami() -> dict[str, Any]:
    document = next(yaml.safe_load_all(CATALOGUE.read_text(encoding="utf-8")))
    return next(entry for entry in document["spec"]["data"] if entry["name"] == "whoami")


def _manifest(chart: dict[str, Any]) -> str:
    return yaml.safe_dump({"spec": {"chart": chart}})


def test_act_one_submits_exactly_the_fields_the_form_has(rehearsal: Any) -> None:
    """A field the form lacks is ignored by the portal, and one it requires and
    does not get fails the run -- neither is visible from the script."""
    template = yaml.safe_load(TEMPLATE.read_text(encoding="utf-8"))
    form = {name for page in template["spec"]["parameters"] for name in page["properties"]}

    assert set(rehearsal.act_one_values("otter-shop", "ref")) == form


def test_act_one_no_longer_types_anything_about_a_chart(rehearsal: Any) -> None:
    values = rehearsal.act_one_values("otter-shop", "ref")

    assert not [key for key in values if key.startswith("chart") or key in {"values_file_content", "vip_block_size"}]
    assert "advertised_services" not in values
    assert "service_selector" not in values


def test_act_one_picks_the_requestable_entry_by_the_ref_the_portal_derives(rehearsal: Any) -> None:
    """`resource:default/<hfid lowercased>`, which is what the provider names it."""
    entry = _whoami()
    assert entry["requestable"] is True
    assert f"resource:default/{entry['name'].lower()}" == rehearsal.ACT_ONE_ENTITY
    assert rehearsal.act_one_values("otter-shop", "ref")["catalogue_entry"] == rehearsal.ACT_ONE_ENTITY


def test_the_pinned_chart_the_rehearsal_expects_is_the_entrys(rehearsal: Any) -> None:
    entry = _whoami()
    assert {
        "repository": entry["chart_repository"],
        "name": entry["chart_name"],
        "version": entry["chart_version"],
    } == rehearsal.PINNED_CHART
    assert yaml.safe_load(entry["default_values"]) == rehearsal.PINNED_VALUES


def test_a_manifest_with_the_entrys_chart_and_values_has_no_problems(rehearsal: Any) -> None:
    entry = _whoami()
    manifest = _manifest(
        {
            "repository": entry["chart_repository"],
            "name": entry["chart_name"],
            "version": entry["chart_version"],
            "values": yaml.safe_load(entry["default_values"]),
        }
    )

    assert rehearsal.pinned_chart_problems(manifest) == []


@pytest.mark.parametrize(
    ("field", "wrong"),
    [("version", "7.0.0"), ("name", "nginx"), ("repository", "https://example.invalid/")],
)
def test_a_manifest_with_another_chart_is_reported(rehearsal: Any, field: str, wrong: str) -> None:
    chart = {**rehearsal.PINNED_CHART, "values": rehearsal.PINNED_VALUES, field: wrong}

    problems = rehearsal.pinned_chart_problems(_manifest(chart))

    assert problems
    assert any(field in problem for problem in problems)


def test_a_manifest_missing_the_values_is_reported(rehearsal: Any) -> None:
    problems = rehearsal.pinned_chart_problems(_manifest(dict(rehearsal.PINNED_CHART)))

    assert any("chart.values" in problem for problem in problems)


def test_a_manifest_with_no_chart_is_reported(rehearsal: Any) -> None:
    assert rehearsal.pinned_chart_problems("spec: {}\n")
