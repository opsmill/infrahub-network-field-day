---
description: "Task list for the Lab DNS Service"
---

# Tasks: Lab DNS Service

**Input**: Design documents from `specs/037-lab-dns-service/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/zone-artifact.md](./contracts/zone-artifact.md), [quickstart.md](./quickstart.md)

**Tests**: included, because the [constitution](../../.specify/memory/constitution.md) (principle IV) requires a test for every generator and transform.

**Format**: `- [ ] T### [P?] [Story?] Description with file path`. `[P]` means the task touches a different file from every unfinished task before it.

## Phase 1: Checks that decide the design

These three checks are run against the live lab. If one fails, stop and return to [research.md](./research.md) before writing code.

- [ ] T001 Run quickstart step 1: compare a live application's LoadBalancer address with its `vip_block`, and find a chart value that fixes the Service address to the first address of the block on the lab's Cilium version. Record the result under [research R-3](./research.md#r-3).
- [ ] T002 [P] Find a CoreDNS chart version that can mount an existing ConfigMap in place of its own Corefile, and confirm the chart repository is reachable from the cluster. Record the chart repository, name and version in [research.md](./research.md#r-2).
- [ ] T003 [P] Confirm the resolver's VIP block can sit inside the `otternet` cluster's `vip_pools` supernet, so the border leaf advertises it and the leaves' inbound route policy accepts it. Read `schemas/cluster/kubernetes.yml` and `objects/34_otternet_cluster.yml`, and record the block chosen in [research.md](./research.md#r-1).

**Checkpoint**: the three answers are recorded. Nothing below starts before this.

## Phase 2: Foundation, blocking every story

- [ ] T004 Add the optional attribute `dns_zone` (Text, hostname pattern, `optional: true`) to `ServiceFabricApp` in `schemas/service/kubernetes_services.yml`. Do not make any existing attribute mandatory.
- [ ] T005 Run `uv run infrahubctl schema check schemas/`, then regenerate `src/solution_arista_avd/protocols.py` with `uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py`. Never edit that file by hand.
- [ ] T006 [P] Add the `udp` protocol (protocol 17) to the `SecurityIPProtocol` objects in `objects/32_otternet_security.yml`.
- [ ] T007 [P] Add the `dns_resolvers` group to `objects/00_groups.yml`.
- [ ] T008 Add the catalogue entry `lab-dns` (`requestable: false`, the chart from T002, the values that mount the ConfigMap and fix the Service address from T001) to `objects/35a_otternet_app_catalogue.yml`.
- [ ] T009 Add the resolver application `otternet-dns` to `objects/36_otternet_app_services.yml`: `dns_zone: int.otternet.lab`, `exposed: true`, the `vip_block` from T003, `definition: lab-dns`, `definition_pinned: true`, and member of `dns_resolvers`.
- [ ] T010 [P] Write `tests/unit/test_dns_schema_contract.py`: the attribute exists and is optional, `udp` exists, at most one application carries `dns_zone`, and the resolver's block lies inside the cluster's VIP pool.

**Checkpoint**: `uv run invoke lint` and `uv run invoke test` pass, each run on its own.

## Phase 3: User Story 1 - A requested application gets a name (Priority: P1)

**Goal**: after a merge, `<app>.int.otternet.lab` resolves to the application's address.

**Independent test**: [quickstart step 3](./quickstart.md#3-a-requested-application-gets-a-name-user-story-1), resolving from a host that can already reach the resolver.

- [ ] T011 [P] [US1] Write `generators/generate_dns_record.gql`: the application's `name`, `status`, `exposed`, `vip_block` (prefix and its addresses), and the resolver's `dns_zone`.
- [ ] T012 [US1] Regenerate the typed query models for T011. Never edit a `*_query.py` file by hand.
- [ ] T013 [US1] Write `generators/generate_dns_record.py`: for an exposed, live application with a block, upsert the address from [research R-3](./research.md#r-3) and set its `fqdn` to `<name>.<zone>`; skip and report a name that is not a valid DNS label. Upsert on the address's natural key so a repeated run changes nothing.
- [ ] T014 [US1] Make `generate_dns_record.py` request a re-render of the resolver's artifact, as `generators/generate_monitoring_collector.py` does, because the artifact's target is the resolver and not the application.
- [ ] T015 [P] [US1] Write `transforms/dns_zone_config.gql`: every address whose `fqdn` ends with the zone, with its application's `status`, and the resolver's `dns_zone`.
- [ ] T016 [US1] Write `transforms/dns_zone_config.py` to the [zone artifact contract](./contracts/zone-artifact.md): one ConfigMap holding the Corefile and the zone file, one A record per live application, an SOA serial that changes only when the records change, a comment line for every skipped application.
- [ ] T017 [US1] Register the queries, the generator, the transform and the artifact definition `DNS Zone Configuration` (target `dns_resolvers`) in `.infrahub.yml`, and add the generator's event rule to `triggers.yml`. The rule must name no `Deployment*` or `Monitoring*` kind.
- [ ] T018 [US1] Add the `InfrahubSync` named `dns-zone-config` to `vidra/infrahub-syncs.yaml`, delivering the artifact into the resolver's namespace.
- [ ] T019 [P] [US1] Write `tests/unit/test_dns_record_generator.py`: creates the record, skips an application with no block, skips an invalid label, and a second run makes no change.
- [ ] T020 [P] [US1] Write `tests/unit/test_dns_zone_config.py`: renders one record per live application, is byte-identical when nothing changed, and matches the artifact contract.
- [ ] T021 [US1] Deliver the resolver on the lab cluster (`uv run invoke cluster`, then check with `kubectl get fabricapp otternet-dns`) and run quickstart step 3. Report the measured delay between merge and answer against SC-001.

**Checkpoint**: a requested application's name resolves. This is the suggested first scope.

## Phase 4: User Story 2 - A withdrawn application loses its name (Priority: P1)

**Goal**: setting `status` to `decommissioning` or `decommissioned` removes the name after the merge.

**Independent test**: [quickstart step 4](./quickstart.md#4-a-withdrawn-application-loses-its-name-user-story-2).

- [ ] T022 [US2] In `generators/generate_dns_record.py`, clear `fqdn` and delete the address the generator created when the application is withdrawn. Leave an address whose `fqdn` was not set by this generator untouched.
- [ ] T023 [US2] In `transforms/dns_zone_config.py`, drop the record of a withdrawn application, and raise when that leaves no records, so the last good ConfigMap stays in the cluster.
- [ ] T024 [P] [US2] Extend `tests/unit/test_dns_record_generator.py` and `tests/unit/test_dns_zone_config.py`: withdrawal removes only that application's name, and an empty zone raises.
- [ ] T025 [US2] Run quickstart step 4 on the live lab, viewing the artifact difference in the proposed change before merging.

## Phase 5: User Story 3 - The resolver's records come only from Infrahub (Priority: P1)

**Goal**: the zone the resolver serves equals the artifact on `main`; a hand edit does not survive.

**Independent test**: [quickstart step 5](./quickstart.md#5-the-resolver-serves-only-the-artifact-user-story-3).

- [ ] T026 [US3] Make the transform raise when two applications produce the same label, and cover it in `tests/unit/test_dns_zone_config.py`.
- [ ] T027 [P] [US3] Add a check in `checks/dns_zone_check.py` (registered in `.infrahub.yml`) that refuses a proposed change with two resolvers, or with a record whose address lies outside its application's block. Add `tests/unit/test_dns_zone_check.py`.
- [ ] T028 [US3] Run quickstart step 5: compare the cluster's ConfigMap with the artifact, then add a record by hand and confirm the next delivery removes it.

## Phase 6: User Story 4 - The branch machine uses the resolver (Priority: P2)

**Goal**: after bootstrap, `branch-desktop` asks the resolver for the zone, the firewall lets it through, and other names behave as before.

**Independent test**: [quickstart steps 2 and 6](./quickstart.md#2-prove-the-firewall-path-research-r-1).

- [ ] T029 [US4] Add to `objects/32_otternet_security.yml`: the `dns-udp` and `dns-tcp` services on port 53, an address-book entry for the resolver's VIP, and the rule `branch-to-dns` on the `branch` to `k8s-prod` pair after `branch-to-access-portal`, with `managed_by_service: false`.
- [ ] T030 [US4] Add the same rule, address-book entry and the two application declarations to `lab/configs/fw/vsrx/junos.conf`, so the rendered artifact and the device baseline stay byte-for-byte equal.
- [ ] T031 [P] [US4] Update the baseline tests that name the rule set: `tests/unit/test_junos_config.py`, `tests/unit/test_junos_seed_data.py`, `tests/unit/test_security_schema_contract.py`. Read each first and change only what the new rule requires.
- [ ] T032 [US4] Add the resolver address for `branch-desktop` to `lab/wan/tenants.yml`, and change `lab/wan/render.py` and `lab/wan/templates/host-init.sh.j2` so the desktop sends queries for the zone to it and resolves other names as before ([research R-4](./research.md#r-4)).
- [ ] T033 [P] [US4] Write `tests/unit/test_dns_resolver_address.py`: the address in `lab/wan/tenants.yml` equals the one in `objects/`.
- [ ] T034 [US4] Run quickstart steps 2 and 6 after a bootstrap, and confirm the reconciler reports `differed=0` for `fw1`.

## Phase 7: Polish

- [ ] T035 [P] Write `docs/docs/developer-guide/dns-service.md` (what it does, the pieces, the traps found in [research.md](./research.md)), link it with a relative path from the pages that mention applications, and add it to `aristaAvdSidebar` in `docs/sidebars.ts`.
- [ ] T036 [P] Add the generator, the transform and the check to [docs/docs/developer-guide/generator-transform-inventory.md](../../docs/docs/developer-guide/generator-transform-inventory.md) and to the generator list in [AGENTS.md](../../AGENTS.md).
- [ ] T037 [P] Add the zone and the name to [docs/docs/service-portal.md](../../docs/docs/service-portal.md): a requested application is reachable by name.
- [ ] T038 Run `uv run invoke lint` and `uv run invoke test`, each on its own, then `uv run invoke test --integration` because a generator was added.

## Dependencies and order

- Phase 1 blocks everything. Phase 2 blocks Phases 3 to 6.
- US1 comes first. US2 builds on the generator and transform from US1. US3 builds on the transform. US4 only needs Phase 2, but its live check needs US1.
- Within a phase, tasks without `[P]` run in order.

## Parallel examples

- Phase 1: T002 and T003 together.
- Phase 2: T006, T007 and T010 together after T005.
- US1: T011 and T015 together; T019 and T020 together after the code exists.
- US4: T031 and T033 together.

## Implementation strategy

1. Phases 1 and 2, then US1: a requested application has a name. Stop and check it live.
2. US2 and US3 next: withdrawal and the guarantees that make the zone trustworthy.
3. US4 last: it changes the firewall baseline and the lab's host configuration, which are the riskiest files. If the baseline tests resist, US1 to US3 are still testable from any host that can reach the resolver.
