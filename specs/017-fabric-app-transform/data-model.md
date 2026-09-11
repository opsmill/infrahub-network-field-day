# Data Model: Crossplane FabricApp Manifest

**Feature**: `specs/017-fabric-app-transform` | **Date**: 2026-09-11

No schema change. Cycle 013 added the attachments this reads.

## 1. Field mapping — schema to XRD

| Infrahub | XRD | Transform |
| --- | --- | --- |
| `name` | `metadata.name` | verbatim |
| `namespace_name` | `spec.namespace` | verbatim, **required** |
| `vrf` → name | `spec.tenant` | lower-cased **and** `_`→`-` — `K8S_PROD` becomes `k8s-prod` (R3) |
| `chart_repository` / `chart_name` / `chart_version` | `spec.chart.{repository,name,version}` | verbatim |
| `values_file` attachment, else `chart_values` | `spec.chart.values` | parsed, emitted verbatim |
| `manifests_file` attachment, else `manifests` | `spec.manifests` | parsed, emitted verbatim |
| `exposed` | gates `spec.expose` | omit the block when false |
| `vip_block` → prefix | `spec.expose.vipBlock` | the prefix string |
| `service_selector` | `spec.expose.serviceSelector` | `key=value` list → label map |
| `communities` | `spec.expose.communities` | list of strings |

`ServiceFabricApp` has **no** `advertisement_selector` — that attribute belongs to
`ServiceFabricPeering`. The XRD defaults `expose.advertisementSelector`, so omitting it is
correct rather than a gap.
| `policy_default_deny` | `spec.policy.defaultDeny` | bool |
| `policy_allow_dns` | `spec.policy.allowDNS` | bool |
| `policy_allow_intra_namespace` | `spec.policy.allowIntraNamespace` | bool |
| `policy_allow_egress_api_server` | `spec.policy.allowEgressToAPIServer` | bool |
| `policy_allow_egress_internet` | `spec.policy.allowEgressToInternet` | bool |
| `allowed_source_prefixes` → prefixes | `spec.policy.allowFrom` | list of CIDR strings, sorted |
| `policy_allow_ports` | `spec.policy.allowFromPorts` | `port` as a **string**, `protocol` defaulting to TCP |
| `workload_selector` | `spec.policy.workloadSelector` | `key=value` list → label map |

## 2. Key order

Fixed by construction, matching the XRD's own field order:
`namespace`, `tenant`, `chart`, `manifests`, `expose`, `policy`.
Half of what makes an unchanged model render byte-identically.

## 3. Type discipline

| Value | Must render as | Why |
| --- | --- | --- |
| A selector value like `true` | string `'true'` | A Kubernetes label map is `map[string]string`; a bool is rejected |
| `allowFromPorts[].port` | string | The XRD types it as a string |
| A community like `65401:112` | quoted string | A colon in a plain scalar is the one construct YAML parsers read differently |
| `allowFrom` entries | strings | CIDRs |

Cycle 011 established the mechanism: let the dumper decide, and force a quote on colon-bearing
scalars.

## 4. Validation rules

All before any output is produced.

| # | Condition | Message names |
| --- | --- | --- |
| V-1 | No target matched | the kind |
| V-2 | No `namespace_name` | the app |
| V-3 | `exposed` with no `vip_block` | the app and the field |
| V-4 | Neither chart nor manifests | the app, and why a workload-less FabricApp is worse than an error |
| V-5 | An attachment's content is not parseable YAML | the app and the file name |

## 5. Seed objects added

| Object | Why |
| --- | --- |
| `IpamPrefix 10.112.240.0/28`, role `vip_pool` | Verified absent; `spec.expose.vipBlock` cannot be rendered without it |
| `ServiceFabricApp nfd41-demo` | The target; none exists |
| `ServiceFabricAppManifestsFile` on it | Uploaded by the seeding script — `object load` cannot write file content |
| Group `service_fabric_apps` | The artifact definition's target |

## 6. What is deliberately unchanged

`ServiceFabricPeering`, `ClusterFabricPeering`, the peering generator and its artifact. SC-010
asserts cycle 011's checksum is still `0d800c9d5005b5fdb6b371bb5627d143`.
