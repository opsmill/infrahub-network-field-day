"""Upload application payload files into their Infrahub attachments.

`infrahubctl object load` cannot write file content -- a `CoreFileObject` needs
`upload_from_bytes()` before its first `save()` -- so the payloads that cycle 013
moved out of JSON attributes need a seeding step of their own.

This is the second half of the arrangement cycle 013 chose: git holds the
reviewable YAML under `payloads/`, Infrahub holds the authoritative
attachment, and the transform reads the attachment. Cycle 033 narrowed it to
Helm values alone -- an application is a chart now, so there are no raw
manifests left to attach. Running it twice with
unchanged content is a no-op, because `save_file_if_changed` compares checksums
before uploading.

`invoke load` should call this after `object load`, or a fresh instance will
have applications with no payload.

    uv run python scripts/seed_app_payloads.py --branch <branch>
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))

import yaml  # noqa: E402
from infrahub_sdk import Config, InfrahubClient  # noqa: E402

from solution_arista_avd.generator import save_file_if_changed  # noqa: E402

# Deliberately NOT under objects/: `infrahubctl object load objects/` parses
# every YAML file in that tree as an Infrahub object file, and a payload is a
# bare list of Kubernetes manifests. Putting it there aborts the entire load
# with a pydantic dict_type error, taking every other object file with it.
PAYLOAD_DIR = _REPO_ROOT / "payloads"

# application name -> (payload file, attachment kind, relationship on the app)
#
# Helm values only since cycle 033. `ServiceFabricAppManifestsFile` was
# withdrawn with the raw-manifests path, and the kind no longer resolves --
# naming it here raises `SchemaNotFoundError` rather than seeding nothing.
PAYLOADS: dict[str, tuple[str, str, str]] = {
    "otternet-demo": ("otternet-demo-values.yaml", "ServiceFabricAppValuesFile", "values_file"),
    "otternet-metrics": ("otternet-metrics-values.yaml", "ServiceFabricAppValuesFile", "values_file"),
    "otternet-telemetry": ("otternet-telemetry-values.yaml", "ServiceFabricAppValuesFile", "values_file"),
    "otternet-dns": ("otternet-dns-values.yaml", "ServiceFabricAppValuesFile", "values_file"),
}


# Catalogue entry -> the application whose payload file is its `default_values`
# (specs/035-application-catalogue).
#
# THE THREE `lab-*` ENTRIES TAKE THEIR VALUES FROM THE SAME PAYLOAD FILE AS THE
# APPLICATION THEY DESCRIBE, so git holds one source and the entry and the
# application's pinned attachment cannot disagree. `whoami`, the requestable
# entry, is not here: its values are short and sit inline in
# objects/35a_otternet_app_catalogue.yml.
#
# The text is the payload file AS COMMITTED, not the assembled attachment: the
# metrics application's attachment has 220 KB of Grafana dashboard JSON folded
# in at upload time (`assemble_payload`), and a 237 KB attribute would be read
# in full by every catalogue refresh and every page of the entry. The entry
# therefore holds the reviewable YAML, and the dashboards stay a property of the
# application's own attachment. It is a Text attribute, so the keys with dots
# and slashes that break a JSON attribute are harmless.
DEFINITION_PAYLOADS: dict[str, str] = {
    "lab-whoami": "otternet-demo",
    "lab-metrics": "otternet-metrics",
    "lab-telemetry": "otternet-telemetry",
    "lab-dns": "otternet-dns",
}


# Applications whose values payload has Grafana dashboards folded in at upload
# time (cycle 034): application name -> directory of dashboard JSON files.
#
# THE DASHBOARDS STAY SEPARATE FILES IN GIT, so each is reviewable and diffable
# on its own; the attachment Infrahub holds is the assembled whole, which is what
# the transform renders and the chart receives under `grafana.dashboards`. The
# assembly is deterministic -- files sorted, keys in a fixed order -- so an
# unchanged tree produces an unchanged checksum and the upload stays a no-op.
DASHBOARDS: dict[str, str] = {
    "otternet-metrics": "dashboards",
}

# Where the chart's file provider reads them from. The provider's `path` must be
# /var/lib/grafana/dashboards/<provider>, or the chart mounts them somewhere
# Grafana never looks.
_DASHBOARD_PROVIDER = "otternet"


def assemble_payload(app_name: str, path: Path) -> bytes:
    """The bytes to attach: the payload file, plus any dashboards for this app."""
    if app_name not in DASHBOARDS:
        return path.read_bytes()

    values = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    grafana = values.setdefault("grafana", {})
    grafana["dashboardProviders"] = {
        "dashboardproviders.yaml": {
            "apiVersion": 1,
            "providers": [
                {
                    "name": _DASHBOARD_PROVIDER,
                    "orgId": 1,
                    "folder": "OTTERNET",
                    "type": "file",
                    "disableDeletion": True,
                    "editable": False,
                    "options": {"path": f"/var/lib/grafana/dashboards/{_DASHBOARD_PROVIDER}"},
                }
            ],
        }
    }
    grafana["dashboards"] = {
        _DASHBOARD_PROVIDER: {
            board.stem: {"json": board.read_text(encoding="utf-8")}
            for board in sorted((PAYLOAD_DIR / DASHBOARDS[app_name]).glob("*.json"))
        }
    }
    header = (
        f"# Assembled by scripts/seed_app_payloads.py from payloads/{path.name} and "
        f"payloads/{DASHBOARDS[app_name]}/*.json.\n# Edit those, not this attachment.\n"
    )
    return (header + yaml.safe_dump(values, sort_keys=False, width=4096)).encode()


def definition_default_values(entry: str) -> str:
    """The text an infrastructure catalogue entry carries as `default_values`."""
    app_name = DEFINITION_PAYLOADS[entry]
    filename = PAYLOADS[app_name][0]
    return (PAYLOAD_DIR / filename).read_text(encoding="utf-8")


async def seed_definitions(client: InfrahubClient, branch: str) -> int:
    """Set each infrastructure entry's `default_values`. Returns how many changed.

    Guarded on the current text, so a second run saves nothing and moves nothing.
    """
    changed = 0
    for entry in DEFINITION_PAYLOADS:
        wanted = definition_default_values(entry)
        node = await client.get(kind="ServiceApplicationDefinition", branch=branch, name__value=entry)
        if node.default_values.value == wanted:  # type: ignore[attr-defined]
            print(f"{entry}: default_values unchanged")
            continue
        node.default_values.value = wanted  # type: ignore[attr-defined]
        await node.save(update_group_context=False)
        changed += 1
        print(f"{entry}: default_values set ({len(wanted)} characters)")
    return changed


async def seed(branch: str) -> int:
    """Upload every payload. Returns the number of files actually written."""
    token = os.environ.get("INFRAHUB_API_TOKEN")
    if not token:
        msg = (
            "INFRAHUB_API_TOKEN is not set. Export it first -- the same token infrahubctl "
            "uses, which for a local stack is INFRAHUB_INITIAL_ADMIN_TOKEN from "
            "docker-compose.override.yml."
        )
        raise SystemExit(msg)

    client = InfrahubClient(
        config=Config(
            address=os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000"),
            api_token=token,
            default_branch=branch,
        )
    )

    uploaded = 0
    for app_name, (filename, kind, relationship) in PAYLOADS.items():
        path = PAYLOAD_DIR / filename
        if not path.is_file():
            msg = f"payload {path} is missing; it is the reviewable source for {app_name}"
            raise FileNotFoundError(msg)

        content = assemble_payload(app_name, path)
        checksum = hashlib.sha256(content).hexdigest()

        app = await client.get(kind="ServiceFabricApp", branch=branch, name__value=app_name)

        existing_file = None
        existing_checksum = None
        manager = getattr(app, relationship)
        if manager.id:
            await manager.fetch()
            existing_file = manager.peer
            if existing_file is not None:
                existing_content = await existing_file.download_file()
                existing_checksum = hashlib.sha256(existing_content).hexdigest()

        wrote = await save_file_if_changed(
            existing_file=existing_file,
            existing_checksum=existing_checksum,
            new_checksum=checksum,
            new_content=content,
            filename=filename,
            create_file=lambda k=kind, a=app: client.create(kind=k, branch=branch, data={"app": a.id}),
        )
        uploaded += int(wrote)
        print(f"{app_name}: {'uploaded' if wrote else 'unchanged'} ({len(content)} bytes)")

    # After the payloads, so an entry is only ever set from a file that exists.
    uploaded += await seed_definitions(client, branch)
    return uploaded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", default="main", help="Infrahub branch to seed")
    args = parser.parse_args()

    written = asyncio.run(seed(args.branch))
    print(f"{written} payload(s) written")


if __name__ == "__main__":
    main()
