# Implementation Plan: Lab DNS Service

**Branch**: `037-lab-dns-service` | **Date**: 2026-10-07 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from [spec.md](./spec.md)

## Summary

Branch users get a name such as `otter-shop.int.otternet.lab` for every exposed, live application. The names are answered by a CoreDNS server that runs as a lab application in the Kubernetes cluster. A generator writes each name onto the application's VIP address (`IpamIPAddress.fqdn`), a transform renders the resolver's Corefile and zone as one ConfigMap artifact, and a Vidra `InfrahubSync` delivers it, the same way the telemetry collector's configuration is delivered. `branch-desktop` is configured to ask the resolver for the zone.

The plan is not ready to implement. [Research](./research.md) found four problems the spec did not know about, and one is decided and the others need a decision from Alex Gittings. They are listed under [Problems that need a decision](#problems-that-need-a-decision).

## Technical Context

**Language/Version**: Python 3.12 (Infrahub SDK 1.22.0, Infrahub 1.10.6; from `infrahubctl info`), YAML schemas, Jinja-free Python transform

**Primary Dependencies**: Infrahub SDK, Vidra operator, Crossplane `FabricApp` composition, CoreDNS Helm chart (not verified, see [research.md](./research.md#r-2))

**Storage**: Infrahub graph (`IpamIPAddress.fqdn`, one new optional attribute on `ServiceFabricApp`); the artifact is stored by Infrahub

**Testing**: pytest unit tests (`uv run invoke test`), the integration suite only because a generator is added (`uv run invoke test --integration`), and one live check from `branch-desktop`

**Target Platform**: the OTTERNET lab: the `otternet` Kubernetes cluster and `branch-desktop`

**Project Type**: Infrahub repository (schema, generator, transform, seed data, Vidra declaration)

**Performance Goals**: a name resolves within about one minute of the merge (the delay the kubelet takes to project a changed ConfigMap, as recorded for Telegraf in [vidra/infrahub-syncs.yaml](../../vidra/infrahub-syncs.yaml))

**Constraints**: no trigger rule may name a `Deployment*` or `Monitoring*` kind; the Junos artifact is held byte-for-byte against the hand-written firewall baseline, so the baseline file changes with the seed; an empty artifact must never be delivered

**Scale/Scope**: the lab has a handful of applications; one zone; one resolver; one client

## Constitution Check

Gates are the five principles in [.specify/memory/constitution.md](../../.specify/memory/constitution.md) (version 1.2.0).

| Principle | Result | Note |
| --- | --- | --- |
| I. Schema-Driven Architecture | Pass | The new attribute and the `udp` protocol object are defined in `schemas/` and `objects/` before any generator or transform uses them. `protocols.py` is regenerated, not edited. |
| II. Idempotent Operations | Pass, with a test | The generator upserts by the address's natural key and removes only what it created. The plan requires a repeated-run test. |
| III. Type Safety | Pass | The generator and transform use generated `*_query.py` models. |
| IV. Test-Required Quality | Pass | Unit tests for the generator and the transform; integration tests because a generator is added. |
| V. Convention-Based Structure | Pass | Files follow `generate_<entity>.py` with a matching `.gql`, and are registered in `.infrahub.yml`. |

Post-design re-check: unchanged. No violation needs justifying.

## Problems that need a decision

1. **Decided: the firewall allows the branch to reach the resolver in the bootstrapped version.** The rule is seed data, which also means the device baseline `lab/configs/fw/vsrx/junos.conf` and the tests that hold the artifact against it change in the same cycle. [Details](./research.md#r-1).
2. **Nothing makes the application's LoadBalancer take the first address of its block.** Decision 1 of the spec says the name points at the first address. The files show that Infrahub allocates the block, and do not show that Infrahub chooses which address in the block the Service receives. If it does not, the name points at an address nobody answers on. [Details and options](./research.md#r-3).
3. **FR-021 conflicts with how the branch machine is configured.** `lab/wan/render.py` reads only `lab/wan/tenants.yml`, so the resolver address cannot come from Infrahub without a new dependency. [CLAUDE RECOMMENDED – based on [tests/unit/test_srl_config.py](../../tests/unit/test_srl_config.py) holding two copies of the admin hash equal] Keep one line in `tenants.yml` and hold it equal to the Infrahub address with a test. This needs the spec amended. [Details](./research.md#r-4).
4. **Only `tcp` and `icmp` exist as protocols.** DNS needs `udp`. Adding the object is small, and the Junos transform declares an application from the protocol's name, so no transform change is expected. [Details](./research.md#r-5).

## Project Structure

### Documentation (this feature)

```text
specs/037-lab-dns-service/
├── spec.md
├── plan.md              # this file
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── zone-artifact.md
├── checklists/requirements.md
└── tasks.md             # created by /speckit-tasks
```

### Source code (repository root)

```text
schemas/service/kubernetes_services.yml     # dns_zone attribute on ServiceFabricApp (optional)
objects/32_otternet_security.yml            # udp protocol, DNS services, resolver address-book entry, branch-to-dns rule
lab/configs/fw/vsrx/junos.conf              # the firewall baseline gains the same rule, entry and applications
objects/35a_otternet_app_catalogue.yml      # lab-dns catalogue entry (requestable: false)
objects/36_otternet_app_services.yml        # the resolver application and its zone
generators/generate_dns_record.py + .gql    # writes fqdn on each application's VIP address
transforms/dns_zone_config.py + .gql        # renders the ConfigMap artifact
vidra/infrahub-syncs.yaml                   # InfrahubSync "dns-zone-config"
lab/wan/tenants.yml                         # resolver address for branch-desktop (see problem 3)
.infrahub.yml                               # query, generator, transform and artifact registrations
tests/unit/                                 # generator, transform, contract tests
```

**Structure Decision**: follow the telemetry collector's layout: one transform, one artifact definition, one `InfrahubSync`, and one generator that keeps the artifact current. Reasons are in [research.md](./research.md#r-2).

## Complexity Tracking

No constitution violation. Nothing to justify.
