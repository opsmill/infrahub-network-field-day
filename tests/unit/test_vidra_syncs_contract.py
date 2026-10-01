"""Every Vidra sync names an artifact Infrahub actually renders (cycle 034).

`artefactName` must equal an `artifact_name` in `.infrahub.yml` exactly --
spaces and capitals included -- and a mismatch fails in the worst way: the
operator's query returns no artifacts, the sync reports `Succeeded` over an
empty set, and nothing arrives. This holds every declaration against the
definitions, and pins the one sync whose destination is not `default`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]


def _syncs() -> list[dict]:
    text = (REPO / "vidra" / "infrahub-syncs.yaml").read_text(encoding="utf-8")
    return [doc for doc in yaml.safe_load_all(text) if doc and doc.get("kind") == "InfrahubSync"]


def _artifact_names() -> set[str]:
    config = yaml.safe_load((REPO / ".infrahub.yml").read_text(encoding="utf-8"))
    return {definition["artifact_name"] for definition in config["artifact_definitions"]}


def test_every_sync_names_a_rendered_artifact() -> None:
    names = _artifact_names()
    for sync in _syncs():
        wanted = sync["spec"]["source"]["artefactName"]
        assert wanted in names, f"{sync['metadata']['name']}: no artifact definition is named {wanted!r}"
        assert sync["spec"]["source"]["targetBranch"] == "main", "a feature branch must never reach the cluster"


def test_the_collector_configuration_is_delivered_into_telegrafs_namespace() -> None:
    """A pod can mount a ConfigMap only from its own namespace."""
    sync = next(s for s in _syncs() if s["spec"]["source"]["artefactName"] == "Telemetry Collector Configuration")
    assert sync["spec"]["destination"]["namespace"] == "otternet-telemetry"
