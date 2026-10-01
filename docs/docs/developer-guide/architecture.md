---
title: Architecture overview
description: System architecture and data flow for the Infrahub Arista AVD solution.
audience: developer
sidebar_position: 1
---

# Architecture overview

:::info Developer Guide
Assumes familiarity with Infrahub and Python. If you only want to *use* the system, start with [Quick Start](../quick-start.md).
:::

The solution is a repository of schemas, generators, and transforms loaded on top of the Infrahub platform. The sections below cover its components, data model, and the generator and transform pipelines.

## System components

```text
┌─────────────────────────────────────────────────────────────────────────┐
│                           Infrahub Platform                              │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │   Neo4j Graph   │  │   PostgreSQL    │  │   Object Store          │  │
│  │   Database      │  │   (Metadata)    │  │   (Hostvars, Configs)   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │   Redis Cache   │  │   RabbitMQ      │  │   Infrahub Server       │  │
│  │                 │  │   (Queue)       │  │   (API + Git Backend)   │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        Repository Solution                               │
├─────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │     Schemas     │  │   Generators    │  │   Transforms            │  │
│  │   (YAML DSL)    │  │   (Python)      │  │   (Python + Jinja2)     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────┐  │
│  │  Object Data    │  │     Queries     │  │   Core Library          │  │
│  │   (Seed YAML)   │  │    (GraphQL)    │  │   (src/solution_arista_avd)  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data model hierarchy

The repository models one fabric, `OTTERNET_FABRIC`: a single-pod, 3-stage L3LS EVPN/VXLAN fabric
with two spines and three leaf racks.

```text
NetworkFabric "OTTERNET_FABRIC"
└── NetworkPod "otternet-pod1"
    ├── DcimFabricSwitch [spine] "spine-otternet-pod1-1", "spine-otternet-pod1-2"
    ├── LocationRack "K8S_LEAFS"     (MLAG pair)
    │   └── DcimFabricSwitch [leaf] "leaf-otternet-pod1-1-1", "leaf-otternet-pod1-1-2"
    ├── LocationRack "APP_LEAFS"     (MLAG pair)
    │   └── DcimFabricSwitch [leaf] "leaf-otternet-pod1-2-1", "leaf-otternet-pod1-2-2"
    └── LocationRack "BORDER_LEAFS"  (single border leaf)
        └── DcimFabricSwitch [leaf] "leaf-otternet-pod1-3-1"
            └── DcimInterface (e.g., "Ethernet1")
                ├── NetworkLink → remote interface
                └── IpamIPAddress
```

The schema can also express a fabric-level tier above the spines, through a `NetworkFabric`
device design; `OTTERNET_FABRIC` declares none.

## IP address management

Fabric-level pool allocation:

```text
NetworkFabric
├── loopback_pool: CoreIPPrefixPool
│   └── Internal CoreIPAddressPool wrapper: Loopback0 addresses
├── vtep_pool: CoreIPPrefixPool
│   └── Internal CoreIPAddressPool wrapper: VTEP loopback addresses
├── uplink_pool: CoreIPPrefixPool
│   └── Prefix allocations for point-to-point links
├── mgmt_pool: CoreIPAddressPool
│   └── OOB management addresses
├── CoreNumberPool: OTTERNET-ASN-Pool (65104-65109)
│   └── Tier-aware eBGP ASN allocation: shared spine ASN per pod, leaf ASNs per device or MLAG domain.
│       The seven switches' ASNs (65100-65103) are pinned in objects/26_otternet_devices.yml.
└── CoreNumberPool: OTTERNET-NodeID-Pool (1-100)
    └── Per-device unique identifier
```

## Generator pipeline

Generators run in sequence to build infrastructure:

```text
┌─────────────────────────┐
│  1. FabricGenerator     │  Run on: NetworkFabric
│  - Resolve fabric pools │  Creates: no devices for OTTERNET_FABRIC
│  - Signal the pods      │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  2. PodGenerator        │  Triggered on: NetworkPod
│  - Create spine devices │  Creates: Spine switches
│  - Expand interfaces    │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  3. RackGenerator       │  Triggered on: LocationRack
│  - Create leaf devices  │  Creates: Leaf switches
│  - Link to spines       │
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│  4. AVD Generators      │  Run on: avd_devices / NetworkFabric
│  - Build hostvars       │  Creates: AVD configs
│  - Generate struct cfg  │
└─────────────────────────┘
```

Two further generators sit outside this chain:

- **`ServerCablingGenerator`** (on `ComputePhysicalServer`) cables a server to the leaves in its rack, then reconciles its LAGs and VLANs and re-triggers hostvar generation for those leaves.
- **`BackfillStructuredConfigGenerator`** (on `AvdStructuredConfigFile`) runs in the opposite direction, reading AVD's structured-config output back into IPAM, interface, BGP, and routing objects.

See [Generators](./generators.md).

## Transform pipeline

Transforms convert data to artifacts:

```text
┌──────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│  GraphQL Query   │ ──▶ │  Transform Logic   │ ──▶ │  Output Artifact│
│  (Data Fetch)    │     │  (Python/Jinja2)   │     │  (Config/Doc)   │
└──────────────────┘     └────────────────────┘     └─────────────────┘

Examples:
- DcimInterface → ComputedInterfaceDescription → "→ device:interface"
- NetworkFabric → CablingPlan → CSV cabling matrix
- DcimDevice → AvdEosConfig → EOS CLI configuration
- NetworkFabric → AvdFabricDoc → Markdown documentation
- DcimDevice → AvdAntaCatalog → ANTA test catalog (YAML)
- NetworkFabric → ContainerLabTopology → ContainerLab topology (YAML)
```

## Validation pipeline

Alongside transforms, proposed-change validation runs **checks** — Python routines that report pass, information, or error rather than producing an artifact. The repository ships five: `cv-config-validation`, which deploys the rendered EOS configs into a CloudVision workspace and blocks the proposed change on a failed build; `fabric-pool-validation`; and the global `peering-consistency`, `zone-advertisement` and `wan-service-consistency`. See [Checks](./checks.md).

## Checksum-based change detection

Generators use checksums to avoid redundant regeneration:

```python
class GeneratorMixin:
    def calculate_checksum(self, related_node_ids: list[str]) -> str:
        """Create deterministic hash from related node IDs"""
        return hashlib.sha256("".join(sorted(related_node_ids))).hexdigest()

# Usage in generator:
new_checksum = self.calculate_checksum([pod.id, device.id, ...])
if new_checksum != target.checksum:
    # Regenerate
    target.checksum = new_checksum
```

## Configuration files

| File | Role |
|------|------|
| `.infrahub.yml` | Register queries, generators, transforms, artifacts |
| `repository.yml` | Define repository as CoreRepository in Infrahub |
| `docker-compose.yml` | Orchestrate Infrahub services |
| `pyproject.toml` | Python dependencies and tool configuration |

## Docker service stack

```yaml
services:
  infrahub-server:    # Main API server
  infrahub-git:       # Git backend for repository
  infrahub-worker:    # Async task execution
  neo4j:              # Graph database
  postgres:           # Relational metadata
  redis:              # Cache layer
  rabbitmq:           # Message queue
```

## Development workflow

```text
1. Edit schema (schemas/*.yml)
        ↓
2. Load schema: inv load-schema
        ↓
3. Edit generator/transform code
        ↓
4. Test: pytest tests/
        ↓
5. Lint: inv lint
        ↓
6. Reload: inv load
        ↓
7. Run generators via UI
```

## Pool role resolution

Fabric and pod IP pool intent is role-driven. `NetworkFabric.fabric_ip_pools` is the authoritative fabric collection for Management, Loopback, Loopback VTEP, Fabric Point-to-Point, DCI, and Fabric Supernet roles. `NetworkPod.pod_ip_pools` is the authoritative pod collection for pod-scoped Loopback, Loopback VTEP, Fabric Point-to-Point, MLAG, and MLAG Peering roles.

Validation resolves a pool's purpose from the roles on its backing `IpamPrefix` resources. The proposed-change check rejects duplicate authoritative roles, mixed-role pools, non-IP pool members, pod management pools, and pod prefixes that are not contained by the matching parent fabric pool.

During migration, legacy fabric and pod pool relationships are still present and object data is dual-populated. Generators prefer collection relationships and fall back to legacy relationships only when needed.

## Source

- Infrahub configuration: [`.infrahub.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/.infrahub.yml) — the queries, generators, transforms, and artifact definitions registered with Infrahub.
- Schemas: [`schemas/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/schemas) — the data model.
- Generators: [`generators/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/generators) — Python generator classes.
- Transforms: [`transforms/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/transforms) — Python transform classes and templates.
- Checks: [`checks/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/checks) — proposed-change validation, currently CloudVision.
- Playbooks: [`ansible/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/ansible) — the tree Semaphore runs for EOS config deployment and ContainerLab staging.
- Core library: [`src/solution_arista_avd/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/src/solution_arista_avd) — shared protocols, AVD utilities, sorting, addressing.
- Service portal: [`backstage/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/backstage) — the Backstage portal whose catalog provider generates one request template per service kind.
