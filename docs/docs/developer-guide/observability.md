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
| Service-lifecycle exporter | compose, beside Infrahub, host port 8003 | `invoke metrics-exporter` |
| Grafana's Dex client | `tooling/10-dex.yaml` | `invoke tooling` |
| Grafana's and Telegraf's Secrets | k3s | `invoke cluster` |

The exporter, the Dex client and the Secrets sit outside Infrahub for a reason each:

- **The exporter** has no published image or chart.
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
  measurements at an interval. `enabled: false` withdraws a profile without deleting it. A
  profile that names a **`service_kind`** watches services instead: see
  [Services](#services).
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

  Two measurements carry more than their name suggests, because the dashboards compare them with
  intent:
  - **`interface-counters`** also subscribes to `oper-status`, mapped onto IF-MIB's `ifOperStatus`
    numbers (`UP` is 1). A gNMI interface and the firewall's SNMP one therefore compare with the
    same `== 1`.
  - **`bgp-neighbor-state`** also subscribes to the per-AFI prefix counts, so a session that is
    Established and carries nothing is visible. `evpn-routes` uses the same subscription, and a
    leaf asked for both subscribes once.
- **`intended.prom`**: what Infrahub intends, read back by Telegraf so dashboards can compare it
  with what is observed. Every series carries the device's `kind`, so a dashboard scopes intent
  the way it scopes observations, and a silent device's sessions still count as intended:
  - **BGP sessions**: for switches, from each one's stored structured config, with their VRF. For
    the SR Linux routers, from their modelled neighbours, with no VRF, because the model does not
    record the network instance a router neighbour lives in. A WAN dashboard therefore matches on
    device and peer address and takes the VRF from what the router reports.
  - **Cabled links and the interfaces expected up**: from `NetworkLink`, which records the fabric's
    cabling. The WAN's circuits are not `NetworkLink`s.

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

## Dashboards

The dashboards are JSON files under `payloads/dashboards/`, one per file, and
`scripts/seed_app_payloads.py` folds them into the `otternet-metrics` values attachment. Grafana
opens on **Organisation**, whose first row is the lab's health: one tile per family, each 0 or
green when the lab matches its intent, and each linking to the dashboard that explains it.

| Dashboard | Shows |
| --- | --- |
| Organisation | Health tiles; then devices, services, tenants and proposed changes from the exporter |
| Deployment state | Each device's `DeploymentState`, and how the counts moved over time |
| Fabric telemetry | Every intended BGP session and cabled link against what the switches report; EVPN and IPv4 prefixes; throughput, errors, CPU and memory |
| WAN routing | The same for the SR Linux routers, per VRF; prefixes received and sent per session |
| Perimeter firewall | fw1's zone handoffs by their modelled description, sessions, and the routing engine |
| Kubernetes nodes | Pod CPU against each node's one CPU, pod memory, node network, the lab host, and Cilium's flows and drops |
| Services | Every service request from its branch to its health: requested, merged, deployed, healthy, removed |

Every dashboard refreshes once a minute, because a k3s node is one CPU. The per-device
dashboards share a `device` variable listing the devices Infrahub models, rather than the ones
currently reporting, so a silent device is still selectable.

Read these before trusting a number on them:

- **Containerised network operating systems report the lab host.** cEOS and SR Linux report the
  host's CPUs and memory as their own, as does node-exporter. The CPU and memory panels are still
  useful, because a device that leaves the pack is the signal, and they say so. A node's own load
  is its pods' CPU from the kubelet, drawn against its one CPU.
- **`tests/unit/test_dashboard_metrics_contract.py` holds every panel to a series that exists.**
  It renders the collector's intent and fails when a panel queries a metric no collector,
  exporter or scrape job produces, or filters a `kind` that never reports it.
- **`scripts/check_grafana_panels.py` holds every panel to data as Grafana returns it.** It
  checks the datasource's health, then runs each visible query of each dashboard in the
  `OTTERNET` folder through Grafana's `/api/ds/query` over the last 30 minutes, with the
  dashboard's own variables. It fails naming every panel that returns no data or an error.
  `verify_bootstrap.sh` runs it, and it works against any running Grafana through a
  port-forward. Two queries are allowed to be empty, both listed in its `ALLOWED_EMPTY`:
  the per-port breakouts on Fabric telemetry's "Errors and discards" and the firewall's
  "Interface errors", each filtered with `> 0`, so a healthy lab has no series. Each panel's
  other query must still return data. Services' "Probed ports answering" was a third until
  the collector was admitted at the applications' pod gates; both of its queries now
  return data.

**The chart's own dashboards are off** (`grafana.defaultDashboardsEnabled: false`). The
kube-prometheus-stack chart ships 21 of them into Grafana's `General` folder, beside the seven
above. They were turned off rather than moved to a `Platform` folder, for four reasons. No
OTTERNET dashboard links to one, and `test_no_otternet_dashboard_links_outside_the_folder`
keeps it that way. No runbook step opens one. Several cannot show anything here: the USE Method
dashboards read a node-exporter job that is never scraped, and the API server latency panels
read histogram buckets dropped at scrape time. And Kubernetes nodes replaces the node-level
views. Explore still reaches every series.

Two chart settings looked unrelated to dashboards. Without each, the dashboards were wrong:

- **`grafana.ini` `plugins.preinstall_disabled`.** Grafana 13 updates its bundled datasource
  plugins at start-up. On the chart's read-only root that stops the bundled Prometheus plugin
  and then fails to replace it (`unlinkat ... read-only file system`). Every query then returns
  `plugin.notRegistered`, and every panel reads "No data" while Prometheus holds all of it.
- **A fixed `prometheusOperator.kubeletService.name`.** The operator names the kubelet Service
  after the release, and the composed release's name is generated. A re-delivery left the old
  Service behind, every kubelet series was scraped twice, and every pod CPU and memory sum read
  double.

## Services

Every service is monitored because it exists, and nobody adds monitoring for one.
Two things make that true, and both are configured in Infrahub.

### Service profiles select by kind

A `MonitoringProfile` with `service_kind` set watches every **live** service of that
kind, where it sits: `ServiceGeneric` means every kind, including one added later.
Live means what it means to every renderer here: not `decommissioning` and not
`decommissioned`, so withdrawing a service withdraws its monitoring in the same
proposed change. A service profile names no device group, because a service is in
a group only when a generator sits beneath its kind and the three WAN kinds are in
none. That is why `device_groups` became optional; the renderer still refuses a
device profile with no group.

The measurement catalogue gained six service measurements.
`transforms/telemetry_services.py::SERVICE_DISPATCH` says how each is rendered for
each kind; whether it applies is the profiles' business.

| Measurement | Kinds | What the collector's artifact carries |
| --- | --- | --- |
| `service-lifecycle` | every kind | one scrape of the lifecycle exporter, `?kinds=` from the profile |
| `service-delivery` | `ServiceFabricApp` | the namespace whose pods must be ready, and the VIP block an address must be assigned from |
| `service-reachability` | `ServiceFabricApp` | a TCP probe of the VIP per advertised TCP port, and the application's own FabricApp admitting the collector |
| `service-access` | `ServiceAppAccess` | each granted rule and the firewall holding it |
| `service-routing` | the WAN kinds, tenant cloud, onboarding, segment, peering | the BGP sessions that realise the service |
| `service-cabling` | `ServiceServerPlacement` | the switch ports the machine is cabled to |

Four profiles are seeded: `services-lifecycle` (every kind), `services-apps`,
`services-access` and `services-routing` (every kind). Each can be switched off,
re-timed or narrowed on its own, and the artifact diff of that edit is exactly the
monitoring that moves.

The checks join intent to series something already collects. No device is polled
for a service:

- **Routing.** An L3VPN's sessions are the ones its circuits' WAN sites record, an
  internet-access product's the ones its peering records. A tenant cloud,
  onboarding, segment or peering names a VRF instead, and takes the sessions the
  fabric's structured configs put in it: on the peering's own leaves, or a
  segment's tagged ones. All are joined to `bgp_neighbor_session_state_code` on
  device and peer address.
- **Delivery.** kube-state-metrics, joined by namespace: pods ready, and a
  LoadBalancer address assigned. Readiness is the kubelet's own probing, which the
  composed pod policy admits as `host`.
- **Access.** The firewall named by the grant's rules must be confirmed in sync,
  and the grant's application must pass its own checks. The branch-side session is
  not probed: no collector sits at the branch.

### Monitoring opens a fourth gate, and only for the collector

A session to an application passes three gates: the route, the firewall, and the
application's own CiliumNetworkPolicy. A grant opens all three for one source. The
collector probing the application from inside the cluster needs the third alone,
and `allowed_source_prefixes` cannot give it. Cilium matches `fromCIDR` against
traffic from outside the cluster only. Measured from a throwaway pod before this
change: Telegraf's pod timed out against `otternet-demo` and Grafana, while the
same probes from the host network answered in 8 ms.

The FabricApp therefore carries `spec.monitoring`, and the composition renders it as
one more policy, `allow-collector`:

```yaml
spec:
  monitoring:
    collectorNamespaces: [otternet-telemetry]
    ports:
      - port: "3000"     # Grafana's pod port; its VIP answers on 80
        protocol: TCP
```

Four rules keep this from weakening anything:

- **Infrahub decides it, from monitoring intent.** `crossplane_fabric_app` renders
  the field from every enabled service profile that asks for `service-reachability`
  of applications. The value is the namespace of each profile's collector. Take the
  measurement off `services-apps` and, in one proposed change, each FabricApp loses
  its admission and the collector's artifact loses its probes. Measured on a scratch
  branch: with the measurement removed, both FabricApps rendered byte-identical to
  `main`.
- **Only the collector's namespace.** The rule is `fromEndpoints` on
  `io.kubernetes.pod.namespace`, a label Cilium derives from the pod rather than one
  a pod can set. It goes to the same endpoints `allow-ingress` protects, with no
  `fromCIDR` and no `fromEntities`.
- **Only the application's own ports.** Cilium enforces after service translation,
  so a probe of Grafana's VIP on 80 reaches the pod as 3000. The admission therefore
  names the pod ports, `policy_allow_ports`, which external sources are already
  confined to. An application declaring none is not admitted, rather than admitted
  on every port.
- **Only where the gate is closed.** With neither `policy_default_deny` nor a source
  prefix, nothing selects the pods and the collector is admitted already. A policy
  selecting them would turn their ingress deny-by-default for every other source.
  The composition renders `allow-collector` only under `defaultDeny` or a non-empty
  `allowFrom`, and the transform omits the field there too.

**One function decides both halves.** `telemetry_services.py::collector_admission`
is what `crossplane_fabric_app` renders the admission from. The Telemetry Collector
Configuration renders a probe of a gated application only where that same function
admits the collector's own namespace, and a probe never targets a gate that drops it.
`tests/unit/test_probe_admission_contract.py` renders both artifacts from one intent
across each change that should move them, and holds them to each other.

Measured on the live cluster, through a copy of the composition and a scratch claim
gated like `otternet-demo`, with Service port 80 mapped to pod port 8080 and a
second listener on 9090:

| Source | Pod `8080` / VIP `80` | Pod `9090` / VIP `90` |
| --- | --- | --- |
| collector namespace, from either node | answered | dropped |
| any other namespace, from either node | dropped | dropped |
| collector namespace, `spec.monitoring` removed | dropped | dropped |

Telegraf's own `net_response` from the collector namespace read `result_code=0` on
port 80 and `timeout` on port 90. With the gate open, no `allow-collector` was
rendered at all.

An application that is not exposed, has no VIP block yet, advertises no TCP
service, or is withdrawn is neither probed nor admitted. Each artifact says why in
a `# not probed:` comment. A probe's address is the one the application's values pin
with `lbipam.cilium.io/ips`. Otherwise it is the first address of its block, which
Cilium LB-IPAM gives the first Service of a pool the composition makes for that
application alone.

**Delivery order matters once.** The XRD field and the composition must be applied
to the cluster before Vidra delivers a FabricApp carrying `spec.monitoring`. They
are the lab's, applied by `install-crossplane.sh`. An XRD without the field either
refuses a FabricApp carrying it or silently prunes it, depending on how the writer
validates. A pruned field renders no admission, so the probe times out.

### The lifecycle exporter

`scripts/service_lifecycle_exporter.py`, with its logic in
`src/solution_arista_avd/service_lifecycle.py`, reports each service's stage as
`otternet_service_stage`:

| Stage | Means |
| --- | --- |
| `requested` | on a branch whose proposed change is open, new, deleted or changed against `main`, with its validators' verdict |
| `merged` | on `main` and live, while some tracked device is not confirmed in sync since the service last changed |
| `deployed` | on `main`, live, and every tracked device confirmed in sync since then |
| `decommissioning` | on `main` with status `decommissioning` or `decommissioned` |
| `removed` | deleted from `main` in the last 24 hours |

Healthy is not a stage the exporter decides: it is `deployed` and every check
passing, which only Prometheus can join, and the Services dashboard does that join.
Created, status-changed and deleted services and merged proposed changes are also
exported as `..._timestamp_seconds` series whose value is the event's time, so
Grafana draws them as annotations at the exact moment. They come from
`InfrahubEvent`, not from series appearing.

Four things about it are deliberate:

- **It is not the Infrahub exporter.** That one reads one branch, configured once,
  and exports attributes of nodes. A request lives on a branch nobody configured,
  its verdict is on validators, its deployment in `DeploymentState` timestamps,
  and its removal only in `InfrahubEvent`.
- **It has no configuration.** The kinds it reports are the scrape's `?kinds=`,
  rendered from `services-lifecycle` into the collector's artifact.
- **"Deployed" is fleet-wide.** Only the generators know which devices a service
  changes, so it asks the stronger question the graph answers. One device stuck
  unconfirmed holds every later change at `merged`.
- **A failed poll keeps the last snapshot** and reports
  `otternet_service_lifecycle_up 0`. The Infrahub exporter empties a kind's series
  on a failed fetch, which reads exactly like every service being deleted.

Two Infrahub behaviours it works around, both measured:

- `node_metadata.updated_at` disagrees between `main` and a branch for a node
  neither changed. A request is therefore a status change, or an edit dated after the
  branch was cut and after `main`'s last change.
- A deletion event carries no attributes, and events arrive newest first. They are
  folded oldest first, so a removed service keeps its name.

It reads as `metrics-exporter`, the Infrahub exporter's view-only account, writes
nothing, and nothing generates from what it reports.

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
| `INFRAHUB_EXPORTER_PASSWORD`, `INFRAHUB_EXPORTER_TOKEN` | `provision_metrics_exporter.py` | `infrahub-exporter`, `service-lifecycle-exporter` |
| `OTTERNET_LIFECYCLE_POLL` | you, optionally | `service-lifecycle-exporter`, seconds between polls (15) |
| `GRAFANA_ADMIN_PASSWORD` | `invoke cluster` | Secret `grafana-admin`, for operators only |
| `OTTERNET_EOS_USERNAME`, `OTTERNET_EOS_PASSWORD` | you, optionally | Secret `telemetry-credentials` (gNMI), defaulting to the reconciler's |

## Design decisions and measured pitfalls

Moved from the repository instruction file. These are the decisions that look like oversights, each with the measurement behind it.

Grafana and Prometheus (`otternet-metrics`) and Telegraf (`otternet-telemetry`) are seeded
`ServiceFabricApp`s, delivered by Vidra like `otternet-demo`. **Telegraf's whole configuration is
an artifact**: `telemetry_collector_config` renders one ConfigMap per `MonitoringCollector` from
the `MonitoringProfile`s that name it, and a third `InfrahubSync` delivers it into
`otternet-telemetry`. What the lab watches is changed in Infrahub and reviewed in a proposed
change, exactly like what it is configured with. See
[observability](./observability.md).

Seven things look like oversights and are not:

- **The new name is deliberate.** `otternet-metrics` replaces the lab's `otternet-observability`,
  which `invoke cluster` keeps out with `OTTERNET_SKIP_OBSERVABILITY`. Two kube-prometheus-stack
  releases contend for the same CRDs, and the second fails `invalid ownership metadata`. Vidra
  goes up before Crossplane, so both would be created in one window and deleting the lab's
  afterwards is too late.
- **`policy_default_deny: false` on both applications, and Grafana's pod gate still holds.**
  Prometheus scrapes cluster internals that the composition's one selector-scoped ingress policy
  cannot express. With `allowed_source_prefixes` non-empty the composition still renders
  `allow-ingress` on Grafana's pods, and seeding the pod CIDR makes that policy exist from the
  first render. So the branch is dropped at the pod until a grant adds `10.70.0.0/24`.
- **The new address field is `telemetry_address`, never `mgmt_ip`.** To the reconciler,
  `mgmt_ip` means "push over eAPI" (`reach = target.mgmt_ip or target.container`), and cycle 027
  holds it on `DcimFabricSwitch` alone. The WAN routers, fw1 and the k3s nodes needed an address a
  pod can reach, and `test_deployment_inventory_targets.py` pins that the reconciler never reads
  the new one.
- **The collector relationship is `monitoring_profiles`, not `profiles`.** Every node already has
  a built-in `profiles` relationship to `CoreProfile`. A schema relationship of that name loads
  cleanly and makes the query resolve against `CoreProfile`, failing with `Cannot query field
  'device_groups' on type 'CoreProfile'`.
- **`generate-monitoring-collector` writes nothing.** The artifact's target is the collector, and
  almost nothing that changes what should be collected is a change to the collector. So it
  re-renders the artifact on its branch, in every proposed change and after every merge. **No
  trigger may name a `Monitoring*` kind**, for the same reason as `Deployment*`.
- **The Dex back channel goes over the management network.** The browser uses the issuer
  `10.90.0.11`; Grafana's token exchange goes to `172.20.41.101`, the path Vidra already uses,
  because `10.90.0.11` from a pod crosses fw1 and no rule permits it. Grafana's VIP
  (`10.112.240.81`) is pinned and its block seeded, because Dex names it before Infrahub
  delivers anything.
- **The SNMP community is in an artifact, deliberately.** The device must receive it in its
  configuration. It is read-only, bound to `mgmt_junos` and restricted to the management
  network: vrnetlab forwards UDP/161 with the poller's real source address, so the
  clients are `172.20.41.0/24`, not vrnetlab's internal `10.0.0.0/24`. Unbound, or with
  the internal subnet, every poll counts as a "Bad community use" and nothing answers.
  It is no longer the only credential there: since cycle 035 the firewall's two login hashes
  are too, as template content rather than data -- see `junos_config` below.

Three measured facts about the device side:

- **gNMI was off on every switch.** ContainerLab's boot template enables it, and provisioning's
  `rollback clean-config` removed it. It is back through `avd_custom_hostvars` and the lab's
  `group_vars`, with the golden files regenerated.
- **The WAN routers stream over gNMI natively since the SR Linux re-platform**, and through the
  SAME OpenConfig paths as the switches, so the series arrive under the same names and labels
  (`bgp_neighbor_session_state_code{neighbor_address,name}`, `interface_counters_*`, `cpu_*`,
  `memory_*`) and every fabric panel covers the WAN with no second query. Port 57400, TLS with
  `default-tls-profile` — a certificate each router generates for itself — so
  `insecure_skip_verify`; credentials are the switches' own `${GNMI_USERNAME}`/`${GNMI_PASSWORD}`,
  because the routers render the same `NetworkLocalUser` `admin` hash. FRR 10.2-10.5 shipped no
  SNMP and no gNMI module, which is why the `frr_exporter` sidecars existed; they are gone.
- **The return-type generator mistypes a fragment on a generic.** `... on DcimInterface` becomes a
  literal `__typename: "DcimInterface"` that no node reports, so every endpoint parsed as the
  fieldless fallback and the link series came out empty with nothing raised. Use concrete kinds.

Four things the first rebuilds with it measured, each of which cost an afternoon:

- **Never `kubectl patch` a Helm-managed object, even to test a fix.** The patch takes
  field ownership (`kubectl-patch` in `managedFields`), and every later Helm upgrade then
  fails `conflict occurred while applying object ... conflict with "kubectl-patch"` --
  visible only in the Release's status. Recovery: drop that `managedFields` entry, delete
  the failed release secret so provider-helm retries, then restart the Deployment, because
  the failed upgrade already moved its config checksum.
- **With `policy_default_deny: false`, every `allow-*` flag must be off too.** The
  composition renders a CiliumNetworkPolicy per true flag, and any policy selecting a pod
  makes that direction deny-by-default for it -- Prometheus could reach nothing off its own
  node until all four were off.
- **fw1's TCP MSS is sized for the VXLAN fabric behind it**, `9214 - 50 - 20 - 20 = 9124`,
  not for its own interface. At 9138 every full-size segment died inside the fabric and
  Grafana's shell loaded while its JavaScript never arrived.
- **A k3s node is one CPU** (`cpu.max 100000 100000`), so a busy Grafana starves on it.
  The dashboards refresh each minute rather than every 30 seconds for that reason.

An audit of every panel after the SR Linux rebuild found two causes no dashboard
review could have caught, both now pinned by `tests/unit/test_dashboard_metrics_contract.py`:

- **Grafana 13 unregisters its own Prometheus plugin on a read-only root** while
  "preinstalling" an update to it, so every panel read "No data" with Prometheus full.
  `grafana.ini` `plugins.preinstall_disabled` is what stops it.
- **A generated release name leaves a second kubelet Service behind**, and every kubelet
  series is then scraped twice. The values pin `prometheusOperator.kubeletService.name`.
  A stale Service from an earlier name still needs deleting by hand, once.

That test also fails when a panel queries a metric nothing produces, derived by rendering
the collector's intent rather than from a list.

**The exporter reads as `metrics-exporter`, never `admin` or `agent`.** It is built from a pinned
upstream commit, because none is published, and runs on host port 8002, because 8001 is
`infrahub-mcp`. `invoke metrics-exporter` provisions the account and starts it, and the bootstrap
runs it after `mcp`.

### Services are monitored because they exist (cycle 035)

**OTTERNET / Services** shows every request from its branch to its health, and nobody adds
monitoring for a service. See the Services section of
[observability](./observability.md). Six things look like oversights:

- **A service profile selects by `service_kind`, not by group, and `device_groups` is optional.**
  A service is in a group only when a generator sits beneath its kind; the three WAN kinds are
  in none. `ServiceGeneric` means every kind. The renderer refuses a device profile with no
  group, a service profile with one, and a kind it does not know.
- **Live means not `decommissioning`/`decommissioned`**, as the withdrawal table says, so a
  revoke withdraws its monitoring in the same proposed change.
- **Monitoring is a FOURTH gate opening, and it opens only the third gate, only for the
  collector** (cycle 036). Cilium's `fromCIDR` never matches a pod, so no
  `allowed_source_prefixes` entry can admit Telegraf. Measured: its pod timed out against
  `otternet-demo` and Grafana while the host network answered. The FabricApp now carries
  `spec.monitoring` (`collectorNamespaces`, `ports`), and the composition renders it as
  `allow-collector`, a `fromEndpoints` rule on `io.kubernetes.pod.namespace`. It goes to the
  `allow-ingress` endpoints with no CIDR and no entities. Four things look like oversights:
  - **The ports are the POD's (`policy_allow_ports`), not `advertised_services`.** Cilium
    enforces after service translation, so Grafana's VIP port 80 arrives as 3000. No pod
    port declared means no admission, never every port.
  - **It renders only where the gate is already closed** (`defaultDeny`, or a non-empty
    `allowFrom`), in the transform AND in the composition's guard. On an open gate the
    collector is admitted already, and a policy selecting the pods would make their ingress
    deny-by-default for every other source.
  - **One function, `telemetry_services.py::collector_admission`, decides both artifacts.**
    The FabricApp is rendered from it, and the collector probes a gated application only
    where it admits the collector's own namespace.
    `tests/unit/test_probe_admission_contract.py` holds the two to each other. Removing
    `service-reachability` from a profile removes the probe and closes the path in one
    proposed change, with the FabricApps byte-identical to before the field existed.
  - **The XRD and composition must reach the cluster BEFORE Vidra delivers a FabricApp
    carrying the field.** They are the lab's, applied by `install-crossplane.sh` during
    `invoke cluster`, not delivered by Vidra.
- **The service-lifecycle exporter has no configuration.** `scripts/service_lifecycle_exporter.py`
  runs on host port 8003, as `metrics-exporter`, from the bind-mounted checkout (no
  `invoke build`). Telegraf scrapes it with `?kinds=` rendered from `services-lifecycle`, so
  which kinds it reports is an artifact diff. It is not the Infrahub exporter because a
  request lives on a branch nobody configured.
- **"Deployed" is fleet-wide**: every tracked device confirmed in sync since the service last
  changed. Only the generators know which devices a service touches.
- **`node_metadata.updated_at` disagrees between main and a branch for an untouched node**
  (measured), so a branch request is a status change or an edit dated after the branch cut.
  Comparing the two timestamps marks every service on a fresh branch as changed.
