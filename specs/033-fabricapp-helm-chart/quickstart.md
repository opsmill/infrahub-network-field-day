# Quickstart: Validating the Helm-chart Fabric Application

**Feature**: `specs/033-fabricapp-helm-chart`

How to prove the schema change works. Each scenario maps to a success criterion
in [spec.md](./spec.md); the shapes being validated are in
[data-model.md](./data-model.md) and [contracts/schema-kinds.md](./contracts/schema-kinds.md).

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be OK
export INFRAHUB_API_TOKEN=...    # INFRAHUB_INITIAL_ADMIN_TOKEN from docker-compose.override.yml
```

Work on a branch. The migration is ordered (research R1, R2) and a mistake on
`main` leaves applications that cannot be loaded.

```bash
uv run infrahubctl branch create 033-fabricapp-helm-chart
```

---

## Scenario 1 — The migration order is real (SC-001)

Establishes why the order in data-model.md is not optional. Run this **before**
migrating data, with the mandatory chart fields already in the YAML:

```bash
uv run infrahubctl schema check schemas/ --branch 033-fabricapp-helm-chart
```

**Expected — a refusal**, one message per field per non-compliant application:

```text
Unable to load the schema:
  Attribute-level 'optional' constraint violation on schema 'ServiceFabricApp'.
  Node (nfd41-demo) is not compliant., ...
```

The message names the node and never the attribute, so treat "which field?" as
something to work out from the diff, not from the error.

---

## Scenario 2 — Migrate the data, then the schema (SC-001, SC-002)

Every application needs the three chart fields, **including ones not in
`objects/`** — a used instance carries applications created through the portal.

```bash
# 1. What is actually there?
uv run infrahubctl object load objects/ --branch 033-fabricapp-helm-chart   # or the migration script
```

Then delete every `ServiceFabricAppManifestsFile` instance, because the schema
load removes the kind whether or not instances exist and afterwards there is no
way to query for what is left (research R2).

Re-run the check, which should now pass and show exactly this diff:

```text
changed:
    ServiceFabricApp:
        attributes:
            removed:
                manifests: null
        relationships:
            added:
                advertised_services: null
            removed:
                manifests_file: null
removed:
    ServiceFabricAppManifestsFile: null
```

Then load:

```bash
uv run infrahubctl schema load schemas/ --branch 033-fabricapp-helm-chart --wait 60
```

**Pass**: "Schema updated on all workers." Any other diff — especially an
unexpected `changed:` on a field this feature does not touch — is a failure.

---

## Scenario 3 — The withdrawn surface is gone (SC-003, SC-004)

```bash
uv run python - <<'PY'
import asyncio, os
from infrahub_sdk import Config, InfrahubClient
BRANCH = "033-fabricapp-helm-chart"
async def main():
    c = InfrahubClient(config=Config(address="http://localhost:8000",
                                     api_token=os.environ["INFRAHUB_API_TOKEN"],
                                     default_branch=BRANCH))
    try:
        await c.all(kind="ServiceFabricAppManifestsFile", branch=BRANCH)
        print("FAIL: the kind still resolves")
    except Exception as exc:
        print("PASS: kind gone —", type(exc).__name__)
    app = await c.get(kind="ServiceFabricApp", name__value="nfd41-demo", branch=BRANCH)
    print("PASS" if not hasattr(app, "manifests") else "FAIL", "- manifests attribute")
    print("PASS" if not hasattr(app, "manifests_file") else "FAIL", "- manifests_file relationship")
    print("PASS" if hasattr(app, "advertised_services") else "FAIL", "- advertised_services relationship")
asyncio.run(main())
PY
```

**Expected**: four PASS lines. The first raises `SchemaNotFoundError`.

---

## Scenario 4 — A chart is the whole workload source (SC-002)

Create an application naming only a cluster, a namespace and the three chart
fields. It must be accepted. Then create one omitting `chart_version`; it must be
refused by the model, not by the renderer.

**Pass**: the first succeeds, the second fails at create time naming the missing
mandatory attribute.

---

## Scenario 5 — A named service carries its own port and protocol (SC-005, SC-008)

The core of User Story 3. Note the `fetch()` — without it `add()` raises
`UninitializedError` (research R4).

```bash
uv run python - <<'PY'
import asyncio, os
from infrahub_sdk import Config, InfrahubClient
BRANCH = "033-fabricapp-helm-chart"
async def main():
    c = InfrahubClient(config=Config(address="http://localhost:8000",
                                     api_token=os.environ["INFRAHUB_API_TOKEN"],
                                     default_branch=BRANCH))
    http = await c.get(kind="SecurityService", name__value="junos-http", branch=BRANCH)
    before = (http.name.value, http.description.value, http.port.value)

    app = await c.get(kind="ServiceFabricApp", name__value="nfd41-demo", branch=BRANCH)
    await app.advertised_services.fetch()          # REQUIRED before add()
    app.advertised_services.add(http.id)
    await app.save()

    again = await c.get(kind="ServiceFabricApp", name__value="nfd41-demo", branch=BRANCH)
    await again.advertised_services.fetch()
    for peer in again.advertised_services.peers:
        svc = await c.get(kind="SecurityService", id=peer.id, branch=BRANCH)
        proto = await c.get(kind="SecurityIPProtocol", id=svc.ip_protocol.id, branch=BRANCH)
        print("resolved:", svc.name.value, svc.port.value, proto.name.value)

    after = await c.get(kind="SecurityService", name__value="junos-http", branch=BRANCH)
    unchanged = before == (after.name.value, after.description.value, after.port.value)
    print("PASS" if unchanged else "FAIL", "- service object unchanged")
asyncio.run(main())
PY
```

**Expected**:

```text
resolved: junos-http 80 tcp
PASS - service object unchanged
```

Both lines matter. The first is G1 — a port *and* a protocol, one hop from the
application, with no payload fetched and no cluster consulted. The second is G2
and FR-026: naming the firewall's own service must not take it over.

---

## Scenario 6 — Protocols regenerate clean (SC-003, Constitution III)

`infrahubctl protocols` reads the YAML, not the loaded schema, so it ignores
`state: absent` (research R3). Run this **after** the absent blocks have been
deleted from the YAML:

```bash
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
grep -c "ServiceFabricAppManifestsFile" src/solution_arista_avd/protocols.py   # must print 0
grep -n "class ServiceFabricApp(" -A 25 src/solution_arista_avd/protocols.py
```

**Pass**: the count is `0`, `chart_name` / `chart_repository` / `chart_version`
are `String` rather than `StringOptional`, `advertised_services` appears as
`RelationshipManager[SecurityService]`, and neither `manifests` nor
`manifests_file` is present.

Running this while the `state: absent` blocks are still in the YAML prints `2`
and is the expected intermediate state, not a failure.

---

## Scenario 7 — Gates

```bash
uv run pytest tests/unit
uv run invoke lint
```

Do not pipe these to `tail` or `head`: a pipeline reports the last command's
status, so a failing linter exits `0` through the pipe.

`tests/unit/test_service_layer_schema_contract.py` currently asserts that an
application's workload source may be a chart, manifests, or both
(`test_fabric_app_workload_source_supports_chart_manifests_or_both`). It must be
updated to assert the single supported source — SC-007.

---

## Cleanup

```bash
uv run infrahubctl branch delete 033-fabricapp-helm-chart
```

## What this quickstart does not cover

The renderer, the access generator, the two portals and the seeded chart values
land in the Transform, Generator and Objects cycles. Their consumer changes are
listed in [contracts/schema-kinds.md](./contracts/schema-kinds.md) §6.
SC-006 (a fresh bootstrap renders `nfd41-demo` from a chart) can only be
validated once those land, via `scripts/verify_bootstrap.sh`.
