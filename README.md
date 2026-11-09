# Infrahub Otternet

![CI](https://github.com/opsmill/infrahub-network-field-day/actions/workflows/ci.yml/badge.svg)

The Arista EVPN/VXLAN fabric of the OTTERNET lab. Infrahub holds its model, and AVD renders its configurations.

A fork of [opsmill/infrahub-arista-avd](https://github.com/opsmill/infrahub-arista-avd) with one thing changed: instead of seven illustrative example designs, it models **one real fabric** — the OTTERNET containerlab topology. Topology, addressing, EVPN services, tenant VRFs, firewall handoffs and workload BGP peerings all live in Infrahub as structured, queryable data, and PyAVD renders them into the EOS configuration the switches actually run.

The claim is falsifiable, and tested. The lab in `lab/` can still be built from static Ansible `group_vars` (`lab/avd/`); this repository holds the same fabric as Infrahub objects, and asserts that the configuration it renders is **byte-for-byte identical** to what the lab is deployed with. The source of truth moves; nothing on the wire changes.

```console
$ uv run pytest tests/unit/test_otternet_golden_config.py
9 passed in 1.31s

$ uv run pytest tests/integration/test_otternet_fabric.py -m e2e
11 passed in 326.92s
```

The second one boots a real Infrahub stack in testcontainers, loads the schemas and seed data, runs the generator chain, renders the EOS artifact for all seven switches, and diffs each against `tests/integration/golden/otternet/` — the configuration copied from the running lab.

**Jump to:** [The fabric](#the-fabric) · [What it's for](#what-its-for) · [How it works](#how-it-works) · [Quick start](#quick-start) · [What's included](#whats-included) · [Documentation](#documentation)

## The fabric

| | |
|---|---|
| **Topology** | Single-pod 3-stage L3LS: two spines, two MLAG leaf pairs (`K8S_LEAFS`, `APP_LEAFS`), one non-MLAG border leaf |
| **Routing** | eBGP underlay, eBGP EVPN overlay; ASNs per MLAG pair (`65100` spines, `65101`–`65103` leaves) |
| **Tenants** | 4 tenants, 6 VRFs — `K8S_PROD`, `APP_PROD`, `TENANT_ACME`, `TENANT_GLOBEX`, `WAN`, `BRANCH` |
| **Security** | No route leaking anywhere. Every tenant VRF's only egress is a default route pointing at its own firewall zone, originated on the border leaf — so the firewall is the only path that exists, not a policy that could be bypassed. |
| **Workload BGP** | Cilium peers eBGP from each k3s node into `K8S_PROD`, bounded by an inbound route map and `maximum_routes` |
| **Platform** | Arista cEOS-LAB containers, driven by containerlab |

Numbering the deployed lab fixes — node ID, management address, loopback, ASN — is pinned in `objects/26_otternet_devices.yml` and preserved by the generators, since the fabric's route targets and BGP communities already reference it. Everything design-driven is generated: uplink and MLAG cabling, interface expansion, point-to-point and MLAG peer addressing, AVD host_vars, structured config, and the rendered artifacts.

Hostnames come from the generators (`spine-{pod}-{index}`, `leaf-{pod}-{rack_index}-{index}`) and the lab is redeployed under them, rather than the generators being taught the lab's names. `scripts/regenerate_otternet_golden.py` proves that rename is cosmetic: it substitutes the names back out and asserts the result equals the deployed configuration exactly.

## What it's for

- **Generate a complete fabric from a design** — define topology parameters and addressing pools; generators create the spines and leaves each pod and rack design calls for, allocate loopback, interconnect, and management addresses, BGP ASNs, and node IDs, and cable devices together automatically.
- **Render EOS device configurations and documentation** — PyAVD runs inside Infrahub workers and produces EOS CLI configurations, per-device and fabric-level Markdown documentation, and a cabling plan CSV as downloadable artifacts.
- **Make incremental day-two changes** — edit the design and regenerate; checksum-based idempotency applies changes only to affected objects; branch-aware pools prevent collisions across parallel work.
- **Give other teams access to network data** — the fabric is queryable through the Infrahub Web UI, GraphQL API, and MCP interface; the Backstage service portal lets stakeholders without API or CLI access request services; every request is a branch with a proposed change.
- **Track and review every change** — all changes run through Infrahub branches and proposed changes, with a full diff before any change reaches a device.

## How it works

The full pipeline, from a high-level fabric design to versioned, deployable configuration:

![The AVD + Infrahub pipeline: generate topology, format host vars, run EOS Designs, generate artifacts, and store and version every output in the knowledge graph.](docs/static/img/pipeline.png)

## Quick start

There are two environments, and each comes up with one command. Both need
[Docker](https://docs.docker.com/get-docker/) with Compose v2, [uv](https://docs.astral.sh/uv/getting-started/installation/),
Python 3.11 to 3.13, `git`, `curl`, `openssl`, and Node 22, 24 or 26. PyAVD is installed in the
project's Infrahub image, so it needs no separate install. `invoke prereqs` lists anything the machine is missing.

| Environment | Runs on | What it includes | Guide |
|---|---|---|---|
| Full lab | Linux, about 48 GB of memory, `/dev/kvm`, passwordless `sudo` | Infrahub, the ContainerLab devices configured from their artifacts, the tooling cluster and the Kubernetes workload cluster | [Set up the full lab environment](docs/docs/setup-lab.md) |
| Demo without the lab | macOS or Linux, about 12 GB of memory | Infrahub with the fabric cabled and every artifact rendered, Dex and the service portal; no devices and no Kubernetes | [Set up a demo environment without the lab](docs/docs/setup-demo.md) |

Both start the same way:

```bash
uv sync --all-packages
export INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec   # the local stack's admin token

uv run invoke prereqs && uv run invoke bootstrap                       # full lab
uv run invoke prereqs --no-lab && uv run invoke bootstrap --no-lab     # demo without the lab
```

Infrahub is then at `http://localhost:8000`. For development, where you run each stage yourself, follow
[Set up the stack step by step](docs/docs/developer-guide/stack-step-by-step.md).

## What you'll see

What a bootstrap builds, in order. Steps 1 to 6 happen in both environments; step 7 needs the full lab.

1. **Seed data appears in the UI** — the manufacturer, cEOS-LAB device type and templates, addressing and numbering pools, and the `OTTERNET_FABRIC` design with its pod, three leaf racks, seven switches, four tenants and six VRFs are loaded.
2. **FabricGenerator runs** — `OTTERNET_FABRIC` declares no device tier above its spines, so it creates no devices; it resolves the fabric's pools and triggers the pod generator.
3. **PodGenerator and RackGenerator trigger automatically** — the two spines and five leaves are reconciled (their pinned identity is preserved), cabled to their uplinks and MLAG peers, and given interconnect addresses.
4. **AVD generators run** — each device's PyAVD host_vars and structured configuration are stored as `AvdArtifact` graph objects.
5. **Transforms produce artifacts** — EOS device configuration, per-device Markdown documentation, fabric documentation, and a cabling plan CSV are available as downloadable artifacts on each device and fabric object.
6. **Propose and review** — the bootstrap runs the chain on a branch and merges it. Any later change, from the UI, the portal or the MCP server, goes through a proposed change that shows a diff of every changed object and the rendered artifacts before anything is merged.
7. **Deploy to devices (full lab only)** — `uv run invoke provision` pushes each device's rendered artifact onto it, and the deployment reconciler (`uv run invoke reconcile`) does the same on a timer, pushing only what differs. CloudVision validates a proposed change's EOS configs in a workspace; it does not deploy.

## What's included

- **Schemas** — 44 schema files covering the fabric, the WAN, the firewall, the cluster and the service layer:
  - Topology: NetworkFabric, NetworkPod, LocationRack, DcimFabricSwitch, DcimInterface, NetworkLink
  - Devices beyond the fabric: DcimDevice (the SR Linux WAN routers), SecurityFirewall, ComputePhysicalServer
  - IPAM: prefixes and addresses with role tagging (loopback, interconnect, management, server)
  - EVPN: tenants, VRFs, SVIs, L2 VLANs
  - MLAG: domain and peer pool definitions
  - AVD types: `AvdArtifact` for per-device hostvar and structured config tracking with checksums
- **Generators** — fourteen checksum-based, idempotent generators:
  - FabricGenerator, PodGenerator, RackGenerator — device creation, addressing, and cabling
  - GenerateAVDDeviceHostvar — assembles per-device PyAVD input from the source of truth
  - AvdDeviceStructuredConfigGenerator — runs PyAVD to produce structured configuration
  - GenerateServerCabling — handles server attachment
  - One per service kind — network segments, tenant onboarding, server placement, applications, access grants, cluster peering — plus the monitoring collector's freshness generator
- **Transforms** — render structured data into downloadable artifacts:
  - EOS device configuration (via PyAVD, running inside Infrahub workers)
  - Per-device and fabric-level Markdown documentation
  - Cabling plan CSV
  - ANTA test catalogs — generation ships; test execution is on the roadmap
  - Computed interface descriptions
  - SR Linux configuration for the WAN routers, and Junos configuration for the firewall
  - Crossplane manifests for applications and cluster peering, delivered by Vidra, and the telemetry collector's configuration
- **Seed data** — the manufacturer, cEOS-LAB device type, interface profiles and device templates, addressing and number pools (loopback, VTEP, interconnect, MLAG, management, ASN, node ID), and the `OTTERNET_FABRIC` design: one pod, three leaf racks, the seven switches with their pinned identity, four tenants over six VRFs, and the workload endpoints.
- **Service portal** — Backstage, with one generated request template per service kind. It runs in the tooling cluster in the full lab, and as a Docker Compose container beside Infrahub in the demo environment:
  - Network segment (subnet, VLAN, and gateway SVI, allocated from pools)
  - Server placement into a rack, cabled to its leaves
  - Tenant onboarding onto a fabric
  - Exposed applications and access grants
- **Stack** — Docker Compose, extending Infrahub 1.10.6 with PyAVD. The version is the `INFRAHUB_BASE_VERSION` default in the `Dockerfile`. It includes the Infrahub UI, Neo4j, and Semaphore (a bundled Ansible runner, which does not configure devices; see [Supported capabilities](docs/docs/supported-capabilities.md)).

| File | What it does |
|------|-------------|
| `.infrahub.yml` | Registers all generators, transforms, queries, and artifact definitions with Infrahub |
| `schemas/` | YAML schema definitions for the full data model |
| `generators/` | Python generators (fabric, pod, rack, AVD hostvars, structured config, server cabling, and the service layer) |
| `transforms/` | Python and Jinja2 transforms (EOS, SR Linux and Junos config, docs, cabling plan, ANTA catalog, Crossplane manifests, telemetry config) |
| `objects/` | Seed YAML for the fabric, the WAN, the firewall, the Kubernetes cluster, the application catalogue, and the seeded services |
| `triggers.yml` | Event trigger rules wiring schema changes to generator runs |
| `backstage/` | Backstage service portal, deployed into the tooling cluster |
| `docker-compose.yml` | Stack definition; `docker-compose.override.yml` adds Semaphore and the lab's supporting services, and `docker-compose.no-lab.yml` adds Dex and the portal for the demo environment |
| `Dockerfile` | Custom Infrahub image with PyAVD |
| `tasks.py` | Invoke task definitions (`build`, `start`, `load`, `avd`, `prereqs`, `bootstrap`, `lab`, `lint`, `test`; `uv run invoke --list` shows all) |

> **Note:** Brownfield import (modeling an existing fabric and importing configurations via Infrahub Sync) is available in a guided engagement today — it is not yet a self-serve path.

## Documentation

The full documentation is under [`docs/`](docs/docs/). Key entry points:

| | |
|--|--|
| **Run the whole lab** | [Set up the full lab environment](docs/docs/setup-lab.md) — Infrahub, the devices and both clusters on one Linux host |
| **Show the workflow on a laptop** | [Set up a demo environment without the lab](docs/docs/setup-demo.md) — Infrahub and the portal, no devices |
| **Show the lab to an audience** | [Demo runbook](docs/docs/demo-runbook.md) — the demo script for the full lab: preflight checks, six acts, and measured timings |
| **Run each stage yourself** | [Set up the stack step by step](docs/docs/developer-guide/stack-step-by-step.md), then [Provision your first fabric](docs/docs/provision-first-fabric.md) — from seed data to rendered EOS artifacts, for development |
| **Check what's supported** | [Supported capabilities](docs/docs/supported-capabilities.md) — capability matrix (supported / partial / not yet) |
| **Run a day-two workflow** | [Add a network segment](docs/docs/how-to/add-network-segment.md) — and the other how-to guides |
| **Understand the generator pipeline** | [Architecture overview](docs/docs/developer-guide/architecture.md) — system components, data model, and generator chain |
| **Understand the AVD pipeline** | [AVD pipeline overview](docs/docs/developer-guide/avd/overview.md) — two-phase pipeline, hostvars reference, role mapping |
| **Extend the pipeline** | [Extending the pipeline](docs/docs/developer-guide/avd/extending.md) — new device roles, transform outputs, schema fields |
| **Debug pipeline issues** | [Debugging the pipeline](docs/docs/developer-guide/avd/debugging.md) — intermediate-file inspection, single-generator re-runs, common failure modes |

## Community and support

- **Bugs and feature requests:** [GitHub Issues on opsmill/infrahub-arista-avd](https://github.com/opsmill/infrahub-arista-avd/issues), the upstream project. This repository does not accept issues.

## Related projects

| Project | Description |
|---------|-------------|
| [Infrahub](https://github.com/opsmill/infrahub) | The infrastructure data management and automation platform this reference design runs on |
| [Arista AVD](https://github.com/aristanetworks/avd) | Arista Validated Design — the collection and PyAVD engine that render EOS configurations |
| [AVD documentation](https://avd.arista.com/) | Upstream AVD reference and PyAVD documentation |

## About Infrahub

[Infrahub](https://github.com/opsmill/infrahub) is an open source infrastructure data management and automation platform (Apache 2.0), developed by [OpsMill](https://opsmill.com). It gives infrastructure and network teams a unified, schema-driven source of truth for all infrastructure data — devices, topology, IP space, configuration — with built-in version control, a generator framework for automation, and native integrations with Git, Ansible, Terraform, and CI/CD pipelines.
