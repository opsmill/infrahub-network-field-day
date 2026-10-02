"""A node removed from the topology must not survive `invoke lab --destroy`.

`containerlab destroy -t` removes only the nodes the current file declares, so
the FRR `-exporter` sidecars outlived the SR Linux re-platform and the next
fresh bootstrap was refused with "lab has already been deployed".
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import tasks

if TYPE_CHECKING:
    from pathlib import Path


class _Ctx:
    def __init__(self, listing: str) -> None:
        self.listing = listing
        self.commands: list[str] = []

    def run(self, command: str, **_kwargs: Any) -> SimpleNamespace:
        self.commands.append(command)
        return SimpleNamespace(stdout=self.listing if command.startswith("docker ps") else "", ok=True)


def _topology(tmp_path: Path) -> Path:
    path = tmp_path / "otternet.clab.yml"
    path.write_text("name: otternet\ntopology:\n  nodes:\n    isp-pe1: {}\n    spine1: {}\n", encoding="utf-8")
    return path


def test_only_undeclared_nodes_of_this_lab_are_removed(tmp_path: Path) -> None:
    ctx = _Ctx(
        "clab-otternet-isp-pe1 isp-pe1\nclab-otternet-isp-pe1-exporter isp-pe1-exporter\nclab-otternet-spine1 spine1\n"
    )

    tasks._remove_orphaned_lab_nodes(ctx, _topology(tmp_path))  # type: ignore[arg-type]

    assert "label=containerlab=otternet" in ctx.commands[0]
    assert ctx.commands[1:] == ["docker rm -f clab-otternet-isp-pe1-exporter"]


def test_nothing_is_removed_when_every_node_is_declared(tmp_path: Path) -> None:
    ctx = _Ctx("clab-otternet-isp-pe1 isp-pe1\nclab-otternet-spine1 spine1\n")

    tasks._remove_orphaned_lab_nodes(ctx, _topology(tmp_path))  # type: ignore[arg-type]

    assert len(ctx.commands) == 1
