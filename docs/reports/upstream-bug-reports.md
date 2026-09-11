# Upstream bug reports — drafts for review

**Drafted**: 2026-09-11 | **Found during**: cycles 010–019 | **Infrahub**: 1.10.6, SDK 1.22.0

Four findings worth reporting upstream. **Nothing here has been filed** — these are drafts for
you to review, edit and submit. Two of them are actively shaping this repository's schema, so
they are not academic.

---

## 1. `infrahubctl object load` returns HTTP 500 for a JSON key containing `.` or `/`

**Repository**: `opsmill/infrahub-sdk-python` (the defect is in the object-load path, not the server)
**Severity**: high — it makes a whole class of payload unloadable

### What happens

Loading an object whose JSON attribute has a key containing a dot or a slash fails with
`Internal Server Error`. Worse, it aborts the **entire load**, taking every other object file
with it — a payload file dropped into `objects/` left the branch with no cluster and no devices.

### Why it matters

Every Kubernetes payload has such keys: `app.kubernetes.io/name`, `kubernetes.io/hostname`,
`grafana.ini`, `node-role.kubernetes.io/control-plane`. Any project modelling Kubernetes data
in a JSON attribute hits this immediately.

### The diagnosis, which narrows it considerably

The GraphQL mutation path handles the identical payload correctly — including nested
`{"sub.key/with": "slash"}` — and reads it back byte-for-byte. Probed on the same instance:

| Path | Dotted/slashed JSON key |
| --- | --- |
| GraphQL mutation + query | ✅ works, nested included |
| `infrahubctl object load` | ❌ HTTP 500 |

So this is the SDK's object-load path, not Infrahub's JSON attribute handling. An earlier note
in this repository recorded it as a server bug; that was wrong.

### Repro

```yaml
apiVersion: infrahub.app/v1
kind: Object
spec:
  kind: <any kind with a JSON attribute>
  data:
    - name: probe
      some_json_attribute:
        app.kubernetes.io/name: demo
```

`foo.bar` and `foo/bar` each reproduce it independently; a plain key loads fine.

### Workaround in use here

Payloads moved to `CoreFileObject` attachments uploaded via the SDK (`upload_from_bytes()`),
and label selectors stored as `key=value` string lists that a transform parses back into maps.

---

## 2. `SecurityPolicyRule` ships without a `human_friendly_id`

**Repository**: `opsmill/schema-library` (schema `infrahub/security`, version 1.0.2)
**Severity**: medium — the kind is effectively unloadable in bulk

### What happens

`SecurityPolicyRule` declares `uniqueness_constraints` but no `human_friendly_id`. Loading 19
rules produced **one** rule and eighteen `Violates uniqueness constraint` errors: with no HFID
there is nothing to upsert against, so every row after the first collides.

### Why it matters

A policy rule is inherently a child object — it only means anything within its policy — so bulk
loading is the normal case, and it is exactly the case that fails.

### Suggested fix

```yaml
human_friendly_id:
  - policy__name__value
  - source_zone__name__value
  - destination_zone__name__value
  - index__value
```

### Workaround in use here

`schemas/security_extensions.yml` re-declares the node with that HFID, because an `extensions:`
block cannot add one. Verified idempotent afterwards.

---

## 3. A scheduled flow can be permanently wedged by an orphaned run holding its concurrency slot

**Repository**: `opsmill/infrahub`
**Severity**: high — silent, and it stops repository syncs entirely

### What happens

`git_repositories_sync` is scheduled every minute. On this instance it had not run for **seven
hours**. Every scheduled run was being cancelled with:

```text
Deployment concurrency limit reached.
```

The deployment has a concurrency limit of 1, and a flow run orphaned when the workers restarted
was still holding the slot in `PENDING` with **no start time**. `clean-up-deadlocks` was stuck
the same way, on the same minute — so the mechanism that might have cleared it was itself
blocked by it.

### Why it matters

The only symptom is that repository syncs stop happening. Nothing errors, nothing appears
unhealthy, and a user pushing a commit simply sees it never picked up. It also takes out
`clean-up-deadlocks`, so it does not self-heal.

### Repro

Restart the task workers while a scheduled run is in flight, then watch
`git_repositories_sync`.

### Fix used here

Cancelling the two orphaned `PENDING` runs released both slots and the minute-by-minute
schedule resumed immediately.

### Suggested fix

Release a concurrency slot when its holder is orphaned — either a lease with a TTL, or reaping
`PENDING` runs whose worker is gone.

---

## 4. `infrahubctl check` prints advisory messages at ERROR level

**Repository**: `opsmill/infrahub-sdk-python`
**Severity**: low — cosmetic, but actively misleading

### What happens

When a check fails, `infrahubctl check` prints **every** message at `ERROR` level, including
those logged with `log_info()`:

```text
ERROR  peering_consistency_check: FAILED
ERROR    session 'k8s-leaf1' records peer_asn 64999 …      <- the real failure
ERROR    ADVISORY: EvpnSviNode on app-leaf1 for VLAN …     <- log_info
ERROR    ADVISORY: EvpnSviNode on app-leaf2 for VLAN …     <- log_info
```

Only the first is a failure; the rest are advisory and do not affect the result — confirmed by
reverting the real problem, after which the check passes and the advisories are not printed at
all.

### Why it matters

The SDK has no `log_warning`, so `log_info` with a prefix is the documented way to express a
non-blocking finding. Rendering them identically to failures means a check with one real
problem and thirteen notes reads as fourteen problems.

### Suggested fix

Print `log_info` messages at `INFO`, or omit them from the failure summary.
