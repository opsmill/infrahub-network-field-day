"""Migrate every `ServiceFabricApp` onto a chart, before the schema demands one.

Cycle 033 makes `chart_repository`, `chart_name` and `chart_version` mandatory
and withdraws the raw-manifests path. Neither change can be loaded against
populated data:

  * Making the three attributes mandatory is REFUSED while any application
    leaves them empty. The server answers `Attribute-level 'optional' constraint
    violation on schema 'ServiceFabricApp'. Node (nfd41-demo) is not compliant.`
    -- once per attribute per application, naming the node and never the field,
    so a partial migration looks exactly like none at all.
  * Withdrawing `ServiceFabricAppManifestsFile` succeeds whether or not
    instances exist, and afterwards the kind no longer resolves. Anything still
    attached is unreachable rather than deleted, and there is no query that can
    find it. The files have to go first or they never go at all.

So this runs BEFORE `infrahubctl schema load`, which inverts the usual order --
`invoke load` does schema then objects, and this is objects then schema.

**It enumerates from the graph, never from `objects/`.** Only `nfd41-demo` is
seeded; any other application arrived through the portal or the API, and a
migration written from the seed files would leave exactly those behind. The
instance this was written against had two.

    uv run python scripts/migrate_fabric_app_charts.py --branch <branch>
    uv run python scripts/migrate_fabric_app_charts.py --branch <branch> --apply
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

from infrahub_sdk import Config, InfrahubClient

# Chart coordinates per application, keyed by name.
#
# There is no default and there is deliberately no fallback. A default chart
# repository is a value nobody chose, and an application pointing at the wrong
# chart renders, merges and delivers -- which is the class of silent failure
# this whole cycle exists to remove. An unknown application stops the run.
CHARTS: dict[str, tuple[str, str, str]] = {
    # The two-tier whoami demo becomes a single-tier release of the same image:
    # chart 6.0.0 ships appVersion 1.11.0, which is `traefik/whoami:v1.11.0`,
    # the image its manifests already ran. Verified against the repository's
    # own index.yaml rather than taken from a chart page.
    "nfd41-demo": ("https://cowboysysop.github.io/charts/", "whoami", "6.0.0"),
    # Created through the portal rather than seeded, and the reason this script
    # reads the graph. Its manifests ran ghcr.io/stefanprodan/podinfo:6.7.1, and
    # the podinfo chart version tracks its app version.
    "podinfo": ("https://stefanprodan.github.io/podinfo", "podinfo", "6.7.1"),
}

CHART_FIELDS = ("chart_repository", "chart_name", "chart_version")


def _value(field: Any) -> Any:
    return field.value if field is not None else None


def _client(branch: str) -> InfrahubClient:
    token = os.environ.get("INFRAHUB_API_TOKEN")
    if not token:
        msg = (
            "INFRAHUB_API_TOKEN is not set. Export the same token infrahubctl uses -- "
            "for a local stack that is INFRAHUB_INITIAL_ADMIN_TOKEN from "
            "docker-compose.override.yml."
        )
        raise SystemExit(msg)

    return InfrahubClient(
        config=Config(
            address=os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000"),
            api_token=token,
            default_branch=branch,
        )
    )


async def _applications_missing_a_chart(client: InfrahubClient, branch: str) -> list[Any]:
    """Every application lacking any of the three chart fields.

    Returns the nodes rather than their names, because the caller writes to
    them and re-fetching by name would race with a concurrent edit.
    """
    apps = await client.all(kind="ServiceFabricApp", branch=branch)
    return [app for app in apps if any(_value(getattr(app, field, None)) in (None, "") for field in CHART_FIELDS)]


async def report(client: InfrahubClient, branch: str) -> int:
    """Say what would change. Returns the number of applications needing work."""
    apps = await client.all(kind="ServiceFabricApp", branch=branch)
    incomplete = await _applications_missing_a_chart(client, branch)
    files = await client.all(kind="ServiceFabricAppManifestsFile", branch=branch)

    print(f"applications: {len(apps)}")
    for app in apps:
        name = _value(app.name)
        state = "complete" if app not in incomplete else "MISSING A CHART"
        print(f"  {name}: {state}")
        if app in incomplete and name not in CHARTS:
            print(f"    !! no chart known for {name!r}; add it to CHARTS before running --apply")

    print(f"manifests files to delete: {len(files)}")
    for node in files:
        print(f"  {_value(node.file_name)}")

    return len(incomplete)


async def apply(client: InfrahubClient, branch: str) -> tuple[int, int]:
    """Populate the chart fields, then delete the manifests attachments.

    In that order: the files are what make an application's old payload
    recoverable, so they are removed only once every application has somewhere
    else to describe itself.
    """
    incomplete = await _applications_missing_a_chart(client, branch)

    unknown = sorted(str(_value(app.name)) for app in incomplete if _value(app.name) not in CHARTS)
    if unknown:
        msg = (
            f"no chart coordinates known for {', '.join(unknown)}. Add them to CHARTS -- "
            "guessing one would point an application at a chart nobody chose, which "
            "renders and delivers without complaint."
        )
        raise SystemExit(msg)

    populated = 0
    for app in incomplete:
        repository, chart, version = CHARTS[str(_value(app.name))]
        app.chart_repository.value = repository
        app.chart_name.value = chart
        app.chart_version.value = version
        await app.save()
        populated += 1
        print(f"populated {_value(app.name)}: {chart} {version} from {repository}")

    deleted = 0
    for node in await client.all(kind="ServiceFabricAppManifestsFile", branch=branch):
        name = _value(node.file_name)
        await node.delete()
        deleted += 1
        print(f"deleted manifests attachment {name}")

    return populated, deleted


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--branch", required=True, help="branch to migrate")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the changes; without it the script only reports",
    )
    args = parser.parse_args()

    client = _client(args.branch)

    if not args.apply:
        outstanding = await report(client, args.branch)
        print(f"\n{outstanding} application(s) would be populated. Re-run with --apply.")
        return 0

    populated, deleted = await apply(client, args.branch)
    print(f"\npopulated {populated} application(s), deleted {deleted} manifests attachment(s)")

    remaining = await _applications_missing_a_chart(client, args.branch)
    if remaining:
        names = ", ".join(str(_value(app.name)) for app in remaining)
        msg = f"still incomplete after the run: {names}. The schema load will be refused."
        raise SystemExit(msg)

    print("every application now carries a chart; the schema load will be accepted")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
