---
title: Builder demo
description: Release a prepared capability from the Git remote, review its data in Infrahub, then move the repository ref to make its code live.
audience: user
---

# Builder demo

The builder demonstration adds a capability, the internet-access service for a WAN
customer, and takes it through an Infrahub proposed change. The work is prepared
beforehand and released on cue, so the time spent generating it is skipped and the
review is the live part. Say so on stage: the branch is prepared output.

## How it reaches Infrahub

The repository is registered as a **read-only repository** that tracks one `ref`. Infrahub
imports that ref into its default branch. It creates no branch from Git and pushes nothing,
so it needs no write credential on the remote. Changing the `ref` is what makes new code live.

A `CoreRepository` behaves differently: it turns each remote branch into an Infrahub branch
and pushes it back. Measured on this stack, that push failed with no write credential and the
branch was left `sync_with_git: False`, never imported. That is why the demo does not use one.

A Git ref and an Infrahub branch are different things, and the demo uses both:

| What | How it arrives | Reviewed in |
| --- | --- | --- |
| Queries, transforms, templates, checks, menus | The repository `ref` moves to the released branch | Git, on the remote |
| Schema and the `acme-internet` object | Loaded onto a plain Infrahub branch | The Infrahub proposed change |

`.infrahub.yml` has no `schemas:` or `objects:` section, so a repository import carries code
only. The proposed change therefore shows the schema and data diff. The code takes effect
after the merge, when the ref moves.

Three branches take part:

- **`main`** has the capability removed. It is the baseline.
- **`stage/internet-access`** is the baseline plus the implementation, kept in the local checkout.
- **`demo/internet-access-<n>`** is the remote branch a release publishes. The `ref` points at it.

## One-time setup on a fresh stack

Register the repository against the Git remote when the stack is first loaded:

```bash
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
# Optional. A private remote needs a read token; it is written to a temporary file and deleted.
# export INFRAHUB_REPOSITORY_TOKEN=<read-only token>
uv run invoke bootstrap --fresh
```

Use a fresh stack. Infrahub refuses to change an existing repository's kind in place, and to
delete one while trigger actions reference its generators. The default (`/upstream`, the
bind-mounted checkout) is unchanged when the variable is not set.

`main` must be pushed to the remote first, and the staged branch must descend from the
`main` Infrahub has imported.

## Release

```bash
uv run invoke demo-release     # publish stage/internet-access as demo/internet-access-1
```

It does these steps, and stops with a message when one fails:

1. Runs `git push origin stage/internet-access:demo/internet-access-1`. The `source:destination`
   form publishes the staged branch under another name without checking it out.
2. Creates the Infrahub branch `demo/internet-access-1`.
3. Loads the staged schema and `objects/37_otternet_wan_services.yml` onto it, read from the
   staged commit with `git archive`.
4. Opens the proposed change, then re-runs its checks. A first pass can race the data just
   loaded, so the re-run is what makes the checks judge the final branch.

Review the proposed change and merge it. Nothing reads the new kind yet, so the merge is safe.

## Activate

```bash
uv run invoke demo-activate    # point the repository ref at demo/internet-access-1
```

Infrahub imports the released commit into `main`: the transform, template, check and menu.
The artifacts are regenerated, so `isp-pe1` renders `statement 30`, and the reconciler pushes it. Run it
after the merge. The other order leaves queries on `main` naming a kind `main` does not have.

## Rehearse again

```bash
uv run invoke demo-reset       # ref back to main, kind and data removed, branches deleted
uv run invoke demo-release --run 2
```

`demo-reset` works whether or not the merge happened. Never reuse a name: a commit Infrahub
has pulled is not rewritten, so each release takes the next number.

## Before relying on it

Measured on a fresh stack, the whole path took about two minutes from the ref move to the router:

| Step | Measured |
| --- | --- |
| `demo-release` to a ready proposed change | about 1 minute, six additions, all validators green |
| Ref move to the commit imported | 29 seconds |
| Import to the `isp-pe1` artifact carrying `statement 30` | 20 seconds |
| Artifact to the router (reconciler cycle) | about 30 seconds |
| Acme's site to the internet host | HTTP 200 after, no response before; globex has none either way |

Moving the ref back to `main` does not re-render the artifacts by itself, so `demo-reset`
and `demo-activate` regenerate them explicitly.

Not yet measured: a private remote needs a read token, and that path is untested.
