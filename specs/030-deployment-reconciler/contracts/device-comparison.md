# Contract: per-family device comparison

The one interface this feature genuinely exposes. Each family implements the same shape; the
bodies differ because the devices differ. Every command below was run against the live lab
(research R1–R3) — these are transcripts, not sketches.

```text
compare(target, artifact) -> Comparison{raw_diff, normalised_diff, differs}
push(target, artifact)    -> str   # already exists in scripts/provision_lab.py
cleanup(target)           -> None  # sweep this service's own leftovers
```

`differs` is `bool(normalised_diff)`. Nothing else may decide whether to push.

---

## EOS — `DcimFabricSwitch`, over eAPI at `mgmt_ip`

**compare**

```text
enable
configure session infrahub-<unix-ts>
rollback clean-config
<artifact lines, trailing `end` stripped, blanks dropped>
end
show session-config named infrahub-<unix-ts> diffs
```

then **always**:

```text
enable
configure session infrahub-<unix-ts> abort
```

**Normalisation**: none. Measured empty for an unchanged device.

**Output shape** when it differs:

```text
--- system:/running-config
+++ session:/infrahub-<ts>-session-config
+ip host probe-marker-does-not-exist 10.255.255.254
```

**Session names must be unique per run.** EOS keeps one *completed* session per name and
refuses to re-enter that name. `provision_lab.py` already carries this scar.

**cleanup**: `show configuration sessions` returns a JSON object keyed by session name. Abort
each key beginning `infrahub-`. Leave every other key alone (FR-031).

---

## FRR — `DcimDevice`, by container name

**compare** — stage into a directory this service owns, never over `/etc/frr/frr.conf`
(bind-mounted read-only by the lab repository):

```text
mkdir -p /tmp/infrahub-reconcile
cat > /tmp/infrahub-reconcile/frr.conf
python3 /usr/lib/frr/frr-reload.py --test \
        --confdir /tmp/infrahub-reconcile /tmp/infrahub-reconcile/frr.conf
```

**Output shape** — sections, **not** `+`/`-` prefixes:

```text
Lines To Add
============
router bgp 65030
 ...
```

**Exit status is meaningless**: `0` whether or not the configuration matches.

**Normalisation is REQUIRED.** An unchanged device reports these every time, because the
artifact states them and `show running-config` never echoes them back:

| Suppressed | Why |
| --- | --- |
| `neighbor <addr> activate` under an IPv4-unicast address-family | FRR's default; omitted from running state |
| `service integrated-vtysh-config` | File directive, not running state |
| `line vty` and its bare `exit` | Same |
| The `router bgp` / `address-family` / `exit` scaffolding **when it encloses only suppressed lines** | Context lines, not changes |

Anything else is a difference (FR-011a, fail-noisy).

---

## Junos — `SecurityFirewall`, by container name, via the vSRX inside it

**compare**

```text
docker exec -i <container> sh -c 'cat > /tmp/infrahub-reconcile.conf'
scp -O <staged> admin@127.0.0.1:/var/tmp/infrahub-reconcile.conf
```

then over the CLI on stdin (`configure` is refused as a remote command):

```text
configure exclusive
load replace /var/tmp/infrahub-reconcile.conf
show | compare
rollback 0
exit
exit
```

**`scp -O` is load-bearing.** Without it the copy fails with
`problem checking file: No such file or directory`, `load replace` does nothing, and
`show | compare` returns empty — which reads exactly like "in sync". Measured.

**`load replace` only**, never `override` or `update`: both were measured against this device
and both delete the `system` stanza, including the `services { ssh; netconf; }` this service
arrives on.

**Normalisation is REQUIRED.** An unchanged device reports 55 changed lines, in two categories
`AGENTS.md` already documents as unclosable:

| Suppressed | Why |
| --- | --- |
| `!    from-zone <a> to-zone <b> { ... }` | Zone-pair *ordering*. No object carries the order; Junos matches on zone, not position. Presentation only |
| Comment blocks (`/* … */`) appearing only as removed-and-re-added | Junos does not round-trip the artifact's comments; the `## SECRET-DATA` re-salting is the same phenomenon |

Anything else is a difference.

**cleanup**: `rollback 0` then `exit` releases the exclusive lock. A cycle killed mid-compare
leaves it held, so cycle start must release a lock this service owns (FR-030).

**Checked on every fourth cycle only** (FR-004) — the exclusive lock is the cost.

---

## Ordering within a cycle

1. Sweep leftovers (EOS sessions, Junos lock).
2. Read intent. Download every artifact; **refuse an empty one regardless of `Ready`** (FR-012).
3. For each device: skip if `suspend`; compare; push if it differs; record.
4. Sweep records whose device no longer resolves.

The firewall is last, and only on every fourth cycle.
