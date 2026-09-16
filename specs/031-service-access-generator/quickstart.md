# Quickstart: validating the access grant generator

Proves the claim the spec makes end to end — a grant becomes a firewall rule, the rule reaches the rendered artifact, and the artifact reaches `fw1`. Roughly 15 minutes against a running environment.

**Everything happens on a branch.** The generator writes derived data and the firewall push is a replace; doing either straight onto `main` leaves nowhere to see what changed first.

## Prerequisites

```bash
uv run infrahubctl info          # Connection Status must be ✅
uv run invoke reconcile --once --dry-run   # the lab is up and fw1 is reachable
```

A bootstrapped environment (`uv run invoke bootstrap`) with the fabric, the WAN and `fw1` running. The seeded grant is unapproved, so a fresh bootstrap has the kind populated and nothing generated.

---

## 1. Unit tests — the logic, without a server

```bash
uv run pytest tests/unit/test_app_access_generator.py -v
uv run pytest tests/unit/test_junos_config.py -v
```

**Expected**: both pass. The second matters as much as the first — it holds the rendered Junos artifact byte-for-byte against `junos.conf`, and it must still pass **with the seeded grant present**, because that grant is unapproved and generates nothing. If it fails here, the seed grant was approved by mistake.

Covers FR-070 to FR-073 and SC-006.

---

## 2. The gate — an unapproved grant creates nothing

```bash
uv run infrahubctl branch create access-demo
uv run infrahubctl generator generate-app-access --branch access-demo \
  name=<seeded-grant-name>
```

**Expected**: the generator runs, reports success, and creates nothing. Confirm:

```bash
# no rule named svc-<grant>
uv run infrahubctl object --branch access-demo ...   # or check in the UI
```

**This is the failure mode worth rehearsing**: "ran successfully and did nothing" is exactly what a broken generator looks like. The distinguishing evidence is step 3 producing objects from the same generator with one field changed.

Covers US1-4, FR-030, SC-006.

---

## 3. Approve it — the objects appear

Flip `approved` to `true` on the branch, through the UI or the API, and re-run:

```bash
uv run infrahubctl generator generate-app-access --branch access-demo \
  name=<seeded-grant-name>
```

**Expected**, on the branch:

| Object | Check |
| --- | --- |
| `SecurityIPAMIPAddress` `svc-<grant>-vip` | exists, wraps the grant's `destination_vip`, `book_index` ≥ 1000 |
| `SecurityService` per port | exists for ports with no existing service; ports 80 and 443 **adopt** `junos-http` / `junos-https` instead |
| `SecurityPolicyRule` `svc-<grant>` | exists, `index` ≥ 100, `managed_by_service: true`, correct zone pair |
| the grant's `granted_rules` | names the rule |
| the grant's `status` | `active` |

And the negative that matters:

```bash
# every hand-written rule still reads managed_by_service: false
```

**Expected**: all nineteen. If any baseline rule flipped, the generator marked something it did not create, and revocation would later delete it.

Covers US1-1, US1-5, US1-6, US1-7, FR-020 to FR-024, SC-001.

---

## 4. Idempotence — run it again

```bash
uv run infrahubctl generator generate-app-access --branch access-demo \
  name=<seeded-grant-name>
```

**Expected**: no second rule, no second address entry, no second service object, and no modification to any existing object. Compare the branch diff before and after; it must be empty.

Constitution principle II also requires `$infrahub-test-generator-idempotence` for generator changes where live validation is permitted.

Covers US1-2, FR-025, SC-002.

---

## 5. The rule reaches the artifact

```bash
uv run invoke avd --branch access-demo      # regenerate artifacts on the branch
# then download the junos_config artifact for fw1 and read it
```

**Expected**: the rendered configuration contains a `policy svc-<grant>` block in the derived zone pair, permitting the grant's source address to reach `svc-<grant>-vip` on the permitted ports, and the address book declares `svc-<grant>-vip` after every hand-written entry.

**Download it, do not trust its status.** Generation is asynchronous — the REST endpoint returns 200 and the rendering happens afterwards, so an artifact can report `Ready` and be empty. This is the same trap `scripts/verify_bootstrap.sh` exists to catch.

Covers US3-1, FR-062, SC-004.

---

## 6. The artifact reaches the firewall

```bash
uv run invoke reconcile --once --dry-run --branch access-demo   # reports differs
uv run invoke reconcile --once --branch access-demo             # pushes
uv run invoke reconcile --once --dry-run --branch access-demo   # reports matching
```

**Expected**: `fw1` differs before the push and matches after it.

Two things that read like failures and are not:

- **A diff showing the password hashes changing is Junos, not a credential rewrite.** Junos re-serialises `## SECRET-DATA` with a fresh salt on any load; re-loading the device's own unmodified configuration produces the same diff.
- **Junos reports changed lines on every comparison** — zone-pair ordering and comment round-tripping. That is why `differs` is computed from `deployment/normalise.py` output and never from raw text.

Covers US3-2, SC-004.

---

## 7. Revocation — what it created goes, what it adopted stays

Set `approved` back to `false` and re-run:

```bash
uv run infrahubctl generator generate-app-access --branch access-demo \
  name=<seeded-grant-name>
```

**Expected**:

| | Outcome |
| --- | --- |
| `svc-<grant>` rule | **gone** |
| `svc-<grant>-vip` address entry | **gone** |
| Service objects the generator created | **gone** |
| `junos-http` / `junos-https` | **still there** — adopted, never created, so never deleted |
| All nineteen hand-written rules | **still there**, indices and `book_index` ordering unchanged |

The last two rows are the whole point of story 2. If `junos-https` disappeared, adoption is upserting rather than fetching, and revoking one grant would break the baseline rules that share the port.

Covers US2-1 to US2-4, FR-040 to FR-042, SC-003.

---

## 8. Clean up

```bash
uv run infrahubctl branch delete access-demo
```

The branch was never merged, so `main` is untouched and `fw1` still holds what the branch pushed. Re-run `uv run invoke reconcile --once` against `main` to put it back.

---

## Full-environment check

After merging, the claim that nothing regressed is only worth making from nothing:

```bash
scripts/verify_bootstrap.sh          # ~20 minutes, destroys and rebuilds
```

**Expected**: all sixteen assertions pass with the seeded grant present. "It worked" and "it is stable" are different claims and only a full teardown distinguishes them.

Covers SC-005, SC-007.
