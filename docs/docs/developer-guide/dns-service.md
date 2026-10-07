---
title: DNS service
description: How the lab resolver gets its names from Infrahub, what each part does, and what was measured.
audience: developer
sidebar_position: 33
---

# DNS service

A branch user who requests an application can view it as `<name>.int.otternet.lab`, for example `otter-shop.int.otternet.lab`. The
name is not entered by the requester. Infrahub derives it from the application, renders it into a zone file, and a CoreDNS server
that runs in the lab's Kubernetes cluster serves that file to the branch machine.

Specification, plan and tasks: `specs/037-lab-dns-service/`.

## The parts

| Part | File | What it does |
| --- | --- | --- |
| Zone | `dns_zone` on the resolver `ServiceFabricApp` (`objects/36_otternet_app_services.yml`) | Holds the zone name, `int.otternet.lab`. Only the resolver has it. |
| Name | `IpamIPAddress.fqdn`, written by `generate-dns-record` (`generators/generate_dns_record.py`) | Puts `<name>.<zone>` on an exposed, live application's VIP address, and takes it off when the application is withdrawn. |
| Artifact | `DNS Zone Configuration`, rendered by `dns_zone_config` (`transforms/dns_zone_config.py`) | One ConfigMap holding the Corefile and the zone file. |
| Delivery | `InfrahubSync` named `dns-zone-config` (`vidra/infrahub-syncs.yaml`) | Vidra applies the ConfigMap into the `otternet-dns` namespace. |
| Resolver | `otternet-dns`, catalogue entry `lab-dns` (`payloads/otternet-dns-values.yaml`) | CoreDNS, installed from the CoreDNS Helm chart, mounting the ConfigMap `lab-dns`. |
| Firewall | Rule `branch-to-dns` (`objects/32_otternet_security.yml`, `lab/configs/fw/vsrx/junos.conf`) | Lets the branch LAN reach the resolver on UDP and TCP port 53 without a request. |
| Branch machine | `dns:` under `branch-desktop` in `lab/wan/tenants.yml` | Adds the resolver as the first nameserver in `/etc/resolv.conf`. |
| Check | `dns-zone-consistency` (`checks/dns_zone_check.py`) | Refuses two resolvers, and a name that points outside its application's VIP block. |

## How a name appears and goes

1. An application is created on a branch. `generate-fabric-app` allocates its VIP block.
2. The block changes the application, which fires `generate-dns-record` (the four rules in `triggers.yml` watch creation, `status`,
   `exposed` and `vip_block`). The generator creates an `IpamIPAddress` for the first address of the block and sets its `fqdn`.
3. The generator asks for the resolver artifact to be rendered again on the same branch, because the artifact's target is the
   resolver and not the application. The proposed change then shows the new record in the artifact difference.
4. After the merge, Vidra applies the ConfigMap. The kubelet projects it into the pod in up to about a minute, and CoreDNS's `file`
   plugin reloads the zone (`reload 10s`) when the serial in the file differs.
5. Setting `status` to `decommissioning` or `decommissioned`, or `exposed` to false, repeats steps 2 to 4 with the name removed.

## Decisions and why

- **The name points at the first address of the VIP block.** Measured on the lab: `otternet-demo`'s block `10.112.240.0/28` gave its
  Service `10.112.240.0`, and `otter-shop`'s `10.112.240.16/28` gave `10.112.240.16`. Cilium creates one `CiliumLoadBalancerIPPool` for each
  application from its block, and an application's first LoadBalancer Service takes the first free address.
- **That rule does not cover an application that pins another address or has several Services.** `otternet-metrics` pins Grafana to
  `10.112.240.81` with `lbipam.cilium.io/ips`, so it has no name from this generator. Seed an address with the `fqdn` instead. The
  generator never moves a name that already has an address.
- **The resolver own address is pinned** the same way (`10.112.240.96`), because the branch machine's setting, the firewall rule and
  the zone's NS record all name it before a generator could choose one. `tests/unit/test_dns_service_contract.py` holds the five places
  that write the address equal.
- **The resolver refuses every name outside the zone** (`rcode REFUSED`). The glibc resolver moves on to the next nameserver on a refusal
  and treats `NXDOMAIN` as final, so the branch machine keeps resolving everything else through the container's own nameserver.
- **The services are the Junos built-ins `junos-dns-udp` and `junos-dns-tcp`.** Services with a `junos-` prefix are not declared in the
  artifact's `applications` stanza, so the firewall baseline needed no application declarations. The `udp` protocol (17) was added as a
  `SecurityIPProtocol` object, which only `tcp` and `icmp` were before.
- **The zone is a derived artifact, not stored nodes.** No new kind was added: withdrawal means there is no live application and so no record.

## What the renderer refuses

- An empty zone. It would remove every name, so the last good ConfigMap stays in the cluster.
- Two addresses for one name.
- A resolver with no name of its own, because the NS record would point at nothing.

## Traps

- **A seeded name needs its own `fqdn`.** No trigger rule fires on `main`, so `generate-dns-record` never runs for seed data. The
  resolver address carries its `fqdn` in `objects/32_otternet_security.yml` for this reason.
- **The artifact lags the code on a demo stack.** `invoke bootstrap --fresh --demo` builds the stack from the remote `main`, so the
  generator, transform and artifact definition arrive only when `invoke demo-advance` brings the local `main` through an Infrahub proposed
  change. Until then the resolver pod waits for its ConfigMap.
- **A resolver that is down delays every lookup on the branch machine** by the resolver timeout, because it is listed first.
- **Do not add a second generator on `ServiceFabricApp` without extending `tests/unit/test_service_trigger_contract.py`.** It holds each
  generator to its own watched fields and its own write-backs.

## Checking it

```bash
# From a shell that can reach the resolver (branch-desktop, or the host through the lab network)
dig +short otternet-dns.int.otternet.lab @10.112.240.96
getent hosts otter-shop.int.otternet.lab      # glibc, as an application would ask
getent hosts example.com                      # a name outside the zone resolves as before

export KUBECONFIG=/home/ubuntu/dev/nfd41/infrahub/lab/k8s/.kubeconfig/kubeconfig.yaml
kubectl -n otternet-dns get pods,cm,svc
```
