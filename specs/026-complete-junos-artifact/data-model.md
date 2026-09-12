# Phase 1 Data Model: Completing the Perimeter Firewall Artifact

**Cycle**: 026 | **Date**: 2026-09-12

One new schema attribute, one seeded value, and two additions to the render context. Everything
else this cycle emits is template text.

## The one schema change

`schemas/security_extensions.yml`, the local extension file that already carries `book_index` on
`SecurityGenericAddress` and `log_session_close` on `SecurityPolicyRule` — both added by cycle 023
in this exact shape.

```yaml
extensions:
  nodes:
    - kind: SecurityFirewall
      attributes:
        - name: tcp_mss
          kind: Number
          label: TCP MSS Clamp
          optional: true
          description: "..."
```

| Property | Value | Why |
| --- | --- | --- |
| `kind` | `Number` | the device writes `mss 9138` |
| `optional` | **`true`** | a firewall with no clamp must render **no** `flow` stanza |
| default | **none** | a default would render `mss 0` or an empty block on a future firewall |

`schemas/security/security.yml` is marketplace-adopted and is **not** touched. `SecurityFirewall`
gains the attribute through the local extension, exactly as `SecurityPolicyRule` gained
`log_session_close`.

## The one seeded value

`objects/32_nfd41_security.yml`, on the existing `SecurityFirewall` entry for `fw1`:

```yaml
tcp_mss: 9138
```

Transcribed from the device file. The comment block above `flow` gives the arithmetic:
`9192 - 14 (Ethernet) - 20 (IP) - 20 (TCP) = 9138`.

This is an attribute of the firewall, so it goes on the firewall's existing entry rather than in a
new file.

## The render context

`transforms/junos_config.py` gains two keys.

### `static_routes`

A list, one entry per `RoutingStaticRoute` on the firewall, read through
`SecurityFirewall.static_routes` — the relationship cycle 024 created and cycle 025 populated.

| Key | Source | Used for |
| --- | --- | --- |
| `prefix` | `prefix` | the destination |
| `next_hop` | `next_hop` | the gateway |
| `comment` | `route_name` | the `/* … */` text |
| `pad` | **derived** | spaces before `next-hop` |
| `gap` | **derived** | spaces before the comment |

**Order**: deterministic, and the file's order is reproducible from the data. Unlike cycle 023's
zone-pair policies — where Junos evaluates first-match and order is semantic — static routes are
longest-prefix matched, so no behaviour depends on the sequence. Ordering is therefore a
presentational choice this cycle is free to make, and it makes the one that matches the file.

### `tcp_mss`

An integer or `None`. `None` means render no `flow` stanza at all.

## The two derived spacing values

This is the cycle's one piece of real derivation, and [research.md](./research.md) R1 is the
evidence for it.

**The alignment invariant is the semicolon, not the comment.** It lands at column 50 on all eight
lines:

```text
        route 10.110.0.0/24 next-hop 10.250.110.1;   /* k8s nodes */
        route 10.60.0.0/16  next-hop 10.250.150.1;   /* WAN customer supernet */
        route 10.220.10.0/24 next-hop 10.250.10.1;  /* acme cloud instances */
                                                 ^
                                              column 50
```

| Value | Rule | Nature |
| --- | --- | --- |
| `pad` | `max(1, 14 - len(prefix))` | **a real alignment rule** — pads the prefix field so the `;` lines up |
| `gap` | `3 if len(next_hop) == 12 else 2` | **reproduces an inconsistency**, not a rule |

Tested against the file: **8/8 byte-exact.**

### Why `gap` must be commented as what it is

Six lines carry three spaces before the comment and two carry two. The next-hop length correlates
perfectly over this data, but it is not the *cause* — the cause is that two lines were typed one
space short. Stating that in the code matters, because the alternative readings are both wrong:

- a reader who thinks it is an alignment policy will "fix" the two lines and break SC-001;
- a reader who thinks it is arbitrary will store the spacing in the model, which is presentation
  in the data.

A test pins both cases, so a tidy-up fails loudly.

**Nothing is stored.** Both values are computed at render time from `prefix` and `next_hop`.

## The stanza the transform emits

```text
routing-options {
    static {
        route <prefix><pad>next-hop <next_hop>;<gap>/* <comment> */
        …
    }
}
```

Position: between `interfaces` and `security`, as in the device file. Omitted entirely when the
firewall has no routes — an empty `static { }` is not what the device would hold.

## The `flow` stanza

```text
    flow {
        tcp-mss {
            all-tcp {
                mss <tcp_mss>;
            }
        }
    }
```

The **first** block inside `security`, before `address-book`, preceded by its 6-line comment.
Omitted entirely when `tcp_mss` is unset.

## The three comment blocks

Template text only — no data, no schema.

| Lines | Position | Subject |
| --- | --- | --- |
| 6 | before `flow` | the clamp arithmetic |
| 4 | before `address-book` | why the book uses named objects rather than bare CIDRs |
| 9 | after the address book | **why NAT is absent, and that its absence is load-bearing** |

The NAT block is the one that justifies the effort. It records that a source-NAT rule here would
translate real pod addresses and silently make every downstream ACL meaningless, and that
`make verify` checks no `nat` stanza has appeared. It documents an *absence*, which nothing in the
model can imply — so if the renderer does not carry it, it is lost.

## What this cycle reads and does not change

| Thing | Treatment |
| --- | --- |
| The eight `RoutingStaticRoute` objects | read through `SecurityFirewall.static_routes` |
| `RoutingStaticRoute` schema | unchanged — cycle 024 did that work |
| `schemas/security/security.yml` | untouched, byte-identical to the marketplace |
| The `system` stanza | never modelled, never queried |
| Zone-pair rule order | untouched; first-match order is semantic and already pinned |
| Artifact definition, transform registration, target group | already correct |

## The accounting this cycle closes

```text
677 total = 592 rendered + 13 system + 72 header
```

Verified by computation, and SC-010 requires a **test** to assert it rather than a comment
claiming it — cycle 023 had a comment, and its total was wrong by seven lines.

The two excluded regions are excluded for **different reasons**, and the artifact's own
documentation should say so: `system` is configuration deliberately never modelled (credential
hashes), while the 72-line header is 68 comments and 4 blanks of lab documentation *about* the
file, replaced by the artifact's own provenance line.
