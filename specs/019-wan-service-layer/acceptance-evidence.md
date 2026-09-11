# Acceptance Evidence

**Feature**: `specs/019-wan-service-layer` | **Date**: 2026-09-11
**Branch**: `wan-svc` (Infrahub) / `019-wan-service-layer` (git)

## SC-001, SC-002 — five services, every relationship resolved

```text
L3VPN  acme-l3vpn    | tenant acme   | vrf CUST_ACME    | circuits ['acme-dr', 'acme-hq']
L3VPN  globex-l3vpn  | tenant globex | vrf CUST_GLOBEX  | circuits ['globex-hq']
INET   acme-internet | l3vpn acme-l3vpn | peering isp-to-internet
CLOUD  acme-cloud    | vrf TENANT_ACME    | zone acme-cloud    | vlan ACME_CLOUD
CLOUD  globex-cloud  | vrf TENANT_GLOBEX  | zone globex-cloud  | vlan GLOBEX_CLOUD
```

Total services across all kinds: **7** — one fabric peering, one fabric app, five WAN. Five of
the six service kinds now have objects; only `ServiceAppAccess` does not.

## SC-003 — exactly one internet-access service

```text
internet access services: 1   (globex has internet: false in the lab)
```

Asserted against the lab file's own `internet` flags rather than against a constant, so adding
a third tenant cannot quietly produce the wrong answer.

## SC-004 — idempotent

Second load: no errors, no duplicates, no uniqueness violations.

## SC-005, SC-006 — transcription and gates

```text
uv run pytest tests/unit          904 passed  (897 + 7 new)
lint-ruff / lint-yaml / lint-mypy / lint-markdown    PASS
lint-prose    7 errors / 4 warnings — pre-existing, unchanged
```

The seed tests compare the object file against `../lab/wan/tenants.yml` field by field — PE
VRFs, DC VRFs, zones, subnets — because nothing else does, and the file is a hand
transcription.

---

## One correction: a superseded contract document was wrong

The first load failed with:

```text
'SecurityZone' HFID does not contain the same number of elements as ['fw1', 'acme-cloud']
```

Cycle 010's `contracts/schema-kinds.md` documents `SecurityZone`'s HFID as
`["device__name__value", "name__value"]`, so a zone reference takes two elements. **That
document is superseded** — its own header says so — because the security domain was
subsequently replaced by the `infrahub/security` marketplace schema, whose `SecurityZone` has a
single-element HFID of `name__value` and no uniqueness constraint.

A zone reference is therefore a scalar. Worth knowing: the superseded sections of that contract
still read as authoritative if you land on them directly, and the marketplace adoption changed
more than the kind list.
