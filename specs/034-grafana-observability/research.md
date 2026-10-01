# Research: Grafana Observability and Infrahub-Driven Monitoring

**Feature**: `034-grafana-observability` | **Date**: 2026-10-01

Each entry records what was **measured** (probed on the running lab or read in source) and
what is **inferred**. Inferences become verification tasks in `tasks.md`.

---

## Pinned external inputs

| Input | Pin | Where it is used |
| --- | --- | --- |
| kube-prometheus-stack chart | `90.0.0` (prometheus-community) | `otternet-metrics` |
| influxdata/telegraf chart | `1.8.77` (appVersion Telegraf `1.40.1`) | `otternet-telemetry` |
| frr_exporter | `tynany/frr_exporter:v1.12.0` | lab sidecars, one per FRR router |
| infrahub-exporter | `opsmill/infrahub-exporter@80974df` (2026-04-14) | compose service `infrahub-exporter` |
| Dex | `v2.44.0` (unchanged) | tooling cluster |

## R1. How observability reaches the cluster

**Decision**: Two seeded `ServiceFabricApp`s, each delivered by Vidra like `otternet-demo`:

- **`otternet-metrics`**: the kube-prometheus-stack chart, carrying Prometheus, Grafana and
  node-exporter. It is exposed, and its VIP block is seeded.
- **`otternet-telemetry`**: the `influxdata/telegraf` chart. It is not exposed.

**Rationale**: Since cycle 033, an application is a Helm chart, and the FabricApp XRD composes a
namespace, a Helm release, policy and an LB pool. Nothing else is needed. Splitting them gives
each its own namespace, policy and lifecycle. Telegraf is also the half whose configuration
Infrahub owns (R6).

**Measured**:

- The lab's `otternet-observability` already uses kube-prometheus-stack 90.0.0, with values that
  were solved for this lab: off the control-plane node, a 768Mi limit, and a long readiness
  probe.
- Upstream is at 91.8.2, with Grafana 13.2.3.

**Decision on version**: pin **90.0.0**, the version proven here, and record the upgrade as a
follow-up. The name `otternet-observability` is taken by the lab claim that the handover deletes,
so a new name is required (FR-061).

**Alternatives rejected**:

- A new application kind for observability: contradicts the cycle-033 position that an
  application is a chart.
- Telegraf inside the metrics namespace: it would share the metrics app's single ingress policy
  and lifecycle.

## R2. The CRD race with the lab's own kube-prometheus-stack

**Finding (inferred, high confidence)**: kube-prometheus-stack ≥ 69 ships its CRDs as a templated
subchart. Two Helm releases of it in one cluster contend for ownership of the same CRDs. The
second release fails with `invalid ownership metadata`.

**Measured**: Vidra goes up before Crossplane. Once the XRDs land, our claim and the lab
installer's `20-observability.yaml` are created in the same window.

**Decision**:

- Add an **opt-out to the lab installer**, an environment variable that skips the observability
  claim, and set it from `invoke cluster`.
- The handover still lists `otternet-observability` (defensive, and `test_handover_scope`
  stays honest).
- The metrics app sets `crds.enabled: true`, so it owns its CRDs.

**Alternative rejected**: `crds.enabled: false`, relying on the lab release's CRDs surviving its
teardown through `helm.sh/resource-policy: keep`. That works only while the lab keeps applying a
claim this repository is about to stop needing. It fails silently on any cluster where the lab
claim is absent.

## R3. Grafana sign-in through Dex

**Decision**: Grafana uses `auth.generic_oauth` against the single issuer. Every signed-in user
gets **Viewer**, and sign-in can never produce an Admin. See
[contracts/grafana-oidc.md](./contracts/grafana-oidc.md) for the keys.

**Measured / read**:

- **Values path.** Inside kube-prometheus-stack, the settings go under `grafana."grafana.ini"`.
  Literal secrets are refused by the chart (`assertNoLeakedSecrets`), so the client secret comes
  through `envValueFrom` as `GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET`. The admin credential comes
  through `admin.existingSecret`.
- **Role.** `role_attribute_path = 'Viewer'` with `role_attribute_strict = true` and
  `allow_assign_grafana_admin = false` gives everyone Viewer and forbids Admin.
- **Redirect URI.** It is `<root_url>login/generic_oauth`, so `root_url` must be the VIP and the
  VIP must be known when Dex is configured (R4).

**The back channel does not cross fw1 (measured)**:

- k3s nodes route `10.0.0.0/8` out of the fabric interface and everything else out of `eth0` on
  `172.20.41.0/24`, masqueraded. That is how Vidra already reaches Infrahub at
  `172.20.41.1:8000`.
- Dex's issuer `10.90.0.11` would cross the fabric to fw1, which has no `k8s-prod → tooling`
  rule. The tool node's management address `172.20.41.101:32556` is reachable over the
  management network and is already in its certificate SANs.

**Decision**: the browser-facing `auth_url` uses the issuer `http://10.90.0.11:32556/dex/auth`.
The server-to-server `token_url` and `api_url` use `http://172.20.41.101:32556/dex/...`.
Generic OAuth reads claims from the userinfo response and does not enforce the `iss` claim.
**Verify** this against Grafana 11.x as shipped by chart 90.0.0.

**Consequence for the spec**: FR-054 is narrowed. Neither the Dex back channel nor the Infrahub
API path crosses fw1, so there is no firewall intent to model. The spec is amended to say so.

**Alternative rejected**: a `k8s-prod → tooling` rule on fw1. It adds a thirteenth zone pair to a
pinned renderer and to the lab's `junos.conf`, to carry traffic that already has a working path.
It also pulls an identity-provider dependency through the firewall the demo is about.

## R4. Grafana's address, fixed before Dex is configured

**Decision**: seed the block `10.112.240.80/28` as an `IpamPrefix` inside the `vip_pool`, and pin
Grafana's LoadBalancer IP to `10.112.240.81` with the Cilium LB-IPAM annotation in the values.
`root_url` is `http://10.112.240.81/`, and the Dex redirect URI is
`http://10.112.240.81/login/generic_oauth`.

**Rationale**:

- `.0/28` belongs to `otternet-demo`. `.16`, `.32`, `.48` and `.64` have each been used by a
  portal allocation or a lab-owned application.
- A seeded `IpamPrefix` makes `OTTERNET-VIP-Pool` skip the block, which closes the collision
  class described in the lab's observability comments.
- A block the generator allocated would be unknown when `invoke tooling` runs, and would differ
  between rebuilds.

## R5. Organisation metrics: the Infrahub exporter

**Measured (source read at `opsmill/infrahub-exporter@80974df`, 2026-04-14)**:

- **No distribution.** There is no PyPI package, no public image and no tags. The Dockerfile is
  `development/Dockerfile`, and the entry point is `python -m infrahub_exporter.main -c <file>`.
- **Metrics.** One gauge per configured kind, `infrahub_<kind>_info`, with one series per node,
  always valued `1`. Labels are `id`, `hfid` and each `include` field; a relationship becomes the
  peer's HFID. Counts come from `count by (...)` in PromQL.
- **Auth and transport.** It sends `X-INFRAHUB-KEY`. TLS verification is always on, which is
  irrelevant over HTTP. The default port is 8001, which collides with `infrahub-mcp`.
- **Service discovery.** It ignores `branch` and needs a bare IP. `IpamIPAddress` here exposes
  only a CIDR value.

**Decision**:

- **Build.** A compose service `infrahub-exporter` built from the pinned commit through a git
  build context, on port **8002**, started by bootstrap after `mcp`.
- **Account.** It reads as a dedicated `metrics-exporter` account with a view-only role. The
  provisioning script mirrors `provision_mcp_agent.py`, and the token is kept in `.env`.
- **Kinds.** `DcimGenericDevice`, `ServiceGeneric`, `OrganizationTenant`, `CoreProposedChange`
  and `DeploymentState`. The labels are in [contracts/exporter.md](./contracts/exporter.md).
- **Scraping.** Prometheus scrapes it at `172.20.41.1:8002` through `additionalScrapeConfigs`
  in the metrics app's values.

**Service discovery is not used** (R6). It cannot express *what* to collect, and Telegraf, the
collector that needs targets, cannot consume `http_sd`.

**Alternatives rejected**:

- Running the exporter in the cluster as a third FabricApp: there is no chart and no image, so we
  would publish both.
- Writing our own exporter: the upstream one covers organisation metrics fully.

## R6. Infrahub drives monitoring: collector configuration as an artifact

**Decision**:

- Infrahub renders **one Kubernetes ConfigMap per collector** as an `application/yaml` artifact
  (`Telemetry Collector Configuration`).
- The ConfigMap carries `telegraf.conf`, with every input, target, subscription and filter, and
  `intended.prom`, the intended-state series (R9).
- A third `InfrahubSync` delivers it into the `otternet-telemetry` namespace.
- Telegraf mounts it and runs `--config /etc/telegraf-intent/telegraf.conf --watch-config poll`.

**Rationale**:

- **Reviewable.** Targets *and* instructions are rendered from the graph, so a change to what is
  monitored, or a device joining a group, appears as an artifact diff in the proposed change.
  That is a stronger property than live SD, which changes unreviewed.
- **Proven path.** Vidra's role can create any kind (measured: `*/*`), and the artifact →
  sync → apply path is the one already proven for FabricApps.

**Why not Telegraf pulling the artifact over HTTP (read)**: Telegraf's remote config sends only
`Authorization: Bearer|Token <env>`. Infrahub's API token header is `X-INFRAHUB-KEY`. The pull
would also need `Last-Modified` for its watch interval.

**Freshness (inferred risk)**: an artifact regenerates when its *target* changes, and the target
is the collector. A device joining a group, or a profile edit, would leave it stale. This is the
same trap `generate-app-access` hit with `fw1`.

**Decision**: a small generator, `generate-monitoring-collector`, targets the
`monitoring_collectors` group with `execute_in_proposed_change: true` and
`execute_after_merge: true`.

- It **writes nothing** to the graph. It only requests regeneration of its collector's artifact
  on its own branch, through `POST /api/artifact/generate/{id}?branch=`, the same call as
  `_rerender_firewall`.
- It is triggered by the pipeline, never by an event on a monitoring kind (FR-059b).
- Idempotence is trivial and still tested: a second run requests the same render and changes no
  node.

**Verify**: a device added on a branch makes the proposed change show a collector-artifact diff.

**Unverified**: whether Vidra splits multi-document YAML, and whether `metadata.namespace`
overrides the sync's destination namespace. The artifact is therefore a **single document**, and
the sync's destination namespace is set explicitly.

## R7. Device families: how each one is reached and what it needs

All addresses below are on `otternet-mgmt` (`172.20.41.0/24`). Pods reach it through the
node's `eth0` masquerade rule (`lab/k8s/bootstrap/k3s-entrypoint.sh:102-107`). This was
measured: Vidra's pod reaches `.1:8000` this way.

| Family | Address | Collection | Device-side change | Measured state today |
| --- | --- | --- | --- | --- |
| EOS (7) | `mgmt_ip` .11–.25 | Telegraf `inputs.gnmi`, port 6030, VRF MGMT | `management_api_gnmi` | **off**: provisioning's `rollback clean-config` removed the boot-time gNMI. 6030 is refused, but the default CP-ACL permits it |
| FRR (6) | .61–.91 | Telegraf `inputs.prometheus` → `frr_exporter` :9342 | none in `frr.conf` | the FRR 10.2.1 image has no SNMP module. Daemon sockets are local only |
| Junos fw1 | .31 (vrnetlab forwards udp/161) | Telegraf `inputs.snmp` v2c | top-level `snmp {}` | neither SNMP nor JTI configured |
| k3s nodes (3) | .41–.43 | Telegraf `inputs.prometheus` → node-exporter :9100 (hostNetwork) | none | Ready. node-exporter ships with kube-prometheus-stack |

Per-family decisions:

- **EOS**:
  - **Enabling it.** gNMI is device capability, not monitoring choice. It is added to the
    fabric's `avd_custom_hostvars` (`objects/23_otternet_fabric.yml`) as
    `custom_structured_configuration_management_api_gnmi`: transport `grpc default`, VRF `MGMT`,
    provider `eos-native`. pyavd 6.4.0 renders this (measured), and `eos_designs` has no
    first-class key.
  - **What it changes.** Every switch artifact gains five lines, so the EOS golden files move.
    They derive from the lab's `group_vars`, so the lab repository changes with them
    (`scripts/regenerate_otternet_golden.py`).
  - **Credentials.** gNMI authenticates against local AAA. Telegraf uses the existing local user,
    with its password injected from a Secret.
- **FRR**:
  - **The exporter.** The lab topology gains one `frr_exporter` v1.12.0 sidecar per router. Each
    sidecar shares the router's network namespace (`network-mode: container:<router>`) and binds
    the router's `/var/run/frr`. The topology is lab-owned, like the rest of the topology.
  - **What Infrahub decides.** Which routers are collected, which exporter families Telegraf
    keeps (`namepass`), and at what interval.
  - **Rejected.** BMP: no Telegraf input and a heavy collector. SNMP: needs a different FRR build
    plus snmpd. `vtysh` exec: has to run inside each container.
- **Junos**:
  - **The stanza.** `junos_config` renders a top-level `snmp` stanza: a read-only community,
    `clients`, and `routing-instance-access`, because fxp0 sits in `mgmt_junos` under
    `management-instance`.
  - **Push path.** `_junos_replace_tagged` tags every top-level stanza the artifact emits, so
    removing it from the model removes it from the device.
  - **Rejected.** gNMI/JTI: it lives under `system services extension-service`, and
    `_assert_junos_scope` deliberately refuses `system`.
  - **Verify.** The source address vrnetlab's NAT presents, which decides `clients`, and the
    exact `routing-instance` form, against the running vSRX.
- **k3s nodes**:
  - **Reached directly.** node-exporter listens on the host network, so Telegraf reaches it on
    the management address.
  - **Avoiding a double collection.** kube-prometheus-stack's own node-exporter ServiceMonitor is
    disabled, so Infrahub decides whether nodes are collected.
  - **A caveat to state.** The nodes are containers on a shared kernel, so host-level series
    describe the host. The dashboard says so.

## R8. Giving every device kind a management address

**Measured**: only `DcimFabricSwitch` has `mgmt_ip` (a relationship to `IpamIPAddress`). The FRR
routers and the firewall are reached by container name, and the k3s nodes have no management
address modelled. A pod cannot resolve container names.

**Decision**: add a relationship to `IpamIPAddress`, named **`telemetry_address`**, to `DcimDevice`, `SecurityFirewall` and
`ComputePhysicalServer` through schema extensions. Seed `IpamIPAddress` objects for
`172.20.41.31`, `.41–.43` and `.61–.91` in the management prefix.

**Risk**: `src/solution_arista_avd/deployment/inventory.py` and `devices.py` choose addresses per
family. A newly populated `telemetry_address` on FRR or Junos must not change how they are reached.

**Changed at implementation**: the plan said `mgmt_ip`. That name means "push over eAPI" to the
reconciler (`devices.py`: `reach = target.mgmt_ip or target.container`), and cycle 027's
`test_dcim_schema_contract.py` holds it on switches alone, so the new field has its own name.
**Verify** by reading `Target` construction, and pin it with a unit test.

## R9. Intended state alongside observed state

**Decision**: the collector artifact's `intended.prom` carries gauges that Telegraf reads through
`inputs.file` with `data_format = "prometheus"`:

- `otternet_intended_bgp_neighbor{device,peer_address,vrf} 1`, from each EOS switch's stored
  structured config (`router_bgp.neighbors` and neighbor groups), and from the FRR routers'
  rendered neighbor set.
- `otternet_intended_link{device,interface,peer_device,peer_interface} 1`, from cabled
  `DcimInterface` pairs.
- `otternet_intended_interface_enabled{device,interface}`.

Dashboards join them to observed series on `device` and the address or interface, giving
"intended but down" and "up but unintended". Metric names and labels are a contract:
[contracts/telemetry-collector-artifact.md](./contracts/telemetry-collector-artifact.md).

**Rationale**: the exporter produces only info series per node, and BGP sessions are not graph
nodes here. The stored structured config is what the device actually renders from.

## R10. Monitoring intent schema

**Decision**: a new `Monitoring` namespace with three kinds. See
[data-model.md](./data-model.md).

- **`MonitoringCollector`**: one collector instance and its artifact target.
- **`MonitoringProfile`**: which devices, which measurements, and how often.
- **`MonitoringMeasurement`**: a seeded catalogue of the measurements the renderer knows how to
  render per family.

**Rationale**:

- **Multi-select.** Measurements must be multi-select. A Dropdown is single-valued, and a `List`
  attribute makes `/api/schema/json_schema/{kind}` return 500 on 1.10.6 (see AGENTS.md).
  Relationships to catalogue nodes are multi-valued and portal-safe.
- **Scoping.** Profiles scope by `CoreStandardGroup`, peering the group so that all four device
  kinds are reachable, plus an optional role match. A new group, `kubernetes_nodes`, is seeded
  for the k3s nodes. The other three families already have groups (`avd_devices`,
  `frr_routers`, `junos_firewalls`).
- **The family/measurement table.** "Which measurement applies to which family, and how it is
  rendered" lives in code, keyed by measurement name, and is unit-tested so that every seeded
  measurement has at least one family. A measurement that does not apply to a matched device is
  skipped and listed in a comment in the rendered config (FR-014).

**Alternatives rejected**:

- Attributes on each device: this spreads monitoring intent across four kinds, and it can't
  express "the leaves".
- A JSON blob on the profile: unreviewable, and the portal can't build a form for it.

## R11. Credentials

**Decision**: these values are injected from Secrets that `invoke cluster` creates once Vidra has
created the target namespace. A pod waits in `CreateContainerConfigError` until then, which heals
by itself.

- Dex client secret
- Grafana admin password
- gNMI password
- Exporter token

None of them is a schema attribute, a seed value or artifact content. The Dex client secret
follows the lab's existing literal-default pattern (`INFRAHUB_OIDC_PROVIDER1_CLIENT_SECRET`), with
an environment override.

**The one deviation**: the SNMPv2c community must appear in plain text in the Junos
configuration the device receives, so it is in the `junos_config` artifact. It is
modelled as a read-only, client-restricted community and is treated as configuration, not as a
credential. This is recorded in the plan's Complexity Tracking. SNMPv3 does not avoid it, because
its keys also live in configuration.

## R12. Pod policy for the two applications

**Measured**: the composition's `defaultDeny` covers egress as well as ingress.
`allowEgressToInternet` excludes `10.0.0.0/8`. There is one ingress policy per application.

**Decision**:

- **`otternet-metrics`**: `policy_default_deny: false`. Prometheus scrapes kubelets, the API
  server, the cluster's own endpoints and Telegraf, which a single selector-scoped ingress policy
  cannot express.
  - **The branch gate is not the pod policy.** It is the firewall rule plus the advertisement,
    and both are opened only by the grant. This is explicit, reviewed intent on the seeded
    object.
  - **Grants still add their source.** `ServiceAppAccess` adds its source to
    `allowed_source_prefixes` as usual. That is harmless when nothing is denied.
- **`otternet-telemetry`**: `policy_default_deny: true`, allowing DNS and egress to the internet,
  which covers the management network at `172.20.41.0/24`. Ingress from the metrics namespace
  goes to port 9273 only.

## R13. Bootstrap and verification

**Order**: `start → load → avd → lab → reconcile → backstage_build → tooling → mcp →
metrics-exporter → cluster → reconciler loop`.

**Steps inside `invoke cluster`**:

1. Set the lab installer's opt-out.
2. Wait for the `otternet-metrics` and `otternet-telemetry` namespaces.
3. Create the Secrets.
4. Wait for the Grafana Deployment to become Available and Telegraf to become Ready.

**Changes to `verify_bootstrap.sh`**:

- The FabricApp count becomes `3`, and the composed-namespace count becomes `3`.
- New assertions:
  - **Grafana answers**: from the branch desktop, the VIP refuses before any grant. That proves
    the gate.
  - **A Dex sign-in completes.** It is driven by the same password-grant / form flow
    `provision_portal_accounts.py` uses.
  - **The organisation dashboard has data**: a Prometheus query of `infrahub_dcimgenericdevice_info`
    returns 17 series.
  - **Telemetry**: `count by (family)` of an up-style series from Telegraf equals the modelled
    count for each family (7, 6, 1 and 3).
- Every new assertion has a deliberate-break demonstration in the quickstart.

## R14. The lab repository's share of the change

Lab-repo changes are separate commits in `../lab`:

- the installer opt-out
- six `frr_exporter` sidecars
- `junos.conf` gaining the `snmp` stanza (byte-for-byte pin)
- the EOS `group_vars` gaining `management_api_gnmi` (golden files)
- the branch desktop's Grafana bookmark moved to `http://10.112.240.81/`

`test_handover_scope.py` continues to parse the installer, and the opt-out must keep its parse
honest.
