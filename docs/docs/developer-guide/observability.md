---
title: Observability
---

# Observability

Grafana, Prometheus and the telemetry collector are Infrahub service objects, delivered to the
lab's Kubernetes cluster by Vidra like any other application. Infrahub also decides **what is
monitored**: the collector's whole configuration is an artifact rendered from monitoring
profiles, so a change to what the lab watches is reviewed in a proposed change, just as a change
to what it is configured with is.

## What runs where

| Component | Where | Delivered by |
| --- | --- | --- |
| Grafana, Prometheus, node-exporter (`otternet-metrics`) | k3s, namespace `otternet-metrics` | Vidra, from the `Crossplane FabricApp` artifact |
| Telegraf (`otternet-telemetry`) | k3s, namespace `otternet-telemetry` | Vidra, from the `Crossplane FabricApp` artifact |
| Telegraf's configuration (`telegraf-intent` ConfigMap) | k3s, namespace `otternet-telemetry` | Vidra's third sync, from the `Telemetry Collector Configuration` artifact |
| Infrahub exporter | compose, beside Infrahub, host port 8002 | `invoke metrics-exporter` |
| Grafana's Dex client | `tooling/10-dex.yaml` | `invoke tooling` |
| Grafana's and Telegraf's Secrets | k3s | `invoke cluster` |

The exporter, the Dex client and the Secrets sit outside Infrahub for a reason each:

- **The exporter** has no published image or chart.
- **The sidecars** must share a router's filesystem, and the topology belongs to the lab.
- **Dex** has to exist before Infrahub can deliver anything.
- **Credentials** never pass through the graph.

## Signing in

Grafana uses the lab's one Dex issuer through `auth.generic_oauth`. `sso_provider: dex` on the
`ServiceFabricApp` makes `crossplane_fabric_app` merge the sign-in block into the chart values;
the renderer never infers it from the chart name, and raises for `dex` on a chart it has no
renderer for.

- **Everyone who signs in is a Viewer.** `role_attribute_path` is the literal `'Viewer'`,
  strictly, and the sign-in path can never make anyone an administrator. The password form is
  disabled.
- **The browser and Grafana reach Dex at different addresses.** The browser uses the issuer,
  `10.90.0.11:32556`. Grafana's own token exchange goes out of its pod over the management network
  to the tool node at `172.20.41.101:32556`, the path Vidra already uses to reach Infrahub. No
  firewall rule is needed.
- **The address is pinned.** Grafana's LoadBalancer IP, `10.112.240.81`, is fixed in the values
  through the Cilium LB-IPAM annotation, inside a block seeded in Infrahub (`10.112.240.80/28`).
  Dex's redirect URI names it, and Dex is configured before Infrahub delivers anything.

Access from the branch is an ordinary `ServiceAppAccess` grant on `otternet-metrics`. It opens the
firewall rule, the fabric advertisement and Grafana's pod policy. Nothing is seeded, so a fresh
lab starts with Grafana unreachable from the branch.

## Monitoring as intent

Three kinds, in `schemas/monitoring.yml`:

- **`MonitoringMeasurement`**: a catalogue, such as `interface-counters`, `bgp-neighbor-state` or
  `node-resources`. The name is what the renderer dispatches on.
- **`MonitoringProfile`**: device groups, optionally narrowed to one role, watched for some
  measurements at an interval. `enabled: false` withdraws a profile without deleting it.
- **`MonitoringCollector`**: one running collector, and the target of the artifact.

`telemetry_collector_config` renders one ConfigMap per collector, holding two files:

- **`telegraf.conf`**: every input, chosen by device kind:
  - EOS: gNMI on port 6030 in VRF `MGMT`
  - SR Linux: gNMI on port 57400, TLS (self-signed per lab, so not verified), through the same
    OpenConfig paths as EOS -- so the series names and labels match and fabric panels cover
    the WAN unchanged
  - Junos: SNMP v2c
  - k3s nodes: node-exporter on port 9100

  Every input is tagged from the graph with device, kind, role, rack, pod, and profile.
- **`intended.prom`**: what Infrahub intends, read back by Telegraf so dashboards can compare it
  with what is observed:
  - **BGP sessions**: for switches, from each one's stored structured config; for the SR Linux routers,
    from their modelled neighbours.
  - **Cabled links and the interfaces expected up**: from `NetworkLink`.

### The freshness generator

An artifact regenerates when its target changes, and this artifact's target is the collector. A
device joining `avd_devices` or a profile gaining a measurement is not a change to the collector,
so on its own the artifact would go stale. `generate-monitoring-collector`:

- **Runs** in every proposed change and after every merge.
- **Writes nothing.** It only asks for the artifact to be re-rendered on its own branch.
- **Never runs on an event rule.** No trigger rule may name a `Monitoring*` kind, and
  `test_deployment_schema_contract.py` fails if one does.

## Device-side enablement

Each family is enabled through its own renderer, and every change lands with the lab file the
renderer is pinned against:

- **EOS**: `custom_structured_configuration_management_api_gnmi` in the fabric's
  `avd_custom_hostvars`. ContainerLab's boot template enables gNMI, but provisioning's
  `rollback clean-config` replaced the boot configuration, so gNMI was off until the artifact
  said otherwise.
- **Junos**: a top-level `snmp` stanza from `SecurityFirewall.snmp_community` and `snmp_clients`.
  gNMI/JTI would live under `system`, which the push path refuses by design.
- **SR Linux**: the artifact renders the gNMI server (`grpc-server mgmt`, port 57400, with
  `default-tls-profile`) and `system management openconfig`. Both are part of the full
  configuration a push replaces, and the push's lifeline refuses an artifact without the gNMI
  server. The login is the fabric's `admin`, so one Telegraf credential serves both families.
  The `frr_exporter` sidecars the FRR routers needed are gone with them.

**The SNMP community is the one credential-like value in an artifact.** The device must receive it
in its configuration whatever the model does. It is read-only, bound to `mgmt_junos` (fxp0's
instance), and restricted to the management network `172.20.41.0/24`, because vrnetlab forwards
the poll with its real source address.

## Organisation metrics

The Infrahub exporter reads as `metrics-exporter`, a view-only account that
`scripts/provision_metrics_exporter.py` creates and mints a token for. It is never `admin` or
`agent`, both Super Administrators.

- **Series.** It exports one `infrahub_<kind>_info` series per node for devices, services,
  tenants, proposed changes, and deployment state. Dashboards count them with PromQL.
- **Discovery is off.** Telegraf, the collector that needs targets, cannot consume HTTP service
  discovery, and rendered targets are reviewed.

## Environment

Written to `.env` by the provisioning steps; none is committed.

| Variable | Written by | Used by |
| --- | --- | --- |
| `INFRAHUB_EXPORTER_PASSWORD`, `INFRAHUB_EXPORTER_TOKEN` | `provision_metrics_exporter.py` | `infrahub-exporter` |
| `GRAFANA_ADMIN_PASSWORD` | `invoke cluster` | Secret `grafana-admin`, for operators only |
| `OTTERNET_EOS_USERNAME`, `OTTERNET_EOS_PASSWORD` | you, optionally | Secret `telemetry-credentials` (gNMI), defaulting to the reconciler's |
