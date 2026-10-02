# Arista AVD Reference Design

## Project context

This repository is the Arista AVD Reference Design for Infrahub. It models datacenter
fabric intent, topology, addressing pools, EVPN services, and per-device AVD data in
Infrahub, then renders EOS configurations and documentation through PyAVD.

The long-form design notes, measured pitfalls and incident history that used to live in this
file are in `docs/docs/developer-guide/`. This file keeps the rules and a pointer per area:
**read the linked page before touching that area.**

Key docs to read before larger changes:

- `README.md` and `docs/docs/home.md` for the current product overview.
- `docs/docs/quick-start.md` for stack/load commands.
- `docs/docs/supported-capabilities.md` before assuming a feature is supported.
- `docs/docs/developer-guide/architecture.md` for the data model and generator chain.
- `docs/docs/developer-guide/schemas.md` for schema kinds and dropdown values.
- `docs/docs/developer-guide/generators.md` for generator structure and execution order.
- `docs/docs/developer-guide/transforms.md` for transform structure and artifacts.
- `docs/docs/developer-guide/avd/overview.md` for the two-phase AVD pipeline.
- `docs/docs/developer-guide/avd/extending.md` for extension workflows.
- `docs/docs/developer-guide/avd/debugging.md` for pipeline debugging.
- [Symptom to cause](docs/docs/developer-guide/symptom-to-cause.md) when an error message or behaviour looks odd.

## Repository layout

- `src/solution_arista_avd/` - core library: AVD helpers, cabling, addressing, generator utilities, `deployment/` reconciler.
- `generators/`, `transforms/`, `checks/` - Infrahub generators, Python transforms and proposed-change checks, with their GraphQL queries and generated `*_query.py` models.
- `ansible/` - playbooks Semaphore runs, including ContainerLab deployment.
- `schemas/` - schema definitions: base schemas and project/feature extensions.
- `objects/` - seed data loaded in filename order. One fabric, `OTTERNET_FABRIC`, which is the lab under `lab/`.
- `menus/` - Infrahub UI menus. `docs/` - Docusaurus documentation.
- `lab/` - the OTTERNET lab: ContainerLab topology, WAN, firewall, Kubernetes and Crossplane assets, own `README.md` and Makefile. `invoke lab` resolves it in the main checkout.
- `queries/` - GraphQL queries with no Python consumer here (`artifact_ids.gql`, polled by Vidra).
- `vidra/` - Vidra operator deployment assets: Helm values, ConfigMap, `InfrahubSync` declarations, and the **shape** of the credential Secret, never the credential.
- `tooling/`, `backstage/`, `auth/`, `scripts/` - the tooling cluster (Dex, the portal), the portal source, sign-in docs, and operational scripts.
- `.infrahub.yml` (menus, queries, generators, transforms, artifacts), `repository.yml` (CoreRepository), `triggers.yml` (event rules), `tasks.py` (Invoke tasks).

## Architecture summary

- Hierarchy: `NetworkFabric` -> `NetworkPod` -> `LocationRack` -> `DcimFabricSwitch` -> `DcimInterface` / `NetworkLink` / `IpamIPAddress`.
- **Four device kinds are siblings**: `DcimFabricSwitch` (EOS), `DcimDevice` (SR Linux WAN routers), `SecurityFirewall`, `ComputePhysicalServer`. All inherit `DcimGenericDevice`; none inherits another. **A query naming `DcimDevice` does not see a fabric switch and reports nothing** - peer or spread `DcimGenericDevice` for every kind.
- Fabric generator chain: `generate-fabric` -> `generate-pod` -> `generate-rack` -> `generate-avd-device-hostvar` -> `generate-avd-device-structured-config`.
- Hostvars are `AvdHostvarFile` nodes and structured configs are `AvdStructuredConfigFile` nodes, both under `AvdArtifact`. Transforms render artifacts from the stored files.
- PyAVD is version-sensitive: `pyavd>=6.4.0,<6.5.0`.
- One request portal, Backstage, in the tooling cluster. Every request creates one service object on a branch and a generator builds the technical objects. See [tooling cluster](docs/docs/developer-guide/tooling-cluster.md).

## Hard rules (each one cost real time; the linked page has the evidence)

- **Never rewrite a commit Infrahub has already pulled** (`--amend`, `rebase`, `reset` on a synced commit). Diverged history wedges every sync. Recovery is `git merge -s ours <orphaned commit>`. A failed import is not retried until the commit changes. See [repository sync](docs/docs/developer-guide/repository-sync.md).
- **Infrahub imports only `main`** (`INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES=["main"]`). Never remove that setting; a generator change cannot be tested live on a branch before it merges - call it locally against the branch.
- **No trigger rule may name a `Deployment*` or `Monitoring*` kind**, and nothing may generate from them. It closes a loop. See [deployment state](docs/docs/developer-guide/deployment-state.md).
- **`generate-fabric`, `generate-pod` and `generate-rack` are destructive on re-run** against a fabric that has cabling. Only `invoke avd --topology` runs them, at build time. Use `invoke avd --branch X` for anything you intend to review. See [bootstrap](docs/docs/developer-guide/bootstrap.md).
- **Never `kubectl patch` a Helm-managed object**, even to test a fix: it takes field ownership and every later Helm upgrade conflicts. See [observability](docs/docs/developer-guide/observability.md).
- **Do not pipe `invoke` gates to `tail` or `head`** when the exit status matters; the pipeline reports the last command's status. Run the gate on its own.
- **Never commit credentials.** The portal runs as `backstage-portal`, MCP as `mcp-agent`, the exporter as `metrics-exporter`; never hand any of them the admin or `agent` token.
- **Deleting a service object leaves its `CoreGeneratorInstance`**, which breaks the generator for everyone. Delete the instance and the empty generator group too. See [service triggers](docs/docs/developer-guide/service-triggers.md).
- **No quote characters in an SR Linux artifact comment**, and an empty SR Linux or Junos artifact erases the device. See [generator inventory](docs/docs/developer-guide/generator-transform-inventory.md).
- **Making an attribute mandatory is refused against existing data.** Migrate objects first. `infrahubctl protocols` ignores `state: absent` and the `extensions:` block.
- **Regenerate, never hand-edit**, `src/solution_arista_avd/protocols.py` and `*_query.py`.

## Where the detail went

| Area | Read before touching it |
| --- | --- |
| Tooling cluster, the one Dex, portal HTTPS and certificates, attribution via `context`, `invoke tooling`, Backstage build and catalogue | [tooling-cluster.md](docs/docs/developer-guide/tooling-cluster.md) |
| Portal Topology page and which cables Infrahub holds | [topology-page.md](docs/docs/developer-guide/topology-page.md) |
| `infrahub-mcp` and the `mcp-agent` account | [mcp-server.md](docs/docs/developer-guide/mcp-server.md) |
| Grafana, Prometheus, Telegraf, monitoring profiles, service monitoring, the exporters | [observability.md](docs/docs/developer-guide/observability.md) |
| Every generator, transform and check, with traps for each | [generator-transform-inventory.md](docs/docs/developer-guide/generator-transform-inventory.md) |
| Repository sync and what wedges it | [repository-sync.md](docs/docs/developer-guide/repository-sync.md) |
| Why services expand on their branch, and withdrawal by `status` | [service-triggers.md](docs/docs/developer-guide/service-triggers.md) |
| `DeploymentState` and its one rule | [deployment-state.md](docs/docs/developer-guide/deployment-state.md) |
| The reconciler, normalisers, firewall full-replace, wake logic | [deployment-reconciler.md](docs/docs/developer-guide/deployment-reconciler.md) |
| AVD chain, bootstrap, verification, bringing up the lab, provisioning | [bootstrap.md](docs/docs/developer-guide/bootstrap.md) |
| Cilium, Vidra, Crossplane, the handover | [vidra-delivery.md](docs/docs/developer-guide/vidra-delivery.md) |
| Schema-first workflow, naming, extension checklists | [development-workflow.md](docs/docs/developer-guide/development-workflow.md) |
| Full command list and pitfalls | [commands.md](docs/docs/developer-guide/commands.md) |
| Error message to cause lookup | [symptom-to-cause.md](docs/docs/developer-guide/symptom-to-cause.md) |

One-paragraph summaries:

- **Tooling cluster.** `tooling/` is a second cluster (`tool-node1`) carrying Dex and Backstage, deployed by `scripts/deploy_tooling.sh` (`uv run invoke tooling`), never by Infrahub. There is exactly one Dex, reachable only from the branch side; operators sign in with the local `admin` account. The portal needs HTTPS (a secure context) and `NODE_EXTRA_CA_CERTS`. It writes to Infrahub as the signed-in user through the mutation `context` - attribution, not authorization. `backstage-build` builds the portal; a bare `docker compose build` ships old JavaScript.
- **Services.** Service kinds (`ServiceNetworkSegment`, `ServiceTenantOnboarding`, `ServiceServerPlacement`, `ServiceFabricApp`, `ServiceFabricPeering`, `ServiceAppAccess`, WAN kinds) are built on their branch by event rules in `triggers.yml` and withdrawn by `status` (`decommissioning` counts as gone). Every write-back is guarded so the rules terminate.
- **Generators and transforms.** Generators registered in `.infrahub.yml`: `generate-fabric`, `generate-pod`, `generate-rack`, `generate-server-cabling`, `generate-avd-device-hostvar`, `generate-avd-device-structured-config`, `generate-fabric-peering`, `generate-app-access`, `generate-network-segment`, `generate-fabric-app`, `generate-tenant-onboarding`, `generate-server-placement`, `generate-monitoring-collector`. Transforms, checks and their traps are in the inventory page.
- **Reconciler.** `src/solution_arista_avd/deployment/` compares each device against its artifact and pushes differences; `differs` is computed from normalised output through an allowlist. Run `invoke build` after dependency or package changes - the container runs the image's installed package, not the bind mount.
- **Vidra and the handover.** `invoke cluster` runs Cilium, Vidra, Crossplane, then deletes the lab's four claims; Infrahub re-delivers only the two it models. `syncState: Succeeded` is not evidence anything arrived - count the resources.
- **Observability.** Telegraf's whole configuration is an artifact; what is watched is changed in a proposed change. The new address field is `telemetry_address`, never `mgmt_ip`.

## Skills

Local Infrahub skills live in `.claude/skills/`. If the Skill tool says `Unknown skill: infrahub-managing-*`
(or any `infrahub-*` name), read `.claude/skills/<name>/SKILL.md` directly with the Read tool and follow it.

## Workflow

Before opening a pull request:

1. `uv run invoke lint` and `uv run invoke test`, each run on its own (not piped).
2. `uv run invoke test --integration` only when generators or the bootstrap path changed.
3. For schema or `.gql` changes, regenerate protocols and return types rather than editing them.

Conventions:

- **Worktrees.** Work in a git worktree on a feature branch; remove it when done with `git worktree remove <path>` (then `git branch -d`). `compose_root()` resolves the main checkout so `invoke` targets the one real stack from any worktree.
- **Root-owned files.** Docker-created files under `.git` (or a worktree's gitdir) can be root-owned and break `git`. Fix with `sudo chown -R "$USER":"$USER" <path>`.
- **Infrahub imports only `main`.** A generator, query or check change takes effect on the stack after it merges to `main`. Test a generator change by calling it locally against a branch.
- **Shell.** Bash calls start in the repository root, so do not prefix commands with `cd`.
- **First thing to run when something is odd: `uv run invoke doctor`.**

## Long operations

The harness blocks a foreground `sleep`. For anything slow:

- Start it with `run_in_background`, then wait with the Monitor tool using an until-loop on a condition (a file, an HTTP status, a container state). Never `sleep`.
- Typical durations: `invoke bootstrap` about 20 minutes; `scripts/verify_bootstrap.sh` about 20 minutes; a generator pass 15-21 seconds (hostvars about 15s, structured configs about 6s); artifact rendering settles in about a minute after a merge.
- Say what "done" looks like before waiting: the artifacts non-empty and checksums stable across samples, `invoke reconcile` reporting `differed=0`, the `VidraResource` count (not `syncState`), `sync_status: in-sync`.

## KUBECONFIG

The lab's kubeconfig lives in the **main checkout**, because there is one lab and its runtime state lives under it
(`tasks.py::find_lab_directory`, which resolves `lab/` there even from a worktree):

```bash
export KUBECONFIG=/home/ubuntu/dev/nfd41/infrahub/lab/k8s/.kubeconfig/kubeconfig.yaml          # the lab cluster
export KUBECONFIG=/home/ubuntu/dev/nfd41/infrahub/lab/k8s/.kubeconfig-tooling/kubeconfig.yaml   # the tooling cluster
```

A worktree's own `lab/k8s/.kubeconfig/` is empty. The sibling `/home/ubuntu/dev/nfd41/lab` is the lab's old
standalone repository from before it moved in; it is stale, do not point `KUBECONFIG` or `OTTERNET_LAB_DIR` at it.

## Commands

Full list and pitfalls: [commands.md](docs/docs/developer-guide/commands.md).

```bash
uv sync --all-packages
uv run invoke --list
uv run invoke doctor                    # run first when something is odd
uv run invoke start | stop | destroy | restart
uv run invoke load                      # seed objects; runs NO generators
uv run invoke avd [--branch X] [--merge]   # idempotent AVD stages; --topology only at build time
uv run invoke bootstrap [--fresh]       # the whole environment
uv run invoke lab | provision | reconcile | tooling | cluster | vidra
uv run invoke test [--integration]
uv run invoke lint                      # also lint-ruff, lint-yaml, lint-mypy, lint-markdown, lint-prose
uv run pytest tests/unit/test_avd.py
uv run rumdl check README.md AGENTS.md docs/ lab/README.md schemas/
uv run infrahubctl graphql export-schema --destination schema.graphql   # takes no --branch
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

Docs use pnpm (`uv run invoke docs`), never npm.

## Extension checklists

Adding an AVD-rendered role, a non-EOS role, a transform output or a hostvars field has a fixed checklist
(schema dropdown, `ROLE_TO_AVD_TYPE`, tests, docs). It is in
[development-workflow.md](docs/docs/developer-guide/development-workflow.md). Naming: generators are
`generate_<entity>.py` with a matching `.gql`; never hand-edit `*_query.py`.

## Documentation publishing

`docs/docs/` is synced to `opsmill/infrahub-docs` on every push to `main` and published at
`docs.infrahub.app/arista-avd` under a `/arista-avd` route. Two rules for anything added under `docs/docs/`:

- Link between pages with relative Markdown paths (`](./quick-start.md)`), never root-absolute ones
  (`](/quick-start)`); the aggregation site sets `onBrokenLinks: 'throw'`.
- Keep the sidebar key in `docs/sidebars.ts` named `aristaAvdSidebar`, and add every new page to it.

Edits made directly in `infrahub-docs` are overwritten by the next sync.
