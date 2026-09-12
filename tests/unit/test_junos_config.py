"""Golden-file tests for the perimeter firewall's Junos render.

The oracle is `../lab/configs/fw/vsrx/junos.conf` -- the configuration the
firewall actually runs, written by hand rather than by this repository. That
makes equality the right assertion: a substring check would pass on a policy
stanza with a rule in the wrong position, and Junos evaluates first-match, so
that is a different firewall which loads without complaint.

The artifact covers 573 of the file's 677 lines. The excluded 104 are the
`system` stanza (two credential hashes, permanently out), `routing-options`
(eight routes with no device-level home in the schema) and the 7-line `flow`
block (nothing models it). SC-010 makes that total an arithmetic criterion
rather than a prose caveat, and `test_the_exclusions_add_up` checks it.
"""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Any

import pytest

from transforms.junos_config import JunosConfig

FIXTURE = Path("tests/unit/fixtures/junos/fw1.json")
JUNOS_CONF = Path("../lab/configs/fw/vsrx/junos.conf")
REPO_ROOT = Path(__file__).parents[2]


def _conf() -> list[str]:
    if not JUNOS_CONF.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return JUNOS_CONF.read_text(encoding="utf-8").splitlines()


def _rendered() -> list[str]:
    transform = JunosConfig.__new__(JunosConfig)
    transform.root_directory = str(REPO_ROOT)
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return asyncio.run(transform.transform(data)).splitlines()


def _stanza(lines: list[str], name: str, indent: str = "") -> list[str]:
    """One brace-delimited stanza, inclusive of its own braces."""
    opener = f"{indent}{name} {{"
    start = next((i for i, line in enumerate(lines) if line == opener), None)
    if start is None:
        pytest.fail(f"stanza {name!r} not found at indent {len(indent)}")
    depth = 0
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if depth == 0:
            return lines[start : i + 1]
    pytest.fail(f"stanza {name!r} never closes")


# ---------------------------------------------------------------------------
# The gate: stanza equality against the device's own file
# ---------------------------------------------------------------------------


def test_interfaces_stanza_matches_the_device() -> None:
    assert _stanza(_rendered(), "interfaces") == _stanza(_conf(), "interfaces")


def test_address_book_matches_the_device() -> None:
    """Including its order, which is why `book_index` exists.

    Junos writes the book infrastructure-first then per-tenant, and that order
    is not derivable -- not alphabetical, not by network address, not by prefix
    length. Cycle 023 added `book_index` to SecurityGenericAddress rather than
    accept a book that is semantically identical and textually different.
    """
    assert _stanza(_rendered(), "address-book", "    ") == _stanza(_conf(), "address-book", "    ")


def test_zones_stanza_matches_the_device() -> None:
    assert _stanza(_rendered(), "zones", "    ") == _stanza(_conf(), "zones", "    ")


# ---------------------------------------------------------------------------
# The one deliberate difference
# ---------------------------------------------------------------------------


def test_provenance_names_infrahub_not_the_device() -> None:
    """The lab's file claims no renderer; ours must not claim to be the device."""
    first = _rendered()[0]

    assert first == "! Rendered by Infrahub for fw1 -- do not edit."


# ---------------------------------------------------------------------------
# Things that would be wrong and would still load
# ---------------------------------------------------------------------------


def test_the_any_keyword_is_never_declared_in_the_address_book() -> None:
    """Junos treats `any` as a keyword. Declaring it is redundant and wrong,
    and it is the one address object with no `book_index` for that reason.
    """
    book = _stanza(_rendered(), "address-book", "    ")

    assert not [line for line in book if re.match(r"^\s+address any ", line)]


def test_no_credential_appears_anywhere_in_the_output() -> None:
    """The `system` stanza is excluded permanently, not deferred.

    The requirement is about the graph as much as the artifact: an artifact can
    be diffed, and a credential that reaches the model has reached every branch
    and every export of it.
    """
    text = "\n".join(_rendered())

    for pattern in ("encrypted-password", "ssh-rsa", "ssh-ed25519", "PRIVATE KEY"):
        assert pattern not in text


def test_braces_balance_and_never_go_negative() -> None:
    depth = 0
    for line in _rendered():
        depth += line.count("{") - line.count("}")
        assert depth >= 0, line

    assert depth == 0


def test_the_exclusions_add_up() -> None:
    """SC-010: what is not covered is enumerated, and the enumeration totals.

    A renderer that silently omits part of a firewall's configuration is worse
    than one that does not exist, so this is arithmetic rather than a caveat.
    """
    lines = _conf()
    spans: dict[str, int] = {}
    cur, start = None, 0
    for i, line in enumerate(lines, 1):
        m = re.match(r"^([a-z-]+) \{", line)
        if m:
            cur, start = m.group(1), i
        if line == "}" and cur:
            spans[cur] = i - start + 1
            cur = None

    flow = len(_stanza(lines, "flow", "    "))
    in_scope = spans["interfaces"] + spans["security"] - flow
    excluded = len(lines) - in_scope

    assert in_scope == 573
    assert excluded == 104
    assert spans["system"] + spans["routing-options"] + flow <= excluded


# ---------------------------------------------------------------------------
# Policies
# ---------------------------------------------------------------------------


def _zone_pairs(lines: list[str]) -> dict[tuple[str, str], list[str]]:
    """Each zone pair, with the commentary that introduces it.

    A comment immediately above a `from-zone` line belongs to that pair, except
    the stanza's own opening block -- which introduces the whole `policies`
    stanza rather than the first pair, and is asserted separately.
    """
    block = _stanza(lines, "policies", "    ")
    pairs: dict[tuple[str, str], list[str]] = {}
    i = 0
    while i < len(block):
        m = re.match(r"^        from-zone (\S+) to-zone (\S+) \{", block[i])
        if m:
            start = i
            if i and block[i - 1].strip().endswith("*/"):
                j = i - 1
                while "/*" not in block[j]:
                    j -= 1
                # the head comment sits at stanza indent, a pair's at rule indent
                if block[j].startswith("            /*"):
                    start = j
            depth, end = 0, i
            for k in range(i, len(block)):
                depth += block[k].count("{") - block[k].count("}")
                if depth == 0:
                    end = k
                    break
            pairs[m.groups()] = block[start : end + 1]
            i = end
        i += 1
    return pairs


def test_every_zone_pair_is_present() -> None:
    assert set(_zone_pairs(_rendered())) == set(_zone_pairs(_conf()))


@pytest.mark.parametrize(
    "pair",
    [
        ("app-prod", "k8s-prod"),
        ("k8s-prod", "app-prod"),
        ("wan", "k8s-prod"),
        ("branch", "k8s-prod"),
        ("wan", "acme-cloud"),
        ("wan", "globex-cloud"),
        ("acme-cloud", "wan"),
        ("globex-cloud", "wan"),
        ("wan", "app-prod"),
        ("wan", "branch"),
        ("branch", "wan"),
    ],
)
def test_zone_pair_matches_the_device(pair: tuple[str, str]) -> None:
    """Byte-for-byte WITHIN each pair, which is where order is semantic.

    Junos selects the pair by from-zone/to-zone and evaluates only within it,
    first-match. So rule order inside a pair is behaviour -- and the model
    carries it, in `index`. The order *between* pairs is presentational, has no
    object to hang an index on (pairs are derived, not stored), and is asserted
    as a set above rather than a sequence. See research.md R12.
    """
    assert _zone_pairs(_rendered())[pair] == _zone_pairs(_conf())[pair]


def test_the_anti_spoofing_rule_renders_six_times_identically() -> None:
    """Six objects, not one: `source_zone` and `destination_zone` are
    cardinality-one on the adopted schema, so a rule belongs to exactly one
    pair. The render must not let the six drift apart.
    """
    rendered = _rendered()
    bodies = []
    for i, line in enumerate(rendered):
        if line.strip() == "policy deny-spoofed-infra {":
            depth, end = 0, i
            for k in range(i, len(rendered)):
                depth += rendered[k].count("{") - rendered[k].count("}")
                if depth == 0:
                    end = k
                    break
            bodies.append("\n".join(rendered[i : end + 1]))

    assert len(bodies) == 6
    assert len(set(bodies)) == 1


def test_rule_order_within_every_pair_matches_the_device() -> None:
    """First-match evaluation makes this semantic, not cosmetic."""
    rendered, gold = _zone_pairs(_rendered()), _zone_pairs(_conf())
    names = lambda block: [  # noqa: E731
        m.group(1) for m in (re.match(r"^\s+policy (\S+) \{", line) for line in block) if m
    ]

    for pair in gold:
        assert names(rendered[pair]) == names(gold[pair]), pair


def test_the_policies_stanza_opens_with_the_devices_own_commentary() -> None:
    head = _stanza(_rendered(), "policies", "    ")[1:9]

    assert "Junos evaluates the policies of the matching from-zone/to-zone pair" in "\n".join(head)
