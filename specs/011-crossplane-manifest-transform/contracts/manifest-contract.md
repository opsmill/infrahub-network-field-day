# Contract: Rendered Manifest and Artifact Surface

**Feature**: `specs/011-crossplane-manifest-transform` | **Date**: 2026-09-10

A transform's external interface is what it **emits** and what it **registers**. Two
consumers depend on this: the lab's Crossplane composition, which applies the manifest,
and whatever pulls the artifact out of Infrahub. A change to anything below is a breaking
change to one of them.

---

## 1. The rendered resource

Contract owner: `../lab/crossplane/platform/00-xrd-fabric-peering.yaml` — group
`nfd41.lab`, version `v1alpha1`, kind `FabricPeering`, **cluster-scoped**.

The rendered document, with the values currently loaded:

```yaml
apiVersion: nfd41.lab/v1alpha1
kind: FabricPeering
metadata:
  name: nfd41-fabric-peering
spec:
  localASN: 65401
  authSecretName: nfd41-bgp-auth
  nodeSelector:
    nfd41.lab/bgp: "true"
  advertisementSelector:
    nfd41.lab/advertise: fabric
  podCIDRCommunities:
    - "65401:110"
  timers:
    connectRetrySeconds: 5
    holdTimeSeconds: 9
    keepAliveSeconds: 3
  peers:
    - name: k8s-leaf1
      address: 10.110.0.2
      asn: 65101
    - name: k8s-leaf2
      address: 10.110.0.3
      asn: 65101
```

### Guarantees

| # | Guarantee | Enforced by |
| --- | --- | --- |
| G-1 | Exactly one YAML document, no leading `---` separator needed by the consumer | `yaml.dump` of a single dict |
| G-2 | `localASN` is always present and an integer | V-1 raises otherwise |
| G-3 | `peers` is never empty | V-2 raises otherwise |
| G-4 | Every `peers[].address` is a bare address, never a prefix | address stripping, asserted in unit tests |
| G-5 | Selector values are strings, quoted where YAML would otherwise coerce them (`'true'`) | the dumper's resolver, plus a forced quote on colon-bearing scalars |
| G-6 | `peers` ordered by name; an unchanged model renders byte-identically | explicit sort + fixed key order |
| G-7 | Optional fields are absent when unset, never `null` or empty | FR-018, so the XRD's defaults apply |
| G-8 | No secret value ever appears | only `bgp_auth_secret_name` is read |

### Required by the XRD

`localASN` and `peers` are the XRD's only `required` fields. Everything else has an XRD
default, which is why G-7 matters: emitting `null` would override a default rather than
leave it alone.

---

## 2. The artifact surface

| Property | Value |
| --- | --- |
| Artifact definition name | `crossplane_fabric_peering` |
| Display name | `Crossplane FabricPeering` |
| Content type | `application/yaml` |
| Target group | `service_fabric_peerings` |
| Target kind | `ServiceFabricPeering` (inherits `CoreArtifactTarget`) |
| Transformation | `crossplane_fabric_peering` |
| Parameters | `name: "name__value"` |

`application/yaml` matches the repository's existing convention for YAML artifacts
(`avd_anta_catalog`, `containerlab_topology`).

### Registration contract

Three entries in `.infrahub.yml`, all sharing one name:

```yaml
queries:
  - name: crossplane_fabric_peering
    file_path: "./transforms/crossplane_fabric_peering.gql"

python_transforms:
  - name: crossplane_fabric_peering
    class_name: CrossplaneFabricPeeringTransform
    file_path: "./transforms/crossplane_fabric_peering.py"

artifact_definitions:
  - name: "crossplane_fabric_peering"
    artifact_name: "Crossplane FabricPeering"
    parameters:
      name: "name__value"
    content_type: "application/yaml"
    targets: "service_fabric_peerings"
    transformation: "crossplane_fabric_peering"
```

The transform class must set `query = "crossplane_fabric_peering"`, matching the
registered query name — not the GraphQL operation name inside the file.

---

## 3. The query contract

Operation name `CrossplaneFabricPeeringQuery`, one variable, target aliased `target:`:

```graphql
query CrossplaneFabricPeeringQuery($name: String!) {
  target: ServiceFabricPeering(name__value: $name) {
    edges {
      node {
        id
        name { value }
        status { value }
        communities { value }
        advertisement_selector { value }
        cluster {
          node {
            name { value }
            local_asn { value }
            bgp_auth_secret_name { value }
            bgp_timers { value }
            pod_cidr_communities { value }
            node_selector { value }
            advertisement_selector { value }
          }
        }
        peerings {
          edges {
            node {
              name { value }
              peer_asn { value }
              enabled { value }
              peer_address { node { address { value } } }
            }
          }
        }
      }
    }
  }
}
```

`$name` matches the artifact definition's `parameters.name`. The `target:` alias follows
`avd_anta_catalog.gql` and keeps the transform independent of the target's kind.

---

## 4. Generated model contract

`transforms/crossplane_fabric_peering_query.py`, produced by:

```bash
uv run infrahubctl graphql generate-return-types transforms/crossplane_fabric_peering.gql
```

Class names derive from the operation name, so the root is
`CrossplaneFabricPeeringQuery` and nested models are suffixed by path. The transform
aliases the long ones at module scope, as `avd_anta_catalog.py` does.

**This file is generated. It is never hand-edited**, including to satisfy mypy —
regenerate instead.

---

## 5. Backward compatibility

| Consumer | Impact |
| --- | --- |
| The lab's Crossplane composition | None. The rendered resource satisfies the existing XRD; the composition is unchanged |
| `../lab/crossplane/platform/10-peering.yaml` | Superseded in principle — this artifact is the same content generated from the model. Removing the hand-written file is the lab's call, not this cycle's |
| Existing transforms and artifacts | None. New query, new transform, new artifact definition; nothing existing is touched |
| `objects/00_groups.yml` | One group added. Additive |
| Schema | None. No schema change in this cycle |
