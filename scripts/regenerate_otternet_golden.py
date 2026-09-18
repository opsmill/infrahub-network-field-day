#!/usr/bin/env python3
"""Regenerate the OTTERNET golden EOS configurations from the lab's AVD inputs.

The golden set in ``tests/integration/golden/otternet`` is the reference both parity
tests compare against, so where it comes from matters. It is *not* Infrahub
output — that would make the tests circular. It is rendered from the OTTERNET lab's
own Ansible ``group_vars``, which are the design's source of truth and which
reproduce the deployed switch configurations byte for byte.

The one transformation applied is the hostnames. The lab's containerlab nodes are
called ``spine1`` / ``k8s-leaf1``; Infrahub's pod and rack generators name devices
``spine-{pod}-{index}`` / ``leaf-{pod}-{rack_index}-{index}``. Rather than teach
the generators the lab's names, the lab is redeployed under the generated ones.

This script proves that rename is cosmetic: it substitutes the new names back out
of each rendered config and asserts the result equals the deployed configuration
exactly. If a PyAVD upgrade or a lab design change introduces a real difference,
that check fails and says where — it will not quietly bake the change into the
reference the tests trust.

Usage:
    uv run python scripts/regenerate_otternet_golden.py            # check only
    uv run python scripts/regenerate_otternet_golden.py --write    # update the golden set

Point --lab at the OTTERNET lab checkout if it is not beside this repository.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LAB = REPO_ROOT.parent / "lab"
GOLDEN_DIR = REPO_ROOT / "tests" / "integration" / "golden" / "otternet"

POD_NAME = "otternet-pod1"

# Lab hostname -> the name Infrahub's generators produce. Rack indices are
# K8S_LEAFS=1, APP_LEAFS=2, BORDER_LEAFS=3 (objects/25_otternet_racks.yml).
RENAME: dict[str, str] = {
    "spine1": f"spine-{POD_NAME}-1",
    "spine2": f"spine-{POD_NAME}-2",
    "k8s-leaf1": f"leaf-{POD_NAME}-1-1",
    "k8s-leaf2": f"leaf-{POD_NAME}-1-2",
    "app-leaf1": f"leaf-{POD_NAME}-2-1",
    "app-leaf2": f"leaf-{POD_NAME}-2-2",
    "border-leaf1": f"leaf-{POD_NAME}-3-1",
}

# Which group_vars file supplies each device's node-type block.
NODE_TYPE_FILE = {
    "spine1": "OTTERNET_SPINES.yml",
    "spine2": "OTTERNET_SPINES.yml",
    "k8s-leaf1": "OTTERNET_L3LEAFS.yml",
    "k8s-leaf2": "OTTERNET_L3LEAFS.yml",
    "app-leaf1": "OTTERNET_L3LEAFS.yml",
    "app-leaf2": "OTTERNET_L3LEAFS.yml",
    "border-leaf1": "OTTERNET_L3LEAFS.yml",
}


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def rename_devices(node: Any) -> Any:
    """Replace device names, matching whole strings only.

    Whole-string rather than substring: the lab's AVD inputs reference devices as
    complete values (`uplink_switches`, `nodes`, `switches`), and a substring
    replacement would corrupt any description that happened to contain one.
    """
    if isinstance(node, dict):
        return {key: rename_devices(value) for key, value in node.items()}
    if isinstance(node, list):
        return [rename_devices(value) for value in node]
    if isinstance(node, str):
        return RENAME.get(node, node)
    return node


def build_hostvars(group_vars: Path) -> dict[str, dict[str, Any]]:
    fabric: dict[str, Any] = {}
    for path in sorted((group_vars / "OTTERNET_FABRIC").glob("*.yml")):
        fabric = deep_merge(fabric, yaml.safe_load(path.read_text(encoding="utf-8")) or {})

    node_type_vars = {
        name: yaml.safe_load((group_vars / filename).read_text(encoding="utf-8")) or {}
        for name, filename in {v: v for v in NODE_TYPE_FILE.values()}.items()
    }

    hostvars: dict[str, dict[str, Any]] = {}
    for lab_name, filename in NODE_TYPE_FILE.items():
        merged = deep_merge(copy.deepcopy(fabric), copy.deepcopy(node_type_vars[filename]))
        renamed = rename_devices(merged)
        renamed["inventory_hostname"] = RENAME[lab_name]
        hostvars[RENAME[lab_name]] = renamed
    return hostvars


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--lab", type=Path, default=DEFAULT_LAB, help="path to the OTTERNET lab checkout")
    parser.add_argument("--write", action="store_true", help="update the golden set (default: check only)")
    args = parser.parse_args()

    group_vars = args.lab / "avd" / "group_vars"
    deployed = args.lab / "avd" / "intended" / "configs"
    if not group_vars.is_dir() or not deployed.is_dir():
        print(f"error: no OTTERNET lab AVD data under {args.lab}", file=sys.stderr)
        print("       pass --lab <path-to-otternet-lab>", file=sys.stderr)
        return 1

    from pyavd import get_avd_facts, get_device_config, get_device_structured_config, validate_inputs

    hostvars = build_hostvars(group_vars)

    for host, vars_ in hostvars.items():
        violations = list(validate_inputs(vars_).validation_result.violations)
        if violations:
            print(f"[{host}] PyAVD rejected the lab inputs: {len(violations)} violation(s)")
            for violation in violations[:10]:
                path = ".".join(str(part) for part in (getattr(violation, "path", []) or []))
                print(f"    {path}: {getattr(violation, 'message', violation)}")
            return 1

    facts = get_avd_facts(hostvars)
    back = sorted(((new, old) for old, new in RENAME.items()), key=lambda pair: -len(pair[0]))

    rendered: dict[str, str] = {}
    substantive = 0
    for lab_name, new_name in RENAME.items():
        config = get_device_config(get_device_structured_config(new_name, hostvars[new_name], avd_facts=facts))
        rendered[new_name] = config

        restored = config
        for new, old in back:
            restored = restored.replace(new, old)
        expected = (deployed / f"{lab_name}.cfg").read_text(encoding="utf-8")

        if restored == expected:
            print(f"[{new_name}] hostname-only change vs the deployed {lab_name}.cfg")
            continue

        substantive += 1
        diff = [
            line
            for line in difflib.unified_diff(expected.splitlines(), restored.splitlines(), lineterm="")
            if line[:1] in "+-" and line[:3] not in ("---", "+++")
        ]
        print(f"[{new_name}] NOT a hostname-only change -- {len(diff)} substantive line(s):")
        for line in diff[:30]:
            print(f"    {line}")

    if substantive:
        print(f"\n{substantive} device(s) differ from the deployed lab beyond hostnames; refusing to write.")
        return 2

    if not args.write:
        print(f"\nAll {len(rendered)} configs verified. Re-run with --write to update {GOLDEN_DIR}.")
        return 0

    for path in GOLDEN_DIR.glob("*.cfg"):
        path.unlink()
    shutil.rmtree(GOLDEN_DIR / "__pycache__", ignore_errors=True)
    for name, config in rendered.items():
        (GOLDEN_DIR / f"{name}.cfg").write_text(config, encoding="utf-8")
    print(f"\nWrote {len(rendered)} configs to {GOLDEN_DIR}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
