"""`bootstrap --no-lab` runs Dex from tooling/10-dex.yaml, moved to the one address every party reaches."""

from __future__ import annotations

from pathlib import Path

import yaml

import tasks

ROOT = Path(__file__).resolve().parents[2]


class _ComposeLoader(yaml.SafeLoader):
    """Accepts compose's merge tags, `!reset` and `!override`."""


_ComposeLoader.add_constructor("!reset", lambda _loader, _node: None)
_ComposeLoader.add_constructor("!override", lambda loader, node: loader.construct_sequence(node))


def test_dex_is_moved_to_localhost_and_keeps_its_users() -> None:
    config = tasks._no_lab_dex_config(ROOT / "tooling/10-dex.yaml")
    assert config["issuer"] == "http://localhost:32556/dex"
    assert config["web"] == {"http": "0.0.0.0:32556"}
    clients = {client["id"]: client["redirectURIs"] for client in config["staticClients"]}
    assert "https://localhost:32001/api/auth/oidc/handler/frame" in clients["backstage"]
    assert "http://localhost:8000/auth/oidc/provider1/callback" in clients["infrahub"]
    assert {user["username"] for user in config["staticPasswords"]} >= {"alice", "bob"}


def test_the_compose_file_names_the_same_addresses() -> None:
    compose = yaml.load((ROOT / tasks.NO_LAB_COMPOSE_FILE).read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506
    server = compose["services"]["infrahub-server"]
    assert server["environment"]["INFRAHUB_OIDC_PROVIDER1_DISCOVERY_URL"].startswith(tasks.NO_LAB_DEX + "/dex/")
    portal = compose["services"]["backstage"]["environment"]
    assert portal["BACKSTAGE_BASE_URL"] == tasks.NO_LAB_PORTAL
    assert portal["BACKSTAGE_OIDC_METADATA_URL"].startswith(tasks.NO_LAB_DEX + "/dex/")


def test_dex_is_enabled_wherever_the_portal_is() -> None:
    """The portal depends on Dex; a profile that enables only the portal is an invalid project."""
    compose = yaml.load((ROOT / tasks.NO_LAB_COMPOSE_FILE).read_text(encoding="utf-8"), Loader=_ComposeLoader)  # noqa: S506
    services = compose["services"]
    assert set(services["backstage"]["profiles"]) <= set(services["dex"]["profiles"])
