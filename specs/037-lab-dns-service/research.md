# Research: Lab DNS Service

Each finding comes from a file in this repository. Where the files do not say, the finding says it is not verified.

## R-1: The firewall does not let the branch reach the resolver {#r-1}

- **Finding**: the branch zone may reach only the `access-portal` VIP, and "the branch -> k8s-prod zone pair permits branch-users to reach it and nothing else" ([objects/38_otternet_access_grants.yml](../../objects/38_otternet_access_grants.yml)). A resolver VIP is a different address.
- **Finding**: a seeded access grant was removed because "an ungated seed grant would materialise a rule, a service object and an address-book entry into the default data set permanently", and the rendered Junos artifact is "held byte-for-byte against the hand-written baseline on fw1" (same file). Whether a test enforces that today was not checked.
- **Decision (Alex Gittings, 2026-10-07): access is allowed in the bootstrapped version.** The rule is seed data, so the branch can query the resolver as soon as bootstrap ends, with no request step. The earlier option of creating a grant after bootstrap is rejected.
- **What this changes**: the oracle for the firewall is the device's own file, [lab/configs/fw/vsrx/junos.conf](../../lab/configs/fw/vsrx/junos.conf), and [tests/unit/test_junos_config.py](../../tests/unit/test_junos_config.py) holds the rendered artifact against it. The rule, its address-book entry and the two application declarations (`dns-udp`, `dns-tcp`) must be added to `junos.conf` and to the seed in the same change, and the reconciler pushes the result to `fw1` ([AGENTS.md](../../AGENTS.md)). Which other tests pin the baseline (`test_junos_seed_data.py` and `test_security_schema_contract.py` also mention it) was not read in detail and is a task.
- **The rule**: on the `branch` to `k8s-prod` pair, after the `branch-to-access-portal` rule, `branch-users` may reach a new address-book entry for the resolver's VIP on UDP and TCP 53. The deny-spoofed-infra rule stays first ([objects/32_otternet_security.yml](../../objects/32_otternet_security.yml)).
- **Not verified**: whether the resolver's VIP block is advertised by the border leaf and permitted by the leaves' inbound route policy. The VIP must sit inside the cluster's `vip_pools` supernet or "a block from anywhere else is advertised and refused" ([backstage/catalog/exposed-app-with-access.yaml](../../backstage/catalog/exposed-app-with-access.yaml) comment).

## R-2: Deliver the zone the way the telemetry configuration is delivered {#r-2}

- **Finding**: the collector's configuration is a ConfigMap artifact, `Telemetry Collector Configuration`, delivered into `otternet-telemetry` by an `InfrahubSync` and picked up by the running pod about a minute after a merge ([vidra/infrahub-syncs.yaml](../../vidra/infrahub-syncs.yaml)). The transform refuses an empty result ([transforms/telemetry_collector_config.py](../../transforms/telemetry_collector_config.py)).
- **Finding**: the artifact's target is the collector, so a change to an application does not change the target. `generate-monitoring-collector` exists to re-render it ([.infrahub.yml](../../.infrahub.yml)). The DNS artifact has the same shape and needs the same kind of generator.
- **Decision**: one transform renders one ConfigMap holding the Corefile and the zone file. One `InfrahubSync` delivers it. CoreDNS's `reload` plugin picks up changes. [CLAUDE RECOMMENDED – based on the telemetry precedent] Not verified: that the CoreDNS Helm chart can mount an existing ConfigMap in place of its own Corefile, which chart version to pin, and that the chart repository is reachable from the cluster (the `whoami` entry uses a GitHub Pages repository, so outbound access exists, [objects/35a_otternet_app_catalogue.yml](../../objects/35a_otternet_app_catalogue.yml)).
- **Alternative rejected**: render the resolver as raw manifests. The catalogue entry comment says an application is "a chart and nothing else" since cycle 033, so a chart keeps it consistent.

## R-3: Which address the Service receives {#r-3}

- **Finding**: Infrahub allocates a prefix (`vip_block`, a /28 by default) per application ([schemas/service/kubernetes_services.yml](../../schemas/service/kubernetes_services.yml)). The files read do not say how the LoadBalancer picks an address inside it.
- **Risk**: if Cilium hands the Service any free address in the pool, the name for decision 1 (first address of the block) can point at an address no Service holds.
- **Options**:
  - A. Pin the Service's address through the chart values on the catalogue entry. Not verified that the Cilium version in the lab supports the annotation.
  - B. Read the assigned address back from the cluster. This breaks "Infrahub is the source", and the lab's handover removes cluster-side state.
  - C. Change decision 1 so the name points at the block's network, which is not an address a host holds. Rejected: it cannot answer.
- [CLAUDE RECOMMENDED – based on `externalTrafficPolicy` and labels already being set through catalogue values] Option A, checked first in the quickstart against the live cluster before any generator is written.

## R-4: The branch machine's resolver setting {#r-4}

- **Finding**: `lab/wan/render.py` reads only `lab/wan/tenants.yml`. The branch desktop's address, gateway and interface are there ([lab/wan/tenants.yml](../../lab/wan/tenants.yml)). No `nameserver`, `resolv` or `dns` line exists in `lab/wan/` or in the desktop image.
- **Finding**: the repository already keeps two copies equal with a test: the admin password hash in `tenants.yml` and in the Infrahub seed ([lab/wan/tenants.yml](../../lab/wan/tenants.yml) comment, [tests/unit/test_srl_config.py](../../tests/unit/test_srl_config.py)).
- **Decision**: the resolver address appears once in `tenants.yml` and once in the seeded Infrahub object, with a test holding them equal. FR-021 is amended from "MUST NOT be typed into the lab's ContainerLab files" to "MUST be held equal to the address Infrahub holds". [CLAUDE RECOMMENDED – based on the existing hash test]
- **Not verified**: whether the desktop's `init.sh` can set a per-zone resolver (the image installs `dnsutils`; a systemd-resolved split-DNS setting is not available in a container without systemd, so a `dnsmasq` forwarder or a `search`/`nameserver` line in `/etc/resolv.conf` is the likely route).

## R-5: UDP is not a protocol in the data {#r-5}

- **Finding**: [objects/32_otternet_security.yml](../../objects/32_otternet_security.yml) seeds `tcp` (6) and `icmp` (1) only.
- **Finding**: the Junos transform declares an application from `protocol.node.name.value` and refuses a service with a port and no protocol ([transforms/junos_config.py](../../transforms/junos_config.py)). A `udp` object named `udp` flows through.
- **Decision**: add `udp` (protocol 17) and two `SecurityService` objects, DNS over UDP and DNS over TCP, both on port 53.

## R-6: Withdrawal {#r-6}

- **Finding**: a withdrawn application is `decommissioning` or `decommissioned`, and every write-back must be guarded so the rules terminate ([AGENTS.md](../../AGENTS.md)).
- **Decision**: the generator sets `fqdn` only on an address it created in the application's block, and clears and deletes only what it created. [CLAUDE RECOMMENDED – based on `vip_block_managed`, the same guard for the same reason] This needs a way to know it created the address. The plan uses the `fqdn` value itself: an address whose `fqdn` ends with the zone belongs to DNS. No new managed flag is added.
- **Trigger rule**: the application is a `Service*` kind, not a `Deployment*` or `Monitoring*` kind, so a rule on it is allowed.

## Results measured on the running lab {#results}

Measured on 2026-10-07 after `invoke bootstrap --fresh --demo` and `invoke demo-advance`.

- **R-3 (which address the Service receives): the first address of the block, for one Service per application.**
  `otternet-demo` (block `10.112.240.0/28`) gave `10.112.240.0`, and a requested application with the block `10.112.240.16/28` gave
  `10.112.240.16`, which the zone also named. An application that pins another address does not follow the rule: Grafana pins
  `10.112.240.81` inside `10.112.240.80/28`, so its name is seeded with that address, and a contract test holds every exposed
  seeded application to this. Pinning with `lbipam.cilium.io/ips` works on the lab's Cilium 1.18.6, and the resolver uses it.
- **R-2 (the chart): CoreDNS chart 1.48.2 works as planned.** `deployment.skipConfig: true` makes the chart mount a ConfigMap named
  for the release (`fullnameOverride: lab-dns`), and `zoneFiles` is needed only for its `filename`. One Service carries UDP and TCP
  on port 53. The pod ran and the ConfigMap arrived through the new `dns-zone-config` sync.
- **R-1 (the firewall): the seeded `branch-to-dns` rule works.** The reconciler converged with `differed=0` on `fw1`, and
  `branch-desktop` queried the resolver straight after bootstrap with no request made. The services are the Junos built-ins
  `junos-dns-udp` and `junos-dns-tcp`, so `junos.conf` gained only an address-book entry and a policy, and no application declarations.
- **Timings, request to name:** the name was written on the request's branch 20 seconds after the application was requested.
  After the merge the record reached the resolver's ConfigMap in 15 to 75 seconds, and the name resolved from `branch-desktop` 10 to
  30 seconds after that. A withdrawal took 60 to 75 seconds to leave the ConfigMap and 70 seconds more to stop resolving.
- **Two generator runs raced and made a branch unmergeable.** The created event and the arrival of the block each fired
  `generate-dns-record`, and both created the same address. The unique constraint holds at merge, not at write, so the merge failed.
  Found only by requesting an application and merging it. Fixed by naming the namespace in the create and by removing duplicates the
  generator created; see [the generator](../../generators/generate_dns_record.py).
- **Not done: the integration suite** (`uv run invoke test --integration`), which starts a separate Infrahub stack in Docker. The
  end-to-end request, merge, resolve, withdraw and resolve again cycle was run by hand against the live lab instead, twice, and
  passed both times (the first run after a fix for the race, the second from a clean start).
- **Platform stall, unrelated to this feature:** see [repository sync](../../docs/docs/developer-guide/repository-sync.md).
