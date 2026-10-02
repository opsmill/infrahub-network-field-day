---
title: Development workflow, naming and extension checklist
description: Schema-first workflow, generated files, naming conventions and the checklists for adding a device role, a transform or a hostvars field.
audience: developer
sidebar_position: 35
---

# Development workflow, naming and extension checklist

## Development workflow

1. Prefer schema-first changes: add or update YAML under `schemas/` before code uses
   new nodes, attributes, relationships, or dropdown values.
2. Regenerate generated files rather than hand-editing them:
   - `src/solution_arista_avd/protocols.py` is generated.
   - `*_query.py` Pydantic models next to `.gql` files are generated.

   **`infrahubctl protocols` does not apply the `extensions:` block.** It renders
   `SecurityZone` with `name` and `interfaces` only — no `trust_level`, no `vrf`, none
   of the advertisement fields — even though all of those are loaded and queryable.
   Regenerating after an extension-only schema change therefore produces an empty diff, and
   **no extension-added field is reachable through the generated protocols**. Code that
   needs one reads it through a generated `*_query.py` model instead.

   **A generic's `order_weight` does not reach an already-loaded node.** When a generic
   attribute changes, the server copies every property onto the inheriting nodes *except*
   `order_weight` (`AttributeSchema.update_from_generic` excludes it). Moving
   `ServiceGeneric.name` to 100 therefore reorders a freshly bootstrapped instance and leaves a
   running one exactly as it was, with `schema check` reporting the change against the generic
   alone. The same holds for inherited relationships such as `owner`.

   **Give every kind a reviewer sees a `display_label`.** Without one, rows, relationship
   pickers and proposed-change diffs read `Kind(ID: <uuid>)`, and nothing fails.
   `tests/unit/test_demo_presentation_contract.py` pins the ones added for that reason.
3. Implement generators, transforms, object data, menus, checks, or docs using the
   matching local Infrahub skills when a task touches those artifact types.
4. Keep generators idempotent: use upserts/natural keys, deterministic ordering,
   checksum comparisons, and repeated-run validation.
5. Keep GraphQL responses typed: update `.gql`, regenerate return types, and use the
   generated Pydantic models in production code.
6. Add or update unit tests for changed generator, transform, hostvars, role mapping,
   or utility behavior.
7. Run local unit/lint validation, integration tests and generator idempotence test as applicable.

## Naming conventions

- Generators: `generate_<entity>.py`.
- Generator GraphQL queries: matching `.gql` files.
- Generated query models: `*_query.py`; regenerate them from `.gql` files rather
  than hand-editing.
- Node namespaces commonly used here: `Network.*`, `Location.*`,
  `Organization.*`, `Ipam.*`, `Dcim.*`, `Avd.*`, `Routing.*`, `Evpn.*`,
  `Interface.*`, `Compute.*`.

## Extension checklist

When adding an **AVD-rendered fabric** device role:

1. Add the role value to the **`DcimFabricSwitch`** dropdown in
   `schemas/dcim_extensions.yml`. That list must stay equal to `ROLE_TO_AVD_TYPE`;
   `tests/unit/test_dcim_schema_contract.py` asserts it.
2. Load/check schema and regenerate generated files.
3. Update `ROLE_TO_AVD_TYPE` in `src/solution_arista_avd/avd.py`.
4. Update `generators/generate_avd_device_hostvar.py` for role-specific fields.
5. Update whichever upstream generator creates devices of that role and group membership.
6. Add tests, especially `tests/unit/test_avd.py` and hostvars tests when needed.
7. Update `docs/docs/developer-guide/avd/role-mapping.md` and hostvars docs.

When adding a **non-EOS** device role, steps 3 to 5 and 7 do not apply, and the role
goes on **`DcimDevice`'s** dropdown rather than `DcimFabricSwitch`'s — cycle 027 split
the one dropdown into two, so "add the role value in `schemas/dcim_extensions.yml`"
now requires choosing which kind. The role values `isp_edge`, `isp_core`,
`internet_edge`, `customer_edge`, `branch_router` and `k8s_node` describe equipment
pyAVD never renders, and they are deliberately absent from `ROLE_TO_AVD_TYPE` (there is
no `firewall` value at all: a firewall is a `SecurityFirewall`):

- `get_avd_type` raises `ValueError` for an unmapped role. That loud failure is the
  wanted behaviour here; mapping one would instead let a firewall or an SR Linux router be
  rendered as an EOS switch, which fails silently.
- Devices with these roles must never join the `avd_devices` group, which is the only
  path into the AVD hostvar generator. Membership is set in one place,
  `src/solution_arista_avd/generator.py`, on the device-creation path the fabric and
  rack generators run from device designs — so a manually loaded device stays out.
- Add the role to `NON_AVD_DEVICE_ROLES` in `tests/unit/test_avd.py`, which keeps
  `test_schema_roles_all_mapped` guarding the fabric roles while excluding these, and
  update `docs/docs/developer-guide/schemas.md` instead of the AVD role-mapping doc.

When adding a transform output:

1. Add the `.gql` query under `transforms/`.
2. Regenerate the matching `*_query.py`; do not hand-write it.
3. Implement the transform class in `transforms/`.
4. Register the query, transform, and artifact definition in `.infrahub.yml`.
5. Add unit tests and integration coverage when appropriate.

When adding a hostvars field:

1. Add schema if the source data is not already represented.
2. Reload/check schema and regenerate protocols / GraphQL schema / return types.
   Use `graphql export-schema --destination schema.graphql` with the current CLI.
3. Update `generators/avd_device_hostvar.gql`.
4. Map the field in `generators/generate_avd_device_hostvar.py`.
5. Confirm the field is accepted by the pinned PyAVD version.
6. Add tests and update `docs/docs/developer-guide/avd/hostvars.md`.
