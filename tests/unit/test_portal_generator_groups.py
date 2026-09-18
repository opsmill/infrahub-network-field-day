"""Every kind the portal offers must join the group its generator watches.

A generator definition targets a `CoreStandardGroup`, and a service created
outside that group is created and then **silently never built**. The request
succeeds, a proposed change opens, and nothing materialises -- which is
indistinguishable from a request still being worked on.

That is not hypothetical here. `ServiceFabricPeering` is DISCOVERED by the
catalog provider under the service generic rather than named in `kinds`, and a
discovered kind carries no `groups`. It was offered with a working form and a
working create mutation, and `generate-fabric-peering` never saw a single one.

The check is a cross-reference between two files that have no reason to agree
on their own: the portal's `infrahub.catalog.kinds` and this repository's
`.infrahub.yml` generator definitions.
"""

from __future__ import annotations

from pathlib import Path

import yaml

APP_CONFIG = Path("backstage/app-config.yaml")
INFRAHUB_YML = Path(".infrahub.yml")


def _portal_kinds() -> dict[str, list[str]]:
    config = yaml.safe_load(APP_CONFIG.read_text(encoding="utf-8"))
    return {entry["kind"]: entry.get("groups") or [] for entry in config["infrahub"]["catalog"]["kinds"]}


def _generator_targets() -> dict[str, str]:
    config = yaml.safe_load(INFRAHUB_YML.read_text(encoding="utf-8"))
    return {
        definition["name"]: definition["targets"]
        for definition in config.get("generator_definitions", [])
        if definition.get("targets")
    }


# Service kinds with no generator at all. The WAN three are rendered by
# `frr_config` from the service layer directly -- there is nothing to expand, so
# there is no group for them to be missing from.
WITHOUT_GENERATORS = {
    "ServiceL3vpn",
    "ServiceTenantCloud",
    "ServiceInternetAccess",
}


def _service_kinds() -> set[str]:
    """Every service kind, from the schemas rather than from the portal config.

    THIS IS THE WHOLE POINT OF THE TEST. The provider DISCOVERS kinds under the
    service generic, so a kind absent from `infrahub.catalog.kinds` is still
    offered -- with a form, a create mutation, and no groups. A check that
    iterated the config would not see the one kind this was written for, which
    is exactly the mistake the first version of this test made: removing the
    entry again left it passing.
    """
    kinds = set()
    for path in sorted(Path("schemas/service").glob("*.yml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        for node in document.get("nodes") or []:
            if "ServiceGeneric" in (node.get("inherit_from") or []):
                kinds.add(f"{node['namespace']}{node['name']}")
    return kinds


def test_every_service_kind_joins_its_generators_group() -> None:
    """The cross-reference, in the direction that matters.

    A kind the portal offers whose generator watches a group it does not join
    produces a request that can never be fulfilled: created, proposed, and never
    built.
    """
    targets = set(_generator_targets().values())
    configured = _portal_kinds()

    orphaned = [
        kind
        for kind in sorted(_service_kinds())
        if kind not in WITHOUT_GENERATORS and not (set(configured.get(kind) or []) & targets)
    ]
    assert not orphaned, (
        f"offered by the portal but in no group a generator targets: {orphaned}. "
        "A request for one of these is created and then never built. Name the "
        "kind in app-config.yaml with its generator's group -- discovery alone "
        "gives it none."
    )


def test_the_kinds_without_generators_really_have_none() -> None:
    """The exemption list is an assertion, not a way to silence the test.

    Adding a generator for one of these without removing it here would let the
    first test pass while the kind went unbuilt -- the very thing it guards.
    """
    generators = _generator_targets()
    for kind in WITHOUT_GENERATORS:
        # A generator for `ServiceL3vpn` would be named for it; nothing in this
        # repository maps a kind to a definition name, so the group is the link.
        expected = f"service_{kind.removeprefix('Service').lower()}s"
        assert expected not in generators.values(), (
            f"{kind} now has a generator targeting {expected}; "
            "give it that group in app-config.yaml and drop it from WITHOUT_GENERATORS"
        )
