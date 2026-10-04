# Quickstart: validating the application catalogue

## Offline (this repository, no stack)

```bash
uv run invoke lint
uv run invoke test
uv run pytest tests/unit/test_application_catalogue_schema_contract.py tests/unit/test_application_catalogue_seed_data.py tests/unit/test_fabric_app_pin.py tests/unit/test_application_catalogue_portal.py tests/unit/test_service_trigger_contract.py tests/unit/test_crossplane_fabric_app.py
```

Expected: every gate exits 0.

## Lab phase (not runnable offline)

See the checklist in `RUN-NOTES.md`: load the schema, load objects and seed payloads, re-export `schema.graphql`, rebuild the portal, then run act one of the demo and check the rendered Crossplane artifact shows chart `whoami` 6.0.0 and the values. Contracts: [schema kinds](./contracts/schema-kinds.md), [template](./contracts/template-contract.md); model: [data-model.md](./data-model.md).
