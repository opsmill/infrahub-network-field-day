"""The lab DNS service holds together across its files (specs/037-lab-dns-service).

The resolver's address is written in four places because three of them are read
without Infrahub (the branch machine's init script is rendered from
`lab/wan/tenants.yml`, the firewall's baseline is a device file, and the chart
values are a payload). Every copy is held equal to the one in the seed data here,
so a change to one fails by name instead of as a resolver nobody can reach.
"""

from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
RESOLVER = "otternet-dns"
ZONE = "int.otternet.lab"


def _docs(name: str) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all((REPO / name).read_text(encoding="utf-8")) if d]


def _objects(file: str, kind: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for doc in _docs(file):
        spec = doc.get("spec") or {}
        if spec.get("kind") == kind:
            out.extend(spec["data"])
    return out


def _resolver() -> dict[str, Any]:
    apps = [a for a in _objects("objects/36_otternet_app_services.yml", "ServiceFabricApp") if a["name"] == RESOLVER]
    assert len(apps) == 1
    return apps[0]


def _values() -> dict[str, Any]:
    return yaml.safe_load((REPO / "payloads/otternet-dns-values.yaml").read_text(encoding="utf-8"))


def _infrahub_yml() -> dict[str, Any]:
    return yaml.safe_load((REPO / ".infrahub.yml").read_text(encoding="utf-8"))


def _first_address(prefix: str) -> str:
    return str(ipaddress.ip_network(prefix, strict=False).network_address)


def test_exactly_one_application_is_the_resolver_and_it_is_in_both_groups() -> None:
    apps = _objects("objects/36_otternet_app_services.yml", "ServiceFabricApp")
    assert [a["name"] for a in apps if a.get("dns_zone")] == [RESOLVER]
    assert _resolver()["dns_zone"] == ZONE
    assert {"service_fabric_apps", "dns_resolvers"} <= set(_resolver()["member_of_groups"])
    groups = {g["name"] for g in _objects("objects/00_groups.yml", "CoreStandardGroup")}
    assert "dns_resolvers" in groups


def test_the_resolvers_address_is_the_same_in_every_place_it_is_written() -> None:
    block = _resolver()["vip_block"][0]
    address = _first_address(block)

    pinned = _values()["service"]["annotations"]["lbipam.cilium.io/ips"]
    assert pinned == address, "the Service must take the first address of the block: the name and the rule use it"

    host = next(
        h
        for h in yaml.safe_load((REPO / "lab/wan/tenants.yml").read_text(encoding="utf-8"))["branch"]["hosts"]
        if h["node"] == "branch-desktop"
    )
    assert host["dns"] == {"server": address, "zone": ZONE}

    named = [
        a
        for a in _objects("objects/32_otternet_security.yml", "IpamIPAddress")
        if a.get("fqdn") == f"{RESOLVER}.{ZONE}"
    ]
    assert [a["address"] for a in named] == [f"{address}/32"]

    entry = next(
        a for a in _objects("objects/32_otternet_security.yml", "SecurityIPAMIPAddress") if a["name"] == "dns-resolver"
    )
    assert entry["ip_address"] == [f"{address}/32", "default"]

    conf = (REPO / "lab/configs/fw/vsrx/junos.conf").read_text(encoding="utf-8")
    assert f"address dns-resolver {address}/32;" in conf


def test_the_vip_block_is_declared_so_the_pool_skips_it_and_lies_inside_the_pool() -> None:
    block = _resolver()["vip_block"][0]
    prefixes = {p["prefix"]: p for p in _objects("objects/29_otternet_offfabric_prefixes.yml", "IpamPrefix")}
    assert block in prefixes
    assert ipaddress.ip_network(block).subnet_of(ipaddress.ip_network("10.112.240.0/24"))


def test_the_charts_zone_file_name_matches_the_zone_the_artifact_writes() -> None:
    names = [z["filename"] for z in _values()["zoneFiles"]]
    assert names == [f"{ZONE}.db"]
    assert _values()["fullnameOverride"] == "lab-dns", "the ConfigMap the transform writes is named for the release"
    assert _values()["deployment"]["skipConfig"] is True


def test_the_catalogue_entry_and_the_application_agree_on_the_chart() -> None:
    entry = next(
        e
        for e in _objects("objects/35a_otternet_app_catalogue.yml", "ServiceApplicationDefinition")
        if e["name"] == "lab-dns"
    )
    app = _resolver()
    for key in ("chart_repository", "chart_name", "chart_version"):
        assert entry[key] == app[key]
    assert entry["requestable"] is False
    assert app["definition"] == "lab-dns"
    assert app["definition_pinned"] is True


def test_the_resolver_admits_the_branch_lan_on_53_over_both_protocols() -> None:
    app = _resolver()
    assert app["allowed_source_prefixes"] == [["10.70.0.0/24", "default"]]
    assert {(p["port"], p["protocol"]) for p in app["policy_allow_ports"]} == {("53", "UDP"), ("53", "TCP")}
    services = {s["name"]: s for s in _objects("objects/32_otternet_security.yml", "SecurityService")}
    for name in app["advertised_services"]:
        assert services[name]["port"] == 53
    assert {services[n]["ip_protocol"] for n in app["advertised_services"]} == {"udp", "tcp"}
    protocols = {p["name"] for p in _objects("objects/32_otternet_security.yml", "SecurityIPProtocol")}
    assert "udp" in protocols


def test_the_standing_firewall_rule_sits_between_the_portal_rule_and_the_ping_rule() -> None:
    rules = [
        r
        for r in _objects("objects/32_otternet_security.yml", "SecurityPolicyRule")
        if r.get("source_zone") == "branch" and r.get("destination_zone") == "k8s-prod"
    ]
    by_index = {r["index"]: r["name"] for r in rules}
    assert by_index[10] == "deny-spoofed-infra"
    assert by_index[20] == "branch-to-access-portal"
    assert by_index[25] == "branch-to-dns"
    assert by_index[30] == "branch-to-k8s-icmp"
    rule = next(r for r in rules if r["name"] == "branch-to-dns")
    assert rule["managed_by_service"] is False
    assert rule["source_address"] == ["branch-users"]
    assert rule["destination_address"] == ["dns-resolver"]


def test_the_artifact_the_sync_delivers_is_the_one_the_resolver_group_targets() -> None:
    config = _infrahub_yml()
    definition = next(a for a in config["artifact_definitions"] if a["name"] == "dns_zone_config")
    assert definition["targets"] == "dns_resolvers"
    syncs = _docs("vidra/infrahub-syncs.yaml")
    sync = next(s for s in syncs if s["metadata"]["name"] == "dns-zone-config")
    assert sync["spec"]["source"]["artefactName"] == definition["artifact_name"]
    assert sync["spec"]["destination"]["namespace"] == _resolver()["namespace_name"]


def test_everything_registered_exists_on_disk() -> None:
    config = _infrahub_yml()
    queries = {q["name"]: q["file_path"] for q in config["queries"]}
    for name in ("dns_zone_config", "generate_dns_record", "dns_zone_check"):
        assert (REPO / queries[name]).is_file(), name
    generator = next(g for g in config["generator_definitions"] if g["name"] == "generate-dns-record")
    assert (REPO / generator["file_path"]).is_file()
    assert generator["query"] in queries
    assert generator["targets"] == "service_fabric_apps"
    transform = next(t for t in config["python_transforms"] if t["name"] == "dns_zone_config")
    assert (REPO / transform["file_path"]).is_file()
    check = next(c for c in config["check_definitions"] if c["name"] == "dns-zone-consistency")
    assert (REPO / check["file_path"]).is_file()


def test_the_trigger_rules_run_the_generator_and_name_no_forbidden_kind() -> None:
    triggers = _docs("triggers.yml")
    actions = [
        d for doc in triggers for d in (doc["spec"]["data"] if doc["spec"]["kind"] == "CoreGeneratorAction" else [])
    ]
    assert {"name": "run-dns-record-generator", "generator": "generate-dns-record"} in actions
    rules = [
        d
        for doc in triggers
        for d in (doc["spec"]["data"] if doc["spec"]["kind"] == "CoreNodeTriggerRule" else [])
        if d.get("action") == "run-dns-record-generator"
    ]
    assert len(rules) == 4
    for rule in rules:
        assert rule["node_kind"] == "ServiceFabricApp"
        assert not rule["node_kind"].startswith(("Deployment", "Monitoring"))
