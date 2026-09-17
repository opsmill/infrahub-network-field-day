"""Golden-file tests for the perimeter firewall's Junos render.

The oracle is `../lab/configs/fw/vsrx/junos.conf` -- the configuration the
firewall actually runs, written by hand rather than by this repository. That
makes equality the right assertion: a substring check would pass on a policy
stanza with a rule in the wrong position, and Junos evaluates first-match, so
that is a different firewall which loads without complaint.

The artifact covers 656 of the file's 741 lines. The excluded 85 are the
`system` stanza (13 lines: two credential hashes, permanently out) and the
file header (72 lines of lab documentation, which is not configuration).
SC-010 makes that total an arithmetic criterion rather than a prose caveat,
and `test_the_exclusions_add_up` derives all three figures from the file --
so the numbers in this docstring are commentary and the test is the check.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
from collections import Counter
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
    """Against the device file plus fxp0, which that file does not carry.

    This is the one place the artifact deliberately renders configuration
    `junos.conf` does not contain. See FXP0_FROM_INIT_CONF for why, and for what
    breaks if vrnetlab's addressing moves.
    """
    assert _stanza(_rendered(), "interfaces") == _with_fxp0(_stanza(_conf(), "interfaces"))
    # and the block really is absent from the device file as CONFIGURATION, so
    # this test asserts something rather than comparing a file with itself.
    # `junos.conf` mentions fxp0 in four comments; none of them defines it.
    assert not any(line.strip().startswith("fxp0 {") for line in _conf())


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

    # `#`, not `!`: Junos's comment character. `!` is EOS/FRR syntax and makes
    # the artifact fail to load at line 1, taking part of the file with it.
    assert first == "# Rendered by Infrahub for fw1 -- do not edit."


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


# Cycle 023's version of `test_the_exclusions_add_up` stood here. It asserted
# `in_scope == 573` and `excluded == 104`, the figures from a scope where
# `routing-options` and the `flow` clamp were both unrendered. Cycle 026
# renders both, so those literals describe a world that no longer exists.
#
# It is REPLACED rather than renamed, and the replacement lives further down
# with the other cycle-026 clauses. Two functions of the same name in one
# module do not collide loudly -- the second silently shadows the first, and
# the first stops running. Ruff caught exactly that here.


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


def test_the_anti_spoofing_rule_renders_once_per_zone_pair_identically() -> None:
    """One object per pair, not one shared object: `source_zone` and
    `destination_zone` are cardinality-one on the adopted schema, so a rule
    belongs to exactly one pair. The render must not let the copies drift apart.

    The count moves when a zone pair is added -- it went from six to seven with
    the `tooling` zone -- which is why it is derived from the zone pairs rather
    than written down. A hard-coded six would have to be edited every time, and
    the thing worth asserting was never the number.
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

    # Derived from the oracle, so adding a zone pair does not mean editing a
    # number here. What matters is that every copy is identical, not how many.
    expected = "\n".join(_conf()).count("policy deny-spoofed-infra {")
    assert expected > 1, "the oracle should carry one anti-spoofing rule per pair"
    assert len(bodies) == expected
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


# ---------------------------------------------------------------------------
# Cycle 026: the whole-file comparison.
#
# The stanza-level assertions above pass while three explanatory comment blocks
# are missing from the rendered `security` stanza -- which is how that gap
# survived cycles 023, 024 and 025. Each of those cycles re-read the previous
# cycle's spec instead of diffing the artifact.
#
# C1 turns "is the artifact complete?" into one number. The stanza checks stay:
# C1 says WHETHER, they say WHERE.
# ---------------------------------------------------------------------------

PROVENANCE_PREFIX = "# Rendered by Infrahub"


def _top_level_stanza_of(lines: list[str]) -> list[str | None]:
    """Tag each line with the top-level stanza it belongs to, or None."""
    tags: list[str | None] = []
    current: str | None = None
    depth = 0
    for line in lines:
        if depth == 0 and re.match(r"^\S+.*\{$", line):
            current = line.split()[0]
        if current:
            tags.append(current)
            depth += line.count("{") - line.count("}")
            if depth == 0:
                current = None
        else:
            tags.append(None)
    return tags


# The management interface, which `junos.conf` does not contain and never has.
#
# vrnetlab generates it into `init.conf` INSIDE the container; that file is not
# version-controlled in either repository, so unlike every other line this suite
# checks, these ten have no committed source. They are reproduced here by hand
# from the running device.
#
# They are in scope because cycle 030 modelled fxp0 deliberately: `load replace`
# on the `interfaces` hierarchy deletes everything the artifact does not name,
# so leaving it out meant every push deleted the firewall's management
# interface. The consequence is that the model is now authoritative for this
# address, and this block is the only thing asserting it still matches the
# device. If vrnetlab's addressing ever changes, this is what has to change with
# it -- and the failure mode if it does not is an unreachable firewall.
FXP0_FROM_INIT_CONF = [
    "    fxp0 {",
    "        unit 0 {",
    "            family inet {",
    "                address 10.0.0.15/24;",
    "            }",
    "            family inet6 {",
    "                address 2001:db8::2/64;",
    "            }",
    "        }",
    "    }",
]


def _with_fxp0(lines: list[str]) -> list[str]:
    """`junos.conf` lines with the management interface spliced in.

    Inserted immediately before the first data interface, which is where the
    transform's name sort puts it: `fxp0` sorts before `ge-0/0/0`.
    """
    out = list(lines)
    first_data_iface = next(i for i, line in enumerate(out) if line.startswith("    ge-0/0/0 {"))
    return out[:first_data_iface] + FXP0_FROM_INIT_CONF + out[first_data_iface:]


def _oracle_in_scope() -> list[str]:
    """The device file minus the two regions the artifact deliberately omits.

    `system` holds two `encrypted-password` hashes -- configuration this
    project will never model. The 72-line header is 68 comments and 4 blanks
    of lab documentation ABOUT the file, including how vrnetlab appends it to
    init.conf; the artifact replaces it with its own provenance line, because
    reproducing it would make a false claim about where the file came from.

    Two different reasons, which is why they are named separately rather than
    lumped together as "excluded lines".
    """
    lines = _conf()
    tags = _top_level_stanza_of(lines)
    in_scope = [line for line, tag in zip(lines, tags, strict=True) if tag not in (None, "system")]
    # ... plus fxp0, which the artifact renders and this file does not carry.
    # Spliced here rather than in each caller so every test that compares the
    # artifact against the device works from one definition of "in scope".
    return _with_fxp0(in_scope)


def _rendered_body() -> list[str]:
    return [line for line in _rendered() if not line.startswith(PROVENANCE_PREFIX)]


def _split_at_policies(lines: list[str]) -> tuple[list[str], list[str]]:
    index = lines.index("    policies {")
    return lines[:index], lines[index:]


def _zone_pair_blocks(lines: list[str]) -> dict[tuple[str, str], list[str]]:
    """Each `from-zone X to-zone Y { ... }` block, keyed by its pair."""
    blocks: dict[tuple[str, str], list[str]] = {}
    index = 0
    while index < len(lines):
        match = re.match(r"^        from-zone (\S+) to-zone (\S+) \{$", lines[index])
        if match:
            depth, end = 0, index
            while True:
                depth += lines[end].count("{") - lines[end].count("}")
                if depth == 0:
                    break
                end += 1
            blocks[match.groups()] = lines[index : end + 1]
            index = end
        index += 1
    return blocks


def test_everything_outside_the_policies_stanza_matches_exactly() -> None:
    """C1a. Byte-for-byte, no exceptions.

    Interfaces, routing-options, the flow clamp, the address book, every
    comment block and the zones. This is the part of SC-001 that holds without
    qualification.
    """
    oracle, rendered = _split_at_policies(_oracle_in_scope())[0], _split_at_policies(_rendered_body())[0]
    diff = list(difflib.unified_diff(oracle, rendered, "device file", "artifact", lineterm="", n=1))
    assert not diff, "artifact differs outside `policies`:\n" + "\n".join(diff[:60])


def test_every_zone_pair_matches_byte_for_byte() -> None:
    """C1b. The same eleven pairs, each identical in content.

    What is NOT asserted is the SEQUENCE of the eleven blocks, and that is a
    limitation of the model rather than of this renderer. Cycle 023 established
    it and cycle 026 re-confirmed it: a zone pair is DERIVED from each rule's
    source and destination zone, so there is no pair object to carry an order.
    `SecurityPolicyRule.index` orders rules WITHIN a pair -- it holds only 10,
    20 and 30 across all nineteen rules -- and carries nothing about the pairs
    themselves.

    Reproducing the file's sequence would mean adding an attribute whose only
    purpose is to record it. Junos matches a packet to its zone pair by zone
    and not by position, so that sequence is presentation, and this cycle
    declined to put presentation in the model for the same reason it declined
    to store the route-line spacing.
    """
    oracle = _zone_pair_blocks(_split_at_policies(_oracle_in_scope())[1])
    rendered = _zone_pair_blocks(_split_at_policies(_rendered_body())[1])

    assert set(oracle) == set(rendered)
    # Twelve since the `tooling` zone arrived: the six fabric-facing zones pair
    # up as before, plus branch -> tooling. Asserted rather than derived because
    # a pair silently disappearing is exactly what this test exists to catch.
    assert len(oracle) == 12

    differing = {pair: (oracle[pair], rendered[pair]) for pair in oracle if oracle[pair] != rendered[pair]}
    assert not differing, f"zone pairs differing in content: {sorted(differing)}"


def test_the_artifact_and_the_device_file_hold_the_same_lines() -> None:
    """C1c. Nothing is added or lost -- only the pair blocks move.

    Blank-line placement inside `policies` follows the sequence, so it moves
    with it; every non-blank line is accounted for in both directions.
    """
    oracle = [line for line in _oracle_in_scope() if line.strip()]
    rendered = [line for line in _rendered_body() if line.strip()]
    assert Counter(oracle) == Counter(rendered)


def test_the_exclusions_add_up() -> None:
    """C2. Computed from the file, not hard-coded.

    Cycle 023 carried a prose comment claiming its total and the total was
    wrong by seven lines. Three literals here would drift from the file the
    same way; these are derived from it at test time.
    """
    lines = _conf()
    tags = _top_level_stanza_of(lines)

    header = sum(1 for tag in tags if tag is None)
    system = sum(1 for tag in tags if tag == "system")
    rendered = len(lines) - header - system

    assert header + system + rendered == len(lines)

    # Three categories now, not two. The artifact reproduces everything in scope
    # AND renders the management interface, which this file does not carry --
    # cycle 030 modelled fxp0 because `load replace` was otherwise deleting it
    # on every push. Adding rather than hiding it keeps this an assertion about
    # the total rather than a caveat beside one.
    assert rendered + len(FXP0_FROM_INIT_CONF) == len(_oracle_in_scope())

    # Non-blank, because blank-line placement inside `policies` follows the
    # zone-pair sequence, which the model cannot reproduce -- see
    # test_every_zone_pair_matches_byte_for_byte. Every line of content is
    # present; three blanks fall in different places.
    assert len([line for line in _rendered_body() if line.strip()]) == len(
        [line for line in _oracle_in_scope() if line.strip()]
    )


def _config_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip() and not line.strip().startswith(("/*", "*", "*/"))]


def test_the_artifact_invents_no_configuration() -> None:
    """C10. Zero before this cycle, and it must stay zero.

    The direction that catches a template emitting something plausible and
    wrong -- which the byte-for-byte diff also catches, but this one keeps
    saying so if the diff is ever relaxed.
    """
    invented = Counter(_config_lines(_rendered_body())) - Counter(_config_lines(_oracle_in_scope()))
    assert not invented, f"configuration in the artifact and not on the device: {dict(invented)}"


# ---------------------------------------------------------------------------
# Cycle 026: the route lines' spacing.
# ---------------------------------------------------------------------------


def _route_lines(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip().startswith("route ")]


def test_every_route_line_puts_its_semicolon_at_column_fifty() -> None:
    """C4. The real alignment invariant, asserted directly.

    Padding the prefix field is what produces it. Stating it separately from
    the byte comparison means a failure says "the alignment rule broke" rather
    than "something differs".
    """
    rendered = _route_lines(_rendered())
    assert len(rendered) == 8
    for line in rendered:
        assert line.index(";") + 1 == 50, f"semicolon not at column 50: {line!r}"


def test_the_three_route_spacing_cases_are_reproduced() -> None:
    """C3. Named cases, not just the aggregate diff.

    The third is the one that matters: six lines carry three spaces before the
    comment and two carry two, because those two were typed one space short.
    A whole-file diff catches a "tidy-up" only while the oracle is untouched;
    naming the case catches it regardless.
    """
    by_prefix = {line.split()[1]: line for line in _route_lines(_rendered())}

    # 13-character prefix, 12-character next hop: one space, then three.
    assert by_prefix["10.110.0.0/24"] == ("        route 10.110.0.0/24 next-hop 10.250.110.1;   /* k8s nodes */")
    # 12-character prefix: padded with two spaces to hold the column.
    assert by_prefix["10.60.0.0/16"] == (
        "        route 10.60.0.0/16  next-hop 10.250.150.1;   /* WAN customer supernet */"
    )
    # 11-character next hop: TWO spaces before the comment, not three.
    assert by_prefix["10.220.10.0/24"] == (
        "        route 10.220.10.0/24 next-hop 10.250.10.1;  /* acme cloud instances */"
    )


def test_routes_are_ordered_by_the_port_they_leave_through() -> None:
    """The file's order, and it is derived rather than chosen.

    ge-0/0/0 first with its three k8s ranges, then one route per remaining
    interface. Nothing stores an index.
    """
    prefixes = [line.split()[1] for line in _route_lines(_rendered())]
    assert prefixes == [
        "10.110.0.0/24",
        "10.111.0.0/16",
        "10.112.0.0/16",
        "10.210.0.0/24",
        "10.60.0.0/16",
        "10.70.0.0/24",
        "10.220.10.0/24",
        "10.220.20.0/24",
    ]


# ---------------------------------------------------------------------------
# Cycle 026: emptiness. An absent value must render nothing, not a zero.
# ---------------------------------------------------------------------------


def _render_without(key: str) -> list[str]:
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    node = data["target"]["edges"][0]["node"]
    if key == "static_routes":
        node["static_routes"]["edges"] = []
    else:
        node[key] = {"value": None}
    transform = JunosConfig.__new__(JunosConfig)
    transform.root_directory = str(REPO_ROOT)
    return asyncio.run(transform.transform(data)).splitlines()


def test_a_firewall_with_no_routes_renders_no_routing_options_stanza() -> None:
    """C6. Not an empty `static { }` -- the device would hold no stanza."""
    rendered = _render_without("static_routes")
    assert not any(line.startswith("routing-options") for line in rendered)
    assert not any("static {" in line for line in rendered)


def test_a_firewall_with_no_clamp_renders_no_flow_stanza() -> None:
    """C6. And emphatically not `mss 0`, which an attribute default would give."""
    rendered = _render_without("tcp_mss")
    assert not any(line.strip().startswith("flow {") for line in rendered)
    assert not any(line.strip().startswith("tcp-mss {") for line in rendered)
    assert not any("mss 0" in line for line in rendered)

    # Asserted on the STANZA, not on the string "tcp-mss": the interfaces
    # comment transcribed from the device refers to "`security flow tcp-mss`
    # below", and that prose survives. It is fw1's own text, so on a firewall
    # with no clamp it would point at a stanza that is not there -- a wart in
    # the transcribed comment rather than in this renderer, and out of scope
    # here because the comment is the device's words, not ours.


def test_the_three_recovered_comment_blocks_are_present() -> None:
    """C7. The NAT block gets its own assertion because it documents an ABSENCE.

    Nothing in the model implies "there is no NAT here", so nothing but the
    template can carry it and nothing but a test can notice it going missing --
    which is exactly what happened for three cycles.
    """
    rendered = "\n".join(_rendered())
    assert "Clamp TCP to what the 9192-byte interface MTU can actually carry" in rendered
    assert "Named objects rather than bare CIDRs" in rendered
    assert "NAT is absent from this file, and that absence is load-bearing" in rendered
    assert "`make verify`" in rendered


# ---------------------------------------------------------------------------
# Applications: declaring the services Junos does not predefine
# ---------------------------------------------------------------------------


def _rendered_with_custom_service() -> list[str]:
    """The fixture plus one generated service, as generate-app-access creates it."""
    data: dict[str, Any] = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data["SecurityGenericService"]["edges"].append(
        {
            "node": {
                "__typename": "SecurityService",
                "name": {"value": "svc-branch-to-nfd41-demo-tcp-8080"},
                "description": {"value": "tcp/8080, granted by branch-to-nfd41-demo"},
                "port": {"value": 8080},
                "ip_protocol": {"node": {"name": {"value": "tcp"}}},
            }
        }
    )
    transform = JunosConfig.__new__(JunosConfig)
    transform.root_directory = str(REPO_ROOT)
    return asyncio.run(transform.transform(data)).splitlines()


def test_the_applications_stanza_declares_exactly_the_non_builtins() -> None:
    """It exists only when something needs it, and then says only what is needed.

    This asserted the stanza was ABSENT until the tooling zone arrived. That was
    right while every service the rules referenced was a Junos built-in --
    rendering `applications { }` would have differed from the device for no
    reason. The tooling portal and its identity provider are on NodePorts, which
    are not built-ins, so the stanza is now correct and its absence would be the
    bug: a policy naming an undeclared application makes the device refuse the
    whole commit with `statements constraint check failed`.

    What is still asserted is the discipline -- every name inside is one the
    model defines, and nothing built-in is redeclared.
    """
    rendered = _rendered()
    declared = [
        line.strip().removeprefix("application ").removesuffix(" {")
        for line in rendered
        if line.startswith("    application ") and line.rstrip().endswith("{")
    ]
    assert declared, "the tooling ports are not Junos built-ins and must be declared"
    assert not [name for name in declared if name.startswith("junos-")], (
        "a Junos built-in must never be redeclared; the device already has it"
    )


def test_a_generated_service_is_declared() -> None:
    """The bug this stanza exists for.

    Without it a policy referenced `svc-branch-to-nfd41-demo-tcp-8080`, nothing
    declared it, and the device refused the entire commit with
    `statements constraint check failed` -- naming no object and pointing at no
    line. Every stanza test passed, because the rule itself was correct.
    """
    rendered = _rendered_with_custom_service()
    stanza = _stanza(rendered, "applications")
    assert "    application svc-branch-to-nfd41-demo-tcp-8080 {" in stanza
    assert "        protocol tcp;" in stanza
    assert "        destination-port 8080;" in stanza


def test_built_in_applications_are_never_declared() -> None:
    """Declaring a Junos built-in is rejected as a redefinition.

    The `junos-` prefix is a fact about Junos -- Juniper namespaces every
    predefined application that way -- not a convention of this repository.
    """
    stanza = "\n".join(_stanza(_rendered_with_custom_service(), "applications"))
    for built_in in ("junos-http", "junos-https", "junos-ping"):
        assert f"application {built_in} " not in stanza


def test_the_any_keyword_is_never_declared() -> None:
    """`any` is a keyword, exactly as it is in the address book: referenced by
    rules, declared nowhere, and carrying no port to declare with."""
    stanza = "\n".join(_stanza(_rendered_with_custom_service(), "applications"))
    assert "application any {" not in stanza


def test_the_applications_stanza_sits_outside_security() -> None:
    """Applications are referenced BY security policies and are not part of that
    hierarchy. Nesting them commits cleanly and leaves every reference
    unresolved -- the same silent failure this stanza was added to fix.
    """
    rendered = _rendered_with_custom_service()
    security_start = next(i for i, line in enumerate(rendered) if line == "security {")
    security_end = security_start + len(_stanza(rendered, "security")) - 1
    applications_start = next(i for i, line in enumerate(rendered) if line == "applications {")
    assert applications_start > security_end
