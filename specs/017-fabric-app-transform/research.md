# Phase 0 Research: Crossplane FabricApp Manifest

**Feature**: `specs/017-fabric-app-transform` | **Date**: 2026-09-11

## R1 — Reading the attachment

**Decision**: `await file.download_file()`, the same call `generate_avd_device_hostvar.py`
already uses for `AvdHostvarFile`.

The payload is stored as bytes in object storage, not in the graph, so the query returns the
file's metadata — `checksum`, `file_name` — and the content is fetched separately. The
transform parses it with `yaml.safe_load` and emits it verbatim into `spec.manifests`.

**Consequence for the transform's shape**: `transform()` must be `async`, because
`download_file()` is. Cycle 011's transform is synchronous; `avd_anta_catalog` is async, so
both shapes exist in the repository and the async one is the precedent here.

**Alternatives considered**: passing the attachment's content through the GraphQL response —
rejected, the SDK does not return file content in a query; that is the point of `storage_id`.

## R2 — Precedence between attachment and attribute

**Decision**: Attachment wins, per cycle 013's documented rule. Read the attribute only when no
attachment exists.

Cycle 013's R2 chose this direction because the attachment is the only one of the two that can
hold a payload with dotted keys. Implementing the opposite here would make the attachment
unreachable in exactly the case it was added for.

## R3 — `tenant`

**Decision**: From the VRF's name, lower-cased.

The XRD defaults `tenant` to `k8s-prod`; all three lab instances set exactly that; and
`ServiceFabricApp.vrf` points at VRF `K8S_PROD`. Lower-casing **and** replacing underscores with hyphens bridges the naming conventions:
Infrahub VRFs here are upper snake case, Kubernetes tenants are lower kebab. Lower-casing alone
yields `k8s_prod`, which is neither the XRD's default nor what the hand-written manifest says —
caught by the oracle comparison rather than by reading the schema.

**Alternatives considered**: a new attribute on the service — rejected, a schema change for a
value already modelled. Hardcoding `k8s-prod` — rejected, it would silently mislabel a second
tenant's app.

## R4 — The VIP block must be created

**Decision**: Add `10.112.240.0/28` to object data with role `vip_pool`.

Verified absent. The two other blocks the lab uses (`.16/28`, `.32/28`) belong to the
observability and access apps, which this cycle does not seed, so only one is added.

`IpamPrefix.role` is `optional: false`, and `vip_pool` is among the roles cycle 010 added — so
the role exists and is the right one.

## R5 — Seeding the payload

**Decision**: A committed YAML file under `objects/payloads/`, uploaded by a committed script.

Cycle 013 chose option A for exactly this: git holds the reviewable source, Infrahub holds the
authoritative attachment, and the transform reads the attachment. The script reuses
`save_file_if_changed`, so re-running it with unchanged content is a no-op.

**The known cost**, recorded in cycle 013: the file and the attachment can drift if someone
edits one and forgets the other. The script is idempotent and cheap, so the mitigation is to
run it as part of `invoke load`.

## R6 — Async transform and the artifact target group

**Decision**: `async def transform`, and a new group `service_fabric_apps`.

Cycle 011's artifact definition targets `service_fabric_peerings`. Applications are a different
set — a group per service kind keeps an artifact definition from generating against a target it
cannot render.

## Risk register

| Risk | Mitigation |
| --- | --- |
| The render disagrees with the hand-written manifest | SC-003 compares field by field; SC-005 singles out `allowFrom`, where an error is most costly |
| `policy` emitted as `{}` overrides XRD defaults | FR-015; an edge case in the spec |
| Adding a second artifact definition disturbs the first | SC-010 asserts cycle 011's checksum is unchanged |
| The payload file and the attachment drift | R5; the script is idempotent and belongs in `invoke load` |
| `download_file()` on a missing attachment | FR-017 fails naming the app |
