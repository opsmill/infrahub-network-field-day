"""The rename table of scripts/migrate_wan_srlinux.py, held against the seed files.

The migration renames interfaces in place so the seed files then upsert onto
names that already exist. If the two disagreed, the object load would create a
second interface beside each renamed one -- and srl_config would render both,
one under a name SR Linux rejects, which aborts the whole candidate.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

if TYPE_CHECKING:
    from types import ModuleType

ADDRESSING = Path("objects/31a_otternet_wan_addressing.yml")


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migrate_wan_srlinux", Path("scripts/migrate_wan_srlinux.py"))
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_rename_table() -> None:
    m = _migration()
    assert m.srl_name("eth1") == "ethernet-1/1"
    assert m.srl_name("eth12") == "ethernet-1/12"
    assert m.srl_name("lo") == "lo0"
    assert m.srl_name("ethernet-1/1") is None, "a second run must find nothing to rename"
    assert m.srl_name("irb0") is None
    assert m.srl_name("br-branch") is None, "deleted, not renamed: it changes kind"


def test_the_rollback_rename_is_the_exact_inverse() -> None:
    """`--reverse` is the rollback; measured on a branch, the old frr_config query then matched main."""
    m = _migration()
    for old in ("eth1", "eth2", "eth3", "eth4", "lo"):
        assert m.frr_name(m.srl_name(old)) == old
    assert m.frr_name("irb0") is None, "irb0 has no FRR-era name; the old seeds recreate br-branch"
    assert m.frr_name("eth1") is None, "a second reverse run must find nothing to rename"


def test_the_static_ce_is_not_a_router_and_keeps_its_names() -> None:
    m = _migration()
    assert "cust-acme-dr-ce" not in m.ROUTERS
    seeded = [
        e["name"]
        for doc in yaml.safe_load_all(ADDRESSING.read_text(encoding="utf-8"))
        if doc and doc["spec"]["kind"] == "InterfacePhysical"
        for e in doc["spec"]["data"]
        if e["device"] == "cust-acme-dr-ce"
    ]
    assert sorted(seeded) == ["eth1", "eth2"]


def test_every_seeded_router_interface_is_a_native_sr_linux_name() -> None:
    """What the migration produces and what the seed files name must be one set."""
    m = _migration()
    for doc in yaml.safe_load_all(ADDRESSING.read_text(encoding="utf-8")):
        if not doc or doc["spec"]["kind"] not in {"InterfacePhysical", "InterfaceVirtual"}:
            continue
        for entry in doc["spec"]["data"]:
            if entry["device"] in m.ROUTERS:
                name = entry["name"]
                assert name.startswith("ethernet-1/") or name in {"lo0", "irb0"}, (entry["device"], name)
                assert m.srl_name(name) is None, (entry["device"], name)


def test_the_group_rename_matches_the_seed() -> None:
    m = _migration()
    groups = [
        e["name"]
        for doc in yaml.safe_load_all(Path("objects/00_groups.yml").read_text(encoding="utf-8"))
        if doc
        for e in doc["spec"]["data"]
    ]
    assert m.NEW_GROUP in groups
    assert m.OLD_GROUP not in groups
