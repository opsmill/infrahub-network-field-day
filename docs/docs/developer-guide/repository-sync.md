---
title: Repository sync and what wedges it
description: How Infrahub imports this repository, why a failed import is not retried, and why only main is imported.
audience: developer
sidebar_position: 31
---

# Repository sync and what wedges it

Infrahub clones the repository over git and imports what it finds: queries, generators,
transforms, checks, artifact definitions, and menus — **from `main` only**, see the end of this
section. Two behaviours are worth knowing before debugging a change that never arrives.

**A failed import is not retried until the commit changes.** Infrahub compares the commit it
has against the repository's HEAD, and an unchanged hash means there is nothing to do — even
when the last import failed halfway. The repository sits at `sync_status: error-import`
indefinitely and polling does not help. Recovery is a new commit, not patience.

**Never rewrite a commit Infrahub has already pulled.** `git commit --amend`, `git rebase` and
`git reset` on an already-synced commit leave Infrahub's clone holding a commit that is no
longer an ancestor of `main`, and every sync afterwards fails with
`Unable to pull the branch main for repository test-repository, there are conflicts that must
be resolved`. The message says "conflicts" and names no file, because there is no file conflict
— the histories have diverged.

The diagnosis is that `operational_status` reads `error` while `sync_status` still reads
`in-sync`, so the one-line summary looks half-healthy; compare the repository's `commit` against
`git log` and check whether it is still an ancestor:

```bash
git merge-base --is-ancestor <repository commit> HEAD && echo ok || echo diverged
```

Recovery is to make it an ancestor again rather than to force anything: `git merge -s ours
<orphaned commit>` keeps the working tree exactly as it is and records the orphaned commit as a
second parent, so the clone fast-forwards on its next poll. Re-cloning the repository object
works too and throws away its artifact and check history.

**A partial import leaves the graph inconsistent and reports nothing.** One observed run
registered the new `CoreGraphQLQuery` and not the `CoreGeneratorDefinition` beside it, because
the import failed on an unrelated menu upsert after the queries and before the generators. That makes
"the query is there, the generator is not" a symptom of a failed import rather than of a
malformed definition. Check `sync_status` on the `CoreRepository` first:

```bash
# sync_status should be `in-sync`; `error-import` means the last import failed
uv run infrahubctl repository list
docker compose logs task-worker --since 10m | grep -i "Failed to synchronize"
```

The failure seen here was a race between the two `task-worker` replicas importing the same
repository, surfacing as `Multiple CoreMenuItem nodes have the same hfid` on a menu item whose
HFID is not in fact duplicated.

**Infrahub imports only `main`, and `INFRAHUB_GIT_IMPORT_SYNC_BRANCH_NAMES` is why.** The
CoreRepository's `/upstream` is this checkout, bind-mounted, and by default Infrahub turns
**every local git branch** of its source into an Infrahub branch — each agent worktree and each
feature branch. Every Infrahub branch registers about 171 Prefect automations (display labels,
human-friendly ids, profile refresh) and imports the repository for itself. Measured with a
handful of worktrees: the task manager at 100% CPU, 3,868 automations, 126 queued runs,
SQLAlchemy pool timeouts, and `set_state` 500s that failed a portal request's generators with
`One or more generators failed`. Nothing named the branches as the cause.

`docker-compose.override.yml` sets the variable to `["main"]` on the task workers (where the git
sync runs) and the server. It is Infrahub's own filter, `get_filtered_remote_branches`: a JSON
list of names or regexes tried with `re.fullmatch`. Things to know:

- **The developer loop is unchanged.** Commit or merge to the checkout's `main` and the next poll
  imports it; `/upstream`, the CoreRepository and its stored commit did not move, so the
  `merge-base --is-ancestor` diagnosis above still applies.
- **It filters new branches, not ones Infrahub already has.** A branch that already exists
  in Infrahub with `sync_with_git: true` keeps syncing whatever its name. Delete the Infrahub
  branch once and it does not come back. Every branch this repository creates, the portal's,
  `invoke avd --branch`, the demo scripts, is `sync_with_git: false`, so their proposed changes
  run `main`'s generators, checks and transforms, as before.
- **A mirror was considered and rejected.** A main-only bare mirror kept current by a fetch
  loop would work too, at the cost of a service, a poll interval stacked on Infrahub's own, and
  a second place Infrahub pushes to. The setting does the same with no moving part.
- `tests/unit/test_repository_sync_contract.py` pins the value and the `/upstream` mount.
  Integration tests are unaffected: they build their own Infrahub and repository.

The builder demo registers a repository on the Git remote instead, in read-only or read-write mode, so its filter and credentials differ from the defaults here. See [Builder demo](../demo-builder.md).
