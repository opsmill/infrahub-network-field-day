---
title: Set up a demo environment without the lab
description: Bring up Infrahub, the OTTERNET fabric with every artifact rendered, and the service portal on a laptop, with no devices and no Kubernetes, to demonstrate the workflow.
audience: user
---

# Set up a demo environment without the lab

This environment shows the OTTERNET fabric in Infrahub on a single laptop. One command builds Infrahub, loads the fabric design, cables the fabric, renders every device configuration, and starts the service portal and its sign-in service. Nothing in it configures a device.

It is for demonstrating the workflow, not for development. To change schemas, generators or transforms, use [Set up the stack step by step](./developer-guide/stack-step-by-step.md). To show configurations reaching running switches, use [Set up the full lab environment](./setup-lab.md).

## What you can show, and what is missing

The environment contains:

- Infrahub at `http://localhost:8000`, with `OTTERNET_FABRIC` cabled and every artifact rendered: the EOS configurations, the per-device and fabric documentation, and the cabling plan.
- The service portal at `https://localhost:32001`, where a branch user requests a service. Each request creates a branch and a proposed change in Infrahub.
- Dex at `http://localhost:32556/dex`, which signs portal users in to both the portal and Infrahub.
- The Infrahub MCP server, with a token for `alice` written to `.env`.

It leaves out everything that needs the lab:

- No switches, firewall or WAN routers, so no configuration is pushed and the reconciler does not run.
- No Kubernetes cluster, so a requested application is never deployed and the Grafana dashboards do not exist.
- No branch desktop.

The [demo runbook](./demo-runbook.md) assumes the full lab. Its steps that reach an application, a device or a dashboard do not work in this environment.

## Requirements

The environment runs on macOS or Linux. It needs no ContainerLab, no `sudo` and no `/dev/kvm`.

- About 12 GB of memory.
- At least 20 GB of free disk where Docker keeps its data.
- Docker with Compose v2, usable without `sudo`.
- `git`, `curl` and `openssl`.
- Node 22, 24 or 26, to build the portal. Corepack and Yarn are not needed: the build runs the Yarn
  release committed in `backstage/.yarn/`.
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.11 to 3.13.

## Bring the environment up

1. Install the Python dependencies from the repository root:

   ```bash
   uv sync --all-packages
   ```

2. Export the admin token of the local stack. `infrahubctl` needs it for every load step:

   ```bash
   export INFRAHUB_API_TOKEN=06438eb2-8019-4776-878c-0941b1f1d1ec
   ```

3. Check the machine:

   ```bash
   uv run invoke prereqs --no-lab
   ```

   It lists each missing tool, too little memory or disk, a port another program already uses, and a download site the machine cannot reach. Fix every `FAIL` line before you continue.

4. Bring the environment up:

   ```bash
   uv run invoke bootstrap --no-lab
   ```

   It builds the Infrahub image, starts the stack, loads the schemas and seed data, runs the fabric generators on a branch and merges it, then starts Dex, the portal, and the MCP server.

The run ends with the readiness checks. The checks for the lab and the Kubernetes cluster fail in this environment because those parts do not exist, so the run prints them but does not exit with an error.

## Sign in

| Where | Account | Password |
| --- | --- | --- |
| Infrahub, `http://localhost:8000` | `admin` | `infrahub` |
| Infrahub, as the network engineer who edits network data and merges proposed changes | `alex` | `INFRAHUB_NETWORK_ADMIN_PASSWORD` in `.env` |
| The portal, `https://localhost:32001`, and Infrahub through **Sign in with Dex** | `alice@otternet.lab` or `bob@otternet.lab` | `password` |

The portal certificate is signed by a certificate authority that the bootstrap creates, and your browser does not trust it. Accept the browser warning once. The portal needs HTTPS to work at all.

## What to show

<!-- vale Google.Spelling = NO -->

- **Rendered configurations.** In Infrahub, open a switch under **Data Center → Switches** and view its artifacts: the EOS configuration that PyAVD rendered from the fabric design. See [Viewing artifacts](./viewing-artifacts.md).
- **A service request.** Sign in to the portal as `alice` and request a network segment. Infrahub creates a branch, a generator builds the VLAN, subnet and gateway on that branch, and a proposed change shows the difference. Sign in to Infrahub as `alex` to review and merge it. [Service request workflows](./demo-workflows.md) walks through four requests, each through the portal and by hand in Infrahub.
- **A change on a branch.** Edit the fabric design on a branch and open a proposed change. The proposed change shows the changed objects and the changed configurations before anything is merged.

<!-- vale Google.Spelling = YES -->

## Stop, start and rebuild

| Command | What it does |
| --- | --- |
| `uv run invoke stop` | Stops the stack and keeps its data |
| `uv run invoke start`, then `uv run invoke tooling` | Starts the stack again. `start` does not start Dex and the portal, and recreating the Infrahub server disconnects them; `tooling` recreates both |
| `uv run invoke bootstrap --fresh --no-lab` | Deletes the stack and its data and builds it again from nothing |

Do not run `uv run invoke bootstrap --no-lab` a second time without `--fresh`. The second run repeats the fabric generators against a fabric that is already cabled, and those generators delete interfaces that are in use.

To move to the full lab later, run `uv run invoke bootstrap --fresh` on a machine that meets the [full lab requirements](./setup-lab.md#requirements).

More detail on this mode, including how Dex and the portal share the Infrahub server's network, is in [Infrahub without the lab](./developer-guide/bootstrap.md#infrahub-without-the-lab).
