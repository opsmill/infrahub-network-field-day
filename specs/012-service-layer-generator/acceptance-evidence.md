# Acceptance Evidence

**Feature**: `specs/012-service-layer-generator` | **Date**: 2026-09-10
**Branch**: `svc-gen` (Infrahub) / `012-service-layer-generator` (git) | **Infrahub**: 1.10.6

## SC-001 / T029 — sessions derived from cabling

```text
$ uv run infrahubctl generator generate-fabric-peering --branch svc-gen name=nfd41-fabric-peering
INFO  Adopted fabric peering to leaf-nfd41-pod1-1-1 (asn 65101)
INFO  Adopted fabric peering to leaf-nfd41-pod1-1-2 (asn 65101)
```

Two sessions from three cluster nodes across two leaves — `node2` and `node3` both attach to
leaf 2, and the peer set is distinct devices (D-4). No object file was edited to produce them.

## SC-003 / T030 — the adoption was pure

| Field | Before | After |
| --- | --- | --- |
| `name` | `k8s-leaf1`, `k8s-leaf2` | unchanged |
| `peer_address` | `10.110.0.2/24`, `10.110.0.3/24` | unchanged |
| `enabled` | `true` | unchanged |
| `peer_device` | the two leaves | unchanged, and a `DcimDevice` — never a `ComputePhysicalServer` (G-2) |
| `peer_asn` | `65101` (typed into a file) | `65101` (**read from `DcimDevice.asn`**) |

The ASN is the same number reached from the node AVD renders the switch from, which is the
drift this feature exists to remove.

## SC-004 / T031 — the artifact did not move

```text
$ diff baseline.yaml after.yaml
BYTE-IDENTICAL — the refactor changed nothing
```

The single most important check in the cycle: replacing hand-written rows with generated ones
altered nothing that reaches Kubernetes.

## SC-002 / T034 — idempotent

A second run: still two sessions, and the render still byte-identical to the baseline.

## SC-010 / T032, T033 — through the artifact

| | Value |
| --- | --- |
| Checksum before | `0d800c9d5005b5fdb6b371bb5627d143` |
| Checksum after | `0d800c9d5005b5fdb6b371bb5627d143` |
| Artifact count | 1, `Ready` |

That is **exactly the value cycle 011 recorded**, so the artifact is unchanged across two
cycles and a change of mechanism.

The regeneration was confirmed to have executed before the unchanged checksum was believed:
`22:20:54 Beginning subflow run 'Generate artifact Crossplane FabricPeering'`, following the
trigger at `22:20:50`. Cycle 011 found that passing the artifact id where the endpoint wants
the artifact definition id returns HTTP 200 and then fails in the background, which looks
exactly like a passing stability test.

## SC-007 / T038 — a foreign object survives

A `ClusterFabricPeering` the derivation would never produce (`hand-written-do-not-delete`,
peer `app-leaf1`, ASN 64512) was created by hand, then the generator was run:

```text
sessions: 3 [('hand-written-do-not-delete', 64512), ('k8s-leaf1', 65101), ('k8s-leaf2', 65101)]
FR-022 foreign object survived: True
```

This holds by construction rather than by generator code. From `infrahub_sdk/query_groups.py`:

```python
self.unused_member_ids = list(set(existing_group.members.peer_ids) - set(members))
```

Deletion candidates are last run's tracking-group members minus this run's, so an object that
was never a member cannot be one.

The artifact was also unaffected by a third session existing on the cluster, because only the
sessions linked to the *service* render.

## SC-006 / T039, T040 — cleanup removes what it should, and only that

`leaf-nfd41-pod1-1-1`'s role was changed to `isp_edge` so the derivation would stop qualifying
it, and the generator re-run:

```text
INFO  Adopted fabric peering to leaf-nfd41-pod1-1-2 (asn 65101)
INFO  Linked 1 session(s) to the service
sessions now: 2 ['hand-written-do-not-delete', 'k8s-leaf2']
```

Both guarantees held **in the same pass**: `k8s-leaf1`'s session was deleted because it was no
longer justified, and the foreign session survived. The artifact lost exactly that peer:

```diff
19,21d18
<     - name: k8s-leaf1
<       address: 10.110.0.2
<       asn: 65101
```

## SC-005 — a real change moves the checksum

The diff above is the complement of SC-004. Without it, "the checksum did not move" would
prove nothing, because an inert artifact also does not move.

## T041 — restored

Role restored, foreign session deleted, `objects/34_nfd41_cluster.yml` re-loaded, generator
re-run: **byte-identical to the baseline again.**

That restore is also the evidence for T043 — the object file is idempotent and does not
disturb the generated sessions.

## SC-008 / SC-009 — tests and linters

```text
uv run pytest tests/unit          832 passed  (810 + 22 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing in docs/, unchanged
```

`upserting` and `FabricPeeringGenerator` were added to the Vale vocabulary, matching the
existing entries for every other generator class name and `upsert`/`upserted`.

---

## Three things the implementation changed about the design

Each was found by running the code, not by reading the schema.

### 1. There is no "create" path, and there cannot be

`peer_address` is mandatory on `ClusterFabricPeering` and is recorded **only on an existing
session**. A newly cabled leaf therefore has no address the generator is permitted to supply,
and FR-027 forbids inventing or allocating one. Every payload is an adoption; a peer with no
session is refused by name.

This makes US1's original independent test ("delete both sessions, re-run, confirm two
reappear") impossible. The achievable test is the one actually run: adopt, and prove the
artifact is unchanged.

### 2. `save(allow_upsert=True)` cannot express a partial update

Research R3 planned to preserve `name` and `peer_address` by omitting them from the payload.
The first live run rejected that outright:

```text
['ClusterFabricPeeringUpsert', 'data', 'name'] name is mandatory for ClusterFabricPeering
['ClusterFabricPeeringUpsert', 'data', 'peer_address'] peer_address is mandatory
```

An upsert validates every mandatory field on the node. Preserving a value means **fetching the
existing node and setting one attribute**, which R3 had considered and rejected as an
unnecessary round trip. R3's rejection was wrong on the mechanics.

### 3. The query must select `__typename`

The generated models are discriminated unions, but the server returns `__typename` only when
asked. The first run failed with `union_tag_not_found`. Every other `.gql` in the repository
already selects it at union points; this one did not.

---

## The honest limitation: one of two duplicated facts was fixed

**T042 was revised rather than executed.** It called for removing the two hand-written
`ClusterFabricPeering` rows from `objects/34_nfd41_cluster.yml`. That is not possible: those
rows are the only record of each session's `peer_address`, and T041 proved the point — the
restore worked *because* re-loading that file recreated the deleted session. Remove the rows
and a deleted session can never come back.

Ownership is now split, and the file says so:

| Field | Owner |
| --- | --- |
| `name`, `peer_address`, `description`, `svi` | **object data** — authoritative |
| `peer_asn` | **the generator** — the file's value is a seed it overwrites from the fabric |

So `peer_asn` is still *present* in the file but no longer *authoritative*: if it disagrees
with the fabric, the generator corrects it rather than shipping the disagreement. That is a
real improvement over a single hand-maintained copy, and a smaller one than the task assumed.

Removing the rows entirely becomes possible once the leaves' peering SVIs are modelled, which
makes the address derivable exactly as the ASN now is.

### And a correction to the spec's Out of Scope

The spec justified deferring SVI modelling on the grounds that it "is a schema change, so it
is a cycle of its own". **That justification was wrong.** `InterfaceVirtual` already exists —
14 are loaded, including `Loopback0` on every leaf — and `IpamIPAddress.interface` is an
existing relationship. Modelling the two peering SVIs is **object data, not schema**, which
makes the follow-up considerably cheaper than represented when Q2 was answered.

Q2's answer (reuse the recorded address) is still correctly implemented here. But had the cost
of option B been stated accurately, it might have been chosen instead.

### A related discovery: the lab's switches are modelled twice

`k8s-leaf1` / `k8s-leaf2` (ASN 65101) and `leaf-nfd41-pod1-1-1` / `-1-2` (ASN 65101) are the
same two physical switches under two names — the containerlab hostnames and the AVD-generated
fabric names. That is why a session's `name` is not derivable from its `peer_device.name`, and
it is pre-existing in the data rather than anything this cycle introduced. Worth deciding
deliberately, because a check comparing the two ends of a session will have to know it.

## Principle II — the documented alternative

`$infrahub-test-generator-idempotence` is not installed. The constitution permits a documented
alternative; this is it, in increasing strength:

| Layer | Evidence |
| --- | --- |
| Unit | 22 fixture tests covering derivation, dedup, near-end exclusion, role filtering, ordering, adoption, and all seven validation paths — most unreachable live, since the schema forbids the shapes they describe |
| Live | The generator run twice against an unchanged model: same two sessions, same values |
| Observable | The artifact regenerated after each run, checksum unchanged at `0d800c9d…`, and *moved* when the model genuinely changed |

The third layer is stronger than a generic idempotence check: it validates what an operator
consumes, not object counts.

`$infrahub-run-integration-tests` is likewise not installed — the same exception as cycles 010
and 011.
