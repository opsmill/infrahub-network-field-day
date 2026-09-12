"""Seed-parity tests for the perimeter firewall (objects/32).

`objects/32_nfd41_security.yml` is a hand transcription of
`../lab/configs/fw/vsrx/junos.conf`, and cycle 023 found it was not a faithful
one: cycle 010 modelled the firewall's structure correctly and its values
approximately. These tests are what stop that recurring.

They compare **both directions**. A value invented here fails as loudly as one
omitted, which a one-directional check would miss -- and a paraphrased interface
description is exactly the kind of thing that passes a "is it set?" test.

THE PARSER MATTERS. Junos writes a single value bare and several in brackets:

    destination-address k8s-services;
    destination-address [ k8s-nodes k8s-pods k8s-services ];

A parser that handles only the first form reads every bracketed rule as empty.
That is not hypothetical: it is what overstated this cycle's gap during
research, turning 20 field corrections into an apparent rewrite.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

OBJECT_FILE = Path("objects/32_nfd41_security.yml")
JUNOS_CONF = Path("../lab/configs/fw/vsrx/junos.conf")

# Junos keywords, referenced by rules but never declared in the address book.
KEYWORDS = {"any"}


def _docs() -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all(OBJECT_FILE.read_text(encoding="utf-8")) if d]


def _data(kind: str) -> list[dict[str, Any]]:
    for doc in _docs():
        if doc.get("spec", {}).get("kind") == kind:
            return doc["spec"]["data"]
    pytest.fail(f"no {kind} block in {OBJECT_FILE}")


def _conf() -> list[str]:
    if not JUNOS_CONF.is_file():
        pytest.skip("lab repo not checked out alongside this one")
    return JUNOS_CONF.read_text(encoding="utf-8").splitlines()


def _values(line: str, key: str) -> list[str] | None:
    """Junos list syntax: bare for one value, bracketed for several."""
    m = re.search(rf"^\s+{key} (?:\[ ([^\]]+) \]|(\S+));", line)
    if not m:
        return None
    return (m.group(1) or m.group(2)).split()


def _oracle_rules() -> dict[tuple[str, str, str], dict[str, list[str]]]:
    rules: dict[tuple[str, str, str], dict[str, list[str]]] = {}
    pair: tuple[str, str] | None = None
    key: tuple[str, str, str] | None = None
    for line in _conf():
        m = re.match(r"^        from-zone (\S+) to-zone (\S+) \{", line)
        if m:
            pair = (m.group(1), m.group(2))
        m = re.match(r"^            policy (\S+) \{", line)
        if m and pair:
            key = (pair[0], pair[1], m.group(1))
            rules[key] = {"source": [], "destination": [], "application": []}
        if key:
            for field, junos_key in (
                ("source", "source-address"),
                ("destination", "destination-address"),
                ("application", "application"),
            ):
                found = _values(line, junos_key)
                if found:
                    rules[key][field] = found
    return rules


def _oracle_interfaces() -> dict[str, dict[str, Any]]:
    ifaces: dict[str, dict[str, Any]] = {}
    cur: str | None = None
    for line in _conf():
        m = re.match(r"^    (ge-\S+) \{", line)
        if m:
            cur = m.group(1)
            ifaces[cur] = {}
        if cur:
            d = re.search(r'description "([^"]+)"', line)
            mtu = re.match(r"^        mtu (\d+);", line)
            if d:
                ifaces[cur]["description"] = d.group(1)
            if mtu:
                ifaces[cur]["mtu"] = int(mtu.group(1))
            if line == "    }":
                cur = None
    return ifaces


def _seeded_rules() -> dict[tuple[str, str, str], dict[str, list[str]]]:
    out = {}
    for rule in _data("SecurityPolicyRule"):
        key = (rule["source_zone"], rule["destination_zone"], rule["name"])
        # Addresses and GROUPS are separate relationships on the adopted
        # schema -- `source_address` peers with SecurityGenericAddress and
        # `source_groups` with SecurityGenericAddressGroup. A comparison that
        # reads only the first concludes the groups are unreferenced, which is
        # exactly the wrong turn this cycle took during research.
        services = rule.get("destination_services") or {}
        out[key] = {
            "source": sorted(rule.get("source_address", []) + rule.get("source_groups", [])),
            "destination": sorted(rule.get("destination_address", []) + rule.get("destination_groups", [])),
            "application": sorted(e["name"] for e in services.get("data", [])),
        }
    return out


# ---------------------------------------------------------------------------
# The parser that got it wrong the first time
# ---------------------------------------------------------------------------


def test_the_oracle_parser_handles_the_bracket_form() -> None:
    """Guards the mistake that overstated this cycle's gap during research."""
    assert _values("                    destination-address k8s-services;", "destination-address") == ["k8s-services"]
    assert _values(
        "                    destination-address [ k8s-nodes k8s-pods k8s-services ];", "destination-address"
    ) == ["k8s-nodes", "k8s-pods", "k8s-services"]


# ---------------------------------------------------------------------------
# Rule parity, both directions
# ---------------------------------------------------------------------------


def test_every_rule_in_the_file_is_seeded() -> None:
    assert set(_oracle_rules()) == set(_seeded_rules())


@pytest.mark.parametrize("field", ["source", "destination", "application"])
def test_rule_field_matches_the_oracle(field: str) -> None:
    """Nothing missing, and nothing invented."""
    oracle, seeded = _oracle_rules(), _seeded_rules()
    mismatched = {
        key: (seeded[key][field], sorted(oracle[key][field]))
        for key in oracle
        if seeded[key][field] != sorted(oracle[key][field])
    }

    assert mismatched == {}, f"{field}: seeded != oracle for {list(mismatched)}"


def test_every_address_group_is_referenced_by_the_rules_that_name_it() -> None:
    """All four groups are referenced, via `source_groups`/`destination_groups`.

    Those are real relationships on the adopted schema, distinct from
    `source_address`/`destination_address`. Reading only the address fields
    makes the groups look unreferenced -- a wrong turn worth guarding against,
    since the two field pairs are easy to conflate.
    """
    groups = {g["name"] for g in _data("SecurityAddressGroup")}
    referenced = {name for rule in _seeded_rules().values() for name in rule["source"] + rule["destination"]}

    assert groups <= referenced, f"groups referenced by no rule: {sorted(groups - referenced)}"


def test_no_rule_uses_a_field_the_schema_does_not_have() -> None:
    """`infrahubctl object load` accepts an unknown field without complaint, so
    a typo in a relationship name is silent. This list is the schema's, checked
    against it rather than guessed.
    """
    allowed = {
        "name",
        "index",
        "action",
        "log",
        "log_session_close",
        "managed_by_service",
        "policy",
        "source_zone",
        "destination_zone",
        "source_address",
        "destination_address",
        "source_groups",
        "destination_groups",
        "source_services",
        "destination_services",
        "source_service_groups",
        "destination_service_groups",
    }
    used = {key for rule in _data("SecurityPolicyRule") for key in rule}

    assert used <= allowed, f"fields the schema does not define: {sorted(used - allowed)}"


# ---------------------------------------------------------------------------
# Interfaces
# ---------------------------------------------------------------------------


def test_interface_descriptions_are_the_devices_own() -> None:
    """Not a paraphrase. These strings appear on the firewall."""
    oracle = _oracle_interfaces()
    seeded = {i["name"]: i for i in _data("SecurityFirewallInterface")}

    for name, entry in oracle.items():
        assert seeded[name]["description"] == entry["description"], name


def test_interface_mtu_is_the_platform_maximum_not_the_default() -> None:
    """9192, not the schema's 1514 and not the fabric's 9214.

    Junos counts the 14-byte Ethernet header, so the fabric's 9214 would need
    9228, which vSRX rejects. `security flow tcp-mss` covers the shortfall.
    """
    oracle = _oracle_interfaces()
    seeded = {i["name"]: i for i in _data("SecurityFirewallInterface")}

    for name, entry in oracle.items():
        assert seeded[name]["mtu"] == entry["mtu"] == 9192, name


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


def test_every_application_a_rule_names_exists_as_a_service() -> None:
    services = {s["name"] for s in _data("SecurityService")}
    used = {app for rule in _seeded_rules().values() for app in rule["application"]}

    assert used <= services, f"applications with no service object: {sorted(used - services)}"


def test_the_any_keyword_is_modelled_as_both_an_address_and_a_service() -> None:
    """Rules reference `any` in both positions, so a relationship needs an
    object to point at -- even though Junos declares it in neither stanza.
    """
    services = {s["name"] for s in _data("SecurityService")}
    # `any` is a literal SecurityPrefix rather than an IPAM-backed one: there is
    # no IpamPrefix for 0.0.0.0/0 and there should not be, since nothing routes
    # or allocates from it. MARKETPLACE.md reserves the IPAM-backed kinds for
    # networks another enforcement point also matches on.
    addresses = {a["name"] for a in _data("SecurityPrefix")}

    assert services >= KEYWORDS
    assert addresses >= KEYWORDS


# ---------------------------------------------------------------------------
# The address book's order
# ---------------------------------------------------------------------------


def _oracle_book_order() -> list[str]:
    return [m.group(1) for m in (re.match(r"^\s+address ([a-z0-9-]+) \S+;", line) for line in _conf()) if m]


def _seeded_book() -> list[tuple[int, str]]:
    entries = [
        (entry["book_index"], entry["name"])
        for kind in ("SecurityIPAMIPPrefix", "SecurityIPAMIPAddress", "SecurityPrefix")
        for entry in _data(kind)
        if entry.get("book_index") is not None
    ]
    return sorted(entries)


def test_book_index_reproduces_the_files_address_order() -> None:
    """Junos' address-book order is authoring order, and nothing derives it.

    It is not alphabetical, not by network address and not by prefix length --
    all three were tested. `book_index` exists because the alternative was a
    rendered book that is semantically identical and textually different, which
    Junos would accept and a reviewer diffing against the device would not.
    """
    assert [name for _, name in _seeded_book()] == _oracle_book_order()


def test_only_the_any_keyword_has_no_book_index() -> None:
    """An absent index is also the signal to leave an entry out of the book.

    `any` is referenced by rules and declared by Junos in neither the address
    book nor the applications stanza, so it is the one address object with no
    position in the rendered file.
    """
    indexed = {name for _, name in _seeded_book()}
    all_addresses = {
        entry["name"]
        for kind in ("SecurityIPAMIPPrefix", "SecurityIPAMIPAddress", "SecurityPrefix")
        for entry in _data(kind)
    }

    assert all_addresses - indexed == KEYWORDS


def test_book_indexes_are_unique() -> None:
    indexes = [i for i, _ in _seeded_book()]

    assert len(indexes) == len(set(indexes))
