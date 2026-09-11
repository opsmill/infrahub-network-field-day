---
title: Transforms
description: Data transforms and artifact generation — how Infrahub data becomes configs, docs, and CSVs.
audience: developer
sidebar_position: 4
---

# Transforms

:::info Developer Guide
Documents the transform implementations. To *view* artifacts as an operator, see [Viewing Artifacts](../viewing-artifacts.md).
:::

## Overview

Transforms convert Infrahub data into usable outputs (configs, documentation, computed attributes). They run on-demand when artifacts are accessed.

## Transform types

1. **Python Transforms** - Complex logic, external library calls (PyAVD)
2. **Jinja2 Transforms** - Template-based text generation

Every transform this repository registers is a Python transform. One of them,
`containerlab_topology`, renders its output through a Jinja2 template it loads itself; the
`jinja2_transforms:` block of `.infrahub.yml` is unused here.

## Transform architecture

```text
┌──────────────────┐     ┌────────────────────┐     ┌─────────────────┐
│  GraphQL Query   │ ──▶ │  Transform Class   │ ──▶ │  Artifact       │
│  (*.gql)         │     │  (*Transform)      │     │  (config/doc)   │
└──────────────────┘     └────────────────────┘     └─────────────────┘
```

## Python transforms

### ComputedInterfaceDescription

**File**: `transforms/computed_interface_description.py`

**Purpose**: Generate human-readable interface descriptions

**Input**: DcimInterface
**Output**: String like "→ remote-device:Ethernet1"

```python
class ComputedInterfaceDescription(InfrahubTransform):
    async def transform(self, data):
        interface = data["DcimInterface"]["edges"][0]["node"]
        link = interface.get("link")
        if not link:
            return ""

        # Find the remote end
        remote = link["interface_a"] if link["interface_b"]["id"] == interface["id"] else link["interface_b"]
        return f"→ {remote['device']['name']['value']}:{remote['name']['value']}"
```

### CablingPlan

**File**: `transforms/cabling_plan.py`

**Purpose**: Generate CSV cabling documentation for a fabric

**Input**: NetworkFabric
**Output**: CSV file with all connections

```csv
Source Device,Source Interface,Destination Device,Destination Interface,Link Type
spine-A1-1,Ethernet1,super-spine-A-1,Ethernet1,uplink
leaf-A1-01-1,Ethernet49,spine-A1-1,Ethernet1,uplink
```

### AvdEosConfigTransform

**File**: `transforms/avd_eos_config.py`

**Purpose**: Convert AVD structured config to EOS CLI

**Input**: DcimDevice (with AvdArtifact)
**Output**: EOS CLI configuration

```python
class AvdEosConfigTransform(InfrahubTransform):
    async def transform(self, data):
        device = data["DcimDevice"]["edges"][0]["node"]
        artifact = device["avd_artifact"]["node"]

        if not artifact["structured_config_identifier"]["value"]:
            return "! No structured config available"

        config = await self.client.object_store.get(
            identifier=artifact["structured_config_identifier"]["value"]
        )
        return pyavd.get_device_config(json.loads(config))
```

### AvdFabricDocTransform

**File**: `transforms/avd_fabric_doc.py`

**Purpose**: Generate fabric-wide documentation

**Input**: NetworkFabric
**Output**: Markdown documentation

```python
class AvdFabricDocTransform(InfrahubTransform):
    async def transform(self, data):
        # Collect all device hostvars and structured configs
        all_hostvars = {}
        all_structured = {}

        for device in devices:
            hostvars = await self.client.object_store.get(...)
            structured = await self.client.object_store.get(...)
            all_hostvars[device.name] = hostvars
            all_structured[device.name] = structured

        avd_facts = pyavd.get_avd_facts(all_hostvars)
        return pyavd.get_fabric_documentation(
            avd_facts, all_structured, fabric_name
        )
```

### AvdDeviceDocTransform

**File**: `transforms/avd_device_doc.py`

**Purpose**: Generate per-device documentation

**Input**: DcimDevice
**Output**: Markdown documentation for single device

### AvdAntaCatalogTransform

**File**: `transforms/avd_anta_catalog.py`

**Purpose**: Render a per-device [ANTA](https://anta.arista.com) test catalog from the stored
structured config

**Input**: DcimDevice
**Output**: YAML catalog, or a one-line marker comment

Unlike EOS config rendering, catalog generation needs fabric-wide data, so the transform gathers
every sibling device's structured config in the same fabric into one `AVDFabricData` before calling
`pyavd.get_device_test_catalog()`.

It is gated by the fabric's `anta_enabled` flag. When ANTA is disabled — or the device has no
fabric, or no structured config — the transform returns a marker comment instead of a catalog, so
the artifact renders successfully and says why it is empty:

```text
# ANTA disabled for fabric Fabric-L3LS-Multi-Domain
```

### CrossplaneFabricPeeringTransform

**File**: `transforms/crossplane_fabric_peering.py`

**Purpose**: Render the `FabricPeering` custom resource the lab's Crossplane composition
consumes, from the Infrahub model

**Input**: ServiceFabricPeering
**Output**: YAML — one Kubernetes custom resource

This closes the loop the service-layer schema was built for: change the model, re-render,
review the diff, then push.

**Why the target is a service, not the cluster.** Artifact targets must inherit
`CoreArtifactTarget`, and only the service kinds do — `Cluster.Kubernetes` deliberately
does not, so the artifact hangs off the ordered intent ("this cluster peers with the
fabric") while every rendered *value* comes from the technical layer beneath it: the
cluster supplies the local ASN, the auth secret's name, the timers and the selectors, and
each `Cluster.FabricPeering` supplies one peer's name, address, and ASN.

**Pure Python with a YAML dumper**, unlike `ContainerLabTopology`. The output is a
structured document rather than a text configuration, so the transform builds a dictionary
and emits it, which lets the dumper decide what needs quoting. That matters twice here:
`true` is a YAML boolean and `65401:110` carries a colon, and both have to stay strings for
the Kubernetes API to accept them. A template gets that right only for as long as whoever
edits it remembers to.

Two transformations happen before the dictionary is built:

- Label selectors are stored as `key=value` strings rather than JSON maps, because
  Infrahub returns a server error for a JSON attribute key containing a dot or a slash —
  and every Kubernetes label selector has both. The transform parses them back into the
  map the resource needs. See `schemas/MARKETPLACE.md`.
- `peer_address` resolves to an `Ipam.IPAddress`, whose value carries the prefix length.
  A BGP neighbour address must not, so it is stripped.

**It refuses to render an incomplete model.** A cluster with no local ASN, a service with
no enabled peering, or a peering with no address raises an error naming the object and the
field. A manifest with an empty peer list would apply cleanly, report healthy, and carry
no routes — the failure that is hardest to diagnose. A `provisioning` status still
renders, though: whether to apply a manifest is an operator's decision.

Rendering is deterministic — peers sorted by name, selector keys sorted, and mapping key
order fixed by insertion order with `sort_keys=False` — so an unchanged model produces a
byte-identical artifact and a changed checksum means something real. Sequences are indented
under the key that owns them, matching the hand-written manifest the artifact replaces, so a
diff between the two reads as a field comparison.

### CrossplaneFabricAppTransform

**File**: `transforms/crossplane_fabric_app.py`

**Purpose**: Render the `FabricApp` custom resource for an application deployed on the cluster

**Input**: ServiceFabricApp
**Output**: YAML — one Kubernetes custom resource

The counterpart to the peering transform: that one renders the cluster's BGP session, this
one renders an application deployed on top of it.

**It is async, and that is why.** The deployment payload — the Kubernetes manifests, and any
Helm values — is stored as a `CoreFileObject` attachment rather than a JSON attribute, so its
content is fetched with `download_file()` rather than arriving in the query response. The query
returns only the attachment's metadata, and the node is re-fetched by id before the content can
be read, exactly as `AvdAntaCatalogTransform` does for stored structured config.

**Why the payload is an attachment.** A JSON attribute cannot be seeded: Infrahub's object-load
path returns a server error for a JSON key containing a dot or a slash, and a Kubernetes
payload is full of them — `app.kubernetes.io/name`, `kubernetes.io/hostname`,
`nfd41.lab/advertise`. When both an attachment and the inline attribute are set, **the
attachment wins**.

**Seeding needs a script.** `infrahubctl object load` cannot upload file content, so
`scripts/seed_app_payloads.py` uploads `payloads/*.yaml` into the attachments. Run it after
`invoke load`, or an application renders with no workload. The payload files live outside
`objects/` deliberately — everything in that tree is parsed as an Infrahub object file.

**Type discipline.** `true` is a label value and `8080` is a port; both would be rejected by the
Kubernetes API as a boolean or an integer. The dumper decides quoting from the value's type, and
a colon-bearing scalar is force-quoted — the same approach as the peering transform.

**It refuses an incomplete model**: no namespace, exposed with no VIP block, neither chart nor
manifests, or an attachment whose content is not parseable YAML.

### ContainerLabTopology

**File**: `transforms/containerlab_topology.py`

**Purpose**: Render a [ContainerLab](https://containerlab.dev) topology file for a whole fabric

**Input**: NetworkFabric
**Output**: YAML topology (`topology.clab.yml` shape)

The transform uses two queries — `containerlab_topology` for the fabric's devices and
`containerlab_link_endpoints` to resolve link endpoints in batches — and renders through the
`transforms/templates/containerlab_topology.j2` template. Node kinds, container images, and the
interface-mapping bind come from schema attributes (`DcimPlatform.containerlab_os`,
`DcimPlatform.containerlab_image`, `DcimDeviceType.containerlab_interface_mapping`), so changing the
cEOS version is a data change rather than a code change.

Nodes and links are emitted in a stable sorted order, so two renders of unchanged data are
byte-identical. See the [ContainerLab page](../containerlab.md) for the full artifact shape, the
role-selection rules, and how to deploy the topology.

### CVWorkspaceSubmissionWebhookPayload

**File**: `transforms/cv_workspace_submission_webhook.py`

**Purpose**: Build the JSON body for the CloudVision workspace-submission `CoreCustomWebhook`

**Input**: CloudvisionWorkspace
**Output**: JSON object — check name, proposed-change ID, and one entry per linked workspace with
its ID, status, URL, and fabric name

This transform has no artifact definition: it is referenced by the webhook rather than rendered to
the object store. See [Checks](./checks.md) for how it fits the CloudVision validation pipeline.

## Query classes

Each transform has Pydantic models for type-safe query parsing. **These `*_query.py` files are generated, not hand-written** — regenerate them whenever the `.gql` query or the schema changes:

```bash
uv run infrahubctl graphql generate-return-types transforms/computed_interface_description.gql
```

This reads `schema.graphql` at the repo root (refresh with `uv run infrahubctl graphql export-schema --destination schema.graphql` when needed) and emits the matching `*_query.py` next to the query file.

Shape of a typical generated class:

```python
# transforms/computed_interface_description_query.py  (generated)

class InterfaceLink(BaseModel):
    interface_a: InterfaceNode
    interface_b: InterfaceNode

class InterfaceNode(BaseModel):
    id: str
    name: ValueWrapper[str]
    device: DeviceRef
    link: InterfaceLink | None
```

## Artifacts

Artifacts are the output files generated by transforms.

### Artifact definitions

Defined in `.infrahub.yml`:

```yaml
artifact_definitions:
  - name: cabling_plan
    targets: fabrics
    transformation: cabling_plan
    content_type: text/csv

  - name: avd_eos_configuration
    targets: avd_devices
    transformation: avd_eos_config
    content_type: text/plain

  - name: avd_fabric_documentation
    targets: fabrics
    transformation: avd_fabric_doc
    content_type: text/markdown

  - name: avd_device_documentation
    targets: avd_devices
    transformation: avd_device_doc
    content_type: text/markdown

  - name: avd_anta_catalog
    targets: avd_devices
    transformation: avd_anta_catalog
    content_type: application/yaml

  - name: containerlab_topology
    targets: fabrics
    transformation: containerlab_topology
    content_type: application/yaml
```

`cv_workspace_submission_webhook_payload` is deliberately absent from this block — it renders a
webhook body, not an artifact.

### Viewing artifacts

1. Navigate to target object in Infrahub UI
2. Click **Artifacts** tab
3. Select artifact to view/download

### Regenerating artifacts

Artifacts regenerate automatically when:

- Underlying data changes
- Transform code changes
- Manually triggered via UI

## Configuration

Transforms are registered in `.infrahub.yml`:

```yaml
python_transforms:
  - name: computed_interface_description
    class_name: ComputedInterfaceDescription
    file_path: "./transforms/computed_interface_description.py"

  - name: cabling_plan
    class_name: CablingPlan
    file_path: "./transforms/cabling_plan.py"

  - name: avd_eos_config
    class_name: AvdEosConfigTransform
    file_path: "./transforms/avd_eos_config.py"

  - name: avd_fabric_doc
    class_name: AvdFabricDocTransform
    file_path: "./transforms/avd_fabric_doc.py"

  - name: avd_device_doc
    class_name: AvdDeviceDocTransform
    file_path: "./transforms/avd_device_doc.py"

  - name: avd_anta_catalog
    class_name: AvdAntaCatalogTransform
    file_path: "./transforms/avd_anta_catalog.py"

  - name: containerlab_topology
    class_name: ContainerLabTopology
    file_path: "./transforms/containerlab_topology.py"

  - name: cv_workspace_submission_webhook_payload
    class_name: CVWorkspaceSubmissionWebhookPayload
    file_path: "./transforms/cv_workspace_submission_webhook.py"
    convert_query_response: false
```

## File structure

```text
transforms/
├── computed_interface_description.py      # Interface description
├── computed_interface_description.gql     # Interface query
├── computed_interface_description_query.py # Pydantic models
├── cabling_plan.py                        # Cabling plan CSV
├── fabric_cabling_plan.gql                # Fabric cabling query
├── fabric_cabling_plan_query.py           # Pydantic models
├── avd_eos_config.py                      # EOS config transform
├── avd_device_config.gql                  # Device config query
├── avd_device_config_query.py             # Pydantic models
├── avd_fabric_doc.py                      # Fabric documentation
├── avd_device_doc.py                      # Device documentation
├── avd_fabric_devices.gql                 # Fabric devices query
├── avd_fabric_devices_query.py            # Pydantic models
├── avd_anta_catalog.py                    # ANTA catalog transform
├── avd_anta_catalog.gql                   # ANTA catalog query
├── avd_anta_catalog_query.py              # Pydantic models
├── containerlab_topology.py               # ContainerLab topology transform
├── containerlab_topology.gql              # Fabric device/link query
├── containerlab_topology_query.py         # Pydantic models
├── containerlab_link_endpoints.gql        # Batched link-endpoint query
├── containerlab_link_endpoints_query.py   # Pydantic models
├── cv_workspace_submission_webhook.py     # CloudVision webhook payload
├── cv_workspace_submission_webhook.gql    # Workspace query
├── cv_workspace_submission_webhook_query.py  # Pydantic models
└── templates/
    └── containerlab_topology.j2           # ContainerLab topology template
```

## Creating new transforms

### Python transform

1. Create transform class:

```python
# transforms/my_transform.py
from infrahub_sdk.transforms import InfrahubTransform

class MyTransform(InfrahubTransform):
    query = "my_query"

    async def transform(self, data):
        # Process data
        return "output"
```

2. Create GraphQL query:

```graphql
# transforms/my_query.gql
query MyQuery($device_id: String!) {
  DcimDevice(ids: [$device_id]) {
    edges {
      node {
        name { value }
      }
    }
  }
}
```

3. Register in `.infrahub.yml`:

```yaml
queries:
  - name: my_query
    file_path: "./transforms/my_query.gql"

python_transforms:
  - name: my_transform
    class_name: MyTransform
    file_path: "./transforms/my_transform.py"

artifact_definitions:
  - name: my_artifact
    targets: devices
    transformation: my_transform
```

### Jinja2 transform

1. Create template:

```jinja2
{# transforms/templates/my_template.j2 #}
Output for {{ node.name.value }}
```

2. Register in `.infrahub.yml`:

```yaml
jinja2_transforms:
  - name: my_jinja_transform
    template_path: "./transforms/templates/my_template.j2"
    query: my_query
```

## Source

- Python transforms:
  - [`transforms/avd_eos_config.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/avd_eos_config.py) — `AvdEosConfigTransform`.
  - [`transforms/avd_fabric_doc.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/avd_fabric_doc.py) — `AvdFabricDocTransform`.
  - [`transforms/avd_device_doc.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/avd_device_doc.py) — `AvdDeviceDocTransform`.
  - [`transforms/computed_interface_description.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/computed_interface_description.py) — `ComputedInterfaceDescription`.
  - [`transforms/cabling_plan.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/cabling_plan.py) — `CablingPlan`.
  - [`transforms/avd_anta_catalog.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/avd_anta_catalog.py) — `AvdAntaCatalogTransform`.
  - [`transforms/containerlab_topology.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/containerlab_topology.py) — `ContainerLabTopology`.
  - [`transforms/cv_workspace_submission_webhook.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/transforms/cv_workspace_submission_webhook.py) — `CVWorkspaceSubmissionWebhookPayload`.
- Templates: [`transforms/templates/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/transforms/templates).
- Registration: [`.infrahub.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/.infrahub.yml) — `python_transforms:` and `artifact_definitions:` blocks.
- The AVD transforms are documented in detail on the [AVD Transforms](./avd/transforms.md) page.
- The CloudVision webhook payload transform is documented alongside the [Checks](./checks.md) it serves.
