"""Seed-data tests for the WAN service layer (objects/37).

The assertions worth having are the ones that catch a transcription slip
against `../lab/wan/tenants.yml`, because the object file is a hand
transcription of it and nothing else compares the two.

The most important is the asymmetry: acme has internet, globex does not. A
reviewer skimming the file would read two tenants and expect two of everything,
and modelling them identically would lose the only interesting thing about the
pair.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

OBJECT_FILE = Path("objects/37_nfd41_wan_services.yml")
LAB_TENANTS = Path("../lab/wan/tenants.yml")


def _docs() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(OBJECT_FILE.read_text(encoding="utf-8")) if d]


def _data(kind: str) -> list[dict[str, Any]]:
    for doc in _docs():
        if doc.get("spec", {}).get("kind") == kind:
            return doc["spec"]["data"]
    pytest.fail(f"no {kind} block in {OBJECT_FILE}")


def _lab_tenants() -> list[dict[str, Any]]:
    if not LAB_TENANTS.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return yaml.safe_load(LAB_TENANTS.read_text(encoding="utf-8"))["tenants"]


# ---------------------------------------------------------------------------
# The asymmetry -- the assertion that matters most
# ---------------------------------------------------------------------------


def test_only_tenants_with_internet_get_an_internet_service() -> None:
    """acme has `internet: true` in the lab; globex has `internet: false`.

    A tenant having a WAN does not mean it has a way out to the internet.
    Seeding one service per tenant would be symmetrical and wrong.
    """
    expected = {f"{t['name']}-internet" for t in _lab_tenants() if t.get("internet")}
    seeded = {entry["name"] for entry in _data("ServiceInternetAccess")}

    assert seeded == expected
    assert len(seeded) == 1


def test_every_lab_tenant_has_an_l3vpn_and_a_cloud() -> None:
    """Both tenants get a WAN and a DC footprint; only internet differs."""
    names = {t["name"] for t in _lab_tenants()}

    assert {e["name"] for e in _data("ServiceL3vpn")} == {f"{n}-l3vpn" for n in names}
    assert {e["name"] for e in _data("ServiceTenantCloud")} == {f"{n}-cloud" for n in names}


# ---------------------------------------------------------------------------
# Transcription fidelity
# ---------------------------------------------------------------------------


def test_l3vpn_vrfs_match_the_lab() -> None:
    """The PE-side VRF, which is distinct from the DC-side TENANT_* VRF."""
    expected = {f"{t['name']}-l3vpn": t["vrf"] for t in _lab_tenants()}
    seeded = {e["name"]: e["vrf"] for e in _data("ServiceL3vpn")}

    assert seeded == expected


def test_tenant_cloud_matches_the_lab_dc_block() -> None:
    """Each tenant's DC footprint: its own VRF, zone and subnet."""
    for tenant in _lab_tenants():
        entry = next(e for e in _data("ServiceTenantCloud") if e["name"] == f"{tenant['name']}-cloud")
        dc = tenant["dc"]

        assert entry["vrf"] == dc["vrf"]
        assert entry["zone"] == dc["zone"]
        assert entry["prefix"][0] == dc["subnet"]


def test_pe_and_dc_vrfs_are_distinct() -> None:
    """The lab's own note: a tenant gets one VRF on the PE and a separate one
    in the DC. Collapsing them would silently join two tenants' routing."""
    pe = {e["vrf"] for e in _data("ServiceL3vpn")}
    dc = {e["vrf"] for e in _data("ServiceTenantCloud")}

    assert not pe & dc


def test_every_service_names_an_owner_and_a_status() -> None:
    """ServiceGeneric makes owner mandatory; status has a default but an
    explicit one is what an operator reads."""
    for kind in ("ServiceL3vpn", "ServiceInternetAccess", "ServiceTenantCloud"):
        for entry in _data(kind):
            assert entry.get("owner"), f"{kind} {entry['name']} has no owner"
            assert entry.get("status"), f"{kind} {entry['name']} has no status"


def test_service_names_are_unique_across_kinds() -> None:
    """ServiceGeneric constrains name to be unique across every service kind
    (FR-070), so a collision here fails at load rather than in review."""
    names = [e["name"] for k in ("ServiceL3vpn", "ServiceInternetAccess", "ServiceTenantCloud") for e in _data(k)]

    assert len(names) == len(set(names))
