---
title: Builder demo
description: Release a prepared capability by pushing a branch, review it in Infrahub, and merge it without touching the upstream main.
audience: user
---

# Builder demo

The builder demonstration adds a capability, the internet-access service for a WAN
customer, and takes it through an Infrahub proposed change. The work is prepared
beforehand and released on cue, so the time spent generating it is skipped and the
review is the live part. Say so on stage: the branch is prepared output.

The live action is a push, or a branch rename on the remote. Everything after it
happens in Infrahub.

## How a branch arrives

Three branches take part:

- **`main`** has the capability removed. It is the baseline.
- **`stage/internet-access`** is the baseline plus the implementation. Its name never
  matches the import filter, so it can sit on the remote without Infrahub following it.
- **`demo/internet-access-<n>`** is the name a release publishes. Creating it is the trigger.

The staged branch's `.infrahub.yml` declares `schemas:` and `objects:`, so one import carries
the code, the schema and `acme-internet`. `main` declares neither, so nothing else loads them.

```bash
git push origin stage/internet-access:demo/internet-access-1
```

The `source:destination` form publishes the staged branch under another name without checking
it out. You can also rename the branch on the remote in the GitHub UI.

## Choose a mode at bootstrap

The repository kind cannot be changed on an existing stack. Infrahub refuses to change it in
place, and refuses to delete a repository while trigger actions reference its generators. Pick a
mode and bootstrap a fresh stack.

### Read-write

Infrahub watches the remote, syncs `demo/*` branches in by itself and pushes merges to
`demo-main`, never to the real `main`. Infrahub maps its own `main` onto the repository's
`default_branch` when it pushes, so `demo-main` takes the merge instead.

```bash
source ~/.zshrc                                  # exports NFD_GITHUB_TOKEN, a token with write access
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
export INFRAHUB_REPOSITORY_MODE=readwrite
export INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES='["demo/.*"]'
uv run invoke bootstrap --fresh
```

Bootstrap checks first that the token can push (a dry-run push, which must authenticate for
write) and stops with git's message if it cannot. A fine-grained token needs **Contents: Read and
write** on the repository, and the organisation may need to approve it. The username does not
matter: GitHub identifies the owner from the token. The API's `permissions` field shows your own
role on the repository, not what the token may do, so it cannot be used to check.

It then creates `demo-main` on the remote at the tip of `main` if it is missing. The token
reaches Infrahub through a temporary file and is not kept in the repository. To replace it on a
running stack, for example after the token expired, run `uv run invoke demo-credential`.

Turn on branch protection for `main` on the remote. Infrahub only pushes `demo-main`, but a
token with write access could push anywhere, and protection makes that a guarantee.

### Read-only (the default)

Infrahub tracks one `ref` and creates no branch from Git. It needs no token, but someone has
to point it at the released branch. `invoke demo-release` does that. Merging the proposed change
then moves the ref on `main`, so the code goes live with the merge.

```bash
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
uv run invoke bootstrap --fresh
```

## Release

```bash
uv run invoke demo-release     # push, then wait for the branch, its import and the proposed change
```

In read-write mode the command creates the Infrahub branch with `--sync-with-git`, which makes
Infrahub create the git branch itself and push it. It then fetches that branch, copies the staged
branch's contents onto it as one commit and pushes. That is a fast-forward, so nothing Infrahub holds
is rewritten. The branch has Sync with Git on, which is the only kind whose merge also merges git:
branches Infrahub creates from the remote have it off, and it cannot be changed afterwards. In
read-only mode the command pushes the staged branch, creates the Infrahub branch and sets the ref on
it. Either way it then waits for the import of the pushed commit, checks the new kind arrived, opens
the proposed change and re-runs its checks. A first pass can race the import, so the re-run is what
makes the checks judge the final branch.

The proposed change runs every artifact validator and check with the branch's own code, so the
`isp-pe1` diff shows `statement 30` before the merge.

## Rehearse again

```bash
uv run invoke demo-reset --run 1
uv run invoke demo-release --run 2
```

`demo-reset` works whether or not the merge happened. It puts the code back first, removes the
kind's objects and schema node, regenerates the artifacts and deletes the branches.

In read-write mode a merge leaves the capability on `demo-main`. Reset commits the baseline's
tree on top of it and pushes that. Deleting `demo-main` and recreating it would not work: the
Infrahub clone has already pulled the merge commit, and the next merge would push it back.
Never reuse a branch name either, since a commit Infrahub has pulled is not rewritten.

## Measured, read-only mode

Measured on a fresh stack, from the ref move to the router:

| Step | Measured |
| --- | --- |
| Ref set on the branch, to the commit imported there | 24 to 100 seconds |
| Merge, to the `isp-pe1` artifact carrying `statement 30` | 40 seconds |
| Artifact to the router (reconciler cycle) | about 30 seconds |
| Acme's site to the internet host | HTTP 200 after, none before; globex none either way |

Read-write mode is not measured yet. Still to confirm: the poll delay before a pushed branch
syncs in, that a merge pushes `demo-main` and leaves `main` alone, and the forward reset.
