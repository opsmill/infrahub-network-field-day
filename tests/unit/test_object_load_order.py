"""Load-order contract on `objects/`.

Seed files load in filename order, and a reference to something a *later* file
declares fails the load with a message naming the missing object and not the
file that has to move. Worse, it is **invisible on a running instance**: the
object is already there from a previous load, so everything works right up until
someone rebuilds from nothing.

That is exactly how `OTTERNET-VIP-Pool` shipped. It sat in `21_otternet_pools.yml`
drawing from `10.112.240.0/24`, which `29_otternet_offfabric_prefixes.yml` declares
— eight files later. Every test passed, the generator allocated from it
correctly, and a fresh `invoke load` failed with::

    ['CoreIPPrefixPoolUpsert'] Unable to find the node
    10.112.240.0/24 / BuiltinIPPrefix in the database.

It took a full teardown to find. This test is what makes the next one cost a
second instead.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parents[2]
OBJECTS = REPO_ROOT / "objects"

# Pool kinds whose `resources` must name prefixes that already exist.
PREFIX_POOL_KINDS = ("CoreIPPrefixPool", "CoreIPAddressPool")


def _documents(path: Path) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(path.read_text(encoding="utf-8")) if d]


def _object_files() -> list[Path]:
    return sorted(OBJECTS.glob("*.yml"))


def _prefixes_declared_by(path: Path) -> set[str]:
    declared: set[str] = set()
    for document in _documents(path):
        spec = document.get("spec", {})
        if spec.get("kind") in ("IpamPrefix", "BuiltinIPPrefix"):
            for row in spec.get("data", []):
                value = row.get("prefix")
                if value:
                    declared.add(str(value))
    return declared


def _pools_in(path: Path) -> list[tuple[str, list[str]]]:
    pools: list[tuple[str, list[str]]] = []
    for document in _documents(path):
        spec = document.get("spec", {})
        if spec.get("kind") in PREFIX_POOL_KINDS:
            for row in spec.get("data", []):
                resources = row.get("resources") or []
                pools.append((str(row.get("name")), [str(r) for r in resources]))
    return pools


def test_there_are_object_files_and_pools_to_check() -> None:
    """A parametrised rule over an empty list passes while asserting nothing."""
    files = _object_files()
    assert len(files) > 10
    assert sum(len(_pools_in(f)) for f in files) > 3


@pytest.mark.parametrize("path", _object_files(), ids=lambda p: p.name)
def test_every_pool_resource_is_declared_by_an_earlier_file(path: Path) -> None:
    """A pool may only draw from a prefix an earlier (or the same) file declares.

    `CoreIPPrefixPool.resources` is resolved at load time, so a prefix declared
    later does not exist yet. The failure names the prefix, not the ordering.
    """
    pools = _pools_in(path)
    if not pools:
        pytest.skip("no pools in this file")

    available: set[str] = set()
    for candidate in _object_files():
        available |= _prefixes_declared_by(candidate)
        if candidate == path:
            break

    for pool_name, resources in pools:
        missing = [r for r in resources if r not in available]
        assert not missing, (
            f"{path.name} declares pool {pool_name!r} drawing from {missing}, which no file at or "
            f"before {path.name} declares. Seed files load in filename order, so the load fails with "
            '"Unable to find the node ... in the database" — move the pool after the prefix, or the '
            "prefix before the pool."
        )


def test_the_rule_would_have_caught_the_vip_pool() -> None:
    """The regression this file exists for, stated as data rather than prose.

    `10.112.240.0/24` is declared in `29_otternet_offfabric_prefixes.yml`. Any pool
    drawing from it must therefore live in that file or later — which is where
    `OTTERNET-VIP-Pool` now is, and is not where it shipped.
    """
    declaring = [f.name for f in _object_files() if "10.112.240.0/24" in _prefixes_declared_by(f)]
    assert declaring, "10.112.240.0/24 is declared nowhere; this test is measuring the wrong thing"

    using = [f.name for f in _object_files() for name, res in _pools_in(f) if "10.112.240.0/24" in res]
    assert using, "no pool draws from 10.112.240.0/24; this test is measuring the wrong thing"
    assert min(using) >= min(declaring)
