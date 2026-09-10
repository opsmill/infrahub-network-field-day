"""Contract for how `avd_custom_hostvars` composes with generated host_vars.

The override is the documented way to carry AVD inputs this design does not
model natively, at fabric, pod and device scope. For that to be usable it has to
compose with generated data rather than lose to it — and the failure mode when it
does not is silent: a replaced list raises nothing, it just renders configuration
with the override missing.

Precedence is unchanged throughout: where both sides describe the same thing, the
generated value wins.
"""

from __future__ import annotations

from generators.generate_avd_device_hostvar import GenerateAVDDeviceHostvar as Gen


class TestReachingInsideGeneratedLists:
    """The case the override model exists for."""

    def test_override_adds_a_static_route_to_a_generated_vrf(self) -> None:
        """An override reaches into `tenants` even though the generator emits it.

        Before this, modelling any tenant natively meant the whole `tenants` list
        was generated, so a per-VRF override was discarded outright.
        """
        merged = Gen._deep_merge(
            {
                "tenants": [
                    {
                        "name": "TENANT_K8S",
                        "vrfs": [
                            {
                                "name": "K8S_PROD",
                                "static_routes": [{"prefix": "0.0.0.0/0", "next_hop": "10.250.110.2"}],
                            }
                        ],
                    }
                ]
            },
            {"tenants": [{"name": "TENANT_K8S", "vrfs": [{"name": "K8S_PROD", "vrf_vni": 110}]}]},
        )

        vrf = merged["tenants"][0]["vrfs"][0]
        assert vrf["vrf_vni"] == 110
        assert vrf["static_routes"] == [{"prefix": "0.0.0.0/0", "next_hop": "10.250.110.2"}]

    def test_generated_still_wins_on_a_field_both_describe(self) -> None:
        merged = Gen._deep_merge(
            {"tenants": [{"name": "T1", "mac_vrf_vni_base": 999}]},
            {"tenants": [{"name": "T1", "mac_vrf_vni_base": 11000}]},
        )

        assert merged["tenants"][0]["mac_vrf_vni_base"] == 11000

    def test_override_only_entries_survive_alongside_generated_ones(self) -> None:
        merged = Gen._deep_merge(
            {"tenants": [{"name": "TENANT_EXTRA"}]},
            {"tenants": [{"name": "TENANT_K8S"}]},
        )

        assert [tenant["name"] for tenant in merged["tenants"]] == ["TENANT_EXTRA", "TENANT_K8S"]

    def test_identity_key_is_resolved_per_list_not_by_field_name(self) -> None:
        """`nodes` means different things in different places.

        `svis[].nodes` entries are keyed by `node`; `l3leaf.nodes` entries by
        `name`. Resolving the key from the entries themselves handles both
        without a path map.
        """
        merged = Gen._deep_merge(
            {"svis": [{"id": 110, "nodes": [{"node": "k8s-leaf1", "ip_address": "10.110.0.2/24"}]}]},
            {"svis": [{"id": 110, "nodes": [{"node": "k8s-leaf2", "ip_address": "10.110.0.3/24"}]}]},
        )

        assert [entry["node"] for entry in merged["svis"][0]["nodes"]] == ["k8s-leaf1", "k8s-leaf2"]


class TestListsThatMustNotMerge:
    """Where merging would be wrong, or would silently corrupt the input."""

    def test_topology_lists_stay_generator_owned(self) -> None:
        """`<node_type>.nodes` names devices AVD has to resolve facts for.

        Merging would let an override inject a device that does not exist in
        Infrahub, is not cabled and has no host_vars of its own — an AVD input
        that fails a long way from its cause. Infrahub owns the topology.
        """
        merged = Gen._deep_merge(
            {"l3leaf": {"nodes": [{"name": "phantom-leaf", "id": 999}]}},
            {"l3leaf": {"nodes": [{"name": "k8s-leaf1", "id": 1}]}},
        )

        assert merged["l3leaf"]["nodes"] == [{"name": "k8s-leaf1", "id": 1}]

    def test_node_groups_stay_generator_owned(self) -> None:
        merged = Gen._deep_merge(
            {"l3leaf": {"node_groups": [{"group": "PHANTOM"}]}},
            {"l3leaf": {"node_groups": [{"group": "K8S_LEAFS"}]}},
        )

        assert merged["l3leaf"]["node_groups"] == [{"group": "K8S_LEAFS"}]

    def test_a_nodes_list_outside_a_node_type_still_merges(self) -> None:
        """The exclusion is scoped to node-type keys, not to the name `nodes`."""
        merged = Gen._deep_merge(
            {"svis": [{"id": 110, "nodes": [{"node": "leaf1"}]}]},
            {"svis": [{"id": 110, "nodes": [{"node": "leaf2"}]}]},
        )

        assert len(merged["svis"][0]["nodes"]) == 2

    def test_scalar_lists_are_replaced(self) -> None:
        merged = Gen._deep_merge(
            {"l3leaf": {"defaults": {"bgp_defaults": ["no bgp default ipv4-unicast"]}}},
            {"l3leaf": {"defaults": {"bgp_defaults": ["distance bgp 20 200 200"]}}},
        )

        assert merged["l3leaf"]["defaults"]["bgp_defaults"] == ["distance bgp 20 200 200"]

    def test_a_device_name_list_inside_an_entry_is_replaced(self) -> None:
        """`static_routes[].nodes` is a list of hostnames, so it is replaced whole.

        Merging hostname strings would produce a route originated on the union of
        two device sets, which nobody asked for.
        """
        merged = Gen._deep_merge(
            {"static_routes": [{"prefix": "0.0.0.0/0", "next_hop": "10.0.0.1", "nodes": ["old-leaf"]}]},
            {"static_routes": [{"prefix": "0.0.0.0/0", "next_hop": "10.0.0.1", "nodes": ["border-leaf1"]}]},
        )

        assert merged["static_routes"][0]["nodes"] == ["border-leaf1"]

    def test_entries_with_no_shared_scalar_key_are_replaced(self) -> None:
        merged = Gen._deep_merge(
            {"custom_platform_settings": [{"platforms": ["cEOS-LAB"], "reload_delay": {"mlag": 300}}]},
            {"custom_platform_settings": [{"platforms": ["cEOS-LAB"], "reload_delay": {"mlag": 60}}]},
        )

        assert merged["custom_platform_settings"][0]["reload_delay"] == {"mlag": 60}

    def test_a_duplicated_identity_falls_back_to_replacement(self) -> None:
        """An ambiguous key cannot identify an entry, so it is not used."""
        merged = Gen._deep_merge(
            {"tenants": [{"name": "T1", "a": 1}, {"name": "T1", "b": 2}]},
            {"tenants": [{"name": "T1", "c": 3}]},
        )

        assert merged["tenants"] == [{"name": "T1", "c": 3}]


class TestMergeHygiene:
    def test_inputs_are_not_mutated(self) -> None:
        base = {"tenants": [{"name": "T1", "vrfs": [{"name": "V1"}]}]}
        overlay = {"tenants": [{"name": "T1", "vrfs": [{"name": "V1", "vrf_vni": 110}]}]}

        Gen._deep_merge(base, overlay)

        assert base == {"tenants": [{"name": "T1", "vrfs": [{"name": "V1"}]}]}
        assert overlay == {"tenants": [{"name": "T1", "vrfs": [{"name": "V1", "vrf_vni": 110}]}]}

    def test_merging_is_idempotent(self) -> None:
        """Re-merging the same inputs yields the same result.

        Generation re-runs on every change, so a merge that grew a list each time
        would make host_vars drift and defeat the checksum comparison.
        """
        base = {"tenants": [{"name": "T1", "vrfs": [{"name": "V1", "static_routes": [{"prefix": "0.0.0.0/0"}]}]}]}
        overlay = {"tenants": [{"name": "T1", "vrfs": [{"name": "V1", "vrf_vni": 110}]}]}

        once = Gen._deep_merge(base, overlay)
        twice = Gen._deep_merge(once, overlay)

        assert once == twice

    def test_scopes_compose_fabric_then_pod_then_device(self) -> None:
        merged = Gen._merge_custom_hostvars(
            {"ipv4_acls": [{"name": "ACL-FABRIC"}]},
            {"ipv4_acls": [{"name": "ACL-POD"}]},
            {"ipv4_acls": [{"name": "ACL-DEVICE"}]},
        )

        assert [acl["name"] for acl in merged["ipv4_acls"]] == ["ACL-FABRIC", "ACL-POD", "ACL-DEVICE"]
