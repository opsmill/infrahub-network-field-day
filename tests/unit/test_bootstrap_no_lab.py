"""`invoke bootstrap --no-lab` brings up Infrahub only.

The Infrahub-only path must call no step that needs the lab, Dex or the workload cluster, and
`--fresh --no-lab` must not destroy a lab. This file reads `tasks.py` as text; it needs no running Infrahub.
"""

from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEXT = (REPO / "tasks.py").read_text(encoding="utf-8")
BOOTSTRAP = TEXT.split("def bootstrap(", 1)[1].split("def _bootstrap_infrahub_only", 1)[0]
INFRAHUB_ONLY = TEXT.split("def _bootstrap_infrahub_only(", 1)[1].split("def _wait_for_infrahub", 1)[0]


def test_infrahub_only_path_calls_no_step_that_needs_the_lab() -> None:
    for call in ("lab(ctx", "reconcile(ctx", "backstage_build(ctx", "tooling(ctx", "mcp_tokens(ctx", "_cluster_task("):
        assert call not in INFRAHUB_ONLY, call


def test_infrahub_only_path_runs_the_steps_that_need_no_lab() -> None:
    for call in ("mcp(ctx)", "network_admin(ctx)", "metrics_exporter(ctx)", "_release_demo_branch(ctx)"):
        assert call in INFRAHUB_ONLY, call


def test_no_lab_returns_after_the_avd_chain_and_before_the_lab() -> None:
    avd = BOOTSTRAP.index("avd(ctx, branch=branch, topology=True, merge=True)")
    branch = BOOTSTRAP.index("if no_lab:\n        _bootstrap_infrahub_only(")
    deploy = BOOTSTRAP.index('print("\\n=== Deploying the lab ===")')
    assert avd < branch < deploy


def test_fresh_no_lab_leaves_the_lab_alone() -> None:
    fresh = BOOTSTRAP.split("if fresh:", 1)[1].split("destroy(ctx)", 1)[0]
    assert "if not no_lab:" in fresh
    assert fresh.index("if not no_lab:") < fresh.index("lab(ctx, lab_dir=lab_dir, destroy=True)")
