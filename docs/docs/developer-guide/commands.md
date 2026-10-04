---
title: Commands reference
description: The invoke, pytest, linter and infrahubctl commands agents may use, with the pitfalls of each.
audience: developer
sidebar_position: 36
---

# Commands reference

Install and discovery:

```bash
uv sync --all-packages
uv run invoke --list
```

Invoke tasks:

```bash
uv run invoke build
uv run invoke start
uv run invoke stop
uv run invoke destroy
uv run invoke restart
uv run invoke restart --component=infrahub-server
uv run invoke load
uv run invoke load-schema
uv run invoke load-menu
uv run invoke avd                       # regenerate AVD hostvars, structured configs and artifacts
uv run invoke avd --branch my-change    # ... on a branch, so the result can be reviewed
uv run invoke avd --topology            # BUILD-TIME ONLY: also build the fabric and its cabling
uv run invoke avd --branch b --merge    # ... on a branch, merged when it succeeds
uv run invoke bootstrap                 # the whole environment, one command
uv run invoke bootstrap --fresh         # ... destroying the stack and the lab first
scripts/verify_bootstrap.sh             # rebuild from nothing and assert the result
uv run python scripts/demo_rehearsal.py # rehearse the demo runbook up to every merge, then clean up
uv run invoke lab                       # deploy lab/'s topology with management connectivity
uv run invoke lab --destroy             # tear it down
uv run invoke provision                 # push every rendered artifact onto the running devices
uv run invoke provision --dry-run       # ... showing what would be pushed, changing nothing
uv run invoke provision --kind eos      # ... one family only: eos, srl, or junos
uv run invoke reconcile --converge      # cycle until every device is confirmed (the bootstrap path)
uv run invoke reconcile --once          # a single reconcile cycle
uv run invoke reconcile --dry-run --branch X  # report differences, change nothing
uv run invoke reconcile                 # the loop, 600s maximum, 60s floor, wakes early on a merge
uv run invoke reconcile --now           # ask the running loop for an all-device cycle now
uv run invoke backstage-build           # build the portal image (it runs in the tooling cluster)
uv run invoke tooling                   # Dex and the portal, into the tooling cluster
uv run invoke mcp                       # the MCP server beside Infrahub, as mcp-agent; also the Requester Access role
uv run invoke mcp-tokens                # alice's MCP token into .env; needs Dex (run `tooling` first)
uv run invoke ready                     # the demonstration's prerequisites, and what a person still has to do
uv run invoke metrics-exporter          # the Infrahub exporter beside Infrahub, as metrics-exporter
uv run invoke cluster                   # Cilium, Vidra, Crossplane, then the handover
uv run invoke cluster --no-handover     # ... leaving the lab in charge of all four
uv run invoke vidra                     # the operator on its own, for a re-install
uv run invoke doctor                    # FIRST thing to run when something is odd: image staleness vs commits, duplicate reconcile processes, schema.graphql freshness, repository sync_status, dangling CoreGeneratorInstance, then the `ready` checks
uv run invoke init-semaphore
uv run invoke test                      # unit tests, as CI runs them
uv run invoke test --integration        # ... plus the Docker-backed integration suite
uv run invoke lint
uv run invoke lint-ruff
uv run invoke lint-yaml
uv run invoke lint-mypy
uv run invoke lint-markdown
uv run invoke lint-prose
uv run invoke format
uv run invoke docs
```

**Do not pipe these to `tail` or `head` when the exit status matters.** A shell
pipeline reports the LAST command's status, so `invoke lint-ruff 2>&1 | tail -3` is
always successful no matter what the linter found, and a `&& git commit` after it
runs anyway. Measured: the task itself exits 1 correctly on a formatting failure and
`0` through the pipe. Read the output, then run the task on its own when its result
is a gate.

Local tests and linters:

```bash
uv run pytest tests/unit
uv run pytest tests/unit/test_avd.py
uv run pytest tests/unit/test_hostvar_ordering.py
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
uv run mypy --show-error-codes src/solution_arista_avd
uv run yamllint .
uv run rumdl check README.md AGENTS.md docs/ lab/README.md schemas/
uv run rumdl fmt README.md AGENTS.md docs/ lab/README.md schemas/
```

Markdown linting covers authored files only; vendored agent content, `specs/`, and
PyAVD-rendered output under `lab/avd/` are excluded in `[tool.rumdl]`.

Prose linting uses Vale, which is a Go binary rather than a `uv` dependency. Install the
pinned version before running `invoke lint-prose`:

```bash
curl -sL "https://github.com/errata-ai/vale/releases/download/v3.17.1/vale_3.17.1_Linux_64-bit.tar.gz" \
  -o /tmp/vale.tar.gz && tar -xzf /tmp/vale.tar.gz -C ~/.local/bin vale
vale sync
```

Use local `uv run pytest tests/integration` only for ad-hoc local/lab debugging when explicitly
appropriate.

`infrahubctl` examples:

```bash
uv run infrahubctl branch list
uv run infrahubctl branch create <branch-name>
uv run infrahubctl schema check schemas/ --branch <branch-name>
uv run infrahubctl schema load schemas --branch <branch-name>
uv run infrahubctl menu load menus/ --branch <branch-name>
uv run infrahubctl object load objects/ --branch <branch-name>
uv run infrahubctl object load repository.yml --branch <branch-name>
uv run infrahubctl object load triggers.yml --branch <branch-name>
uv run infrahubctl graphql export-schema --destination schema.graphql
# NOTE: export-schema takes no --branch flag; do not pass one.
uv run infrahubctl graphql generate-return-types generators/avd_device_hostvar.gql
uv run infrahubctl graphql generate-return-types transforms/<query>.gql
uv run infrahubctl protocols --schemas schemas --out src/solution_arista_avd/protocols.py
```

For repeated `infrahubctl` calls, define a temporary shell alias in the current session only:

```bash
alias ihctl='uv run infrahubctl'
```

The documentation site uses pnpm, not npm. Prefer `uv run invoke docs`, which runs the same
commands CI runs. To work inside `docs/` directly:

```bash
pnpm install --frozen-lockfile
pnpm run typecheck
pnpm run build
```

pnpm settings for the site live in `docs/pnpm-workspace.yaml`, not in `docs/package.json` -
pnpm no longer reads the `pnpm` field there, so overrides placed in it are ignored.
