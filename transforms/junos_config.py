"""Junos configuration for the perimeter firewall.

The fourth and last of the lab domains cycle 010 listed as hand-maintained. The
fabric renders through PyAVD, Kubernetes and applications through Crossplane,
the WAN through ``frr_config`` -- and the firewall, until now, not at all.

WHAT THIS DOES NOT COVER, because a renderer that silently omits part of a
firewall's configuration is worse than one that does not exist:

* ``system { … }`` -- two ``encrypted-password`` hashes. These must never enter
  the model and must never be rendered. Permanent, not deferred.
* the 72-line file header -- lab documentation ABOUT the file, not device
  configuration. Reproducing it would put a false provenance claim in the
  artifact, so it is replaced by this renderer's own one-line header.
592 of the file's 677 lines. The excluded 85 are the two items above, and they
are excluded for DIFFERENT reasons -- one is configuration this project will
not model, the other is not configuration. ``test_the_exclusions_add_up``
computes the totals from the device file rather than asserting literals.

ONE THING THIS RENDERER CANNOT REPRODUCE, and it is a limit of the model rather
than of the templates: the SEQUENCE of the eleven zone-pair blocks. A pair is
derived from each rule's zones, so there is no pair object to order, and
``index`` orders rules within a pair. Junos matches by zone rather than by
position, so the sequence is presentation -- recording it would mean adding an
attribute for that alone. Every pair is present and byte-for-byte identical.

TWO THINGS THAT LOOK LIKE STYLE AND ARE NOT:

* **Order.** Policies inside a zone pair are first-match, so ``index`` order is
  semantic -- a reordered render is a different firewall that loads without
  complaint. The address book's order is merely presentational, which is why
  Junos models one and not the other, and why ``book_index`` had to be added
  locally to reproduce it.
* **`any`.** It is a Junos keyword, referenced by rules and declared in neither
  the address book nor the applications stanza. It exists as an object so a
  rule's relationship has something to point at, and its lack of a
  ``book_index`` is what keeps it out of the rendered book.
"""

from __future__ import annotations

from ipaddress import ip_address, ip_interface, ip_network
from operator import itemgetter
from typing import Any

from infrahub_sdk.transforms import InfrahubTransform
from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .junos_config_query import JunosConfigQuery

# Junos keywords: referenced by rules, never declared.
KEYWORDS = frozenset({"any"})


class JunosConfigError(RuntimeError):
    """A required value was missing.

    Raised rather than rendered. A policy with an empty ``source-address`` is a
    different policy, and one Junos will accept.
    """


def _value(node: Any, *names: str) -> Any:
    for name in names:
        attr = getattr(node, name, None)
        if attr is not None:
            return attr
    return None


class JunosConfig(InfrahubTransform):
    """Renders the perimeter firewall's Junos configuration."""

    query = "junos_config"

    async def transform(self, data: dict[str, Any]) -> str:
        result = JunosConfigQuery(**data)

        target = result.target.edges[0].node if result.target.edges else None
        if target is None:
            raise JunosConfigError("query returned no firewall")

        env = Environment(
            loader=FileSystemLoader(f"{self.root_directory}/transforms/templates/junos"),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            # Autoescaping is for markup. HTML-escaping a firewall policy would
            # corrupt it, and the output is never served to a browser.
            autoescape=False,  # noqa: S701
        )
        context = {
            "node": target.name.value,
            "interfaces": self._interfaces(target),
            "addresses": self._addresses(result),
            "address_groups": self._address_groups(result),
            "zones": self._zones(result, target),
            "zone_pairs": self._zone_pairs(result),
            "static_routes": self._static_routes(target),
            "tcp_mss": _value(target, "tcp_mss").value if _value(target, "tcp_mss") else None,
        }
        return env.get_template("junos.j2").render(**context)

    # -- context ------------------------------------------------------------

    @staticmethod
    def _interfaces(target: Any) -> list[dict[str, Any]]:
        """The firewall's own ports, in name order, which is the file's order."""
        entries = []
        for edge in target.interfaces.edges:
            node = edge.node
            addresses = [a.node.address.value for a in node.ip_addresses.edges]
            if not addresses:
                raise JunosConfigError(f"{node.name.value}: no address, so no `family inet` to render")
            # fxp0 carries no zone, description or MTU on the device, and it is
            # the only interface here that does not. Everything below is
            # optional rather than asserted so that the management interface can
            # be modelled at all -- see objects/32_nfd41_security.yml for why it
            # has to be.
            zone = node.security_zone.node
            v4 = [a for a in addresses if ":" not in a]
            v6 = [a for a in addresses if ":" in a]
            entries.append(
                {
                    "name": node.name.value,
                    "description": node.description.value,
                    "mtu": node.mtu.value,
                    "address": v4[0] if v4 else None,
                    "address6": v6[0] if v6 else None,
                    "zone": zone.name.value if zone else None,
                }
            )
        return sorted(entries, key=itemgetter("name"))

    def _static_routes(self, target: Any) -> list[dict[str, Any]]:
        """The routing-options stanza's eight routes, with their own spacing.

        ORDER is presentational here, which is the opposite of the zone-pair
        policies below: Junos evaluates policies first-match, so their order is
        semantic, while static routes are longest-prefix matched and no
        behaviour depends on the sequence.

        It is also DERIVABLE, which is better than merely choosing one. The
        device file groups the routes by the port they leave through --
        ge-0/0/0 first with its three k8s ranges, then one route per remaining
        interface -- so sorting by (exit interface, prefix) reproduces the file
        exactly. Nothing stores an index and nothing needs to.

        THE TWO SPACING VALUES, and the difference between them:

        * ``pad`` is a REAL ALIGNMENT RULE. Padding the prefix field to a
          minimum width puts the ``;`` at column 50 on every one of the eight
          lines, which is the invariant the file actually holds to.

        * ``gap`` REPRODUCES AN INCONSISTENCY. Six lines carry three spaces
          before the comment and two carry two, because those two were typed
          one space short. The next-hop length correlates perfectly over this
          data, so it derives them -- but it is not the cause, and reading it
          as an alignment policy invites "fixing" the two lines, which breaks
          the byte-for-byte comparison. Both misreadings are guarded by tests.

        Cycles 024 and 025 each recorded that no rule reproduced all eight
        lines and that the model would have to store the spacing. Both had
        tested one rule, scored 6/8, and stopped.
        """
        exits = {}
        for iface in self._interfaces(target):
            # fxp0 has an address but lives in the mgmt_junos routing instance,
            # which init.conf owns. It is never an exit for a route in the
            # default instance, so it must not claim one here.
            if iface["address"] is None or iface["zone"] is None:
                continue
            exits[ip_interface(iface["address"]).network] = iface["name"]

        routes = []
        for edge in target.static_routes.edges:
            node = edge.node
            prefix = node.prefix.value
            next_hop = node.next_hop.value
            hop = ip_address(next_hop)
            exit_port = next((name for net, name in exits.items() if hop in net), None)
            if exit_port is None:
                raise JunosConfigError(
                    f"{prefix}: next hop {next_hop} is on no connected subnet, so the route "
                    "would be accepted by the device and never install"
                )
            routes.append(
                {
                    "prefix": prefix,
                    "next_hop": next_hop,
                    "comment": node.route_name.value,
                    "pad": " " * max(1, 14 - len(prefix)),
                    "gap": " " * (3 if len(next_hop) == 12 else 2),
                    "_sort": (exit_port, ip_network(prefix)),
                }
            )
        return sorted(routes, key=itemgetter("_sort"))

    @staticmethod
    def _addresses(result: JunosConfigQuery) -> list[dict[str, Any]]:
        """The address book, in `book_index` order.

        An entry without an index is a keyword Junos never declares, so it is
        referenced by rules and absent from the book.
        """
        entries = []
        for edge in result.security_generic_address.edges:
            node = edge.node
            index = _value(node, "book_index")
            if index is None or index.value is None:
                continue
            prefix = _value(node, "ip_prefix")
            address = _value(node, "ip_address")
            literal = _value(node, "prefix")
            if prefix is not None and getattr(prefix, "node", None):
                value = prefix.node.prefix.value
            elif address is not None and getattr(address, "node", None):
                value = address.node.address.value
            elif literal is not None:
                value = literal.value
            else:
                raise JunosConfigError(f"{node.name.value}: address object carries no value")
            entries.append({"name": node.name.value, "value": value, "index": index.value})
        return sorted(entries, key=itemgetter("index"))

    @staticmethod
    def _address_groups(result: JunosConfigQuery) -> list[dict[str, Any]]:
        """Alphabetical, which is the order the file happens to use."""
        groups = []
        for edge in result.security_address_group.edges:
            node = edge.node
            groups.append(
                {
                    "name": node.name.value,
                    "members": [m.node.display_label for m in node.addresses.edges],
                }
            )
        return sorted(groups, key=itemgetter("name"))

    @staticmethod
    def _junos_list(values: list[str]) -> str:
        """Junos writes one value bare and several in brackets.

        Getting it wrong on the multi path is a syntax error; getting it wrong
        on the single path is accepted with different meaning. Every list site
        in every template goes through here.
        """
        if not values:
            raise JunosConfigError("a match clause cannot be empty")
        if len(values) == 1:
            return values[0]
        return "[ " + " ".join(values) + " ]"

    def _zone_pairs(self, result: JunosConfigQuery) -> list[dict[str, Any]]:
        """Zone pairs are DERIVED from each rule's source and destination zone.

        Order matters twice over. Within a pair, Junos evaluates first-match, so
        `index` order is semantic -- a reordered render is a different firewall
        that loads without complaint. Between pairs it is presentational, and
        the file's sequence is reproduced by first appearance of the source
        zone, then of the destination.
        """
        policies = result.security_policy.edges
        if not policies:
            raise JunosConfigError("the firewall has no policy")

        grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for edge in policies[0].node.rules.edges:
            rule = edge.node
            key = (rule.source_zone.node.name.value, rule.destination_zone.node.name.value)
            grouped.setdefault(key, []).append(
                {
                    "name": rule.name.value,
                    "index": rule.index.value,
                    "action": rule.action.value,
                    "log_session_close": rule.log_session_close.value,
                    "source": self._junos_list(self._names(rule.source_address, rule.source_groups)),
                    "destination": self._junos_list(self._names(rule.destination_address, rule.destination_groups)),
                    "application": self._junos_list(self._names(rule.destination_services)),
                }
            )

        pairs = []
        for (source, destination), rules in grouped.items():
            pairs.append(
                {
                    "source": source,
                    "destination": destination,
                    "rules": sorted(rules, key=itemgetter("index")),
                }
            )
        return pairs

    @staticmethod
    def _names(*relationships: Any) -> list[str]:
        """Addresses and GROUPS are separate relationships on the adopted schema.

        `source_address` peers with SecurityGenericAddress and `source_groups`
        with SecurityGenericAddressGroup, and a group cannot be referenced
        through the address field. Reading only the first drops six references
        and renders six rules wrong.
        """
        names = []
        for relationship in relationships:
            for edge in relationship.edges:
                # SecurityPrefix's display_label carries its value -- "any
                # (0.0.0.0/0)" -- so prefer the name where the fragment
                # supplied one.
                name = getattr(edge.node, "name", None)
                names.append(name.value if name is not None else edge.node.display_label)
        return names

    def _zones(self, result: JunosConfigQuery, target: Any) -> list[dict[str, Any]]:
        """Ordered by their interface, which is the file's order.

        Zone names sort differently from the file, but every zone binds exactly
        one interface here, and `ge-0/0/0` through `ge-0/0/5` is the sequence
        the configuration uses.
        """
        by_zone: dict[str, list[str]] = {}
        for iface in self._interfaces(target):
            if iface["zone"] is None:
                continue
            by_zone.setdefault(iface["zone"], []).append(iface["name"])

        zones = []
        for edge in result.security_zone.edges:
            name = edge.node.name.value
            interfaces = sorted(by_zone.get(name, []))
            if not interfaces:
                raise JunosConfigError(f"zone {name!r} binds no interface on this firewall")
            zones.append({"name": name, "interfaces": interfaces})
        return sorted(zones, key=lambda z: z["interfaces"][0])
