---
title: Add a network segment
description: Request a subnet, VLAN, and gateway SVI on a fabric through the service portal.
audience: user
sidebar_position: 1
---

# Add a network segment

A network segment is the three technical objects a tenant network is made of: an `IpamPrefix`, an `IpamVLAN`, and an `EvpnSvi` giving it a gateway in a VRF. You don't create those yourself. You request one `ServiceNetworkSegment`, and the `generate-network-segment` generator allocates the next free subnet and VLAN ID from the segment pools and builds the three objects on the request's branch.

Prerequisites:

- A running stack with seed data loaded ([Quick Start](../quick-start.md)).
- A provisioned fabric with devices and artifacts ([Provision Your First Fabric](../provision-first-fabric.md)).
- The VRF the gateway lives in must already exist. The segment selects a VRF; it doesn't create one.

## Open the service portal

From the branch desktop, open **`https://10.90.0.11:32001`** and sign in through Dex, for example as `alice@otternet.lab`. See [The service portal](../service-portal.md) for the certificate, and for the one-time Infrahub sign-in every portal user needs.

Open the catalogue and choose the **Network Segment (generated)** template. It's generated from the `ServiceNetworkSegment` schema, so its fields are the kind's own attributes and relationships.

## Fill the form

Leave **What do you want to do?** on **Request a new service**. The fields come from `schemas/service/network_services.yml` and the service generic:

| Field | Required | Notes |
|-------|:--------:|-------|
| **Name** | ✅ | Unique across every service kind. The VLAN and the SVI take this name, so an existing VLAN of the same name is refused rather than adopted. |
| **Owner** | ✅ | The organization ordering the segment. |
| **Tenant** | ✅ | Who the segment is for. |
| **VRF** | ✅ | The routing domain the gateway lives in. |
| **Fabric** | ✅ | Which fabric carries the segment. |
| **AVD Tags** | ✅ | Which leaves carry the segment, for example `k8s` or `app`. Must match a rack's tags, or the SVI renders on no switch. |
| **Prefix Length** | ✅ | Size of the subnet to allocate; defaults to `24`. |
| **VLAN ID** | | Leave empty to allocate the next free ID from the segment pool. That's the normal case. |
| **Description**, **Subnet Pool**, **VLAN Pool** | | Optional. The pools are resolved by role when left empty. |

The subnet, the VLAN, and the SVI aren't on the form, because the generator allocates them.

## Submit

The template then:

1. **Creates a branch** named `implement_<name>`.
2. **Creates the `ServiceNetworkSegment`** on that branch, in the `service_network_segments` group that `generate-network-segment` targets.
3. **Waits for the generators.** The `created` event rule in `triggers.yml` runs `generate-network-segment`, which allocates the subnet and VLAN ID and creates the prefix, VLAN, and SVI.
4. **Opens a proposed change** from the branch into `main`.

When it finishes, the output links to the proposed change in Infrahub, the segment in the catalogue, and the segment in Infrahub.

## Review and merge

In the proposed change:

1. Inspect the **Data** tab — the segment, plus the prefix, VLAN, and SVI its generator created.
2. Inspect the **Artifacts** tab — the proposed change's pipeline runs `generate-avd-device-hostvar` and the structured-config generator, and its artifact checks re-render the EOS configurations. The leaves matching the segment's AVD tags should gain the VLAN and the SVI; the others should be unchanged.
3. Approve and **Merge** when the updated configs look correct.

Once merged, the segment exists on `main`, and the deployment reconciler pushes the new configuration to the switches on its next cycle.

## Without the portal

An operator can make the same request in the Infrahub UI or with `infrahubctl`:

1. Create a branch.
2. Create a `ServiceNetworkSegment` on it with the fields above, as a member of the `service_network_segments` group. The `created` event rule runs `generate-network-segment` on the branch.
3. Optionally run `uv run invoke avd --branch <branch>` to regenerate hostvars, structured configs, and artifacts on the branch before review.
4. Open a proposed change from the branch.

To withdraw a segment, set its **Status** to `decommissioning` on a branch. An `updated` event rule watches that field, so `generate-network-segment` runs on its own: it deletes the subnet, VLAN, and SVI, releases both pools, and sets the status to `decommissioned`.

The same rules re-run the generator when you edit the description, `vlan_id`, `prefix_length`, the VRF, the AVD tags, or either pool. An allocated subnet is never resized; the run logs a warning instead. Decommission the segment and request it again to change the size.

See also [Common Issues](../troubleshooting.md) if a step fails.

## Source

- Service kind: [`schemas/service/network_services.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/service/network_services.yml).
- Generator: [`generators/generate_network_segment.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_network_segment.py).
- Request template generation: [`backstage/plugins/infrahub-backend/src/provider.ts`](https://github.com/opsmill/infrahub-arista-avd/blob/main/backstage/plugins/infrahub-backend/src/provider.ts).
