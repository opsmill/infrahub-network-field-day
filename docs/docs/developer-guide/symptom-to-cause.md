---
title: Symptom to cause
description: A lookup table from an error message or odd behaviour to its known cause and the page that explains it.
audience: developer
sidebar_position: 40
---

# Symptom to cause

Run `uv run invoke doctor` first when something is odd. It checks image staleness against commits, duplicate
reconcile processes, `schema.graphql` freshness, the repository `sync_status` and dangling `CoreGeneratorInstance`
nodes. This page maps what you saw to the cause that has already been measured in this lab. Each cause is
explained in the linked page.

## Infrahub, the repository and generators

| Symptom | Cause | Where |
| --- | --- | --- |
| Repository stuck at `sync_status: error-import`; a new generator or query never appears | A failed import is not retried until the commit changes. Push a new commit. | [Repository sync](./repository-sync.md) |
| `Unable to pull the branch main for repository ..., there are conflicts that must be resolved` and no file conflict | A commit Infrahub had pulled was rewritten. Run `git merge -s ours <orphaned commit>`. | [Repository sync](./repository-sync.md) |
| `Multiple CoreMenuItem nodes have the same hfid` on an import | A race between the two `task-worker` replicas importing the same repository. | [Repository sync](./repository-sync.md) |
| Task manager at 100% CPU, thousands of automations, `One or more generators failed`, `set_state` 500 errors | Infrahub turned every local git branch or worktree into an Infrahub branch. `INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` must stay `["main"]`. | [Repository sync](./repository-sync.md) |
| A generator change works locally but the branch run still uses old code | Infrahub imports only `main`, and a task worker keeps reloading `main`'s file. Call the generator locally against the branch. | [Repository sync](./repository-sync.md) |
| `Node must have at least one identifier (ID or HFID) to query it` on every proposed change | A deleted service object left its `CoreGeneratorInstance` behind. Delete the instance and the empty generator group. | [Service triggers](./service-triggers.md) |
| A decommission ended with the service `active` | A generator recorded `error` from a withdrawn state, so the next run took the build path. A refusal must raise and leave `decommissioning`. | [Service triggers](./service-triggers.md) |
| `Unable to find the node ... SecurityPolicyRule` in a Revoke run | Two runs of one withdrawal at once; `_delete_if_present` must treat "already gone" as done. | [Service triggers](./service-triggers.md) |
| `CoreGeneratorGroupUpsert` fails with `Unable to find the node ... CoreNode` after a generator run that deleted a node | The SDK adds every node a run reads or saves to the generator group and writes the group last. A node the run deleted is still in the member list. Remove its id from `self.client.group_context.related_node_ids` after the delete, as `generate-dns-record` does in `_forget`. | [Generator inventory](./generator-transform-inventory.md) |
| `Attribute-level 'optional' constraint violation on schema 'X'. Node (y) is not compliant.` | A mandatory attribute was added against existing data. Migrate the objects before loading the schema. | [Generator inventory](./generator-transform-inventory.md) |
| `Node-level 'inherit_from' constraint violation` | A re-declared node must repeat its `inherit_from`. | [Generator inventory](./generator-transform-inventory.md) |
| `A prefix_type or a default_value type must be provided` on allocation | A resource pool lacks `default_prefix_type: IpamPrefix`. | [Generator inventory](./generator-transform-inventory.md) |
| `crossplane_fabric_app` raises `is exposed but has no vip_block` | `generate-fabric-app` has not allocated the block yet, or ran and lost a race. | [Generator inventory](./generator-transform-inventory.md) |
| A segment's SVI renders on no switch | `avd_tags` does not intersect any node-group filter tag. | [Generator inventory](./generator-transform-inventory.md) |
| Proposed change shows changed JSON and no configuration | The hostvar and structured-config passes did not run, or the artifact was validated before they finished. | [Tooling cluster](./tooling-cluster.md) |
| Cabling missing, spines render about 155 lines, every artifact `Ready` | `invoke load` runs no generators. Run `invoke avd --topology` once. | [Bootstrap](./bootstrap.md) |
| A deletion from the model did not reach the device | `--merge` returned before the artifact re-rendered. Run a cycle again; the wait needs a stable window. | [Bootstrap](./bootstrap.md) |
| An artifact is `Ready` but empty | Generation is asynchronous; an unrendered artifact exists and reports `Ready`. | [Bootstrap](./bootstrap.md) |
| `Cannot query field 'device_groups' on type 'CoreProfile'` | A schema relationship named `profiles` collides with the built-in one. Use `monitoring_profiles`. | [Observability](./observability.md) |
| Link series empty, nothing raised | The return-type generator mistyped `... on DcimInterface`. Use concrete kinds. | [Observability](./observability.md) |

## Devices and the reconciler

| Symptom | Cause | Where |
| --- | --- | --- |
| Reconciler container crash-loops on `ModuleNotFoundError: No module named 'infrahub_sdk'` | The image predates a dependency. Run `invoke build`. | [Deployment reconciler](./deployment-reconciler.md) |
| Reconciler reports `failed=7` looking for `clab-nfd41-*` containers | The image holds the pre-rename package. Run `invoke build`. | [Bootstrap](./bootstrap.md) |
| Junos `show \| compare` is empty but the file never loaded | `scp -O` is missing on the Junos path. | [Bootstrap](./bootstrap.md) |
| `commit failed: (statements constraint check failed)` on the firewall | A policy names an application that the artifact did not declare. | [Generator inventory](./generator-transform-inventory.md) |
| Firewall commit rolled back, `root via other` is the newest commit | The post-commit reachability check failed; Junos rolled back itself. | [Deployment reconciler](./deployment-reconciler.md) |
| A router booted with no management interface or half its policy, nothing errored | A quote character in a comment in the SR Linux artifact. | [Generator inventory](./generator-transform-inventory.md) |
| Every BGP session up, every tenant VRF empty | The route-leaking policy has only one of its two halves. | [Generator inventory](./generator-transform-inventory.md) |
| `fw1` appears in sync but still carries cleartext credentials | The comparison cannot see a cleartext password; the comparator asks running configuration. | [Deployment reconciler](./deployment-reconciler.md) |
| `br-otter-tool` ... `does not exist` when deploying the lab | The host bridge does not survive a reboot. Run `lab/scripts/tooling-bridge.sh`, or deploy through `invoke lab`. | [Tooling cluster](./tooling-cluster.md) |

## Kubernetes, Vidra and Crossplane

| Symptom | Cause | Where |
| --- | --- | --- |
| Vidra sync returns `query failed with status 404 Not Found` | The chart was installed before the ConfigMap, so the operator kept the default `queryName`. | [Vidra delivery](./vidra-delivery.md) |
| Vidra reports `no secret found` | The Secret's label must be the bare host, with no scheme and no port. | [Vidra delivery](./vidra-delivery.md) |
| `syncState: Succeeded` and nothing in the cluster | The `artefactName` does not match `.infrahub.yml`, or a delivered resource was deleted. Delete and re-apply the `InfrahubSync`. | [Vidra delivery](./vidra-delivery.md) |
| `already exists but is not managed by this operator` | Another writer created the resource first; Vidra will not adopt it. | [Vidra delivery](./vidra-delivery.md) |
| `invoke cluster` fails with `AlreadyExists` from `apply` | Vidra won a race with the lab installer. Re-run `invoke cluster`. | [Vidra delivery](./vidra-delivery.md) |
| Helm upgrade fails `conflict with "kubectl-patch"` | Someone patched a Helm-managed object. Drop that `managedFields` entry and delete the failed release secret. | [Observability](./observability.md) |
| `invalid ownership metadata` installing kube-prometheus-stack | Two releases contend for the same CRDs. Keep `OTTERNET_SKIP_OBSERVABILITY` set. | [Observability](./observability.md) |
| A granted source is dropped with no denial logged | The third gate: the application's own `allowed_source_prefixes`. The drop is at the pod, not on `fw1`. | [Generator inventory](./generator-transform-inventory.md) |
| Only some requests reach the application, with node-range source addresses | `externalTrafficPolicy: Cluster` SNATs the request. The composition forces `Local`. | [Generator inventory](./generator-transform-inventory.md) |

## Observability

| Symptom | Cause | Where |
| --- | --- | --- |
| Grafana shell loads, its JavaScript never arrives | TCP MSS on `fw1` is too large for the VXLAN fabric behind it; it must be 9124. | [Observability](./observability.md) |
| Every Grafana panel reads "No data" with Prometheus full | Grafana unregistered its Prometheus plugin; set `plugins.preinstall_disabled`. | [Observability](./observability.md) |
| Every kubelet series appears twice | A generated release name left a second kubelet Service. Pin `prometheusOperator.kubeletService.name`. | [Observability](./observability.md) |
| Prometheus can reach nothing off its own node | A CiliumNetworkPolicy still selects the pods; every `allow-*` flag must be off with `policy_default_deny: false`. | [Observability](./observability.md) |
| SNMP polls count as `Bad community use` | The community must be bound to `mgmt_junos` and restricted to `172.20.41.0/24`. | [Observability](./observability.md) |
| Grafana is starved on a k3s node | A node is one CPU; dashboards refresh each minute for that reason. | [Observability](./observability.md) |

## Portal, Dex and the tooling cluster

| Symptom | Cause | Where |
| --- | --- | --- |
| Backstage signs in then dies with `globalThis.crypto.randomUUID is not a function` | The page is served over plain HTTP; the portal needs HTTPS (a secure context). | [Tooling cluster](./tooling-cluster.md) |
| OIDC popup shows `FetchError: request to https://localhost:7007/api/catalog/entities/by-name/User/default/alice failed` | `NODE_EXTRA_CA_CERTS` is missing on the Deployment; Node cannot verify its own catalog call. | [Tooling cluster](./tooling-cluster.md) |
| Firefox shows `MOZILLA_PKIX_ERROR_CA_CERT_USED_AS_END_ENTITY` | The server certificate is self-signed and marked as a CA. It must be a throwaway CA plus a server certificate it signs. | [Tooling cluster](./tooling-cluster.md) |
| Firefox keeps warning after `invoke tooling` | Firefox imports the CA only when it starts. Restart it. | [Tooling cluster](./tooling-cluster.md) |
| `Unable to set context for account that doesn't exist` at the create step, with an orphan branch | The user never signed in to Infrahub. `invoke tooling` provisions accounts for the Dex users. | [Tooling cluster](./tooling-cluster.md) |
| A branch user's request vanishes with nothing logged | The return route via `10.90.0.254` is missing; `tooling-bridge.sh` adds it. | [Tooling cluster](./tooling-cluster.md) |
| A catalogue item works locally and is absent in the lab | It was not added to both app-configs and the Dockerfile `COPY`. | [Tooling cluster](./tooling-cluster.md) |
| A portal code change does not arrive after `docker compose build` | The Dockerfile packages the last bundle. Use `invoke backstage-build`. | [Tooling cluster](./tooling-cluster.md) |
| Backstage build sits on `Corepack is about to download ... yarn-1.22.22.tgz` | `yarn --cwd` loses the Yarn 4 pin. Use `cd`. | [Tooling cluster](./tooling-cluster.md) |
| Backstage build is killed | Node sized its heap to total memory. Use `--max-old-space-size=4096`. | [Tooling cluster](./tooling-cluster.md) |
| A branch desktop icon renders blank | `librsvg2-common` (gdk-pixbuf's SVG loader) is not installed. | [Tooling cluster](./tooling-cluster.md) |
| `infrahub-mcp` fails with `cannot import name 'McpError' from 'mcp'` | The PyPI package resolves against fastmcp 4. Use the pinned image. | [MCP server](./mcp-server.md) |
| `invoke stop` leaves a network that cannot be removed | A profiled service holds the compose network. Use `--profile '*'`. | [MCP server](./mcp-server.md) |

## Working in the repository

| Symptom | Cause | Where |
| --- | --- | --- |
| `Unknown skill: infrahub-managing-*` from the Skill tool | The skill lives under `.claude/skills/`. Read its `SKILL.md` directly. | `AGENTS.md` |
| `git` fails inside a worktree with permission errors under `.git` | Docker created root-owned files. Run `sudo chown -R "$USER" <path>`. | [Development workflow](./development-workflow.md) |
| `infrahubctl graphql export-schema --branch` is rejected | The command takes no `--branch`. | [Commands](./commands.md) |
| A lint gate "passed" after being piped to `tail` | The pipeline reports the last command's status. Run the gate on its own. | [Commands](./commands.md) |
