---
description: "Task list for 034-grafana-observability"
---

# Tasks: Grafana Observability, Requested Like Any Other Application

**Input**: Design documents from `specs/034-grafana-observability/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: REQUIRED. Constitution IV, plus spec FR-056 and SC-001 to SC-010. Test tasks precede
the implementation they cover, and are expected to fail first.

**Organization**: phases follow the spec's user stories. P1 stories come first (US1, US2, US3,
then US6), followed by the P2 stories (US4, US5).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 to US6, as numbered in spec.md
- Paths are repository-relative to `infrahub/` unless prefixed `../lab/`, the sibling lab
  repository. **Lab-repo tasks are committed in `../lab`, separately.**

## Conventions every task follows

- **Skills.** Load `infrahub-managing-schemas`, `-objects`, `-transforms` or `-generators` before
  touching that artifact type.
- **Generated files.** Regenerate them, never hand-edit: `src/solution_arista_avd/protocols.py`
  and `*_query.py` (`uv run infrahubctl graphql generate-return-types <file>.gql`).
- **Extension fields** such as `telemetry_address` on non-switch kinds, `snmp_*` and `sso_provider` are
  **not** in protocols (AGENTS.md). Read them through `*_query.py` models only.
- **Gates.** Never pipe `invoke lint*` or `pytest` into `tail` or `head` when the exit status is
  a gate.
- **Branches.** Do live work on a branch (`--branch 034-…`). Never run `invoke avd --topology`
  against the built fabric.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: scaffolding and pinned external inputs that every later phase references.

- [X] T001 Create directory `metrics/` with a README stub at `metrics/README.md` stating that it holds the Infrahub exporter's configuration (token never committed), mirroring `vidra/`
- [X] T002 [P] Record pinned external versions in `specs/034-grafana-observability/research.md` §R1/R5/R7 as a table: kube-prometheus-stack `90.0.0`, `influxdata/telegraf` chart (pick the latest 1.8.x whose appVersion is ≥ 1.33, and record it), `tynany/frr_exporter:v1.12.0`, infrahub-exporter commit `80974df`
- [X] T003 [P] Add `.env.example` entries (no values) for `INFRAHUB_EXPORTER_TOKEN`, `GRAFANA_DEX_CLIENT_SECRET`, `GRAFANA_ADMIN_PASSWORD`, `TELEMETRY_GNMI_USERNAME`, `TELEMETRY_GNMI_PASSWORD` in `.env.example`. *Done differently: the repository has no `.env.example` convention (`.env` is written by the provisioning scripts), so the variables are documented in `docs/docs/developer-guide/observability.md` (T086).*

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: all schema changes, loaded once and regenerated once (Constitution I). Every story
depends on this phase.

**⚠️ CRITICAL**: no story work can begin until T014 passes.

### Tests for the foundation

- [X] T004 [P] Write `tests/unit/test_monitoring_schema_contract.py`. It loads `schemas/monitoring.yml` and asserts:
  - the three kinds exist in namespace `Monitoring`
  - each has HFID `["name__value"]` and uniqueness `[["name__value"]]`
  - `MonitoringProfile.device_groups` and `.measurements` are cardinality many with `min_count: 1` and not optional
  - `device_groups` peers `CoreStandardGroup`
  - `MonitoringCollector` inherits `CoreArtifactTarget`
  - `interval_seconds` has min 10 and max 3600
  - the identifiers match on both sides of `collector`↔`profiles`
- [X] T005 [P] Extend `tests/unit/test_deployment_schema_contract.py` so that no event rule in `triggers.yml` names a `Monitoring*` kind as its source (FR-059b)
- [X] T006 [P] Write `tests/unit/test_observability_schema_extensions.py`. It asserts:
  - `telemetry_address` (never `mgmt_ip`; peer `IpamIPAddress`, cardinality one, optional) exists on `DcimDevice`, `SecurityFirewall` and `ComputePhysicalServer`, each with a distinct identifier
  - `SecurityFirewall.snmp_community` is optional Text
  - `SecurityFirewall.snmp_clients` peers `IpamPrefix`, cardinality one
  - `ServiceFabricApp.sso_provider` is a Dropdown `none|dex` defaulting to `none`

### Implementation

- [X] T007 Create `schemas/monitoring.yml` with `MonitoringCollector`, `MonitoringProfile` and `MonitoringMeasurement`, exactly as in `data-model.md` (fields, defaults, identifiers, order_weights 1000+ for identifiers, icons `mdi:chart-line` / `mdi:tune` / `mdi:gauge`)
- [X] T008 [P] Add the `telemetry_address` relationship to `DcimDevice` (identifier `dcim_device__telemetry_address`) in `schemas/dcim_extensions.yml`
- [X] T009 [P] Add `telemetry_address` (identifier `security_firewall__telemetry_address`), `snmp_community` and `snmp_clients` (identifier `security_firewall__snmp_clients`) to `SecurityFirewall` in `schemas/security_extensions.yml`
- [X] T010 [P] Add `telemetry_address` (identifier `compute_server__telemetry_address`) to `ComputePhysicalServer` through an `extensions:` block in the compute schema extension file. Create `schemas/compute_extensions.yml` if none exists, and register it in the same load path as the other extension files
- [X] T011 [P] Add the `sso_provider` Dropdown (`none`, `dex`; default `none`; optional false) to `ServiceFabricApp` in `schemas/service/kubernetes_services.yml`, with a comment in house style saying the renderer never infers it from the chart name
- [X] T012 Run `uv run infrahubctl schema check schemas/` and fix every error (no output piped)
- [X] T013 Load on a branch: `uv run infrahubctl branch create 034-observability` and `uv run infrahubctl schema load schemas --branch 034-observability`. Confirm that every existing object loads with no constraint violation (FR-013)
- [X] T014 Regenerate `src/solution_arista_avd/protocols.py` (`uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`) and `schema.graphql` (`uv run infrahubctl graphql export-schema --destination schema.graphql`). Run T004–T006 and confirm they pass

**Checkpoint**: the schema is loaded on a branch and the contract tests are green.

---

## Phase 3: User Story 1 — Observability is an Infrahub-owned application (P1) 🎯 MVP

**Goal**: `otternet-metrics` (kube-prometheus-stack) and `otternet-telemetry` (Telegraf) are seeded
`ServiceFabricApp`s delivered by Vidra, Grafana has a VIP block recorded in Infrahub, and the lab's
own observability stack never runs alongside them.

**Independent Test**: on a branch, both applications render a `Crossplane FabricApp` artifact
naming a chart, a version, values and (for metrics) `10.112.240.80/28`. After merge and
`invoke cluster`, both are `Ready`, there is exactly one Grafana, and the pool never allocates
from `.80/28`.

### Tests for User Story 1

- [X] T015 [P] [US1] Extend `tests/unit/test_fabric_app_chart_seed_data.py` so that `otternet-metrics` and `otternet-telemetry` exist in `objects/36_otternet_app_services.yml`, each with chart repository, name and version, and a values payload in `payloads/`. `otternet-metrics` must be `exposed: true`, `vip_block` `10.112.240.80/28`, `advertised_services: [junos-http]` and `policy_default_deny: false`. `otternet-telemetry` must be `exposed: false` and `policy_default_deny: true`, with DNS and internet egress allowed
- [X] T016 [P] [US1] Add a test in `tests/unit/test_fabric_app_chart_seed_data.py` that `10.112.240.80/28` is seeded as an `IpamPrefix` inside the `vip_pool` prefix and overlaps no other seeded block
- [X] T017 [P] [US1] Update `tests/unit/test_handover_scope.py` for the lab installer's new opt-out, so that it parses the opt-out guard and still asserts `HANDOVER_DELETIONS` equals the installer's applied claims when the opt-out is **unset**

### Implementation for User Story 1

- [X] T018 [US1] Seed `IpamPrefix` `10.112.240.80/28`, with the same role and attributes as the `.0/28` entry, in `objects/29_otternet_offfabric_prefixes.yml`
- [X] T019 [US1] Create `payloads/otternet-metrics-values.yaml` for kube-prometheus-stack 90.0.0. Port the lab's solved values from `../lab/crossplane/apps/20-observability.yaml`: node placement off the control plane, Grafana memory limit 768Mi, a long readiness probe, Cilium/Hubble scrape jobs, and `externalTrafficPolicy: Local`. Then:
  - give the Grafana Service type LoadBalancer with label `otternet.lab/advertise: "true"` and annotation `lbipam.cilium.io/ips: 10.112.240.81`
  - set `crds.enabled: true`
  - set `prometheus-node-exporter.prometheus.monitor.enabled: false` (R7)
  - add `additionalScrapeConfigs` for `infrahub-exporter` (`172.20.41.1:8002`) and `telemetry` (`telegraf.otternet-telemetry.svc:9273`) per `contracts/exporter.md`
  - include no secrets
- [X] T020 [P] [US1] Create `payloads/otternet-telemetry-values.yaml` for the influxdata/telegraf chart:
  - `args: ["--config","/etc/telegraf-intent/telegraf.conf","--watch-config","poll"]`
  - mount ConfigMap `telegraf-intent` at `/etc/telegraf-intent` through `volumes` and `mountPoints`
  - `envFromSecret: telemetry-credentials`
  - Service port 9273
  - chart default config disabled or minimal
  - no secrets
- [X] T021 [US1] Seed `otternet-metrics` and `otternet-telemetry` in `objects/36_otternet_app_services.yml` per `data-model.md`. Both are `status: active`, cluster `otternet`, VRF `K8S_PROD`, owner as for `otternet-demo`, and members of `service_fabric_apps`. `otternet-metrics` gets `sso_provider: none` for now; US2 switches it. Add a comment in house style explaining R2 (the name differs from the lab's `otternet-observability`) and R12 (why `policy_default_deny: false`)
- [X] T022 [US1] Register both payloads in `scripts/seed_app_payloads.py` (the payload list near line 49) so that `invoke load` attaches them as `ServiceFabricAppValuesFile`
- [X] T023 [P] [US1] Lab repo: add an opt-out environment variable (for example `OTTERNET_SKIP_OBSERVABILITY=1`) that skips applying `crossplane/apps/20-observability.yaml` in `../lab/k8s/bootstrap/install-crossplane.sh` (or wherever the installer applies it). Keep the `kubectl apply` line greppable for `test_handover_scope.py`
- [X] T024 [US1] Set the opt-out when `invoke cluster` runs the lab installer in `tasks.py` (the `_cluster_task` call to `install-crossplane.sh`). Keep `otternet-observability` in `LAB_ONLY_APPS` and `HANDOVER_DELETIONS` as a defensive delete, with a comment
- [X] T025 [US1] Run `uv run invoke load` on the branch (or the equivalent object load plus `scripts/seed_app_payloads.py`). Render both artifacts with `uv run infrahubctl transform crossplane_fabric_app name=otternet-metrics --branch 034-observability` and the same for `otternet-telemetry`, and confirm both render. Run T015–T017 and confirm they pass

**Checkpoint**: both applications render. The cluster run is validated in US6.

---

## Phase 4: User Story 2 — Grafana signs in through Dex (P1)

**Goal**: Grafana authenticates against the one issuer. Every user lands as Viewer, nobody becomes
Admin through sign-in, the password form is off, and no secret is in the graph or an artifact.

**Independent Test**: from the branch desktop with a grant in place, or by port-forward from the
host, `http://10.112.240.81/` redirects to Dex. After login as alice, `/api/user` shows
`alice@otternet.lab` and the org role is `Viewer`. See `contracts/grafana-oidc.md` §Observable
behaviour.

### Tests for User Story 2

- [X] T026 [P] [US2] In `tests/unit/test_crossplane_fabric_app.py`, add three tests:
  - `sso_provider: dex` on `otternet-metrics` merges exactly the `grafana:` block in `contracts/grafana-oidc.md`, and `root_url` is derived from the pinned LB address `10.112.240.81`
  - `sso_provider: none` renders byte-identical to the pre-change output for `otternet-demo`
  - `dex` on a chart with no renderer (for example `whoami`) raises a clear error
- [X] T027 [P] [US2] Write `tests/unit/test_no_credentials_rendered.py`. It renders every application artifact and the collector artifact (after US5) from fixtures, then greps for the Dex client secret default, `GRAFANA_ADMIN_PASSWORD` and gNMI password values. It asserts none appears (SC-007), and that the only SNMP community present is in `junos_config` output (the recorded exception)

### Implementation for User Story 2

- [X] T028 [US2] Add `sso_provider { value }` and the values needed to derive the VIP (the pinned LB IP read from the values payload, or `vip_block`) to `transforms/crossplane_fabric_app.gql`, then regenerate `transforms/crossplane_fabric_app_query.py`
- [X] T029 [US2] Implement the merge in `transforms/crossplane_fabric_app.py`:
  - a function `build_sso(app, values) -> dict` holding the renderer constants (issuer `http://10.90.0.11:32556/dex`, back channel `http://172.20.41.101:32556/dex`, client id `grafana`)
  - deep-merge it over the chart values, so that intent overrides tuning
  - raise for `dex` on an unknown chart
  - keep `_payload` and `_dump` behaviour unchanged for `none`
  - keep the function under C901 17
- [X] T030 [P] [US2] Add the static client `grafana` (secret from `GRAFANA_DEX_CLIENT_SECRET`, default literal `grafana-dex-secret`, redirect `http://10.112.240.81/login/generic_oauth`) to `tooling/10-dex.yaml`, following how the `infrahub` client's secret is templated or substituted by `scripts/deploy_tooling.sh`
- [X] T031 [US2] In `tasks.py` `_cluster_task`, after Vidra's first delivery, wait for namespace `otternet-metrics`, then create or update Secrets `grafana-oidc` (`client-secret`) and `grafana-admin` (`admin-user`=`admin`, `admin-password` from `.env` `GRAFANA_ADMIN_PASSWORD`, generated once with `secrets.token_urlsafe` and persisted to `.env` if absent). Make it idempotent (`kubectl apply` of a rendered Secret, never `create`). Add a comment explaining that the pod waits in `CreateContainerConfigError` until then, which heals by itself
- [X] T032 [US2] Switch `otternet-metrics` to `sso_provider: dex` in `objects/36_otternet_app_services.yml`
- [ ] T033 [US2] **Verify R3** live on the branch's rendered values. Deploy, then confirm that Grafana (the version chart 90.0.0 ships) completes the token exchange via `172.20.41.101` while the browser used `10.90.0.11`, so the `iss` mismatch is tolerated. If it is not, record the failure in `research.md` R3 and switch to the documented fallback before continuing. The fallback is a fw1 `k8s-prod → tooling` rule on `tooling-oidc`, which moves the `junos.conf` pin and the zone-pair count in `tests/unit/test_junos_config.py`
- [X] T034 [US2] Run T026–T027 and confirm they pass, then `uv run invoke lint-mypy` and `uv run invoke lint-ruff`

**Checkpoint**: Grafana signs in through Dex as Viewer, and no secret is in any artifact.

---

## Phase 5: User Story 3 — Alice gets Grafana by asking for it (P1)

**Goal**: an ordinary `ServiceAppAccess` from site `branch` to `otternet-metrics` opens the
firewall rule and the advertisement for Grafana's VIP. Nothing is seeded, and revoking the grant
closes it again.

**Independent Test**: quickstart §3. Before the request the VIP does not answer from the branch
desktop. After merge and convergence alice reaches it and signs in. After setting
`decommissioning` it stops answering.

### Tests for User Story 3

- [X] T035 [P] [US3] In `tests/unit/test_generate_app_access.py` (or its existing equivalent), add a case where a grant on an application with `policy_default_deny: false` still derives a rule `branch → k8s-prod` on `junos-http` with destination `10.112.240.81`. It must still record `granted_source_prefixes` and still withdraw correctly
- [X] T036 [P] [US3] Confirm that `test_no_grant_is_seeded` still passes with the new objects (FR-058); no change is expected, so run it

### Implementation for User Story 3

- [X] T037 [US3] Confirm, by reading `generators/generate_app_access.py` (`derive_advertisement` around line 194, the destination-zone derivation around 602), that nothing assumes `policy_default_deny: true` or a `/28` at `.0`. Fix any assumption, with a test in T035
- [X] T038 [US3] Confirm that the curated portal item `backstage/catalog/exposed-app-with-access.yaml` is not needed for this flow (the app already exists) and that the generated `ServiceAppAccess` template lists `otternet-metrics` as an application. If the picker filters by owner or status, adjust the seed data, not the template
- [X] T039 [P] [US3] Lab repo: move the branch desktop bookmark "Grafana (needs access)" to `http://10.112.240.81/` in `../lab/configs/branch/desktop/firefox-policies.json`
- [ ] T040 [US3] Live on a scratch branch: create a `ServiceAppAccess` (requester alice, application `otternet-metrics`, `source_site` branch), open a proposed change and confirm it shows:
  - the rule and the address-book entry
  - `PL-DC-ADVERTISED-BRANCH` on the border leaf
  - the re-rendered Junos and EOS artifacts

  Do not merge on `main` outside the demo rehearsal. Delete the scratch branch afterwards

**Checkpoint**: the request path works unchanged for Grafana.

---

## Phase 6: User Story 6 — Bootstrap delivers it working, and verification proves it (P1)

**Goal**: `invoke bootstrap --fresh` ends with Grafana up and able to sign people in, with the
exporter feeding it. `verify_bootstrap.sh` asserts state rather than exit status, and every new
assertion is shown failing when broken.

**Independent Test**: `scripts/verify_bootstrap.sh` passes from a destroyed environment, and each
row of quickstart §2's table fails when its break is applied.

### Organisation metrics: the exporter (needed by US6's assertions and US4's dashboards)

- [X] T041 [P] [US6] Write `tests/unit/test_metrics_exporter_contract.py`. It asserts:
  - `metrics/exporter.yml` lists exactly the kinds and includes in `contracts/exporter.md`
  - `listen_port` is 8001 in the container
  - service discovery is disabled
  - no `token` value is committed
  - the `infrahub-exporter` compose service publishes host `8002`, builds from commit `80974df`, and is not on `agent`'s or `admin`'s token
- [X] T042 [P] [US6] Create `metrics/exporter.yml` per `contracts/exporter.md`, with the token supplied through `INFRAHUB_SIDECAR_INFRAHUB__TOKEN` or the exporter's env mechanism. Verify the exact env variable name in the exporter's `config.py` in the scratchpad clone, and **verify** the `DeploymentState` field names against `schemas/deployment.yml`
- [X] T043 [US6] Add service `infrahub-exporter` to `docker-compose.override.yml`:
  - build context `https://github.com/opsmill/infrahub-exporter.git#80974df`, dockerfile `development/Dockerfile`
  - command `python -m infrahub_exporter.main -c /config/exporter.yml`
  - mount `./metrics:/config:ro`
  - port `8002:8001`
  - token from `.env`
  - `depends_on: infrahub-server`
  - a profile `metrics`, so `invoke stop` and `invoke destroy` already cover it (`--profile '*'`)
- [X] T044 [P] [US6] Create `scripts/provision_metrics_exporter.py`, modelled on `scripts/provision_mcp_agent.py`. It must, idempotently:
  - create account `metrics-exporter`
  - create a group or role with object `view` permission only (no `edit_default_branch`, no global permissions)
  - mint an API token and write it to `.env` as `INFRAHUB_EXPORTER_TOKEN`
  - leave a token that already exists and still works unchanged
- [X] T045 [US6] Add `invoke metrics-exporter` to `tasks.py`. It runs the provisioning script, then `docker compose --profile metrics up -d --build infrahub-exporter` through `compose_root()`, then waits for `GET http://127.0.0.1:8002/metrics` to contain `infrahub_dcimgenericdevice_info`
- [X] T046 [P] [US6] Add a test pinning `metrics-exporter`'s permissions (view-only, never `Super Administrator`) in `tests/unit/test_metrics_exporter_contract.py`, mirroring `tests/unit/test_mcp_service_contract.py`

### Bootstrap order and verification

- [X] T047 [US6] In `tasks.py` `bootstrap`, insert `metrics-exporter` after `mcp` and before `_cluster_task`, and update the order comment and the docstring
- [X] T048 [US6] In `tasks.py` `_cluster_task`, after the handover:
  - wait for FabricApps `otternet-metrics` and `otternet-telemetry` to be `Ready`
  - wait for Deployment `otternet-metrics/*grafana*` Available and Telegraf Ready
  - wait for the resources themselves, not `syncState` (AGENTS.md)
- [X] T049 [US6] Update `scripts/verify_bootstrap.sh`, "kubernetes" stage (around lines 141–172):
  - FabricApp count `"1"` becomes `"3"`
  - composed Namespace count 1 becomes 3
  - wait for `otternet-metrics` and `otternet-telemetry` Ready beside `otternet-demo`
  - keep the `otternet-access` / `otternet-observability` absence checks
  - update the comment that says "exact" to match the `-ge` route check
- [X] T050 [US6] Add stage "observability" to `scripts/verify_bootstrap.sh`, with assertions:
  - (a) from the branch desktop container, `curl -m5 http://10.112.240.81/` **fails** (no grant: the gate holds)
  - (b) from the host, through `kubectl port-forward` to the Grafana Service, an unauthenticated GET redirects to `http://10.90.0.11:32556/dex/auth` with `client_id=grafana`
  - (c) a scripted Dex login as alice completes, reusing the form flow in `scripts/provision_portal_accounts.py`, and `/api/user/orgs` reports `Viewer`
  - (d) a Prometheus query through port-forward for `count(infrahub_dcimgenericdevice_info)` returns `17`
- [ ] T051 [US6] Run `scripts/verify_bootstrap.sh` from destroyed (about 20 min) and record the pass. For each row in quickstart §2, apply the break on a scratch checkout and show the assertion failing. Record the evidence in the PR description, not in committed files

**Checkpoint**: from nothing, one command brings up a Grafana that refuses the branch until a
grant exists, signs alice in through Dex, and has data.

---

## Phase 7: User Story 4 — Dashboards about the lab and the organisation (P2)

**Goal**: dashboards are provisioned as code: organisation intent, cluster health, and fabric
deployment state.

**Independent Test**: after bootstrap, every panel on the organisation dashboard has data. A
merged service object moves the count within 2 minutes (SC-005).

- [X] T052 [P] [US4] Create `payloads/dashboards/organisation.json`. Panels:
  - devices by kind (`count by (kind)` via `label_replace` on `hfid`)
  - services by status (`infrahub_servicegeneric_info`)
  - tenants
  - proposed changes by state
  - a "data age" panel on `up{job="infrahub-exporter"}`

  Datasource is the chart's default Prometheus. Use stable `uid`s
- [X] T053 [P] [US4] Create `payloads/dashboards/fabric-state.json`: deployment state per device (`infrahub_deploymentstate_info`), drifting devices, and Cilium/Hubble flow summaries from the existing scrape jobs
- [X] T054 [US4] Embed the dashboards under `grafana.dashboardProviders` and `grafana.dashboards.otternet.<name>.json` in the metrics values. `scripts/seed_app_payloads.py` assembles `payloads/otternet-metrics-values.yaml` plus `payloads/dashboards/*.json` into the attached values file, so the JSON stays reviewable as separate files. Add a unit test in `tests/unit/test_fabric_app_chart_seed_data.py` that every dashboard file parses and has a unique `uid`
- [X] T055 [US4] Extend `scripts/verify_bootstrap.sh` stage "observability" with an assertion: through the Grafana API, as alice's session from T050, every panel query of `organisation.json` returns at least one series

**Checkpoint**: Grafana opens onto the organisation's own data.

---

## Phase 8: User Story 5 — Infrahub drives monitoring (P2)

**Goal**: Infrahub decides which devices are watched and what is collected, across all four
device kinds. The collector configuration is an artifact that Vidra delivers and Telegraf runs.
Intended state is exported beside observed state.

**Independent Test**: quickstart §4–§6.
- The collected targets equal the modelled set per family (7, 6, 1 and 3).
- A profile change appears as an artifact diff in its proposed change and changes collection
  within 5 minutes of merge.
- A downed BGP session shows as intended-but-down within 1 minute.
- A device change on a branch moves the collector artifact.

### Seed data for US5

- [X] T056 [P] [US5] Seed groups `monitoring_collectors` and `kubernetes_nodes` in `objects/00_groups.yml`, with comments in house style
- [X] T057 [P] [US5] Seed `IpamIPAddress` management addresses in the `172.20.41.0/24` prefix: fw1 `.31`, k8s-node1–3 `.41–.43`, isp-pe1 `.61`, isp-pe2 `.62`, internet-rtr `.71`, cust-acme-ce `.73`, branch-rtr `.81`, cust-globex-ce `.91`. Take the values from `../lab/otternet.clab.yml` and re-read them at implementation time. Put them in `objects/29_otternet_offfabric_prefixes.yml`, or the file that already holds `172.20.41.0/24`
- [X] T058 [US5] Set `telemetry_address` on the six FRR routers (`objects/26_otternet_devices.yml` or the file declaring them), on fw1 (`objects/32_otternet_security.yml`) and on the k3s nodes (`objects/28_otternet_endpoints.yml`). Add the nodes to `kubernetes_nodes`
- [X] T059 [US5] Create `objects/40_otternet_monitoring.yml` (confirm 40 is the next free number) with:
  - the six `MonitoringMeasurement`s
  - collector `otternet-telegraf` (`namespace_name: otternet-telemetry`, `config_map_name: telegraf-intent`, cluster `otternet`, member of `monitoring_collectors`)
  - the five profiles in `data-model.md`'s table

### Reconciler safety for the new addresses (must precede device-side changes)

- [X] T060 [US5] Write `tests/unit/test_deployment_inventory_targets.py`. It asserts that `src/solution_arista_avd/deployment/inventory.py` and `devices.py` build the same `Target` (address and transport) for every FRR router and for fw1 whether or not `telemetry_address` is populated: FRR by container name, Junos by container name (R8). Fix the code only if this fails, and keep the reach-by-name behaviour

### Device-side enablement (each lands with its lab-file change so the pins hold)

- [X] T061 [P] [US5] EOS gNMI: add `custom_structured_configuration_management_api_gnmi: {transport: {grpc: [{name: default, vrf: MGMT}]}, provider: eos-native}` to the fabric's `avd_custom_hostvars` in `objects/23_otternet_fabric.yml`, with a comment that provisioning's `rollback clean-config` removed the boot-time gNMI (R7)
- [X] T062 [P] [US5] Lab repo: add the same `management_api_gnmi` to the fabric `group_vars` in `../lab/avd/` so the golden files derive identically. Then run `uv run python scripts/regenerate_otternet_golden.py` and commit the updated `tests/integration/golden/otternet/*.cfg` in this repository
- [ ] T063 [P] [US5] Normaliser: capture real `show running-config` from one switch with gNMI enabled (in-sync case) and with it removed (changed case). Add both fixtures and assertions to `tests/unit/test_deployment_normalise.py`. Add a rule to `src/solution_arista_avd/deployment/normalise.py` **only** if the in-sync capture reports a difference
- [X] T064 [P] [US5] Junos SNMP test first: in `tests/unit/test_junos_config.py`, assert that:
  - with `snmp_community` unset the render is byte-identical to today
  - with it set, a top-level `snmp` stanza appears in the position the updated `../lab/configs/fw/vsrx/junos.conf` has it
  - `_assert_junos_scope` still passes
  - `test_the_exclusions_add_up` is recounted
- [X] T065 [US5] **Verify on the running vSRX**, read-only through `show configuration` and a test `load` on a candidate that is then rolled back:
  - the exact `snmp` syntax with `management-instance`, meaning `routing-instance-access` and whether the community needs `routing-instance mgmt_junos { clients … }`
  - the source address vrnetlab's NAT presents, which decides `snmp_clients`

  Record the result in `research.md` R7
- [X] T066 [US5] Implement the `snmp` stanza in `transforms/junos_config.py`, and add `snmp_community`, `snmp_clients` to `transforms/junos_config.gql`, then regenerate `transforms/junos_config_query.py`. Render nothing when the community is unset
- [X] T067 [US5] Lab repo: add the identical `snmp` stanza to `../lab/configs/fw/vsrx/junos.conf`, and set `snmp_community` (read-only value, documented as configuration in a comment) and `snmp_clients` on fw1 in `objects/32_otternet_security.yml`. Update `tests/unit/fixtures/junos/fw1.json` to match. Then run T064 and confirm it passes
- [ ] T068 [P] [US5] Normaliser for Junos: capture `show | compare` after a push that includes the `snmp` stanza (in-sync case) and the changed case, and add both to `tests/unit/test_deployment_normalise.py`. Add a rule only if needed
- [X] T069 [P] [US5] Lab repo: add six `frr_exporter` sidecar nodes (`tynany/frr_exporter:v1.12.0`, `kind: linux`, `network-mode: container:<router>`) to `../lab/otternet.clab.yml`. Bind each router's `/var/run/frr` to a host directory under the lab dir, mounted into both the router and its sidecar, and pass `--frr.socket.dir-path`. Confirm that `invoke lab` still deploys and that `curl <router mgmt>:9342/metrics` answers for all six

### Collector artifact (tests first)

- [X] T070 [P] [US5] Write `tests/unit/test_monitoring_measurements_contract.py`. It asserts that the renderer's dispatch table, keyed by (measurement, device kind), equals the table in `contracts/monitoring-measurements.md` in both directions, and that every seeded measurement in `objects/40_otternet_monitoring.yml` has at least one family
- [X] T071 [P] [US5] Write `tests/unit/test_telemetry_collector_config.py` with fixtures under `tests/unit/fixtures/monitoring/`. It covers the invariants 1–5 in `contracts/telemetry-collector-artifact.md`:
  - a single document with exactly the two keys
  - `telegraf.conf` parses with `tomllib`, and an empty render raises
  - two renders are byte-identical
  - the collector's own group membership is never a target
  - a device with no address (`mgmt_ip` for switches, `telemetry_address` otherwise) is skipped and reported

  It also covers the skip comment for non-applicable measurements, a disabled profile rendering nothing with a comment, `device_role` filtering (leaf-only `evpn-routes`), the gNMI credentials as `${GNMI_USERNAME}`/`${GNMI_PASSWORD}`, the tags from the graph, and the `intended.prom` series names and labels exactly as in the contract
- [X] T072 [US5] Create `transforms/telemetry_collector_config.gql`. It queries one `MonitoringCollector` by `$name`: profiles (enabled, interval, `device_role`, measurements, `device_groups` → members) and, per member, inline fragments for `DcimFabricSwitch`, `DcimDevice`, `SecurityFirewall` and `ComputePhysicalServer`, with `name`, `role`, `mgmt_ip { node { address { value } } }` (switches) or `telemetry_address { node { address { value } } }` (others), rack and pod (switch), and for fw1 `snmp_community`. It also queries the EOS intended-state inputs (each switch's `AvdStructuredConfigFile` content or reference, and cabled `DcimInterface` pairs with `enabled`). Then regenerate `transforms/telemetry_collector_config_query.py`
- [X] T073 [US5] Implement `transforms/telemetry_collector_config.py` (`class TelemetryCollectorConfig(InfrahubTransform)`, typed against `telemetry_collector_config_query.py`). It covers:
  - device selection by groups plus role
  - the dispatch table from T070, rendering `inputs.gnmi`, `inputs.snmp` and `inputs.prometheus` blocks per `contracts/monitoring-measurements.md`
  - `outputs.prometheus_client` `:9273`
  - an `inputs.file` reading `intended.prom`
  - intended BGP neighbours from structured configs, and FRR neighbours using the same derivation `frr_config` uses (reuse its helper, do not copy it)
  - intended links and enabled interfaces
  - a deterministic sort
  - `tomllib` validation of the result before returning
  - a ConfigMap YAML string as output

  Split helpers to stay under C901 17
- [X] T074 [US5] Register in `.infrahub.yml`: query `telemetry_collector_config`, a python transform `telemetry_collector_config`, and the artifact definition `telemetry_collector_config` / `Telemetry Collector Configuration` / `application/yaml` / targets `monitoring_collectors`, with comments in house style
- [X] T075 [US5] Add the third sync to `vidra/infrahub-syncs.yaml`: `artefactName: "Telemetry Collector Configuration"`, destination namespace `otternet-telemetry`, same address and credentials. Extend whatever test pins the syncs' artifact names against `.infrahub.yml` (search `tests/unit` for `infrahub-syncs`) to include it
- [X] T076 [US5] In `tasks.py` `_cluster_task`, after namespace `otternet-telemetry` exists, create or update Secret `telemetry-credentials` (`GNMI_USERNAME`, `GNMI_PASSWORD` from `.env`; default to the existing local AVD user) idempotently, as in T031

### Freshness generator

- [X] T077 [P] [US5] Write `tests/unit/test_generate_monitoring_collector.py`. It asserts that the generator issues exactly one `POST /api/artifact/generate/{id}?branch=<branch>` for its collector's artifact, performs **no** node create, update or delete (mock the client and assert no mutation), and is a no-op when the artifact definition is absent apart from a clear log
- [X] T078 [US5] Create `generators/generate_monitoring_collector.gql` (the collector by name and its artifact id for definition `telemetry_collector_config`), regenerate `generators/generate_monitoring_collector_query.py`, and implement `generators/generate_monitoring_collector.py` (`class MonitoringCollectorGenerator`). Reuse the REST re-render helper pattern from `generators/generate_app_access.py` `_rerender_firewall` (around line 1287). Factor it into `src/solution_arista_avd/generator.py` if both can share it without behaviour change
- [X] T079 [US5] Register `generate-monitoring-collector` in `.infrahub.yml` with targets `monitoring_collectors`, `execute_in_proposed_change: true` and `execute_after_merge: true`, and a comment explaining the freshness gap (R6) and why no trigger rule exists (FR-059b)
- [ ] T080 [US5] Run `$infrahub-test-generator-idempotence` for `generate-monitoring-collector` on a validation branch, and record the branch, scenario, snapshot scope and no-diff result in the PR description

### Dashboards and verification for US5

- [X] T081 [P] [US5] Create these dashboards and embed them as in T054:
  - `payloads/dashboards/fabric-telemetry.json`: interface counters, BGP state per device, and "intended but down" / "up but unintended" tables built on `otternet_intended_bgp_neighbor` joined to observed state per the contract
  - `payloads/dashboards/wan.json`: frr_exporter BGP
  - `payloads/dashboards/perimeter.json`: SNMP interfaces, sessions and CPU
  - `payloads/dashboards/nodes.json`: node-exporter, with a panel note that the nodes share the host kernel
- [ ] T082 [US5] **Verify** the EOS EVPN gNMI path in `contracts/monitoring-measurements.md` footnote 1 against a live cEOS with `gnmic`, or Telegraf with `--test`. If it is unstable, switch to the documented fallback and update the contract and T070's table together
- [X] T083 [US5] Extend `scripts/verify_bootstrap.sh` stage "observability" with per-family telemetry counts through Prometheus. Telegraf targets reporting, labelled `kind`, must equal 7, 6, 1 and 3, so a missing family fails by name
- [ ] T084 [US5] Run quickstart §4 (profile change → artifact diff → collection change ≤5 min), §5 (shut a BGP session → intended-but-down ≤1 min) and §6 (freshness on a branch) live, and record timings for SC-009 and SC-010 in the PR description

**Checkpoint**: monitoring is intent. Every target and every instruction came from Infrahub and
was reviewed in a proposed change.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [X] T085 [P] Add the demo act "alice asks for Grafana" (request, read the proposed change, merge, sign in, revoke) after the existing acts, plus timings and recovery notes, in `docs/docs/demo-runbook.md`
- [X] T086 [P] Create `docs/docs/developer-guide/observability.md`: the two applications, the exporter, the Monitoring schema, the collector artifact and freshness generator, the per-family device-side enablement and its pins, and the credential stance including the SNMP exception. Add it to `docs/sidebars.ts` (key `aristaAvdSidebar`), with relative links only
- [X] T087 [P] Update `docs/docs/supported-capabilities.md` and `docs/docs/developer-guide/vidra-delivery.md`, which gains a third sync and the ConfigMap artifact
- [X] T088 [P] Add AGENTS.md sections in house style, recording what each looks like an oversight:
  - observability: two apps, why `policy_default_deny: false`, why a new name, the installer opt-out
  - the exporter and the `metrics-exporter` account, and why port 8002
  - monitoring as intent: the collector artifact, the freshness generator, and nothing triggering on `Monitoring*`
  - the Dex back channel over the management network
  - gNMI re-enabled through `avd_custom_hostvars`
  - SNMP as the recorded credential exception
  - the `frr_exporter` sidecars and the SR Linux follow-up
- [X] T089 Run `uv run invoke lint` (ruff, mypy, yamllint, rumdl, Vale) and `uv run pytest tests/unit`, each as its own command, and fix every finding
- [ ] T090 Run `$infrahub-run-integration-tests`, and record the tested branch and commit in the PR description
- [ ] T091 Final `scripts/verify_bootstrap.sh` from destroyed, after all phases, then rehearse the demo act end to end from the branch desktop as alice

---

## Dependencies & Execution Order

### Phase dependencies

- **Setup (P1)**: depends on nothing.
- **Foundational (P2)**: depends on Setup and **blocks every story**, since all schema changes
  load together.
- **US1**: needs Foundational. It is the MVP and is needed by US2, US3, US4 and US6.
- **US2**: needs US1, because it edits the same app and its values.
- **US3**: needs US1 (the app and its VIP) and US2, so that alice can sign in. The network grant
  itself works without US2.
- **US6**: needs US1, US2 and US3, because it asserts all of them. Its exporter tasks
  (T041–T046) can start as soon as Foundational is done.
- **US4**: needs US1 and US6's exporter (T041–T045).
- **US5**: needs Foundational and US1 (the telemetry app). It is independent of US2, US3 and US4.
  T081 and T083 extend US4's and US6's files.
- **Polish**: after the stories in scope.

### Inside US5

T056–T059 (seed data) → T060 (inventory safety) → device-side changes T061–T069, which can run in
parallel per family → T070–T071 (tests) → T072–T076 (artifact) → T077–T080 (generator) →
T081–T084.

### Parallel opportunities

- Setup: T002 and T003.
- Foundational: T004–T006 (tests), then T008–T011 (one file each).
- US1: T015–T017, then T019, T020 and T023 together.
- US2: T026, T027 and T030.
- US6: T041, T042, T044 and T046 alongside US2 and US3, since they touch different files.
- US5: per-family enablement (EOS T061–T063 ∥ Junos T064–T068 ∥ FRR T069), with T070, T071
  and T077 in parallel.
- Lab-repo tasks T023, T039, T062, T067 and T069 can be batched into lab commits.

### Parallel example: US5 device-side enablement

```text
Agent A: T061 → T062 → T063   (EOS gNMI, golden files, normaliser)
Agent B: T064 → T065 → T066 → T067 → T068   (Junos SNMP, pins, normaliser)
Agent C: T069   (lab frr_exporter sidecars)
```

---

## Implementation Strategy

### MVP: US1, then US2 and US3

1. Phases 1–2 (schema loaded and green).
2. US1: both applications seeded and rendering, and delivered after `invoke cluster`.
3. US2: Dex sign-in.
4. US3: alice's request.
5. **Stop and demo** acts 1–6 plus the new act. This is the feature the user asked for, and it
   stands on its own.

### Incremental delivery

1. Add US6 so that a fresh bootstrap produces the MVP and `verify_bootstrap.sh` proves it.
2. Add US4 for organisation dashboards.
3. Add US5 for Infrahub-driven telemetry across all four families. This is the largest increment
   and carries the lab-repo pin changes.
4. Polish.

### Notes

- **Verify tasks.** T033, T065, T082 and T042's field check resolve the inferences marked
  **Verify** in research.md. Each records its outcome in `research.md` before downstream tasks
  rely on it.
- **Pinned outputs.** Any task that moves a pinned output (`junos.conf`, EOS golden files) lands
  with the matching lab-repo commit, and the two repositories are tested together.
