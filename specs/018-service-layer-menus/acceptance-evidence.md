# Acceptance Evidence

**Feature**: `specs/018-service-layer-menus` | **Date**: 2026-09-11

## SC-001 / SC-002 — the sections exist

The menu goes from 8 top-level sections to 13:

```text
Fabric Design · Devices · IPAM · Routing · EVPN Services · Locations · Compute · Management
Services · Security · Kubernetes · WAN · Tenancy
```

`Services` contains exactly the six concrete service kinds. Security nests its address book
(7 kinds) and service catalogue (4 kinds) rather than listing eleven siblings flat.

## SC-003 / SC-004 — nothing dead, nothing unreachable

Both asserted by contract tests, because neither is visible to a human reading the YAML and
Infrahub fails the load for neither:

| Assertion | Catches |
| --- | --- |
| Every menu `kind` exists in the schema | A dead entry that renders and does nothing |
| Every menu-visible kind in the new domains is reachable | **The exact state this cycle found**: 28 kinds present in the schema and invisible in the UI |

## SC-005 — it loads, idempotently

```text
uv run infrahubctl menu load menus/ --branch menu-check
INFO  Created node: Organization__Tenants   (…and the rest)

second load: no errors
menu items in graph: 122
```

## SC-006 — tests and linters

```text
uv run pytest tests/unit          897 passed  (886 + 11 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing, unchanged
```

## A note on proportionality

This cycle produced a spec, a checklist, the work, and this evidence — not the five design
documents the preceding seven cycles each needed. FR-065 stated the requirement in full and a
menu file has no interface contract beyond "the kinds exist and are reachable", so there was
nothing to research or model. Matching the ceremony to the work is the judgement; recording it
is so the gap in the specs directory does not read as an omission.

## One test bug, fixed rather than hidden

The first version of `test_no_service_kind_appears_outside_the_service_section` compared
entries by `id()`. Each helper re-parses the YAML, so the objects are never the same instance
and the test failed on a correct menu. It compares `(namespace, name)` now. Worth recording
because it failed loudly rather than passing vacuously — the right way round for a test whose
whole job is catching something invisible.
