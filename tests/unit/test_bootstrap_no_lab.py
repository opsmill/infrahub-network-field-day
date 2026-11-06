"""`invoke bootstrap --no-lab` brings up Infrahub and the tooling node only.

The Infrahub-only path deploys the tooling node alone (Dex, the portal, alice's token) and calls no
step that needs the rest of the lab or the workload cluster; `--fresh --no-lab` must not destroy a lab. This file reads `tasks.py` as text; it needs no running Infrahub.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEXT = (REPO / "tasks.py").read_text(encoding="utf-8")
BOOTSTRAP = TEXT.split("def bootstrap(", 1)[1].split("def _bootstrap_infrahub_only", 1)[0]
INFRAHUB_ONLY = TEXT.split("def _bootstrap_infrahub_only(", 1)[1].split("def _wait_for_infrahub", 1)[0]


def test_infrahub_only_path_calls_no_step_that_needs_the_lab() -> None:
    for call in ("reconcile(ctx", "_cluster_task("):
        assert call not in INFRAHUB_ONLY, call
    # The only lab call deploys the tooling node, never the devices.
    assert INFRAHUB_ONLY.count("lab(ctx") == 1
    assert "lab(ctx, lab_dir=lab_dir, tooling_only=True)" in INFRAHUB_ONLY


def test_infrahub_only_path_runs_the_steps_that_need_no_lab() -> None:
    for call in ("mcp(ctx)", "network_admin(ctx)", "metrics_exporter(ctx)", "_release_demo_branch(ctx)"):
        assert call in INFRAHUB_ONLY, call


def test_infrahub_only_path_brings_up_the_portal_then_mints_alices_token() -> None:
    order = ["tooling_only=True", "backstage_build(ctx)", "tooling(ctx)", "mcp(ctx)", "mcp_tokens(ctx)"]
    positions = [INFRAHUB_ONLY.index(call) for call in order]
    assert positions == sorted(positions), order


def test_no_lab_returns_after_the_avd_chain_and_before_the_lab() -> None:
    avd = BOOTSTRAP.index("avd(ctx, branch=branch, topology=True, merge=True)")
    branch = BOOTSTRAP.index("if no_lab:\n        _bootstrap_infrahub_only(")
    deploy = BOOTSTRAP.index('print("\\n=== Deploying the lab ===")')
    assert avd < branch < deploy


def test_fresh_no_lab_leaves_the_lab_alone() -> None:
    fresh = BOOTSTRAP.split("if fresh:", 1)[1].split("destroy(ctx)", 1)[0]
    assert "if not no_lab:" in fresh
    assert fresh.index("if not no_lab:") < fresh.index("lab(ctx, lab_dir=lab_dir, destroy=True)")
