# Contract: Transform Interface

**Feature**: `specs/022-frr-config-render` | **Date**: 2026-09-11

## 1. Registration

```yaml
queries:
  - name: frr_config
    file_path: "./transforms/frr_config.gql"

python_transforms:
  - name: frr_config
    class_name: FrrConfig
    file_path: "./transforms/frr_config.py"

artifact_definitions:
  - name: "frr_config"
    artifact_name: "FRR Configuration"
    parameters:
      device: "name__value"
    content_type: "text/plain"
    targets: "frr_routers"
    transformation: "frr_config"
```

`transformation` must equal the `python_transforms` name and the class's `query` attribute must
equal the registered query name. A mismatch in either fails silently — the artifact simply never
generates.

`content_type` is `text/plain` because `transform()` returns `str`. Returning a `dict` would make
it `application/json` and produce a JSON-wrapped config.

## 2. Query contract

**Operation**: `FrrConfigQuery`, with one variable — `$device: String!`.

The query is **not** device-scoped only. A provider edge's configuration is assembled from every
tenant, so the query returns:

- the target device, filtered by `$device`: name, role, `router_id`, `asn`, and its
  `RoutingBGPNeighbor` set — the device-scoped sessions no site names (R3)
- every `WanSite`: name, `attachment_kind`, `site_asn`, `lan_prefix`, `bgp_sessions` with each
  session's device and role, and `static_routes`
- every `ServiceL3vpn`: tenant, `vrf`, `dc_service_prefixes`
- every `ServiceTenantCloud`: tenant, `prefix`
- every `ServiceInternetAccess`: its `l3vpn`'s tenant — **presence is the datum**
- the `WanInternetPeering`: `peer_asn`, `customer_aggregate`
- the `isp_edge`, `isp_core` and `internet_edge` devices with their `router_id` and `asn`
- `IpamIPAddress` with `interface → device`, to resolve a static site's CE from its next hop (R4)

**Two inline fragments are mandatory**, in opposite directions:

```graphql
# interface -> addresses
interface { node { __typename ... on InterfaceLayer3 { ip_addresses { edges { node { address { value } } } } } } }

# address -> interface -> device
interface { node { __typename ... on DcimInterface { name { value } device { node { name { value } } } } } }
```

Neither field is selectable on the generic that carries it. The plain form is rejected outright
with a message naming the fragment (R5).

## 3. Transform contract

```python
class FrrConfig(InfrahubTransform):
    query = "frr_config"

    async def transform(self, data: dict[str, Any]) -> str: ...
```

- Wraps `data` in the generated `FrrConfigQuery` Pydantic model before use, following
  `transforms/avd_eos_config.py`. This is how Constitution III is met without `protocols.py`,
  which reflects no extension relationship (R8).
- Selects the template from the device's **role**, per [data-model.md](../data-model.md).
- Builds the Jinja2 environment with `undefined=StrictUndefined`, `trim_blocks=True`,
  `lstrip_blocks=True`, `keep_trailing_newline=True`. **All four matter**: the first turns a
  missing value into a named error instead of a blank (R2), and the other three are what make
  the output byte-identical rather than merely correct.
- Loads templates from `f"{self.root_directory}/transforms/templates/frr"`.
- Returns `str`. Raises on a missing required value rather than rendering a blank.

## 4. Template contract

Five templates under `transforms/templates/frr/`, ported from `../lab/wan/templates/`. Content
is unchanged **including every comment**; only the provenance line differs:

```jinja
! Rendered by Infrahub for {{ node }} -- do not edit.
```

The lab's line claims `wan/render.py` produced the file. Reproducing it verbatim would put a
false provenance claim in six device configurations, so it is the single line excluded from the
parity comparison.

## 5. Output contract

Six artifacts. For each, the rendered text equals
`../lab/wan/rendered/<device>/frr.conf` on every line except the provenance header:

| Device | Lines | Proved zero-diff in Phase 0 |
| --- | --- | --- |
| `isp-pe1` | 159 | **yes** |
| `isp-pe2` | 108 | no — simpler than isp-pe1, still unverified |
| `internet-rtr` | 61 | no |
| `cust-acme-ce` | 43 | **yes** |
| `cust-globex-ce` | 43 | **yes** |
| `branch-rtr` | 34 | no |

## 6. Test contract

`tests/unit/test_frr_config.py`:

- renders each of the six devices from a fixture and asserts equality with the golden file,
  normalising only the provenance line
- fixtures are **captured from the live graph**, not hand-written, so model drift cannot hide a
  rendering bug (FR-041)
- asserts the six-line change SC-003 describes when a tenant's `ServiceInternetAccess` is absent
- asserts a missing required value raises rather than rendering a blank
- asserts the target group holds exactly six devices and excludes `cust-acme-dr-ce`

The golden-file comparison is the gate. A test that checks for substrings instead of equality
would pass on a config with a missing neighbour, which is the failure mode this cycle's data
exists to prevent.
