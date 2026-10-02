---
title: Regenerate a fabric
description: Re-run the AVD generator chain for a fabric on a branch, and know which stages are safe to repeat.
audience: user
sidebar_position: 4
---

# Regenerate a fabric

Regenerating a fabric means re-running the generator chain so the PyAVD hostvars, the structured configurations, and the artifacts rendered from them follow the data in Infrahub. `uv run invoke avd` is the front door. Run it on a branch, review the result as a proposed change, and merge.

The chain has two stages, and only one of them is safe to repeat:

| Stage | Generators | Idempotent | When |
|-------|------------|:----------:|------|
| Topology | `generate-fabric`, `generate-pod`, `generate-rack` | **No — destructive on re-run** | `--topology`, build time only |
| AVD | `generate-avd-device-hostvar`, `generate-avd-device-structured-config` | Yes | every run |

## Regenerate on a branch

```bash
uv run invoke avd --branch my-change
```

This creates the branch if it doesn't exist (or reuses it), runs the two AVD generators on it, and then asks Infrahub to re-render every artifact **on that branch**. Without the branch, artifact regeneration targets `main`, and `infrahubctl transform --branch X` would render your change while the stored artifact never moves.

When it finishes, open a proposed change from `my-change` in the Infrahub UI and review it:

- **Data** — the regenerated `AvdHostvarFile` and `AvdStructuredConfigFile` nodes for every device whose input changed.
- **Artifacts** — the re-rendered EOS configurations, device documentation, fabric documentation, and cabling plan.

## Merge

Merge from the proposed change, or let the task do it:

```bash
uv run invoke avd --branch my-change --merge
```

`--merge` merges the branch and then **waits for the artifacts to render** on `main`. Generation is asynchronous, and an artifact that hasn't rendered yet still reports `Ready`, so the wait requires every artifact to be non-empty and stable across consecutive samples before it returns. It then deletes the merged branch, whose content is all on `main` by then. Once merged, the deployment reconciler pushes the new configurations to the devices on its next cycle.

## Building a topology

Use `--topology` only on an instance where the fabric hasn't been built yet, such as immediately after `invoke load`:

```bash
uv run invoke avd --branch build --topology --merge
```

A fresh load seeds objects but runs no generators, so there is no spine-to-leaf cabling. PyAVD then renders switches with no uplinks and no underlay or overlay BGP — about 155 lines for a spine instead of 239 — while every artifact still reports `Ready`. `--topology` adds the topology stage in front of the AVD stage to close that gap.

:::danger The topology generators are destructive on a fabric that already has cabling
`generate-fabric`, `generate-pod` and `generate-rack` are **not** idempotent.
`generate-pod` takes each spine from nine interfaces to four, deleting the
leaf-role ports racks 1 and 2 are cabled to, and `generate-rack` then fails on
rack 3 with an `IndexError` because its slice of spine ports is empty. That is
why `invoke avd` keeps them behind `--topology` rather than in its default path.

`generate-avd-device-hostvar` and `generate-avd-device-structured-config` *are*
idempotent and run on every `invoke avd`. Re-run those freely; build a topology
on a fresh branch.
:::

## When to regenerate a fabric

- After editing data the hostvars are built from — fabric settings, IP pools, interfaces, VRFs, SVIs — when nothing else has regenerated it.
- After a failed partial run where one of the AVD generators didn't complete.
- After upgrading the PyAVD version, if the structured config output format has changed.

A service request doesn't need this. A proposed change runs `generate-avd-device-hostvar` (and through it the structured-config generator) in its own pipeline, and its artifact checks re-render the configurations, so a request's fabric consequence already shows in its proposed change.

## Inspecting without regenerating

You don't need to regenerate to look at a fabric. In the Infrahub UI, on any branch:

- The fabric's **Artifacts** include the fabric documentation and the cabling plan — every link between devices.
- Each switch's **Artifacts** include its rendered EOS configuration and device documentation.
- The fabric object itself carries the underlay and overlay settings, and its EVPN tenants and SVIs are under **Data Centre Fabric → EVPN** in the menu.

See [Viewing Artifacts](../viewing-artifacts.md) for where each one lives.

## Without the task

You can trigger the same generators in the Infrahub UI:

1. Create a branch.
2. Open **Actions → Generator Definitions**.
3. Run **`generate-avd-device-hostvar`**, then **`generate-avd-device-structured-config`**. The structured-config generator reads the **stored** hostvar files, so it must follow.
4. Create a proposed change from the branch; its checks re-render the artifacts.

See [Provision Your First Fabric](../provision-first-fabric.md) for a step-by-step walkthrough of the full chain, topology included.

## Source

- Task: `avd` in [`tasks.py`](https://github.com/opsmill/infrahub-arista-avd/blob/main/tasks.py).
- Generators: [`generators/`](https://github.com/opsmill/infrahub-arista-avd/tree/main/generators).
