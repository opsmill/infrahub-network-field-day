# Contract: the two fields

Both land in the existing `extensions.nodes` entry for `SecurityZone` in
`schemas/security_extensions.yml`, beside `trust_level` and `vrf`.

## Shape

```yaml
extensions:
  nodes:
    - kind: SecurityZone
      attributes:
        - name: dc_advertised_prefix_list
          kind: Text
          label: DC Advertised Prefix List
          optional: true
          order_weight: 1300
          description: >-
            Name of the prefix list governing what the DC advertises TOWARD
            this zone. A soft reference into custom AVD hostvars, not a
            relationship: nothing enforces that it resolves.
      relationships:
        - name: advertising_device
          peer: DcimFabricSwitch
          label: Advertising Device
          kind: Attribute
          cardinality: one
          optional: true
          identifier: security_zone__advertising_device
          order_weight: 940
          description: >-
            The fabric switch that applies that prefix list to a BGP neighbor.
```

Plus the inverse, so the link is navigable from the switch:

```yaml
    - kind: DcimFabricSwitch
      relationships:
        - name: advertised_zones
          peer: SecurityZone
          kind: Generic
          cardinality: many
          optional: true
          identifier: security_zone__advertising_device
          order_weight: 3200
```

## Five things that are easy to get wrong

| # | Trap | Consequence |
| --- | --- | --- |
| 1 | `peer: DcimDevice` | Loads, validates, **matches nothing**. `DcimDevice` is the WAN's FRR routers in this repository. |
| 2 | Mismatched `identifier` between the two sides | Two independent relationships that each look correct and never connect. |
| 3 | `cardinality` omitted on `advertising_device` | Defaults to `many`. Relationship defaults differ from attribute defaults. |
| 4 | `optional` omitted on `dc_advertised_prefix_list` | Attributes default to **mandatory**, and six zone objects already exist without it — they stop loading. |
| 5 | Adding `on_delete: cascade` | Deletes the *peer*: removing a switch deletes the security zone. `schema check` accepts it silently. |

## What must NOT appear

- Any new node or generic. FR-003 makes this a tripwire: needing one means the
  design drifted toward migrating the fabric's BGP policy rather than
  referencing it.
- Any edit to `schemas/security/security.yml`. Local additions go in the
  extensions file so a later `marketplace get` diffs cleanly.
- Any change under `schemas/routing/`. `RoutingPrefixList` stays AVD output.

## After loading

```bash
uv run infrahubctl schema check schemas/
uv run infrahubctl schema load schemas --branch <b>
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

`protocols.py` is generated. Regenerate it; never hand-edit it to satisfy a
linter.
