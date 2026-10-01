# Implementation Plan: Grafana Observability, Requested Like Any Other Application

**Branch**: `034-grafana-observability` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/034-grafana-observability/spec.md`

## Summary

The cluster's monitoring becomes Infrahub intent. It is delivered as two seeded applications,
both delivered by Vidra:

- **`otternet-metrics`**: kube-prometheus-stack, with Grafana signing in through the one Dex
  issuer.
- **`otternet-telemetry`**: Telegraf.

**Organisation metrics** come from the Infrahub exporter, which runs beside Infrahub under a
dedicated read-only account.

**Device telemetry** covers all four device kinds, and Infrahub drives it. A new `Monitoring`
schema says which device groups are watched for which measurements. Infrahub renders that intent,
with every target, subscription and filter plus the intended-state series, into a **ConfigMap
artifact** that Vidra delivers and Telegraf runs. Each device's own renderer enables telemetry on
it:

- gNMI through AVD custom structured config
- SNMP through `junos_config`
- an `frr_exporter` sidecar in the lab topology
- node-exporter from the chart

**Alice's request** is the existing network-only `ServiceAppAccess`. Merging it opens the firewall
and the advertisement to Grafana's seeded VIP `10.112.240.81`, and she then signs in through Dex
as Viewer.

## Technical Context

**Language/Version**: Python 3.12 in the host venv; the image is 3.13. YAML schemas; Jinja-free
Python transforms.

**Primary Dependencies**:

- infrahub-sdk ≥1.19 (1.22 installed), pyavd 6.4.0
- Infrahub 1.10.6, Vidra, Crossplane FabricApp XRD (lab)
- kube-prometheus-stack 90.0.0, influxdata/telegraf chart (Telegraf ≥1.33)
- frr_exporter v1.12.0
- infrahub-exporter `@80974df`
- Dex v2.44.0

No new Python dependency: `tomllib` is in the standard library and validates the render.

**Storage**: the Infrahub graph; Kubernetes ConfigMaps and Secrets; Prometheus TSDB with the
chart's default retention.

**Testing**: pytest unit tests (transform invariants, dispatch-table contract, byte-for-byte pins,
no-credential grep), `infrahub-run-integration-tests`, generator idempotence for
`generate-monitoring-collector`, and `scripts/verify_bootstrap.sh`.

**Target Platform**: the lab host (Docker Compose Infrahub), the ContainerLab topology, and k3s
`otternet` with Cilium.

**Project Type**: Infrahub repository (schemas, objects, transforms, generators) with lab
automation (invoke, scripts).

**Performance Goals**:

- A monitoring-intent merge changes collection within 5 minutes (SC-009).
- A downed BGP session is visible within 1 minute (SC-010).
- The demo's automation share is under 2 minutes (SC-003).

**Constraints**:

- No credential in the graph or in an artifact. The SNMP community is the recorded exception.
- `junos_config` and `frr_config` stay byte-for-byte equal to the lab files, and the lab files
  move with them.
- Nothing may trigger on `Monitoring*` or `Deployment*` kinds.

**Scale/Scope**: 17 devices, 1 collector, 5 profiles, 6 measurements, 2 new applications,
and about 3 dashboards.

## Constitution Check

*GATE: checked before Phase 0, and re-checked after Phase 1 (below).*

| Principle | Status | Evidence |
| --- | --- | --- |
| I. Schema-Driven | ✅ | `schemas/monitoring.yml` and the extensions come first. Protocols are regenerated, and extension fields are read through `*_query.py` models (AGENTS.md: protocols ignore extensions) |
| I. Namespaces | ⚠️ justified | the new `Monitoring` namespace. See Complexity Tracking |
| II. Idempotent | ✅ | `generate-monitoring-collector` writes no nodes. Its idempotence test asserts that a second run creates no node. Seed data uses upserts, and transforms are deterministic with a byte-identical re-render test |
| III. Type Safety | ✅ | new `.gql` files with generated `*_query.py` models: `telemetry_collector_config`, the extended `crossplane_fabric_app`, the extended `junos_config`. mypy strict |
| IV. Test-Required | ✅ | unit tests per contract invariant, integration via `$infrahub-run-integration-tests`, `$infrahub-test-generator-idempotence` for the new generator, lint gates, and the verify script |
| V. Conventions | ✅ | `transforms/telemetry_collector_config.{py,gql}` + `_query.py`, `generators/generate_monitoring_collector.{py,gql}`, `objects/40_otternet_monitoring.yml` (next number), docs under `docs/docs/` |
| Stack | ✅ | no new Python dependency. The exporter is a container built from a pinned commit, not a Python dependency of this project |

## Project Structure

### Documentation (this feature)

```text
specs/034-grafana-observability/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── monitoring-measurements.md
│   ├── telemetry-collector-artifact.md
│   ├── grafana-oidc.md
│   └── exporter.md
└── tasks.md            # /speckit-tasks
```

### Source Code (repository root)

```text
schemas/
├── monitoring.yml                         # NEW: MonitoringCollector/Profile/Measurement
├── dcim_extensions.yml                    # + DcimDevice.telemetry_address
├── security_extensions.yml                # + SecurityFirewall.telemetry_address, snmp_community, snmp_clients
├── compute/… (extension)                  # + ComputePhysicalServer.telemetry_address
└── service/kubernetes_services.yml        # + ServiceFabricApp.sso_provider
objects/
├── 00_groups.yml                          # + monitoring_collectors, kubernetes_nodes
├── 23_otternet_fabric.yml                 # + management_api_gnmi custom structured config
├── 26_/28_/29_/32_ …                      # mgmt addresses, .80/28 block, fw1 SNMP
├── 36_otternet_app_services.yml           # + otternet-metrics, otternet-telemetry
└── 40_otternet_monitoring.yml             # NEW: catalogue, collector, profiles
payloads/
├── otternet-metrics-values.yaml           # NEW: kps values incl. dashboards, scrape configs
└── otternet-telemetry-values.yaml         # NEW: telegraf values (mount, args, envFromSecret)
transforms/
├── telemetry_collector_config.{py,gql} + _query.py   # NEW
├── crossplane_fabric_app.{py,gql} + _query.py        # + sso_provider merge
└── junos_config.{py,gql} + _query.py                 # + snmp stanza
generators/
└── generate_monitoring_collector.{py,gql} + _query.py # NEW: requests artifact re-render only
metrics/exporter.yml                        # NEW: exporter config (no token)
docker-compose.override.yml                 # + infrahub-exporter service
scripts/
├── provision_metrics_exporter.py           # NEW
├── seed_app_payloads.py                    # + two payloads
└── verify_bootstrap.sh                     # new assertions, counts 1→3
tooling/10-dex.yaml                         # + grafana static client
vidra/infrahub-syncs.yaml                   # + third sync
tasks.py                                    # metrics-exporter task, bootstrap order, cluster secrets, installer opt-out
.infrahub.yml                               # + query, transform, artifact def, generator def
tests/unit/                                 # see Testing
docs/docs/                                  # demo-runbook act, observability page, supported-capabilities
../lab/                                     # R14: installer opt-out, frr_exporter sidecars, junos.conf snmp, group_vars gNMI, bookmark
```

**Structure Decision**: this is the existing single-repository Infrahub layout, so no new
top-level code directories are needed. `metrics/` holds the exporter's configuration, as
`vidra/` holds Vidra's.

## Phase 0 and Phase 1 outputs

- [research.md](./research.md): R1–R14. Every Technical Context unknown is resolved, and each
  residual inference is marked **Verify**.
- [data-model.md](./data-model.md): kinds, extensions, seed data and validation rules.
- [contracts/](./contracts/): the measurement dispatch table, the collector artifact, Grafana
  OIDC, and the exporter.
- [quickstart.md](./quickstart.md): offline gates, rebuild, the demo act, intent-driven
  collection, intended versus observed, and freshness.

## Delivery order (feeds `/speckit-tasks`)

1. **Schema**: the monitoring kinds and the extensions. Check, load on a branch, regenerate
   protocols and return types.
2. **Seed data**: groups, management addresses, the block, applications, the monitoring
   catalogue, collector and profiles.
3. **Device-side enablement**, each with its lab-file change committed beside it so the pins hold:
   - gNMI hostvars and the EOS golden files
   - `junos_config` SNMP and `junos.conf`
   - the lab's `frr_exporter` sidecars
4. **Collector artifact**: the transform, the query, the artifact definition, and
   `generate-monitoring-collector`.
5. **Applications**: values payloads, the `crossplane_fabric_app` `sso_provider` merge, the Dex
   client, and the third Vidra sync.
6. **Exporter**: the compose service, the provisioning script and the invoke task.
7. **Bootstrap**: `tasks.py` order, Secrets, the installer opt-out, and `verify_bootstrap.sh`.
8. **Dashboards**: organisation, fabric (intended versus observed), WAN, firewall and nodes.
9. **Docs**: the demo-runbook act, a new observability developer page, supported capabilities, and
   AGENTS.md sections in house style.

## Testing

- **Contract tests**:
  - the dispatch table equals `monitoring-measurements.md`
  - the collector artifact invariants (1–5)
  - `crossplane_fabric_app` with `sso_provider: dex` merges exactly the
    `grafana-oidc.md` block, and with `none` is byte-identical to before
- **Pins**:
  - `test_junos_config` against the updated `junos.conf`, with the `snmp` stanza only when
    `snmp_community` is set, and `test_the_exclusions_add_up` recounted
  - `test_frr_config` unchanged
  - EOS golden files regenerated
- **Normalisation**: captured `show running-config` output for the new gNMI and SNMP lines, in
  both the in-sync case and the changed case, in `test_deployment_normalise.py`
- **Safety**:
  - a grep over every rendered artifact for the Dex secret, the admin password and the gNMI
    password
  - `test_deployment_schema_contract` extended so that no trigger names a `Monitoring*` kind
  - `test_no_grant_is_seeded` unchanged
  - `test_handover_scope` accounting for the opt-out
- **Generator**: `generate-monitoring-collector` idempotence (no node writes) and a branch
  freshness scenario (quickstart §6)
- **Inventory**: a test that a populated `telemetry_address` on FRR or Junos does not change the
  reconciler's `Target`

## Post-design Constitution re-check

The table above is unchanged by Phase 1. The design adds:

- one generator, with idempotence covered
- one transform, typed and tested
- three nodes in a justified namespace
- extensions read through typed query models

No gate fails.

## Complexity Tracking

| Deviation | Why needed | Simpler alternative rejected because |
| --- | --- | --- |
| New `Monitoring` namespace | monitoring intent is neither device, service nor routing data, and it peers groups across all four device kinds | putting it under `Service` would make it a requestable service with `status` and an owner, which it is not. Under `Network`, it would be filed beside fabric topology |
| SNMPv2c community in an artifact and in the graph (FR-012 exception) | the device must receive it in configuration, so it is unavoidably in the rendered Junos artifact | gNMI on Junos sits under `system`, which the push path refuses by design. SNMPv3 also puts its keys in configuration. Mitigation: read-only and client-restricted |
| Two lab-side components Infrahub does not render: the `frr_exporter` sidecars and the installer opt-out | the FRR image has no telemetry API, and the lab installer has no skip flag | building an SNMP-capable FRR image or running BMP: heavier and further from upstream. A `crds.enabled: false` workaround depends on a claim this cycle stops wanting (R2) |
| Dex back channel over the management network, not through fw1 (FR-054 narrowed) | the path already exists, and Vidra uses it | a `k8s-prod → tooling` rule adds a zone pair to two pinned files to carry traffic that already has a path |
| `policy_default_deny: false` on `otternet-metrics` | Prometheus scrapes cluster internals that one selector-scoped ingress policy cannot express | extending the XRD with multi-workload policy belongs to the lab and is out of scope. The branch gate remains the firewall and the advertisement |
