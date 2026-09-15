# Quickstart: validating the deployment reconciler

**Feature**: `specs/030-deployment-reconciler`

How to prove this works. Every command below was run against the live lab during Phase 0, so a
failure here means something changed rather than that it was never tried.

## Prerequisites

```bash
uv sync --all-packages
uv run infrahubctl info          # Connection Status must be ✅
docker ps --format '{{.Names}}' | grep -c clab-nfd41   # the lab must be up
```

The device credentials default to the lab's own (`admin` / `admin` for EOS, `admin` /
`admin@123` for the vSRX) and are overridden by `NFD41_EOS_PASSWORD` and
`NFD41_VSRX_PASSWORD`. If Infrahub returns `401`, export the token the stack was started with.

---

## 1. The single most important test: an in-sync fabric must be silent

This is the one that catches the defect Phase 0 found. Run a compare-only pass across every
device and confirm **nothing** is reported as differing.

**Expected**: every device reports no difference. If any FRR router or the firewall reports a
difference on a fabric nobody has touched, normalisation (FR-011a) is wrong or missing, and the
reconciler would replace that device's configuration on every cycle forever.

**Do not accept an empty result as a pass without step 2.**

## 2. Prove the comparison is live, per family

An empty diff is worth nothing on its own — it is indistinguishable from a comparator that
silently returns nothing. For each family, inject a known difference into a *copy* of the
artifact, compare, and confirm the injected line comes back attributed. Never commit it.

| Family | Injection that worked in Phase 0 | Expected |
| --- | --- | --- |
| EOS | `ip host probe-marker-does-not-exist 10.255.255.254` | `+ip host probe-marker…` under `--- system:/running-config` |
| FRR | `ip route 10.255.255.0/24 Null0` | the route appears under `Lines To Add` |
| Junos | a `/* marker */` comment inside `security` | `+   /* marker */` in `show | compare` |

Then confirm the device did **not** change:

```bash
# EOS
… show running-config | include probe-marker      # must be empty
# FRR
docker exec clab-nfd41-branch-rtr vtysh -c "show running-config" | grep 10.255.255.0   # empty
# Junos
… show configuration | compare rollback 1          # empty means nothing was committed
```

## 3. Confirm nothing was left behind

```bash
# every switch must report no sessions
… show configuration sessions     # {} on all seven
```

The firewall must be committable — a held exclusive lock is the failure this checks for.

## 4. The loop

| Check | Expect | Requirement |
| --- | --- | --- |
| Start with an interval below 60s | **Refuses to start**, with the floor named | FR-003 |
| Start with no interval set | Runs at 600s | FR-002 |
| Watch four consecutive cycles | The firewall is compared on exactly one of them | FR-004 |
| Make a cycle outrun its interval | The next cycle is **skipped**, not queued | FR-005 |
| Stop Infrahub, run a cycle | No device is changed | FR-013 |

## 5. State in Infrahub

| Do this | Expect | Requirement |
| --- | --- | --- |
| Run one cycle on an in-sync fabric | Every device has one record; `status` `in_sync`; `last_confirmed_at` moved | FR-020, FR-021 |
| Run a cycle where one device differs | That device's `last_checked_at` moved but `last_confirmed_at` did **not** | FR-021, FR-022 |
| Read a record after a failure | `status` `failed`, `last_error` populated, retried next cycle | FR-017 |
| Count writes across ten in-sync cycles | ~1 field per device per cycle, not 7 | FR-028, research R8 |
| Delete a device, run a cycle | Its record is swept | FR-025 |

## 6. Suspend

```bash
# set suspend on one device's record, change its intent, run a cycle
```

**Expect**: that device is never connected to — no session opened, no lock taken — while
another changed device is reconciled normally. Its `status` and `last_checked_at` are both
unchanged: a device nobody looked at must not get a moving timestamp.

## 7. Drift, and the distinction that matters

Change a device by hand without touching Infrahub, then run a cycle.

**Expect**: the difference is detected even though the artifact checksum has not moved; the
record reads `drifted` rather than `pending`; the device is corrected without anyone being
asked; and the normalised diff is attached as a `DeploymentDiffFile`.

`pending` vs `drifted` is the only use of the artifact checksum in the whole design — it does
not decide whether to push, only which cause to record.

## 8. Dry run against a branch

**Expect**: differences reported, **no device changed**, and **no `DeploymentState` created or
modified**. Check the record count before and after; deployment state is a fact about `main`.

## 9. The lift

```bash
uv run pytest tests/unit
uv run invoke lint
uv run invoke provision --dry-run
uv run invoke provision
```

**Expect**: `invoke provision` behaves exactly as before (FR-051) — the command stays, its
implementation moves. The guards gain tests that run with no lab and no Infrahub: the
trailing-`end` strip, the management lifeline check, the Junos scope assertion, and the
normalisation rules against captured real device output.

## 10. Full gate

```bash
uv run pytest tests/unit
uv run invoke lint
uv run pytest tests/integration      # this cycle has real Infrahub interactions
```

Unlike cycle 029, the constitution's integration gate applies properly here.

---

## Rolling back

The service is additive: a new module, a new compose service, and tests. Stopping the container
stops all of it, and `invoke provision` remains the manual path it has always been (FR-073).
Nothing about the artifact chain or the schema changes.
