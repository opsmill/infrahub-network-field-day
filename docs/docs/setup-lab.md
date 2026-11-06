---
title: Set up the full lab environment
description: Bring up Infrahub, the OTTERNET ContainerLab devices, the tooling cluster and the Kubernetes workload cluster on one Linux host, with every device configured from its artifact.
audience: user
---

# Set up the full lab environment

The full lab is the OTTERNET network running beside Infrahub on one Linux host: Arista cEOS switches, a Junos vSRX firewall, SR Linux WAN routers, a branch office desktop, a Kubernetes workload cluster, and a second cluster for the service portal and its sign-in service. One command builds it and configures every device from the artifact Infrahub rendered for it.

Use this environment to run the [demo runbook](./demo-runbook.md), or to develop against real devices. To show the Infrahub workflow on a laptop without devices, use [Set up a demo environment without the lab](./setup-demo.md).

## Requirements

- Linux with about 48 GB of memory and 8 or more CPU cores.
- At least 20 GB of free disk where Docker keeps its data, and about 60 GB for a first run on an empty machine.
- `/dev/kvm`, because the vSRX firewall is a virtual machine. On a cloud instance, this means nested virtualisation or a bare-metal instance type.
- `sudo` without a password, because ContainerLab runs under `sudo` and the run is unattended.
- Docker with Compose v2, usable without `sudo`.
- `git`, `curl`, `openssl`, [ContainerLab](https://containerlab.dev/install/), `kubectl` and `helm`.
- Node 22 or 24 with Corepack enabled (`corepack enable`), to build the portal.
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
   uv run invoke prereqs
   ```

   It lists each missing tool, too little memory or disk, a missing `/dev/kvm` or `sudo`, a port another program already uses, and a download site the machine cannot reach. It also warns when the inotify limits are lower than the Kubernetes nodes need; the lab deploy raises them, and `OTTERNET_PERSIST_LIMITS=1` keeps them after a reboot.

4. Bring the environment up:

   ```bash
   uv run invoke bootstrap
   ```

   The run takes 20 to 30 minutes. It gets the cEOS, vSRX and branch desktop images from `registry.opsmill.io`, builds and loads Infrahub, generates the fabric on a branch and merges it, deploys the lab, configures every device from its artifact, starts the portal and the Kubernetes cluster, and starts the reconciler. The [lab image sources](https://github.com/opsmill/infrahub-network-field-day/blob/main/lab/README.md#images) list the other ways to get the images.

The run ends with the readiness checks. It exits with an error if any check fails, and each failed line names what to run. Run the same checks at any time with `uv run invoke ready`. The checks are listed in [What a finished bootstrap checks](./developer-guide/bootstrap.md#what-a-finished-bootstrap-checks).

## Sign in

| Where | Account | Password |
| --- | --- | --- |
| Infrahub, `http://localhost:8000` | `admin` | `infrahub` |
| Infrahub, as the network engineer who edits network data and merges proposed changes | `alex` | `INFRAHUB_NETWORK_ADMIN_PASSWORD` in `.env` |
| The branch desktop, through Guacamole at `http://<host>:8080/` | `branch` | `branch` |
| The portal, `https://10.90.0.11:32001`, opened from the branch desktop | `alice@otternet.lab` or `bob@otternet.lab` | `password` |

The portal is reachable only from the branch side of the lab, so open it in the browser on the branch desktop. `make -C lab guac` prints the Guacamole address for this host.

Semaphore (`http://localhost:3000`), the Neo4j browser (`http://localhost:7474`) and Prefect (`http://localhost:4200`, where generator, transform and check runs are listed) also run on the host.

## Stop, start and rebuild

| Command | What it does |
| --- | --- |
| `uv run invoke stop` | Stops the Infrahub stack and keeps its data. The lab keeps running |
| `uv run invoke start` | Starts the Infrahub stack again |
| `uv run invoke bootstrap --fresh` | Deletes the Infrahub stack and the lab and builds both again from nothing |

Do not run `uv run invoke bootstrap` a second time without `--fresh`. The second run repeats the fabric generators against a fabric that is already cabled, and those generators delete interfaces that are in use.

Every stage of the bootstrap, its flags, and the order the stages run in are described in [Bootstrapping the whole environment](./developer-guide/bootstrap.md#bootstrapping-the-whole-environment).
