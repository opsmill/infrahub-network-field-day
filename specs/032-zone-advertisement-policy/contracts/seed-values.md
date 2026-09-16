# Contract: seed values

Edits the zone rows already in `objects/32_nfd41_security.yml`. A separate
numbered file would define the same six zones twice and leave load order to
decide which won.

## Values

| Zone | `dc_advertised_prefix_list` | `advertising_device` |
| --- | --- | --- |
| `branch` | `PL-DC-ADVERTISED-BRANCH` | `leaf-nfd41-pod1-3-1` |
| `wan` | `PL-DC-ADVERTISED` | `leaf-nfd41-pod1-3-1` |
| `k8s-prod` | — | — |
| `app-prod` | — | — |
| `acme-cloud` | — | — |
| `globex-cloud` | — | — |

`advertising_device` is a relationship to a kind whose `human_friendly_id` is
`name__value`, so the value is the bare device name.

## The evidence for each

**Two zones, because exactly two BGP neighbors carry an outbound route-map**,
both on the border leaf, from `lab/avd/intended/configs/border-leaf1.cfg`:

```text
VRF BRANCH:  neighbor 10.250.70.2 route-map RM-DC-TO-BRANCH out
VRF WAN:     neighbor 10.250.50.2 route-map RM-DC-TO-EXTERNAL out
```

and each route-map matches one prefix list:

```text
route-map RM-DC-TO-BRANCH   permit 10  match ip address prefix-list PL-DC-ADVERTISED-BRANCH
route-map RM-DC-TO-EXTERNAL permit 10  match ip address prefix-list PL-DC-ADVERTISED
```

**`leaf-nfd41-pod1-3-1` is `border-leaf1`**, matched by management address —
Infrahub and ContainerLab name the same box differently and there is no
renaming layer:

```text
lab/nfd41.clab.yml   border-leaf1          mgmt-ipv4 172.20.41.25
Infrahub             leaf-nfd41-pod1-3-1   mgmt_ip   172.20.41.25/24
```

Its role is `leaf`. **No device in this fabric carries the `border_leaf`
role**, which is half of why this relationship exists at all.

## Why four zones stay empty

Not incomplete work. `k8s-prod` and `app-prod` are internal — the DC advertises
nothing toward them; they *are* the DC.

`acme-cloud` and `globex-cloud` look like candidates and are not. Their
prefixes appear **inside** `PL-DC-ADVERTISED`:

```text
ip prefix-list PL-DC-ADVERTISED
   seq 10 permit 10.112.240.0/24 le 32
   seq 20 permit 10.220.10.0/24 le 32     <- acme-cloud
   seq 30 permit 10.220.20.0/24 le 32     <- globex-cloud
```

They are the *subject* of an advertisement toward `wan`, not the *destination*
of one. Recording `PL-DC-ADVERTISED` against `acme-cloud` would invert the
field's meaning and would tell a later generator to add branch VIPs to a
tenant's list.

## What a test must hold

`FR-062` — the seeded values must match the fabric, so the model and the lab
cannot drift silently. The check that matters is the negative one: exactly two
zones populated, and the four above empty.
