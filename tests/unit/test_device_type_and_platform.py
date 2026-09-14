"""Every device says what it is.

Before this, only the seven fabric switches carried a device type, and only
those plus the seven servers carried a platform. The seven WAN routers and the
firewall had neither: the graph held devices it could not describe.

That is not only untidy. `transforms/containerlab_topology.py` reads a node's
ContainerLab kind and image from the platform, falling back to the device's own
`platform` when it has no `device_type`. A device with neither cannot render as
a topology node at all -- which is half the reason that artifact covers 14 of
the lab's 30 nodes, the other half being that the transform walks only the
fabric.

WHAT THIS PINS, and why it reads the object files rather than the live graph:
the same reason the other contract tests do. A gate that needs a running
Infrahub is a gate that gets skipped.

ONE ASYMMETRY IS DELIBERATE. `ComputePhysicalServer` has no `device_type`
relationship -- neither does `DcimGenericDevice` -- so a server can carry a
platform and nothing else. Requiring a device type there would need a schema
change, and a server is not a network device. The test asserts what the schema
can actually hold rather than a tidier rule it cannot.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).parents[2]
OBJECTS = REPO_ROOT / "objects"

# Devices are declared across these files; the platforms and types they name
# are declared in the three numbered files below them.
DEVICE_FILES = ("31_nfd41_offfabric_devices.yml",)
PLATFORM_FILE = "03_device_type.yml"
DEVICE_TYPE_FILE = "20_nfd41_device_types.yml"
MANUFACTURER_FILE = "02_manufacturer.yml"

# Kinds that can hold a device type. ComputePhysicalServer is absent on purpose.
TYPED_KINDS = {"DcimDevice", "SecurityFirewall"}


def _docs(filename: str) -> list[dict[str, Any]]:
    return [d for d in yaml.safe_load_all((OBJECTS / filename).read_text(encoding="utf-8")) if d]


def _entries(filename: str, kind: str) -> list[dict[str, Any]]:
    return [item for doc in _docs(filename) if doc.get("spec", {}).get("kind") == kind for item in doc["spec"]["data"]]


def _named(filename: str, kind: str) -> set[str]:
    return {e["name"] for e in _entries(filename, kind)}


def test_every_routed_device_declares_a_type_and_a_platform() -> None:
    """The clause the whole change turns on."""
    missing = [
        f"{entry['name']} ({kind})"
        for filename in DEVICE_FILES
        for kind in TYPED_KINDS
        for entry in _entries(filename, kind)
        if not entry.get("device_type") or not entry.get("platform")
    ]

    assert not missing, f"devices with no device type or no platform: {sorted(missing)}"


def test_every_device_type_resolves_to_a_declared_type() -> None:
    """A reference to a type that is not defined loads as a dangling HFID."""
    declared = _named(DEVICE_TYPE_FILE, "DcimDeviceType")
    for filename in DEVICE_FILES:
        for kind in TYPED_KINDS:
            for entry in _entries(filename, kind):
                # HFID form: [manufacturer, type name]
                reference = entry["device_type"]
                name = reference[-1] if isinstance(reference, list) else reference
                assert name in declared, f"{entry['name']}: device type {name!r} is not declared"


def test_every_platform_resolves_to_a_declared_platform() -> None:
    declared = _named(PLATFORM_FILE, "DcimPlatform")
    for filename in DEVICE_FILES:
        for kind in TYPED_KINDS:
            for entry in _entries(filename, kind):
                assert entry["platform"] in declared, f"{entry['name']}: platform {entry['platform']!r} is not declared"


def test_every_device_type_names_a_declared_manufacturer() -> None:
    """`DcimDeviceType.manufacturer` is mandatory in the schema."""
    declared = _named(MANUFACTURER_FILE, "OrganizationManufacturer")
    for entry in _entries(DEVICE_TYPE_FILE, "DcimDeviceType"):
        assert entry.get("manufacturer") in declared, f"device type {entry['name']!r} names an undeclared manufacturer"


def test_every_platform_carries_its_containerlab_kind_and_image() -> None:
    """Without these two a device cannot render as a ContainerLab node.

    Asserted because they are the reason the platform matters beyond being a
    label, and because a platform added later without them would fail silently:
    the topology renders, the node is just absent.
    """
    for entry in _entries(PLATFORM_FILE, "DcimPlatform"):
        assert entry.get("containerlab_os"), f"platform {entry['name']!r} has no containerlab_os"
        assert entry.get("containerlab_image"), f"platform {entry['name']!r} has no containerlab_image"


def test_the_statically_attached_customer_edge_is_not_typed_as_a_router() -> None:
    """cust-acme-dr-ce runs no routing daemon, and the model should say so.

    acme's DR site attaches statically, so the lab gives it a plain multitool
    container rather than FRR. Typing it as an FRR router would make the table
    tidier and wrong.
    """
    entry = next(
        e for filename in DEVICE_FILES for e in _entries(filename, "DcimDevice") if e["name"] == "cust-acme-dr-ce"
    )
    assert entry["platform"] == "Linux"
    assert entry["device_type"][-1] == "Linux Container"
