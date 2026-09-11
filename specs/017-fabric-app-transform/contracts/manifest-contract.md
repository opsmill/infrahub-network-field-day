# Contract: Rendered Manifest

**Feature**: `specs/017-fabric-app-transform` | **Date**: 2026-09-11

## 1. Registration

```yaml
queries:
  - name: crossplane_fabric_app
    file_path: "./transforms/crossplane_fabric_app.gql"

python_transforms:
  - name: crossplane_fabric_app
    class_name: CrossplaneFabricAppTransform
    file_path: "./transforms/crossplane_fabric_app.py"

artifact_definitions:
  - name: "crossplane_fabric_app"
    artifact_name: "Crossplane FabricApp"
    parameters:
      name: "name__value"
    content_type: "application/yaml"
    targets: "service_fabric_apps"
    transformation: "crossplane_fabric_app"
```

The transform's `query` attribute must equal the registered query name. A mismatch is the one
error only a repository sync catches.

`targets` is a **new** group. Applications and peerings are different sets, and an artifact
definition pointed at the wrong one would try to render a resource it cannot.

## 2. Rendered shape

```yaml
apiVersion: nfd41.lab/v1alpha1
kind: FabricApp
metadata:
  name: nfd41-demo
spec:
  namespace: nfd41-demo
  tenant: k8s-prod
  manifests: [...]
  expose:
    vipBlock: 10.112.240.0/28
    serviceSelector:
      nfd41.lab/advertise: 'true'
  policy:
    defaultDeny: true
    allowDNS: true
    allowFrom: [...]
    allowFromPorts:
      - port: '8080'
        protocol: TCP
    workloadSelector:
      app: frontend
```

## 3. Guarantees

| # | |
| --- | --- |
| G-1 | Exactly one YAML document |
| G-2 | Key order fixed by construction, matching the XRD |
| G-3 | Label values and ports are strings, never coerced |
| G-4 | Colon-bearing scalars are quoted |
| G-5 | Unset optional fields are omitted, so the XRD's defaults apply |
| G-6 | An unchanged model renders byte-identically |
| G-7 | The attachment wins over the inline attribute |
| G-8 | An incomplete model raises; no partial manifest is emitted |

## 4. Relationship to the hand-written manifest

`../lab/crossplane/apps/10-demo.yaml` is the oracle. Every shared field must be equal (SC-003);
`policy.allowFrom` is called out separately (SC-005) because it is a security control.

Differences are permitted **only** where the render adds a field carrying the XRD's own
default, making the contract explicit rather than implied — the same direction cycle 011 took.

## 5. What this contract does not cover

- `AppAccess`. Its XRD exists; no hand-written instance does, so a render has no oracle.
- The observability and access applications.
- Delivery to the cluster.
