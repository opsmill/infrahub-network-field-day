# Data Model: Grafana Observability and Infrahub-Driven Monitoring

**Feature**: `034-grafana-observability` | **Date**: 2026-10-01

This model is conceptual and states the properties that the implementing agent builds with the
`infrahub-managing-schemas` skill. Every file starts with the `$schema` comment and
`version: "1.0"`.

## New file: `schemas/monitoring.yml`

A new namespace, `Monitoring`, holds three nodes. None of them is branch-agnostic, because
monitoring intent is reviewed on a branch like any other intent.

### MonitoringCollector

One running collector, which is also the target of the collector-configuration artifact.

| Field | Kind | Optional | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | Text, unique | no | — | e.g. `otternet-telegraf`. HFID `["name__value"]`, display label `name` |
| `description` | Text | yes | — | |
| `collector_type` | Dropdown | no | `telegraf` | choices: `telegraf`. Only one value this cycle, kept as a Dropdown so that a second renderer is additive |
| `namespace_name` | Text | no | — | the Kubernetes namespace its ConfigMap is delivered into (`otternet-telemetry`) |
| `config_map_name` | Text | no | `telegraf-intent` | the ConfigMap's name. The telemetry application's values mount it by this name |
| `cluster` | → `ClusterKubernetes` | no | — | cardinality one, kind `Attribute`, identifier `monitoring_collector__cluster` |
| `monitoring_profiles` | → `MonitoringProfile` | yes | — | cardinality many, identifier `monitoring_collector__profiles` (matches the profile side). Not `profiles`, which is every node's built-in relationship to `CoreProfile` |

- **Inheritance**: `CoreArtifactTarget`, so the artifact definition can target it.
- **Group**: membership in `monitoring_collectors` is seeded.
- **Uniqueness**: `[["name__value"]]`.

### MonitoringProfile

A statement that the devices in some groups are watched for some measurements at an interval.

| Field | Kind | Optional | Default | Notes |
| --- | --- | --- | --- | --- |
| `name` | Text, unique | no | — | e.g. `fabric-bgp`. HFID `["name__value"]` |
| `description` | Text | yes | — | |
| `enabled` | Boolean | no | `true` | false renders nothing for this profile and says so in a comment. It is how a profile is withdrawn without deletion |
| `interval_seconds` | Number | no | `30` | `min_value: 10`, `max_value: 3600` |
| `device_role` | Text | yes | — | if set, it matches only devices whose `role` equals it, e.g. `spine`. Absent means every device in the groups |
| `collector` | → `MonitoringCollector` | no | — | cardinality one, identifier `monitoring_collector__profiles` |
| `device_groups` | → `CoreStandardGroup` | no | — | cardinality many, `min_count: 1`, identifier `monitoring_profile__device_groups`. Peering the group, not a device kind, is what reaches all four device kinds |
| `measurements` | → `MonitoringMeasurement` | no | — | cardinality many, `min_count: 1`, identifier `monitoring_profile__measurements` |

- **Mandatory many**: both `device_groups` and `measurements` are mandatory cardinality-many, so
  Backstage's form builder admits them (AGENTS.md: "cardinality-one plus *mandatory* many
  only").
- **Uniqueness**: `[["name__value"]]`.

### MonitoringMeasurement

A seeded catalogue. A measurement's **name** is the key the renderer dispatches on, so a name no
renderer knows is a validation failure rather than a silent no-op (see the contract).

| Field | Kind | Optional | Notes |
| --- | --- | --- | --- |
| `name` | Text, unique | no | `parameters.regex: "^[a-z][a-z0-9-]+$"`. HFID `["name__value"]` |
| `label` | Text | yes | human label |
| `description` | Text | yes | |

- **Uniqueness**: `[["name__value"]]`.
- **Seeded values**, each with its families in
  [contracts/monitoring-measurements.md](./contracts/monitoring-measurements.md):
  - `interface-counters`
  - `bgp-neighbor-state`
  - `evpn-routes`
  - `system-resources`
  - `security-sessions`
  - `node-resources`

### Relationship summary

```text
MonitoringCollector 1 ──< MonitoringProfile >── many CoreStandardGroup ──members── DcimGenericDevice (all 4 kinds)
         │                        └── many MonitoringMeasurement
         └── ClusterKubernetes
```

## Extensions

### Management address on every device kind (`schemas/dcim_extensions.yml`, `security_extensions.yml`, `compute` extension)

Add `telemetry_address` → `IpamIPAddress` (kind `Attribute`, cardinality one, optional) to these kinds, so a
collector can address every device without name resolution:

- `DcimDevice`
- `SecurityFirewall`
- `ComputePhysicalServer`

**It is not called `mgmt_ip`** (changed at implementation). To the reconciler that name means
"reach this device over eAPI" (`reach = target.mgmt_ip or target.container`), and cycle 027
holds it on `DcimFabricSwitch` alone, a hold that `test_dcim_schema_contract.py` enforces. A
switch's telemetry address *is* its `mgmt_ip`, so the collector reads `mgmt_ip` for switches and
`telemetry_address` for the other three kinds. Each extension uses its own identifier. Two
Two
side-effects follow:

- **Protocols cannot reach these fields.** `infrahubctl protocols` ignores extensions, so code
  reads them through generated `*_query.py` models.
- **Optional, for existing data.** The relationship is optional, so every existing device loads
  unchanged (FR-013).

### SNMP on the firewall (`schemas/security_extensions.yml`)

| Field | Kind | Optional | Notes |
| --- | --- | --- | --- |
| `snmp_community` | Text | yes | read-only v2c community. Absent means no `snmp` stanza is rendered, which keeps the artifact byte-identical while unset. **Configuration, not a credential**. See the plan's Complexity Tracking |
| `snmp_clients` | → `IpamPrefix` | yes | cardinality one, identifier `security_firewall__snmp_clients`. The source prefix permitted to poll |

### Identity provider on an application (`schemas/service/kubernetes_services.yml`)

| Field | Kind | Optional | Default | Notes |
| --- | --- | --- | --- | --- |
| `sso_provider` | Dropdown | no | `none` | choices: `none`, `dex`. `dex` makes `crossplane_fabric_app` merge the identity-provider block into the rendered values. The renderer never infers it from the chart name (FR-010) |

When `dex` is set, the merged block is defined in
[contracts/grafana-oidc.md](./contracts/grafana-oidc.md). The block is **app-agnostic only up to
the chart**: this cycle renders it for the Grafana values path, `grafana."grafana.ini"`, and
raises for `dex` on any chart it has no renderer for. That turns a silent misconfiguration into a
loud one.

`ServiceAppAccess` is **unchanged**.

## Seed data

| File | Adds |
| --- | --- |
| `objects/00_groups.yml` | groups `monitoring_collectors`, `kubernetes_nodes` |
| `objects/26_otternet_devices.yml` and others | `telemetry_address` on the FRR routers, fw1 and the k3s nodes |
| `objects/28_otternet_endpoints.yml` | the k3s nodes join `kubernetes_nodes` |
| `objects/29_otternet_offfabric_prefixes.yml` | `IpamPrefix` `10.112.240.80/28` (role as for `.0/28`). Management `IpamIPAddress` objects `.31`, `.41–.43`, `.61–.91` |
| `objects/23_otternet_fabric.yml` | `custom_structured_configuration_management_api_gnmi` in `avd_custom_hostvars` |
| `objects/32_otternet_security.yml` | `snmp_community`, `snmp_clients` on fw1 |
| `objects/36_otternet_app_services.yml` | `otternet-metrics` (exposed, `sso_provider: dex`, block `.80/28`, `advertised_services: junos-http`, `policy_default_deny: false`) and `otternet-telemetry` (not exposed). Both are in `service_fabric_apps` |
| `objects/40_otternet_monitoring.yml` (new, next free number) | the measurement catalogue, collector `otternet-telegraf`, and profiles (below) |
| `payloads/otternet-metrics-values.yaml`, `payloads/otternet-telemetry-values.yaml` | chart values, attached as `ServiceFabricAppValuesFile` by `scripts/seed_app_payloads.py`. Dashboards inline under `grafana.dashboards` |

Seeded profiles, so that a fresh bootstrap collects from every family:

| Profile | Groups | Role | Measurements |
| --- | --- | --- | --- |
| `fabric-core` | `avd_devices` | — | interface-counters, bgp-neighbor-state, system-resources |
| `fabric-leaf-evpn` | `avd_devices` | `leaf` | evpn-routes |
| `wan-routing` | `frr_routers` | — | bgp-neighbor-state, system-resources |
| `perimeter` | `junos_firewalls` | — | interface-counters, security-sessions, system-resources |
| `cluster-nodes` | `kubernetes_nodes` | — | node-resources |

No `ServiceAppAccess` is seeded (FR-058).

## State and lifecycle

- **Profile**: `enabled` true → rendered. False → absent from the config, with a comment naming
  it. Deleted → absent. There is no status field, because a profile owns no technical objects to
  withdraw.
- **Collector**: deleting it deletes its artifact. The ConfigMap then stays in the cluster until
  the sync is removed, which is the recorded Vidra behaviour ("the operator only deletes a
  resource when the manifest it delivered goes away").
- **Applications**: `status` semantics are unchanged from the cycle-033 table.

## Validation rules (carried into tests)

1. Every seeded `MonitoringMeasurement.name` has a renderer for at least one family.
2. A profile matching zero devices renders nothing and is reported in the artifact comment. It
   is not an error.
3. A measurement not applicable to a matched device's family is skipped for that device and
   listed in a comment.
4. The rendered `telegraf.conf` parses as TOML. An empty or unparseable render raises in the
   transform, so an artifact is never produced empty.
5. `sso_provider: dex` on a chart without a renderer raises.
