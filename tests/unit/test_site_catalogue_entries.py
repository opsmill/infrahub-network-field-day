"""The shop and wiki catalogue entries are generated from the HTML under sites/."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]


def _renderer() -> Any:
    spec = importlib.util.spec_from_file_location("render_site_entries", REPO / "scripts" / "render_site_entries.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entries() -> dict[str, dict[str, Any]]:
    docs = list(yaml.safe_load_all((REPO / "objects" / "35a_otternet_app_catalogue.yml").read_text(encoding="utf-8")))
    return {e["name"]: e for e in docs[0]["spec"]["data"]}


def test_the_entries_match_the_html_they_are_generated_from() -> None:
    renderer = _renderer()
    text = (REPO / "objects" / "35a_otternet_app_catalogue.yml").read_text(encoding="utf-8")
    assert renderer.render(text) == text, "run: uv run python scripts/render_site_entries.py"


def test_each_site_entry_serves_every_page_of_its_site_and_nothing_else() -> None:
    renderer = _renderer()
    for name, _title, _description, directory, with_css in renderer.ENTRIES:
        values = yaml.safe_load(_entries()[name]["default_values"])
        served = set(values["configMaps"]["site"]["data"])
        expected = {p.name for p in (REPO / "sites" / directory).glob("*.html")}
        if with_css:
            expected.add("otternet.css")
        assert served == expected


def test_a_site_exposes_a_local_loadbalancer_with_the_advertise_label() -> None:
    renderer = _renderer()
    for name, *_ in renderer.ENTRIES:
        entry = _entries()[name]
        service = yaml.safe_load(entry["default_values"])["service"]["main"]
        assert service["type"] == "LoadBalancer"
        assert service["externalTrafficPolicy"] == "Local"
        assert service["labels"]["otternet.lab/advertise"] == "true"
        assert service["ports"]["http"] == {"port": 80, "targetPort": 8080}
        assert entry["requestable"] is True


def test_every_link_inside_a_site_points_at_a_page_it_serves() -> None:
    renderer = _renderer()
    for name, *_ in renderer.ENTRIES:
        served = set(yaml.safe_load(_entries()[name]["default_values"])["configMaps"]["site"]["data"])
        for page, content in yaml.safe_load(_entries()[name]["default_values"])["configMaps"]["site"]["data"].items():
            if not page.endswith(".html"):
                continue
            for target in re.findall(r'(?:href|src)="([^"#:]+)"', content):
                assert target in served, f"{name}/{page} links to {target}, which the site does not serve"


def test_a_sites_files_fit_in_one_configmap() -> None:
    """A ConfigMap is limited to 1 MiB; stay well under it."""
    renderer = _renderer()
    for name, _title, _description, directory, with_css in renderer.ENTRIES:
        total = sum(len(v.encode()) for v in renderer.site_files(directory, with_css).values())
        assert total < 700 * 1024, f"{name} is {total} bytes"
