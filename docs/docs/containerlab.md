---
title: ContainerLab
description: The lab under lab/, how it is brought up from Infrahub, and the ContainerLab Topology artifact.
audience: user
---

# ContainerLab

[ContainerLab](https://containerlab.dev) runs the OTTERNET lab as containers: Arista cEOS for the
fabric, FRR for the WAN, a vSRX firewall, k3s nodes, and the branch and tooling hosts.

## The lab

The lab lives in this repository, under `lab/`. `lab/otternet.clab.yml` is the topology, and it is
committed rather than rendered: the lab owns which nodes exist and how they are wired, and Infrahub
owns their configuration. `lab/README.md` covers the lab's own Makefile targets, images and
troubleshooting.

```bash
uv run invoke lab          # deploy lab/otternet.clab.yml, wait for eAPI
uv run invoke provision    # push every rendered artifact onto the devices
```

The fabric boots **unconfigured on purpose**: cEOS nodes get no `startup-config`, only a management
address, and `invoke provision` (or the reconciler) then makes each one match its Infrahub artifact.
`uv run invoke bootstrap` runs both as part of building the whole environment.

Two things `invoke lab` does before deploying, because ContainerLab refuses a topology with a missing
bind path before starting any node:

- It renders `lab/wan/render.py`. Every FRR router bind-mounts its boot configuration from
  `lab/wan/rendered/`, which is generated and ignored by git.
- It creates the tooling bridge and the FRR socket directories the topology binds.

ContainerLab's runtime state, `lab/clab-otternet/`, and the k3s `kubeconfig` files under `lab/k8s/` are
written at deploy time and ignored by git. From a git worktree, `invoke lab` still resolves to `lab/` in
the main checkout, because there is one lab and that state lives with it. Set `OTTERNET_LAB_DIR` to
point elsewhere.

## The ContainerLab topology artifact

| Property | Value |
|----------|-------|
| Artifact name | `ContainerLab Topology` |
| Attached to | Each `NetworkFabric` (target group `fabrics`) |
| Content type | `application/yaml` |
| Transform | `containerlab_topology` |

Separately from the committed lab, Infrahub renders a topology for any modelled fabric. It is a
reference artifact: nothing deploys it, and `invoke lab` uses the committed topology instead.

The artifact is **fabric-scoped**: one topology per fabric, containing every device the fabric owns
through its pods and racks. The rendered `name:` is the fabric name, so the management network and
container names are derived from it (`clab-<fabric-name>-mgmt`).

Find it on the fabric's **Artifacts** tab in the Infrahub UI, the same way as the fabric
documentation — see [Viewing Artifacts](./viewing-artifacts.md).

To preview a render locally without going through a proposed change:

```bash
# COLUMNS is set because infrahubctl prints via Rich, which wraps long lines at the
# terminal width — irrelevant to the server-rendered artifact, but not to a local capture.
COLUMNS=500 uv run infrahubctl transform containerlab_topology name=OTTERNET_FABRIC
```

## What ends up in the topology

```yaml
---
name: OTTERNET_FABRIC

mgmt:
  network: clab-OTTERNET_FABRIC-mgmt
  ipv4-subnet: 172.20.41.0/24

topology:
  kinds:
    arista_ceos:
      image: ceos:4.36.0.1F
      startup-config: configs/__clabNodeName__.cfg
    linux:
      image: ghcr.io/srl-labs/network-multitool:v0.10.0

  nodes:
    host-a:
      kind: linux
      binds:
        - configs/servers/host-a-netplan.yaml:/etc/netplan/netplan.yaml
```

Nodes and links are emitted in a stable sorted order, and endpoints are ordered within each link,
so two renders of unchanged data are byte-identical.

`startup-config` is set only on kinds whose nodes are network devices — the `linux` kind has none,
because servers boot from their netplan bind. The path is `configs/__clabNodeName__.cfg`, the
directory a deployment would place fetched EOS configs in.

### Which devices are included

Switches are selected by `DcimFabricSwitch.role`: every fabric-switch role is included except
`p`, `pe` and `rr` (the list is `NETWORK_ROLES` in `transforms/containerlab_topology.py`).
`OTTERNET_FABRIC`'s seven switches are all `spine` or `leaf`. `ComputePhysicalServer` members of the
fabric are included as Linux nodes.

The `p`, `pe`, and `rr` roles are deliberately **excluded**. They are MPLS core and edge roles the
schema still offers, no fabric in this repository uses them, and their interface naming has not been
validated against ContainerLab, so admitting them would be speculative. Each excluded device is logged as a warning during the render rather than dropped
silently, so a fabric holding them renders without those devices and says so in the transform log.

A link is only emitted when it resolves to exactly two endpoints and both endpoints belong to
devices present in `nodes`.

## Kind, image, and interface mapping come from the schema

Nothing about node identity is hardcoded in the transform. Three schema attributes drive it:

| Attribute | Node | Drives |
|-----------|------|--------|
| `DcimPlatform.containerlab_os` | `kind:` on each node | `arista_ceos`, `linux` |
| `DcimPlatform.containerlab_image` | `image:` on each `kinds` entry | `ceos:4.36.0.1F`, `ghcr.io/srl-labs/network-multitool` |
| `DcimDeviceType.containerlab_interface_mapping` | the `EosIntfMapping.json` bind | unset on `Arista cEOS-LAB` (see below) |

All three are optional `Text` attributes. A device whose platform has no `containerlab_os` cannot
be rendered as a node; a device type with no `containerlab_interface_mapping` gets no
mapping bind (the `binds` key is omitted entirely when a node has nothing to bind).

`containerlab_interface_mapping` holds a **filename only**, not a path, and not the file contents.
The file is resolved relative to the topology file at deploy time. The attribute exists so the
mapping filename does not have to be derived from anything else, such as the `part_number`.

The platform values live in `objects/03_device_type.yml` and the device types in
`objects/20_otternet_device_types.yml`. The `Arista cEOS-LAB` device type sets no
`containerlab_interface_mapping`: every `OTTERNET_FABRIC` switch uses plain `Ethernet<N>` names,
which cEOS maps without help, so no switch node carries a mapping bind.

## Interface names and why the mapping bind matters

Link endpoints are translated from EOS names to the Linux interface names cEOS exposes to
ContainerLab:

| EOS name | ContainerLab name |
|----------|-------------------|
| `Ethernet5` | `eth5` |
| `Ethernet1/1` | `eth1_1` |
| `Ethernet49/1` | `eth49_1` |

The rule is `Ethernet<N>[/<M>]` → `eth<N>[_<M>]`: strip the `Ethernet` prefix and replace `/` with
`_`.

For plain `Ethernet<N>` interfaces that is all cEOS needs — it maps `ethN` to `EthernetN` by
default. Breakout names are the problem. A generated config that says `interface Ethernet1/1` does
not attach to anything if cEOS has decided that `eth1_1` is `Ethernet1_1`, or has not created the
interface at all. `EosIntfMapping.json` is the file that tells cEOS which container interface
corresponds to which EOS interface name, per device type. It is mounted read-only:

```yaml
binds:
  - configs/eos-intf-mapping/<mapping-file>.json:/mnt/flash/EosIntfMapping.json:ro
```

On a device type whose interfaces use breakout names such as `Ethernet<N>/1`, the mapping bind is
what makes the AVD-rendered config match the interfaces that actually exist. To
confirm it took effect after a deploy:

```bash
docker exec clab-<topology>-<a-spine> Cli -c "show interfaces status" | head -20
```

Expect `Ethernet1/1`-style names. Seeing `eth1_1` instead means the bind is missing, or points at a
file that is not on disk next to the topology.

Server nodes carry a netplan bind instead, mounted at `/etc/netplan/netplan.yaml`. The source
filename is derived by convention from the device name (`configs/servers/<device-name>-netplan.yaml`);
netplan contents are not generated from Infrahub.

## Related

- `lab/README.md` — the lab, its Makefile targets, and the images it needs.
- [Viewing Artifacts](./viewing-artifacts.md) — finding, previewing, and downloading artifacts.
- [Transforms](./developer-guide/transforms.md) — how transforms and artifact definitions are wired.
