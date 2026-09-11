# Data Model: Application File Attachments

**Feature**: `specs/013-app-file-attachments` | **Date**: 2026-09-10

Two new kinds and two new relationships. Everything else in the service layer is untouched.

---

## 1. Shape

```text
ServiceFabricApp
├── values_file    ──Component(one, optional)──► ServiceFabricAppValuesFile
│                                                  └── inherit_from: CoreFileObject
└── manifests_file ──Component(one, optional)──► ServiceFabricAppManifestsFile
                                                   └── inherit_from: CoreFileObject
```

`Component` on the parent side and `Parent` on the child side, sharing one identifier, so the
files are owned by the application and do not survive it.

---

## 2. Inherited fields

Both kinds inherit the whole of `CoreFileObject` and declare none of it themselves:

| Field | Meaning here |
| --- | --- |
| `file_name` | The source file's name, for a human reading the object |
| `file_size` | Payload size in bytes |
| `file_type` | Content type |
| `checksum` | **The field that makes an unchanged payload detectable without downloading it** — SC-003 |
| `storage_id` | Where the content lives in object storage, not in the graph |

---

## 3. The new kinds

| Property | `ServiceFabricAppValuesFile` | `ServiceFabricAppManifestsFile` |
| --- | --- | --- |
| `namespace` | `Service` | `Service` |
| `inherit_from` | `[CoreFileObject]` | `[CoreFileObject]` |
| `human_friendly_id` | `["app__name__value"]` | `["app__name__value"]` |
| `uniqueness_constraints` | `[["app"]]` | `[["app"]]` |
| `include_in_menu` | `false` | `false` |
| `app` relationship | `Parent`, cardinality one, mandatory | same |
| `identifier` | `fabricapp__values_file` | `fabricapp__manifests_file` |

Uniqueness is on the relationship, so it is written bare — no `__value` suffix — per the
skill's uniqueness rule. The HFID crosses to the parent's attribute, so it takes `__value`.

---

## 4. The relationships added to `ServiceFabricApp`

| Name | Peer | Kind | Cardinality | Optional | Identifier |
| --- | --- | --- | --- | --- | --- |
| `values_file` | `ServiceFabricAppValuesFile` | `Component` | one | yes | `fabricapp__values_file` |
| `manifests_file` | `ServiceFabricAppManifestsFile` | `Component` | one | yes | `fabricapp__manifests_file` |

Both optional: an application may be chart-only, manifests-only, or small enough to inline.

---

## 5. Precedence

Stated in the schema descriptions, per FR-011 and research R2:

| State | What a consumer reads |
| --- | --- |
| File attached, attribute unset | The file |
| File attached, attribute set | **The file.** The attribute is ignored |
| No file, attribute set | The attribute |
| Neither | Nothing — a valid state for a chart-only or manifests-only application |

The schema cannot enforce this; it documents it. A check could, and that is noted as a
follow-up rather than claimed here.

---

## 6. What is deliberately unchanged

| Kind | Why it matters that it is untouched |
| --- | --- |
| `ServiceFabricApp`'s 16 attributes | `chart_values` and `manifests` stay as the inline escape hatch |
| `ServiceFabricPeering`, `ClusterFabricPeering` | Cycle 011's transform and cycle 012's generator read these; their artifact checksum must not move |
| `AvdHostvarFile`, `AvdStructuredConfigFile` | The pattern is copied, not modified |

---

## 7. Validation rules

The schema enforces the first three. The fourth is documentation.

| # | Rule | Enforced by |
| --- | --- | --- |
| V-1 | An application holds at most one values file and at most one manifests file | cardinality one + `uniqueness_constraints: [["app"]]` |
| V-2 | A file cannot exist without an application | `Parent`, `optional: false` |
| V-3 | Deleting an application removes its files | `Component` on the parent side |
| V-4 | The attachment wins over the attribute | Description text only — see §5 |
