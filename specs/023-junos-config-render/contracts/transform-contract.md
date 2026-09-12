# Contract: Transform Interface

**Feature**: `specs/023-junos-config-render` | **Date**: 2026-09-12

## 1. Registration

```yaml
queries:
  - name: junos_config
    file_path: "./transforms/junos_config.gql"

python_transforms:
  - name: junos_config
    class_name: JunosConfig
    file_path: "./transforms/junos_config.py"

artifact_definitions:
  - name: "junos_config"
    artifact_name: "Junos Configuration"
    parameters:
      device: "name__value"
    content_type: "text/plain"
    targets: "junos_firewalls"
    transformation: "junos_config"
```

`transformation` must equal the `python_transforms` name, and the class's `query` attribute must
equal the registered query name. A mismatch in either fails silently — the artifact simply never
generates. Cycle 022 verified these programmatically rather than by eye; do the same.

## 2. Query contract

**Operation**: `JunosConfigQuery`, one variable — `$device: String!`.

Returns, filtered to the firewall where the relationship allows:

- the `SecurityFirewall` and its `SecurityFirewallInterface` set, each with `name`,
  `description`, `security_zone` and `ip_addresses`
- every `SecurityZone` with its `interfaces`
- the address book: `SecurityGenericAddress` with an inline fragment per concrete kind, because
  the value field differs on each
- `SecurityAddressGroup` with its members
- `SecurityGenericService`, fragmented the same way
- `SecurityPolicy` with its `rules`, each rule's `index`, `action`, `log`, `source_zone`,
  `destination_zone`, and its address and service relationships

**Inline fragments are mandatory and must name the CONCRETE kind**:

```graphql
... on SecurityIPAMIPPrefix  { name { value } ip_prefix  { node { prefix  { value } } } }
... on SecurityIPAMIPAddress { name { value } ip_address { node { address { value } } } }
... on SecurityPrefix        { name { value } prefix { value } }
```

Cycle 022 found the failure mode: a fragment naming an intermediate generic is accepted by
GraphQL, but the generated Pydantic model discriminates on `__typename` and silently falls back
to a variant without the field. Select `__typename` at every union point, nested ones included.

**The query MUST NOT request any credential field.** There is none to request — the `system`
stanza has no model representation — and the requirement is that it stays that way.

## 3. Transform contract

```python
class JunosConfig(InfrahubTransform):
    query = "junos_config"

    async def transform(self, data: dict[str, Any]) -> str: ...
```

- Wraps `data` in the generated `JunosConfigQuery` model, following `transforms/frr_config.py`
  and `transforms/avd_eos_config.py`. This is how Constitution III is met without
  `protocols.py`, which reflects no extension relationship.
- Builds the Jinja2 environment with `undefined=StrictUndefined`, `trim_blocks=True`,
  `lstrip_blocks=True`, `keep_trailing_newline=True`, `autoescape=False`. Cycle 022 showed all
  of them matter: the first turns a missing value into a named error, the rest are what make the
  output byte-identical rather than merely correct.
- Loads templates from `f"{self.root_directory}/transforms/templates/junos"`.
- Groups rules into zone pairs by `(source_zone, destination_zone)` and orders each pair by
  `index`.
- **Excludes the address named `any` from the address book** while still emitting it wherever a
  rule references it.
- Returns `str`. Raises on a missing required value rather than rendering a blank statement.

## 4. Template contract

Under `transforms/templates/junos/`. Authored against the golden file — there is nothing to
port, which is this cycle's standing risk.

Two syntax rules the file demonstrates and a template will get wrong:

```jinja
{# one member #}   application junos-http;
{# several #}      application [ junos-http junos-https ];
```

The same applies to `address-set` members and to a rule's source and destination addresses.
Wrong on the multi path is a syntax error; wrong on the single path is accepted by Junos with
different meaning.

The output opens with a provenance line naming Infrahub and the device, as cycle 022 established.

## 5. Output contract

One artifact, matching the `interfaces` and `security` stanzas of
`../lab/configs/fw/vsrx/junos.conf` — 573 of its 677 lines — excluding only the provenance
header and the 7-line `flow` block.

| Element | Count |
| --- | --- |
| zones | 6 |
| address-book entries | 13 *(not 14 — `any` is excluded)* |
| address-sets | 4 |
| zone pairs | 11 |
| policy rules | 19, of which 6 are `deny-spoofed-infra` |

## 6. Test contract

`tests/unit/test_junos_config.py`:

- renders `fw1` from a fixture and asserts equality with the in-scope stanzas of the golden file
- the fixture is captured from the live graph, never hand-written
- asserts `deny-spoofed-infra` renders six times with byte-identical bodies
- asserts **no credential appears** — no `encrypted-password`, no key material
- asserts brace balance and a trailing newline
- asserts `any` appears in rule references and never in the address book
- asserts rule order within every zone pair matches the golden file

Equality, not substring matching. A substring test passes on a policy stanza with a rule in the
wrong position, which is a different firewall that loads without complaint.
