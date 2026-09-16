# Contract: registration and wiring

Three files wire the generator in. All three must agree or the generator never runs.

## 1. `.infrahub.yml`

```yaml
queries:
  - name: generate_app_access
    file_path: "./generators/generate_app_access.gql"

generator_definitions:
  - name: generate-app-access
    file_path: "./generators/generate_app_access.py"
    query: generate_app_access          # MUST equal the queries entry name
    targets: service_app_accesses       # MUST equal the group name
    parameters:
      name: name__value
    class_name: AppAccessGenerator
    convert_query_response: false
```

Matches `generate-fabric-peering` field for field. `convert_query_response: false` because the generator uses the generated Pydantic models rather than SDK node objects — the same choice every generator here makes.

`execute_in_proposed_change` and `execute_after_merge` are left at their defaults (both `true`), which is what makes acceptance scenario US3-5 true: a merged grant generates without anything being run by hand.

## 2. `objects/00_groups.yml`

Added to the existing `CoreStandardGroup` document, beside `service_fabric_peerings` and `service_fabric_apps`:

```yaml
    # Generator target group for application access grants. A group rather than
    # a direct target because a generator definition cannot point at an object,
    # and a group per service kind so a generator cannot run against a kind it
    # cannot read.
    - name: service_app_accesses
```

`CoreStandardGroup`, not `CoreGeneratorGroup` — see [research.md](../research.md) R7. Every target group in this repository is a standard group, including the one `generate-fabric-peering` already targets.

## 3. `objects/38_nfd41_access_grants.yml`

One grant, **unapproved**. Group membership is declared explicitly, as `objects/35_nfd41_peering_service.yml` and `objects/36_nfd41_app_services.yml` do.

```yaml
      approved: false
      member_of_groups:
        - service_app_accesses
```

`approved: false` is the point, not an oversight: it materializes nothing, so the rendered Junos artifact stays byte-identical and `tests/unit/test_junos_config.py` keeps passing unchanged. The kind stops being empty, the group gains a member, and the demo is one field-flip away. Full reasoning in [research.md](../research.md) R5.

**File number 38** is the next free number after `37_nfd41_wan_services.yml`. Object files load in filename order, and a grant references an application, a zone and an address book entry, so it must load after `32_nfd41_security.yml` and `36_nfd41_app_services.yml`.

## Verification

```bash
uv run infrahubctl generator --list          # generate-app-access appears
uv run infrahubctl object load objects/00_groups.yml --branch <b>
uv run infrahubctl object load objects/38_nfd41_access_grants.yml --branch <b>
uv run infrahubctl generator generate-app-access --branch <b> name=<grant>
```

Three failure modes that look like something else:

- **The generator runs and does nothing.** Check `approved`. An unapproved grant is a silent no-op by design, which is indistinguishable from a broken generator unless you look.
- **`query failed` / no target.** `query:` in the generator definition must equal the `name:` in `queries:`, and `targets:` must equal the group name. Neither is checked at load time.
- **The rule exists but is absent from the rendered configuration.** Check `book_index` on the generated address entry. `junos_config.py::_addresses` skips entries with a null index, so the rule references an address the book never declares.
