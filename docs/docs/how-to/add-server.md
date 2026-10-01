---
title: Add a server
description: Request a physical server in a compute rack and let the fabric cable it.
audience: user
sidebar_position: 2
---

# Add a server

Places a new physical server into a compute rack. You request one `ServiceServerPlacement`; its generator, `generate-server-placement`, creates the `ComputePhysicalServer` from a template and adds it to the `servers` group, and the server-cabling generator then cables it to the rack's leaves. The request runs on its own branch and ends in a proposed change.

Prerequisites:

- A running stack with seed data loaded ([Quick Start](../quick-start.md)).
- A provisioned fabric with at least one **compute** rack ([Provision Your First Fabric](../provision-first-fabric.md)).
- At least one `TemplateComputePhysicalServer` template, for example the seeded `otternet-workload-host`.

## Open the service portal

From the branch desktop, open **`https://10.90.0.11:32001`** and sign in through Dex, for example as `alice@otternet.lab`. See [The service portal](../service-portal.md) for the self-signed certificate and the one-time Infrahub sign-in every portal user needs.

Open the catalogue and choose the **Server Placement (generated)** template. It's generated from the `ServiceServerPlacement` schema, so its fields are the kind's own attributes and relationships.

## Fill the form

Leave **What do you want to do?** on **Request a new service**. The fields come from `schemas/service/onboarding_services.yml` and the service generic:

| Field | Required | Notes |
|-------|:--------:|-------|
| **Name** | ✅ | The service's name, unique across every service kind. |
| **Owner** | ✅ | The organization ordering the machine. |
| **Hostname** | ✅ | The machine's name, which is also its ContainerLab node name. |
| **Role** | ✅ | `compute`, `storage`, or `k8s_node`; defaults to `compute`. |
| **Rack** | ✅ | The rack the machine goes in. Its leaves are what the machine gets cabled to. |
| **Object Template** | ✅ | Supplies the machine's interfaces. Without one there is nothing to cable. |
| **Tenant**, **Description** | | Optional. Set a tenant when the machine isn't shared infrastructure. |

The server itself isn't on the form, because the generator creates it.

## Submit

The template then:

1. **Creates a branch** named `implement_<name>`.
2. **Creates the `ServiceServerPlacement`** on that branch, in the `service_server_placements` group that `generate-server-placement` targets.
3. **Waits for the generators.** The `created` event rule in `triggers.yml` runs `generate-server-placement`, which creates the `ComputePhysicalServer` with status `provisioning` and adds it to the `servers` group. Creating the server fires the event rule that runs `generate-server-cabling`, and the group membership is what puts the server in that generator's targets.
4. **Opens a proposed change** from the branch into `main`.

When it finishes, the output links to the proposed change in Infrahub, the placement in the catalogue, and the placement in Infrahub.

## Review and merge

In the proposed change:

1. **Data tab** — confirm the placement, the new server, its interfaces, and its cabling.
2. **Artifacts tab** — the proposed change's pipeline regenerates hostvars and structured configs and re-renders the EOS configurations. The leaves this server cables into should gain the new access or trunk ports.
3. Approve and **Merge**.

## Automated cabling flow

The server-cabling generator runs when a `ComputePhysicalServer` is created, against the `servers` group. `generate-server-placement` creates the `ComputePhysicalServer` and its `servers` group membership in the same upsert, so the cabling generator sees the target as a group member as soon as it runs.

For a newly added server, the generator:

1. Reads the server rack and server interfaces from the generator query.
2. Finds leaf switches in the same rack and their `server` role physical interfaces.
3. Selects the first available leaf port index that is free on all target leaves.
4. Creates `NetworkLink` objects between the server interfaces and selected leaf physical interfaces.
5. For dual-homed, multi-leaf servers, creates server-side `Bond1`.
6. Creates one switch-side `InterfaceLag` named `Port-Channel<ID>` on each attached leaf. The `channel_id` is derived from the selected leaf port number and is owned in Infrahub.
7. Attaches each leaf physical interface to its local switch-side LAG.
8. Applies tagged and untagged VLANs. Single-homed servers use the paired leaf physical interface; dual-homed servers merge VLAN intent onto server `Bond1` and the switch `Port-Channel<ID>` objects instead of the member Ethernet interfaces.
9. For idempotence, reconciles already-cabled servers by rebuilding the cabling plan from existing `NetworkLink` objects, then reapplying VLANs and LAG state.
10. Sets EVPN Ethernet Segment on switch-side LAGs when the server is attached across non-MLAG leaves.
11. Marks AVD hostvars as not ready for the fabric and triggers hostvar generation, which cascades into structured config generation.

The resulting hostvars include `port_channel.channel_id` for switch-side server LAGs, so PyAVD receives the explicit Port-Channel ID from Infrahub. For bonded servers, VLAN mode and VLAN lists are derived from the logical Bond or Port-Channel VLAN relationships, not from member Ethernet ports.

## If the configs didn't change

If the proposed change shows the server but no updated device configs:

1. Open the proposed change's branch in the Infrahub UI.
2. Navigate to **Actions → Tasks** and check the status of the placement, cabling, hostvar, and structured-config generator runs.
3. If the AVD generators didn't run, regenerate them on the branch with `uv run invoke avd --branch <branch>`.

## Without the portal

An operator can make the same request in the Infrahub UI or with `infrahubctl`: create a branch, create a `ServiceServerPlacement` on it with the fields above as a member of the `service_server_placements` group, and open a proposed change. The `created` event rule runs the placement generator on the branch, exactly as it does for a portal request.

See [Common Issues](../troubleshooting.md) for more.

## Source

- Service kind: [`schemas/service/onboarding_services.yml`](https://github.com/opsmill/infrahub-arista-avd/blob/main/schemas/service/onboarding_services.yml).
- Generators: [`generators/generate_server_placement.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_server_placement.py) and [`generators/generate_server_cabling.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/generators/generate_server_cabling.py).
- Request template generation: [`backstage/plugins/infrahub-backend/src/provider.ts`](https://github.com/opsmill/infrahub-arista-avd/blob/main/backstage/plugins/infrahub-backend/src/provider.ts).
