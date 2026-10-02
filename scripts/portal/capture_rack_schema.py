"""Capture the schema fixture the portal's rack queries are tested against.

WHY THIS EXISTS. The rack elevation asked Infrahub for `facility_id`, `height`
and `mounted_devices` -- fields from an upstream example schema that this one
never had -- and the first anyone knew of it was the page itself reporting
`Cannot query field "facility_id" on type "LocationRack"`. The plugin's unit
tests now walk every rack query against this fixture, so a field the schema
lacks fails a test instead of the page.

Read-only: it issues GETs against `/api/schema/{kind}` and writes one JSON file,
trimmed to what a query can name -- attribute names, relationship names, their
peers and cardinalities.

    uv run python scripts/portal/capture_rack_schema.py
"""

from __future__ import annotations

import json
import os
from operator import itemgetter
from pathlib import Path

import httpx

KINDS = (
    "LocationRack",
    "LocationHall",
    "DcimPhysicalDevice",
    "DcimDeviceType",
    "ComputePhysicalServer",
)

FIXTURE = Path(__file__).resolve().parents[2] / "backstage/plugins/infrahub/src/panels/__fixtures__/rack-schema.json"


def trim(schema: dict) -> dict:
    """Keep only what a GraphQL selection can name."""
    return {
        "attributes": sorted(
            ({"name": a["name"], "kind": a["kind"]} for a in schema["attributes"]),
            key=itemgetter("name"),
        ),
        "relationships": sorted(
            ({"name": r["name"], "peer": r["peer"], "cardinality": r["cardinality"]} for r in schema["relationships"]),
            key=itemgetter("name"),
        ),
    }


def main() -> None:
    address = os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000")
    token = os.environ.get("INFRAHUB_API_TOKEN", "06438eb2-8019-4776-878c-0941b1f1d1ec")
    kinds = {}
    with httpx.Client(base_url=address, headers={"X-INFRAHUB-KEY": token}) as client:
        for kind in KINDS:
            response = client.get(f"/api/schema/{kind}", params={"branch": "main"})
            response.raise_for_status()
            kinds[kind] = trim(response.json())

    fixture = {
        "_comment": (
            "Captured read-only from GET /api/schema/<kind>?branch=main and trimmed to "
            "names, kinds and peers. Recapture with scripts/portal/capture_rack_schema.py "
            "rather than editing by hand."
        ),
        "kinds": kinds,
    }
    FIXTURE.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE.write_text(json.dumps(fixture, indent=2) + "\n")
    print(f"wrote {FIXTURE} ({', '.join(KINDS)})")


if __name__ == "__main__":
    main()
