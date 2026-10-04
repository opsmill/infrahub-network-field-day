# Contract: schema kinds

Asserted by `tests/unit/test_application_catalogue_schema_contract.py`.

1. `ServiceApplicationDefinition` exists in `schemas/catalogue/`, namespace `Service`, name `ApplicationDefinition`.
2. It does not inherit `ServiceGeneric`, `GeneratorTarget` or `CoreArtifactTarget`.
3. `default_values` is `TextArea`; no attribute of the kind is `JSON`.
4. `requestable` defaults to false; `status` offers exactly `active` and `deprecated`, default `active`.
5. `name` is unique and the HFID; `title` is the display label.
6. `ServiceFabricApp.definition` is optional, cardinality one, `on_delete: no-action`; `definition_pinned` is optional Boolean defaulting false.
7. `chart_repository`, `chart_name`, `chart_version` on `ServiceFabricApp` stay `optional: false` (existing test).
8. The kind is in the menu under `ServiceMenu` exactly once and has `include_in_menu: false` in its schema.
9. No trigger rule names the kind and `.infrahub.yml` registers no generator group for it.
