---
title: Builder demo
description: Release a prepared capability with one command, review it as a proposed change in Infrahub, merge it, and take it back out, without writing to the upstream main.
audience: user
---

# Builder demo

The builder demonstration adds a capability, the internet-access service for a WAN customer, and
takes it through an Infrahub proposed change. The work is prepared beforehand and released on
cue, so the time spent generating it is skipped and the review is the live part. Say so on
stage: the branch is prepared output, not a live agent run.

The whole cycle, from release to reset, was run on a fresh stack with the final code and every check passed. The release and merge half was repeated three times. In the runbook this is [act six](./demo-runbook.md#act-six-the-builder-branch), and `uv run invoke demo-run` runs it with a PASS or FAIL line for every check.

## What the audience sees

| Step | What happens | Measured |
| --- | --- | --- |
| `invoke demo-release` | A branch arrives in Infrahub with its code, schema and data, and a proposed change opens. It says `Ready` only once every validator has finished and passed | 2 to 4 minutes on earlier runs; 414 seconds in the 2026-10-05 run on a freshly bootstrapped stack, straight after acts one and two |
| Review in the Infrahub UI | 29 validators in the 2026-10-05 run (32 in an earlier run), every artifact check and every rule check, all run with the branch's own code. The diff is the new schema node and fields, the menu entry, `acme-internet` and the three queries that name the new kind | passes |
| Merge in the Infrahub UI | The merge also merges git and pushes it to `demo-main` | 50 seconds |
| After the merge | The `isp-pe1` artifact carries `statement 30` | 15 seconds |
| The router | The reconciler pushes it | within a minute |
| The outcome | Acme's site gets HTTP 200 from the internet host. Globex's still gets nothing | |
| `invoke demo-reset` | Everything back to the baseline, ready to go again | 320 seconds |

The release time is Infrahub's, not the command's. The task workers pull a pushed branch 75 to 256 s
after the push, whatever the repository's git-sync schedule is. A shorter schedule was tried and does not
help, so do not retry it. Plan for 2 to 4 minutes, and rehearse on the stack you will present on: the 2026-10-05 run took 414 seconds.

## One-time setup

Keep Infrahub's default of **two task workers**. That is what a real stack runs, and a single worker would have
to run every generator and artifact task alone. One worker was measured and does remove the divergence described
under [the task workers](#the-task-workers), but it is not the configuration to show, so nothing needs setting.
A worker that has just cloned the remote sits on `main` instead of `demo-main`. `invoke demo-release`,
`demo-reset` and `demo-restore` correct that before they start, and print what they changed.

The repository is registered against the Git remote when the stack is first loaded, and the kind of
repository cannot change afterwards: Infrahub refuses to change it in place, and refuses to delete one
while trigger actions reference its generators. Do this on a fresh stack.

```bash
source ~/.zshrc                      # exports NFD_GITHUB_TOKEN, a token with write access to the repo
export INFRAHUB_REPOSITORY_URL=https://github.com/opsmill/infrahub-network-field-day.git
export INFRAHUB_REPOSITORY_MODE=readwrite
export INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES='["demo/.*"]'
uv run invoke bootstrap --fresh
```

- **The token needs write access.** Infrahub pushes the branches it creates and the merges it makes.
  Bootstrap checks first, with a dry-run push, which has to authenticate for write, and stops with
  the message from git if it cannot. A fine-grained token needs **Contents: Read and write** on the repository,
  and the organization may need to approve it. A classic token needs the `repo` scope, and the account
  needs write access to the repository. The username does not matter, because GitHub identifies the
  owner from the token. The `permissions` field shows your own role on the repository, not what
  the token may do, so it cannot be used to check.
- **Turn on branch protection for `main`** on the remote. Infrahub only pushes `demo-main`, but a token
  with write access could push anywhere, and protection turns that from a measured fact into a guarantee.
- **`demo-main` is created for you** at the tip of `main` if it is missing, and `uv run invoke bootstrap --fresh`
  deletes it and creates it again at the tip of `main` after the old stack is destroyed, so a new stack never starts
  from the tree an earlier demonstration left. It is the branch Infrahub
  treats as its own `main`, so merges land there and the real `main` is never written. Bootstrap also checks the
  four settings above before it destroys anything. See [bootstrap](./developer-guide/bootstrap.md).
- The token reaches Infrahub through a temporary file and is not kept in the repository. To replace it on
  a running stack, for example when it expires, run `uv run invoke demo-credential`.

## Build the staged branch

```bash
uv run invoke demo-stage
```

This builds `stage/internet-access` on your machine: `main` with the capability put back, plus the
`schemas:` and `objects:` sections in `.infrahub.yml` that let one repository import carry the schema
and the data as well as the code. `main` declares neither, so nothing else loads them. It is a prepared
implementation, the revert of the commit that removed the capability, and you should say so when you show it.

To show a real Spec Kit build instead, cherry-pick that branch's commits onto today's `main`:

```bash
uv run invoke demo-stage --implementation speckit/internet-access --name internet-access-speckit
uv run invoke demo-release --name internet-access-speckit
uv run invoke demo-reset --name internet-access-speckit
```

The branch `speckit/internet-access` holds the Spec Kit run: the specification, plan and tasks under
`specs/035-internet-access/`, and `RUN-NOTES.md` there, which says plainly what the skills produced, where
a correction was needed and where the removed code was consulted. Its schema, queries, check and menu
differ from the revert in 17 files, so read the notes before claiming the two are the same. Measured on the
lab, both gave a proposed change with every validator green and the same diff (6 added, 0 removed), statement
30 on `isp-pe1`, and acme reaching the internet host while globex does not. The Spec Kit branch lists the
Internet Access menu entry after Tenant Clouds instead of before it.

The branch is never pushed under its own name. Rebuild it with `--force` when `main` has moved on. The reset
takes the capability back out by comparing the staged branch with the `main` commit it was cut from, so a staged
branch that is older than the files it changed leaves those files at the older version, and `demo-run` reports
that the baseline tree is not the one it started with.

## Run it

```bash
uv run invoke demo-release
```

One command. It first refuses a staged branch that changes no file besides `.infrahub.yml` compared with the
`main` commit it was cut from, because that branch carries no schema and the release would wait for it until the
timeout. The message says to rebuild the branch with `invoke demo-stage --force`. It then stops with a message
when a step fails:

1. Creates the Infrahub branch `demo/internet-access-1` with Sync with Git on. Infrahub creates the git
   branch itself and pushes it.
2. Fetches that branch, copies the staged branch's contents onto it as one commit and pushes. That is a
   fast-forward, so nothing Infrahub holds is rewritten.
3. Waits until the branch is fully imported, and opens nothing before that: the pushed commit imported
   and in sync, **every task worker having pulled it into its own clone**, the schema and the objects
   present, and no task still queued or running for the branch, on two polls in a row. A failed task
   stops it with the task's title.
4. Opens the proposed change and runs its checks again. The first pass can race the import, so the
   second is what makes the checks judge the final branch.
5. Waits until every validator of the proposed change has completed and passed, on two polls in a row,
   counting only the latest run of each validator. A failure stops it with the names of the validators that
   did not pass. Only then does it print `Ready`.

The release number is chosen for you: `demo-release` takes the next one that no Infrahub branch, remote
branch or worker clone has used, and `demo-reset` removes the latest one in use. Pass `--run <n>` to name
one yourself.

Review the proposed change in the Infrahub UI and merge it there. Then check the router and the two
sites. The merge moved the code, so nothing else is needed.

## Rehearse again

```bash
uv run invoke demo-reset               # removes the latest release; --run <n> names one
uv run invoke demo-release             # takes the next unused release number
```

`demo-reset` works whether or not the merge happened, and it can be run again if it was interrupted.
It decides what to undo from the data and from git, so a half-done reset is finished, not skipped.

After a merge, the capability is on `demo-main`, and the reset takes it back out through Infrahub, not
around it. It creates a second branch with Sync with Git on and commits on it the tree of `demo-main`'s current
tip with only the release's own changes undone, removes the kind's data and schema node there, and merges it.
Infrahub's own merge then pushes the restored `demo-main`. It then regenerates the artifacts and deletes every
branch it made, in Infrahub and on the remote.

What the reset undoes is the difference between the staged branch and the `main` commit the staged branch was
cut from (`git merge-base main stage/<name>`):

- A file the staged branch added is removed from `demo-main`.
- A file the staged branch changed is returned to its version at that commit, even if `demo-main` was edited
  afterwards. The command prints each such file, so the edit is not lost silently.
- The entries the staged branch added to `.infrahub.yml` (the capability's declarations, and the `schemas:` and
  `objects:` sections) are removed. Other entries are kept. An entry that cannot be found is printed.
- Every other file keeps the version `demo-main` has now.

The earlier reset copied the whole tree of the merge-base of the Infrahub branch and the staged branch, which is
an old `main` commit, because `demo-main`'s history never contains the newer commits of the remote `main`. Every
reset therefore moved `demo-main` back to that old tree and reverted the later changes to files such as
`triggers.yml`, `tasks.py` and the skills. This was found on the live stack.

Measured once on the live stack with `demo-stage --force`, `demo-release`, a merge and `demo-restore`: the restore
put 37 files back to the baseline, `git diff origin/demo-main main` was empty afterwards, and `make -C lab verify`
reported 121 passed and 0 failed.

Not verified: a reset of a capability whose files were deleted on `main` after staging, and a staged branch built
with `--implementation` after `main` changed the same files as that branch.

## Run the whole demonstration, and restore the lab

```bash
uv run invoke demo-run                  # acts one and two through the portal, then this branch, then its reset
uv run invoke demo-run --acts builder   # only this branch
uv run invoke demo-restore              # the whole lab back to the baseline
```

`demo-run` prints a PASS or FAIL line for every check and a timing table, and exits non-zero on any failure.
`demo-restore` includes `demo-reset`, then withdraws every application and grant the acts created and checks
the lab against the baseline; the [runbook](./demo-runbook.md#run-it-all-and-put-it-back) lists its steps. Both
change the live lab, and `demo-restore` can be run again if it was interrupted.

## Act one picks its application from the catalogue

`demo-run` starts with act one, the portal request for **Exposed application, with access**. That request no
longer types a chart: it submits one value, the picker's entity ref `resource:default/whoami`, and the rehearsal
then checks that the application was pinned from that entry. The checks are listed in the
[runbook](./demo-runbook.md#act-one-ask-for-an-application); the rendered Crossplane artifact must still show chart
`whoami` 6.0.0 and the entry's values.

The application catalogue is **seed data** (`objects/35a_otternet_app_catalogue.yml`, with the three
infrastructure entries' values set by `scripts/seed_app_payloads.py`), so none of this branch's commands touch
it. `demo-restore` withdraws the application act one created, which was pinned from `whoami`, and leaves the
entry in place. The `ServiceApplicationDefinition` schema node belongs to the baseline schema, not to the capability
this branch stages, so `demo-reset` never removes it. Changing an entry between two runs changes nothing already
requested: an application keeps the chart it was pinned to.

## The task workers

With `default_branch: demo-main` and a remote whose own default is `main`, the two task workers can disagree
about the default branch, and a merge can succeed in Infrahub's graph without ever reaching the remote.
Measured, with two workers and no correction:

- A worker's main worktree can sit on `main` instead of `demo-main`. Infrahub pushes a merge with
  `git push origin demo-main`, which fails there with `src refspec demo-main does not match any`. A worker
  that has just been recreated clones the remote this way.
- Infrahub never imports a commit pushed to `demo-main` from outside, and the periodic git sync broadcasts
  the local default branch of the worker that happens to run it as the pinned commit that every worker
  hard-resets to, once a minute. After a merge only one worker has the new commit, so the next sync pins a
  stale one and the whole pool converges on a commit older than the remote's. The next merge builds on it
  and its push is a non-fast-forward, which Infrahub does not report. Three merges in the first
  builder runs never reached the remote.

This is a finding for Infrahub: the sync should pin the remote's tip, or a push that is rejected should fail the
merge.

`invoke demo-release`, `demo-reset` and `demo-restore` therefore run a check first. It fetches the remote's
`demo-main` into every worker, puts the worker on that branch at that commit, and creates the `commits/<sha>`
worktree Infrahub reads, and it prints a line for every worker it changed. It refuses, naming the worker, if a
worker has local changes it would lose. Do not remove it, and run a merge only through these commands.

Measured with the default two workers, starting from a worker that had just been recreated and sat on `main`: the
check moved it to `demo-main` on its own, a full `demo-run` passed 44 checks with none failed or warned, and
`demo-restore` finished with `make -C lab verify` at 121 passed and 0 failed.

## Rules that each cost a failed run

- **Do not push to `demo-main` yourself.** Infrahub never imports a commit pushed there from outside:
  the remote `main` shadows it, and the worker logs "Ignoring import of mismatched default branch." A
  stray commit also makes Infrahub's next merge push non-fast-forward. Deleting `demo-main` and
  recreating it does not work either, because Infrahub's clone has already pulled the merge commit.
- **Never reuse a branch name.** Deleting a branch in Infrahub leaves the workers' local ref behind, so a
  branch of the same name starts on the old commit, nothing looks new, and the import never happens. Each
  release takes the next `--run` number, and each reset attempt names its branch with a timestamp.
- **Rebuild the staged branch after `main` changes the files the capability touches.** The reset returns
  those files to the version at the commit the staged branch was cut from, so an old staged branch writes old
  versions back.
- **Do not merge before the command says the branch is fully imported.** The graph records the import
  before the workers pull it. A merge in that gap reads a stale local branch, merges a commit that
  `demo-main` already holds, and does nothing: the data merges and the code does not.
- **Branches Infrahub creates from a remote push have Sync with Git off, and it cannot be changed.**
  `BranchUpdate` only accepts a name and a description. Only a branch created with it on has a merge that
  also merges git, which is why the release creates the branch itself.

## Read-only mode

Without `INFRAHUB_REPOSITORY_MODE=readwrite`, bootstrap registers a read-only repository that tracks one
`ref`. It needs no token and pushes nothing, and merging a proposed change moves the ref on `main`, so the
code goes live with the merge. `invoke demo-release` pushes the staged branch, creates the Infrahub branch
and sets the ref on it. It was measured too, and it is the simpler choice when write access to the remote
is not available. For a private remote, also set `INFRAHUB_REPOSITORY_PRIVATE=1` and `NFD_GITHUB_TOKEN`
with read access.
