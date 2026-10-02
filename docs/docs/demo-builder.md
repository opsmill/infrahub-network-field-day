---
title: Builder demo
description: Release a prepared capability from the Git remote into Infrahub on cue, and review it as a proposed change.
audience: user
---

# Builder demo

The builder demonstration adds a capability, the internet-access service for a WAN
customer, and takes it through an Infrahub proposed change. The work is prepared
beforehand and released on cue, so the time spent generating it is skipped and the
review is the live part. Say so on stage: the branch is prepared output.

## How a branch arrives

A pushed Git branch and an Infrahub branch are different things, and the demo uses both.

| What | How it reaches the Infrahub branch |
| --- | --- |
| Queries, transforms, templates, checks, menus | A push to a branch Infrahub imports |
| Schema and the `acme-internet` object | `infrahubctl schema load` and `object load` onto that branch |

`.infrahub.yml` has no `schemas:` or `objects:` section, so a repository import carries
code only. `invoke demo-release` does both halves.

Three branches take part:

- **`main`** has the capability removed. It is the baseline.
- **`stage/internet-access`** is the baseline plus the implementation. Its name never
  matches the import filter, so it can sit on the remote without being imported.
- **`demo/internet-access-<n>`** exists only after a release. Creating it is the trigger.

## One-time setup on a fresh stack

Point Infrahub at the Git remote instead of the bind-mounted checkout, and let `demo/`
branches in:

```bash
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
# A private remote also needs a read token. It is written to a temporary file and deleted.
export INFRAHUB_REPOSITORY_TOKEN=<read-only token>
export INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES='["main","demo/.*"]'
uv run invoke bootstrap --fresh
```

On a running stack, `uv run invoke demo-filter --restart` applies the branch filter. It does
not re-point an existing repository: `test-repository` stores its location and commit, so use a
fresh stack for the demo.

The repository default (`/upstream`) and the `["main"]` filter are unchanged. Every extra
synced branch costs about 171 automations, which is why the filter is a demo-time override.

`main` must be pushed to the remote first, and the staged branch must descend from the
`main` Infrahub has imported.

## Release

```bash
uv run invoke demo-release              # pushes stage/internet-access to demo/internet-access-1
```

It does these steps, and stops with a message when one fails:

1. Checks `stage/internet-access` exists and that the running task worker would import
   `demo/internet-access-1`.
2. Runs `git push origin stage/internet-access:demo/internet-access-1`. The `source:destination`
   form publishes the staged branch under a different name without checking it out.
3. Waits for the Infrahub branch to appear, then for the repository import on it to reach the
   pushed commit.
4. Loads the staged schema and `objects/37_otternet_wan_services.yml` onto the branch, read from the
   staged commit with `git archive`.
5. Opens the proposed change, then re-runs its checks. A first pass can race the data just
   loaded, so the re-run is what makes the checks judge the final branch.

## Rehearse again

```bash
uv run invoke demo-reset --run 1
uv run invoke demo-release --run 2
```

Never reuse a name. A commit Infrahub has pulled is not rewritten, so each release takes
the next number.

## Before relying on it

These are not yet measured on a stack:

- How long Infrahub takes to notice a pushed branch. Push early enough that the wait is not
  on stage, and keep a second branch released as the fallback.
- Whether merging a `sync_with_git` branch does anything on the Git side.
- Whether the `isp-pe1` artifact diff appears on the branch. The WAN kinds have no generator,
  so the diff comes from the proposed change's artifact checks.
- That a read-only credential is enough for a remote with more than one branch.
