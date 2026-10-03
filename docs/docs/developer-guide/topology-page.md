---
title: The topology page and the cables Infrahub holds
description: What the portal Topology page draws, why only some cables are modelled, and what its two controls do.
audience: developer
sidebar_position: 21
---

# The topology page and the cables Infrahub holds

The portal's **Topology** page (`backstage/plugins/infrahub/src/pages/TopologyPage.tsx`) draws every
`NetworkLink` as one picture: spines, leaves, the firewall, the WAN and the customer edges, in rows by
distance from the fabric, with the interface named at each end of every cable. It reads the selected
branch, so a cable added on a branch shows up before it merges. The layout is pure
(`panels/topologyLayout.ts`) and tested without a browser.

**It can only draw cables Infrahub holds, and for a long time that was 17 of the lab's 34.**
`objects/28` recorded the spine-leaf and workload links; the border leaf's firewall handoffs, the WAN and the
MLAG peer links existed only in `lab/otternet.clab.yml`, so the page drew a fabric with nothing around it.
`objects/41_otternet_cabling.yml` holds the 13 that Infrahub can express with ports `objects/` already declares.
Three things about it look like oversights and are not:

- **Links are created bare and the INTERFACES point at them.** A link's `connected_endpoints` takes one interface
  kind per block, and the firewall's ports are `SecurityFirewallInterface`, not `InterfacePhysical`.
- **The four MLAG links are in `objects_post_topology/`, not `objects/`.** Their ports (leaf `Ethernet3` and
  `Ethernet4`) are created by the rack generator, which runs after `invoke load`; a link to a port that does
  not exist yet fails the whole load. `invoke avd --topology` loads that directory once the racks are complete.
  It is an upsert, so re-running it against a built fabric changes nothing.
- **Adding them moved no device.** Regenerated on a branch, the EOS, Junos, SR Linux and Crossplane artifacts were
  byte-identical to `main`. Three artifacts did change, all additively: the cabling plan and the ContainerLab
  topology gain the links, and the Telegraf configuration gains `otternet_intended_link` and
  `otternet_intended_interface_up` series for them, which Vidra then delivers.

**The page has two controls, and both are deliberately modest.** The *Data centre / WAN / Branch* toggles
hide devices and the cables that ran to them but never re-lay-out what is left, so nothing moves while you look
at it; a cable between two domains disappears unless both ends are showing. The domain comes from kind and role
(`domainOf`), not from `location`, which most devices here do not have. The *Deployment state* overlay colours each
device by its `DeploymentState` record, re-read every 30 seconds while it is on. Two readings are on purpose:
an `in_sync` not checked for 20 minutes is shown as **stale**, because the loop that wrote it may be dead, and a
device with no record (the servers, and `cust-acme-dr-ce`, which the reconciler does not manage) is **no
record**, not a fault. `DeploymentState` is branch-agnostic, so the overlay describes the devices as they are
whichever branch is selected.

**No BGP overlay exists, because the portal cannot reach the data.** Session state lives in Prometheus, which
is a `ClusterIP` Service in `otternet-metrics`; only Grafana has a LoadBalancer VIP, and reaching either from the
tooling zone would need the same three gates a `ServiceAppAccess` grant opens (route, firewall rule, pod policy).

Not drawn, because Infrahub has no object for the other end: `fw1` `ge-0/0/6` (the tooling bridge) and the hosts
behind the customer, internet and branch routers.
