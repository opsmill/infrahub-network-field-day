# Contract: Schema Kind Surface

**Feature**: `specs/013-app-file-attachments` | **Date**: 2026-09-10

A schema feature's external interface is the set of kinds it publishes and the graph
invariants they guarantee. Everything downstream — cycle 014's transform, the seeding script,
generated protocols — is written against this surface.

## 1. Published kinds (2)

| Kind | Inherits | Parent | Reached from the app as |
| --- | --- | --- | --- |
| `ServiceFabricAppValuesFile` | `CoreFileObject` | `ServiceFabricApp` (mandatory) | `values_file` |
| `ServiceFabricAppManifestsFile` | `CoreFileObject` | `ServiceFabricApp` (mandatory) | `manifests_file` |

## 2. Extended kinds (1)

| Kind | Change | Compatibility |
| --- | --- | --- |
| `ServiceFabricApp` | gains `values_file` and `manifests_file`, both optional, cardinality one | **Additive** — no field removed, no loaded object invalidated |

## 3. Human-friendly id contract

| Kind | HFID | Reference form |
| --- | --- | --- |
| `ServiceFabricAppValuesFile` | `app__name__value` | `"nfd41-demo"` |
| `ServiceFabricAppManifestsFile` | `app__name__value` | `"nfd41-demo"` |

A single-element HFID is written as a scalar. The two kinds share an HFID form; the kind
disambiguates.

## 4. Uniqueness contract

| Kind | Constraint | Rejects |
| --- | --- | --- |
| `ServiceFabricAppValuesFile` | `[["app"]]` | a second values file on one application |
| `ServiceFabricAppManifestsFile` | `[["app"]]` | a second manifests file on one application |

Relationship names appear bare; attributes would take `__value`.

## 5. Graph invariants

| # | Invariant | Enforced by |
| --- | --- | --- |
| GI-1 | Every file belongs to exactly one application | `Parent`, cardinality one, mandatory |
| GI-2 | An application has at most one file of each kind | cardinality one + uniqueness |
| GI-3 | Deleting an application deletes its files | `Component` |
| GI-4 | Each file carries a checksum that changes only when its content does | `CoreFileObject` |
| GI-5 | Both sides of each relationship share one identifier, so the link is bidirectional and single | matching `identifier` strings |
| GI-6 | Nothing outside `ServiceFabricApp` changes | the diff |

## 6. Consumer expectations

Cycle 014's transform may rely on:

- `app.values_file` and `app.manifests_file` resolving to at most one file each, or to nothing
- content retrievable via the SDK's `download_file()`, as `generate_avd_device_hostvar.py` already does
- `checksum` being stable across an unchanged re-upload, so an artifact rendered from it is stable too
- the attachment taking precedence over the corresponding attribute

## 7. What this contract does not cover

- How content is uploaded. That is the seeding script, in the cycle that needs it.
- Validation of payload contents. They are Kubernetes' contract.
- Enforcement of the precedence rule, which is documented rather than enforceable.
