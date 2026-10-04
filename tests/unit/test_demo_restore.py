"""The pure decisions behind `invoke demo-restore`."""

from __future__ import annotations

from pathlib import Path

from solution_arista_avd import demo_restore as dr

REPO = Path(__file__).resolve().parents[2]

_DOC = """---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: ServiceFabricApp
  data:
    - name: otternet-demo
    - name: shop
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: ServiceAppAccess
  data:
    - name: seeded-grant
---
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: IpamIPAddress
  data:
    - address: 10.0.0.1/32
"""


def test_seeded_names_are_read_per_kind_and_other_kinds_are_ignored() -> None:
    names = dr.seeded_names([_DOC])

    assert names["ServiceFabricApp"] == {"otternet-demo", "shop"}
    assert names["ServiceAppAccess"] == {"seeded-grant"}


def test_the_real_seed_files_hold_the_three_otternet_applications_and_no_grant() -> None:
    texts = [p.read_text(encoding="utf-8") for p in sorted((REPO / "objects").glob("*.yml"))]

    names = dr.seeded_names(texts)

    assert {"otternet-demo", "otternet-metrics", "otternet-telemetry"} <= names["ServiceFabricApp"]
    assert names["ServiceAppAccess"] == set()


def test_demo_created_keeps_only_what_a_presenter_made() -> None:
    created = dr.demo_created(["otternet-demo", "otter-shop", "shop", "otternet-new", "grafana-demo1"], {"shop"})

    assert created == ["grafana-demo1", "otter-shop"]


def test_grants_are_withdrawn_before_applications() -> None:
    assert dr.DEMO_KINDS.index("ServiceAppAccess") < dr.DEMO_KINDS.index("ServiceFabricApp")


def test_generator_records_are_matched_by_service_name_only() -> None:
    records = [
        ("CoreGeneratorInstance", "i1", "generate-app-access: otter-shop-access"),
        ("CoreGeneratorInstance", "i2", "generate-app-access: otter-shop-access-2"),
        ("CoreGeneratorInstance", "i3", "generate-fabric-app: otter-shop"),
        ("CoreGeneratorGroup", "g1", "generate-app-access-abc (name: otter-shop-access)"),
        ("CoreGeneratorGroup", "g2", "generate-app-access-def (name: grafana-demo1)"),
        ("CoreGeneratorInstance", "i4", "generate-fabric-app: not-otter-shop"),
    ]

    found = dr.generator_records_for({"otter-shop-access", "otter-shop"}, records)

    assert sorted(found) == [
        ("CoreGeneratorGroup", "g1"),
        ("CoreGeneratorInstance", "i1"),
        ("CoreGeneratorInstance", "i3"),
    ]


def test_a_restore_branch_is_recognised_by_its_prefix() -> None:
    assert dr.is_restore_branch("restore-1759500000")
    assert not dr.is_restore_branch("implement_otter-shop_demo1")


def test_release_numbers_come_from_every_kind_of_ref_and_skip_reset_branches() -> None:
    names = [
        "demo/internet-access-1",
        "refs/heads/demo/internet-access-3",
        "demo/internet-access-1-reset-1759",
        "demo/other-9",
        "main",
    ]

    assert dr.used_runs("internet-access", names) == [1, 3]
    assert dr.next_run("internet-access", names) == 4
    assert dr.latest_run("internet-access", names) == 3


def test_with_no_release_the_next_run_is_one() -> None:
    assert dr.next_run("internet-access", ["main"]) == 1
    assert dr.latest_run("internet-access", []) == 1
