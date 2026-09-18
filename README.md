# Infrahub Otternet

![CI](https://github.com/opsmill/infrahub-network-field-day/actions/workflows/ci.yml/badge.svg)

The OTTERNET lab's Arista EVPN/VXLAN fabric, modelled in Infrahub and rendered with AVD.

A fork of [opsmill/infrahub-arista-avd](https://github.com/opsmill/infrahub-arista-avd) with one thing changed: instead of seven illustrative example designs, it models **one real fabric** — the OTTERNET containerlab topology. Topology, addressing, EVPN services, tenant VRFs, firewall handoffs and workload BGP peerings all live in Infrahub as structured, queryable data, and PyAVD renders them into the EOS configuration the switches actually run.

The claim is falsifiable, and tested. That lab is currently driven by static Ansible `group_vars`; this repository holds the same fabric as Infrahub objects, and asserts that the configuration it renders is **byte-for-byte identical** to what the lab is deployed with. The source of truth moves; nothing on the wire changes.

```console
$ uv run pytest tests/unit/test_otternet_golden_config.py
9 passed in 1.31s

$ uv run pytest tests/integration/test_otternet_fabric.py -m e2e
11 passed in 326.92s
```

The second one boots a real Infrahub stack in testcontainers, loads the schemas and seed data, runs the generator chain, renders the EOS artifact for all seven switches, and diffs each against `tests/integration/golden/otternet/` — the configuration copied from the running lab.

**Jump to:** [The fabric](#the-fabric) · [What it's for](#what-its-for) · [How it works](#how-it-works) · [Quick start](#quick-start) · [What's included](#whats-included) · [Documentation](#documentation)

## The Fabric

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

## What It's For

- **Generate a complete fabric from a design** — define topology parameters and addressing pools; generators create all super-spines, spines, and leaves, allocate loopback, interconnect, and management addresses, BGP ASNs, and node IDs, and cable devices together automatically.
- **Render EOS device configurations and documentation** — PyAVD runs inside Infrahub workers and produces EOS CLI configurations, per-device and fabric-level Markdown documentation, and a cabling plan CSV as downloadable artifacts.
- **Make incremental day-two changes** — edit the design and regenerate; checksum-based idempotency applies changes only to affected objects; branch-aware pools prevent collisions across parallel work.
- **Give other teams access to network data** — the fabric is queryable through the Infrahub Web UI, GraphQL API, and MCP interface; the Streamlit service portal provides guided workflows for stakeholders without API or CLI access.
- **Track and review every change** — all changes run through Infrahub branches and proposed changes, with a full diff before any change reaches a device.

## How It Works

The full pipeline, from a high-level fabric design to versioned, deployable configuration:

![The AVD + Infrahub pipeline: generate topology, format host vars, run EOS Designs, generate artifacts, and store and version every output in the knowledge graph.](docs/static/img/pipeline.png)

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- Python 3.11+
- PyAVD >= 6.4.0, < 6.5.0 (bundled in the custom Docker image -- no separate install required)

## Quick Start

```bash
# Install Python dependencies, including PyAVD and the Infrahub SDK
uv sync --all-packages

# Build the custom Infrahub image (extends the base image with PyAVD — run once)
export INFRAHUB_BASE_VERSION=1.10.6
uv run invoke build

# Start all services: Infrahub, Neo4j, PostgreSQL, Redis, RabbitMQ, service portal, Semaphore
uv run invoke start

# Load schemas, UI menu, seed data, register the repository, and load event triggers
uv run invoke load
```

Open the Infrahub UI at `http://localhost:8000` and the service portal at `http://localhost:8501`.

Then follow [Provision Your First Fabric](docs/docs/provision-first-fabric.md) to run the generator chain and reach rendered EOS artifacts.

## What You'll See

After `invoke load` completes and you run the generator chain on a fabric:

1. **Seed data appears in the UI** — the manufacturer, cEOS-LAB device type and templates, addressing and numbering pools, and the `OTTERNET_FABRIC` design with its pod, three leaf racks, seven switches, four tenants and six VRFs are loaded.
2. **FabricGenerator runs** — super-spine devices appear on the branch, with loopback and management addresses allocated from pools.
3. **PodGenerator and RackGenerator trigger automatically** — spine and leaf devices appear, cabled to their uplinks, with interconnect addresses, BGP ASNs, and node IDs assigned.
4. **AVD generators run** — each device's PyAVD host_vars and structured configuration are stored as `AvdArtifact` graph objects.
5. **Transforms produce artifacts** — EOS device configuration, per-device Markdown documentation, fabric documentation, and a cabling plan CSV are available as downloadable artifacts on each device and fabric object.
6. **Propose and review** — open a proposed change from the branch; the UI shows a diff of every new object and the rendered artifacts for review before any configuration reaches production.
7. **Deploy to devices** — apply the rendered configurations to the fabric through the bundled Ansible runner (Semaphore) or CloudVision (CVP/CVaaS).

## What's Included

- **Schemas** — 20 schema files covering the full fabric data model:
  - Topology: NetworkFabric, NetworkPod, NetworkDevice, NetworkInterface, NetworkLink
  - IPAM: prefixes and addresses with role tagging (loopback, interconnect, management, server)
  - EVPN: tenants, VRFs, SVIs, L2 VLANs
  - MLAG: domain and peer pool definitions
  - AVD types: `AvdArtifact` for per-device hostvar and structured config tracking with checksums
- **Generators** — six checksum-based, idempotent generators:
  - FabricGenerator, PodGenerator, RackGenerator — device creation, addressing, and cabling
  - GenerateAVDDeviceHostvar — assembles per-device PyAVD input from the source of truth
  - AvdDeviceStructuredConfigGenerator — runs PyAVD to produce structured configuration
  - GenerateServerCabling — handles server attachment
- **Transforms** — render structured data into downloadable artifacts:
  - EOS device configuration (via PyAVD, running inside Infrahub workers)
  - Per-device and fabric-level Markdown documentation
  - Cabling plan CSV
  - ANTA test catalogs — generation ships; test execution is on the roadmap
  - Computed interface descriptions
- **Seed data** — the manufacturer, cEOS-LAB device type, interface profiles and device templates, addressing and number pools (loopback, VTEP, interconnect, MLAG, management, ASN, node ID), and the `OTTERNET_FABRIC` design: one pod, three leaf racks, the seven switches with their pinned identity, four tenants over six VRFs, and the workload endpoints.
- **Service portal** — Streamlit application with guided day-2 workflows:
  - Add network segment (VRF, VLAN, SVI)
  - Provision server into a rack
  - Create EVPN tenant
  - Fabric Design visualization (topology, cabling, settings, EVPN)
- **Stack** — Docker Compose extending Infrahub 1.10.6 with PyAVD. Includes Infrahub UI, service portal, Semaphore (bundled Ansible runner for deployment), and Neo4j.

| File | What it does |
|------|-------------|
| `.infrahub.yml` | Registers all generators, transforms, queries, and artifact definitions with Infrahub |
| `schemas/` | YAML schema definitions for the full data model |
| `generators/` | Python generators (fabric, pod, rack, AVD hostvars, structured config, server cabling) |
| `transforms/` | Python and Jinja2 transforms (EOS config, docs, cabling plan, ANTA catalog, interface descriptions) |
| `objects/` | Seed YAML (manufacturers, device types, pools, profiles, templates, fabrics, racks, VLANs) |
| `triggers.yml` | Event trigger rules wiring schema changes to generator runs |
| `service_catalog/` | Streamlit service portal |
| `docker-compose.yml` | Stack definition; docker-compose.override.yml adds the portal and Semaphore |
| `Dockerfile` | Custom Infrahub image with PyAVD |
| `tasks.py` | Invoke task definitions (build, start, stop, load, lint, test) |

> **Note:** Brownfield import (modeling an existing fabric and importing configurations via Infrahub Sync) is available in a guided engagement today — it is not yet a self-serve path.

## Documentation

The full documentation is under [`docs/`](docs/docs/). Key entry points:

| | |
|--|--|
| **Get the stack running** | [Quick Start](docs/docs/quick-start.md) — prerequisites, install steps, and first load |
| **Provision a fabric end-to-end** | [Provision Your First Fabric](docs/docs/provision-first-fabric.md) — step-by-step walkthrough from seed data to rendered EOS artifacts |
| **Check what's supported** | [Supported Capabilities](docs/docs/supported-capabilities.md) — capability matrix (supported / partial / not yet) |
| **Run a day-two workflow** | [Add a Network Segment](docs/docs/how-to/add-network-segment.md) — and the other how-to guides |
| **Understand the generator pipeline** | [Architecture Overview](docs/docs/developer-guide/architecture.md) — system components, data model, and generator chain |
| **Understand the AVD pipeline** | [AVD Pipeline Overview](docs/docs/developer-guide/avd/overview.md) — two-phase pipeline, hostvars reference, role mapping |
| **Extend the pipeline** | [Extending the Pipeline](docs/docs/developer-guide/avd/extending.md) — new device roles, transform outputs, schema fields |
| **Debug pipeline issues** | [Debugging the Pipeline](docs/docs/developer-guide/avd/debugging.md) — intermediate-file inspection, single-generator re-runs, common failure modes |

## Community & Support

- **Questions and discussion:** [GitHub Discussions](https://github.com/opsmill/infrahub-arista-avd/discussions)
- **Bugs and feature requests:** [GitHub Issues](https://github.com/opsmill/infrahub-arista-avd/issues)

## Related Projects

| Project | Description |
|---------|-------------|
| [Infrahub](https://github.com/opsmill/infrahub) | The infrastructure data management and automation platform this reference design runs on |
| [Arista AVD](https://github.com/aristanetworks/avd) | Arista Validated Design — the collection and PyAVD engine that render EOS configurations |
| [AVD documentation](https://avd.arista.com/) | Upstream AVD reference and PyAVD documentation |

## About Infrahub

[Infrahub](https://github.com/opsmill/infrahub) is an open source infrastructure data management and automation platform (Apache 2.0), developed by [OpsMill](https://opsmill.com). It gives infrastructure and network teams a unified, schema-driven source of truth for all infrastructure data — devices, topology, IP space, configuration — with built-in version control, a generator framework for automation, and native integrations with Git, Ansible, Terraform, and CI/CD pipelines.
