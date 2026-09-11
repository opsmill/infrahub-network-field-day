# Acceptance Evidence

**Feature**: `specs/015-derive-peer-address` | **Date**: 2026-09-11
**Branch**: `peer-addr` (Infrahub) / `015-derive-peer-address` (git) | **Infrahub**: 1.10.6

## SC-001 — the address is derived

```text
leaf-nfd41-pod1-1-1  asn=65101  addr=10.110.0.2/24
leaf-nfd41-pod1-1-2  asn=65101  addr=10.110.0.3/24
```

Both read from the device's `Vlan110` peering SVI. **Both** facts that cycle 012 found
duplicated by hand are now derived from the fabric model.

## SC-002 — the artifact did not move

```text
diff baseline.yaml after.yaml
BYTE-IDENTICAL — deriving the address changed nothing
```

## SC-004 — the create path, which was impossible before this cycle

Both sessions deleted, generator re-run:

```text
INFO  Created fabric peering to leaf-nfd41-pod1-1-1 (asn 65101)
INFO  Created fabric peering to leaf-nfd41-pod1-1-2 (asn 65101)
INFO  Linked 2 session(s) to the service
recreated: 2 — correct devices, ASNs and derived addresses
```

Cycle 012 recorded "there is no create shape, and there cannot be" as a genuine limitation.
It is gone.

**But it has a consequence, and it is the most important finding in this cycle.** A recreated
session is named after its *device*, because `name` is not derivable — so the rendered manifest
changes:

```diff
-    - name: k8s-leaf1
+    - name: leaf-nfd41-pod1-1-1
```

Addresses and ASNs were identical; only the labels moved. This is cycle 012's Q1-C answer
working as designed, and it means **delete-and-recreate is not artifact-neutral**.

## SC-003 — a real change propagates, and drift is reported

An SVI repointed to `10.110.0.9/24`:

```text
WARNING  peer_address drift on leaf-nfd41-pod1-1-1: recorded ...
```

and the manifest followed to `address: 10.110.0.9`. Reverted; byte-identical again.

The warning is the point. An address change moves where BGP points, and an operator sees it in
the run output instead of a later diff.

## SC-005, SC-006 — ambiguity fails

Covered by fixture tests, unreachable live because the schema forbids the shapes: a peer with
no `peering`-role interface, several such interfaces, or one carrying several addresses. Each
raises naming the device, with nothing written.

## SC-007 — idempotent

Repeated runs: same two sessions, same values, byte-identical render.

## SC-009 — tests and linters

```text
uv run pytest tests/unit          859 passed  (855 + 4 net new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing, unchanged
```

---

## SC-008 was unachievable, and this is why

The spec required `objects/34_nfd41_cluster.yml` to lose its `peer_address` values. It cannot:

- `peer_asn` and `peer_address` are both `optional: false` on `ClusterFabricPeering`, so an
  object file cannot declare a session without them.
- Removing them therefore means removing the **rows**, and the rows are what carry `name`.
- Tested: with the rows gone the generator recreates the sessions named after their devices,
  which changes the peer names in the manifest — breaking SC-002, a P1 criterion about not
  changing what reaches the cluster.

So the file keeps both fields as **seeds the generator overwrites**, and the annotation says
so. `name` is the only field it still owns. FR-010 and SC-008 are struck through in the spec
rather than quietly dropped.

This is the same shape as cycle 013's T042: a task that assumed a field could be removed,
defeated by a mandatory-field constraint discovered at implementation time.

## A second finding: `object load` cannot undo a rename

Restoring the deleted-and-recreated sessions by re-loading `objects/34` **did not work**. The
file matches by human-friendly id `(cluster, name)` while uniqueness is `(cluster,
peer_device)`, so a session the generator renamed cannot be matched back by the file that
originally declared it. The names had to be set directly.

Worth knowing before anyone tries to recover from a generator run by re-loading object data.

## Principle II and IV — the documented alternative

Neither `$infrahub-test-generator-idempotence` nor `$infrahub-run-integration-tests` is
installed, the same exception as cycles 010–014. Evidence here: 26 fixture tests including
every ambiguity path, a live double-run, a delete-and-recreate, a real change propagating with
its drift warning, and the artifact compared before and after each.
