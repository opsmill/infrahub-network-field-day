# Acceptance Evidence

**Feature**: `specs/013-app-file-attachments` | **Date**: 2026-09-10
**Branch**: `app-files` (Infrahub) / `013-app-file-attachments` (git) | **Infrahub**: 1.10.6

## SC-001 / T014 — the diff is exactly two kinds

```text
added:
    ServiceFabricAppManifestsFile
    ServiceFabricAppValuesFile
    ServiceFabricApp:
        relationships added: manifests_file, values_file
```

Zero validation errors. Nothing outside `ServiceFabricApp` changed (GI-6).

## SC-002, SC-006, SC-007 / T020, T022 — the payload round-trips

A 155-line, 4830-byte payload containing both dotted and slashed keys:

| Check | Result |
| --- | --- |
| Content identical after round-trip | ✅ |
| `app.kubernetes.io/name` survived | ✅ |
| `node-role.kubernetes.io/control-plane` survived | ✅ |

**This is the defect the cycle exists for.** The same payload as a JSON attribute cannot be
seeded at all: `infrahubctl object load` returns HTTP 500 for a key containing a dot or a
slash. As an attachment it round-trips byte-for-byte.

## SC-003 / T021 — the checksum moves only when the content does

| Step | Checksum |
| --- | --- |
| First upload | `9957f0ff8f41ab6dfd5e7b722b2a9352027906a3` |
| Identical content re-uploaded | `9957f0ff8f41ab6dfd5e7b722b2a9352027906a3` — **unchanged** |
| One line added | `c395480c7b5dcb5937efe22bb4930fdc4525007d` — **moved** |

Both directions, because "unchanged" alone proves nothing if nothing can move it.

⚠️ The first attempt at this measurement was wrong and is recorded rather than quietly fixed:
it compared against the local object's `checksum`, which is `None` until the node is
re-fetched, so it was comparing a real value against nothing. Re-fetching after each save is
what makes the comparison mean anything.

## SC-004 / T023 — one file of each kind per application

Attaching a second `ServiceFabricAppValuesFile` to the same application is rejected by the
server. `uniqueness_constraints: [["app"]]` plus cardinality one (GI-2).

## SC-005 / T024 — files do not outlive their application

Deleting the application removed its attached file. `Component` on the parent side (GI-3).

## SC-008 / T025 — the change was additive

```text
diff baseline.yaml after.yaml
SC-008: BYTE-IDENTICAL — the schema change was additive
```

The `crossplane_fabric_peering` render is unchanged after adding two kinds and two
relationships, which is the strongest available evidence that nothing downstream moved.

**Precisely what this does and does not prove**: the *render* was compared, not a regenerated
artifact object. No artifact exists on the `app-files` branch because no repository sync ran
for it. The artifact's checksum is a function of its content, and the content is unchanged, so
the checksum would be too — but that inference was not executed here, unlike in cycles 011 and
012 where it was.

## SC-009 / T028 — tests and linters

```text
uv run pytest tests/unit          845 passed  (832 + 13 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing in docs/, unchanged
```

`protocols.py` was regenerated and contains both new kinds.

---

## Two pre-existing contract tests had to be narrowed

Adding these kinds broke two tests that had nothing to do with file attachments, and the
reason is worth recording because the fix looks like weakening a guarantee and is not.

`_concrete_service_nodes()` means "every node declared in `schemas/service/*.yml`". Both
invariants below were written against that helper while actually being about **service
kinds**. A payload file lives in the service directory because a service owns it, but it is
not itself a service: no ordered intent, no owner, no status.

| Test | Why it failed | How it was narrowed |
| --- | --- | --- |
| `test_every_concrete_service_kind_is_a_generator_target` | Asserts every node inherits `ServiceGeneric` and `GeneratorTarget`. A file object inherits `CoreFileObject` and should inherit neither | Skips nodes inheriting `CoreFileObject`, via a documented `_is_owned_attachment()` helper |
| `test_no_service_relationship_cascades_into_infrastructure` | FR-053 requires `on_delete: no-action` on service relationships. The new `Component` relationships deliberately cascade — that is GI-3 | Skips relationships whose peer is a service-owned attachment. **The guarantee is untouched**: deleting a service still cannot delete a device or a prefix |

This is the same shape as `NON_AVD_DEVICE_ROLES` in `tests/unit/test_avd.py` — narrowing an
invariant to what it means rather than to what its helper happened to enumerate. A reviewer
should still check the second one deliberately, because "we made a cascade test stop failing"
is exactly the sentence that hides a real bug. What changed is the exclusion of *owned
payload files*; the infrastructure guarantee is asserted unchanged.

## Two discoveries about `CoreFileObject`

**`description` is capped at 128 characters.** The first attempt used a multi-line description
stating the precedence rule in full and was rejected by `schema check` with
`string_too_long`. The rule is now stated tersely in the description and in full in a comment
above it.

**Content must exist before the first save.** `client.create(...)` followed by `save()` raises
`Cannot create ServiceFabricAppValuesFile without file content`. The content is attached with
`upload_from_bytes()` or `upload_from_path()` *before* saving, not uploaded afterwards. This
is why seeding cannot go through `infrahubctl object load` and needs a script.

## Principle IV — the documented alternative

`$infrahub-run-integration-tests` is not installed, the same exception as cycles 010, 011 and
012. The evidence set here: 13 contract assertions over the YAML, a live `schema check` and
`schema load`, live verification of all five graph invariants against a real instance, and the
artifact render comparison. For a purely additive schema change, the render comparison is the
strongest evidence available that nothing downstream moved.
