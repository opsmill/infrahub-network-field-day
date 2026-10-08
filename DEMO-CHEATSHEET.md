# Demo cheat sheet

Commands for setting up the stack and running the three demo acts. Details are in
`docs/docs/demo-runbook.md`, `docs/docs/demo-builder.md` and `docs/docs/developer-guide/bootstrap.md`.

## Setup on a fresh stack

```bash
source ~/.zshrc                      # exports NFD_GITHUB_TOKEN and INFRAHUB_API_TOKEN
uv run invoke bootstrap --fresh --demo [--no-release]    # about 25 minutes
uv run invoke ready                  # every check must say PASS
```

`--demo` sets the read-write repository mode and the `demo/.*` import setting. It fills in the repository
URL only if `INFRAHUB_REPOSITORY_URL` is unset. It needs `NFD_GITHUB_TOKEN` (write access to the repository)
and `INFRAHUB_API_TOKEN`. Bootstrap checks both before it destroys anything.

### Choose whether the demo branch is released during bootstrap

| Option | What happens at the end of bootstrap | When to use it |
| --- | --- | --- |
| `--demo` (release is on by default) | Bootstrap builds `stage/internet-access` and runs `demo-release`. The `demo/*` branch and its proposed change are already open. Adds 2 to 8 minutes | You want to show the review and merge only, and skip the wait for the import |
| `--demo --no-release` | No branch is released. Run `uv run invoke demo-release` on stage | You want the audience to watch the release, or you want to rehearse the release step again |

- **Effect of the default release on act three:** The release is already done, so skip the `demo-release` step in
  act three. Open the existing proposed change instead.
- **If the release fails during bootstrap:** Bootstrap still runs the readiness checks, then exits with an error
  that names `uv run invoke demo-release` as the repeat.
- **`--fresh` deletes every `demo/*` branch:** It deletes them on the remote and locally, and recreates
  `demo-main` at the tip of the remote `main`. A demo stack therefore starts from the remote `main`, not from
  local commits. Bring local commits in with `git pull --ff-only origin main` and `uv run invoke demo-advance`.

## Before each presentation

```bash
git pull --ff-only origin main
uv run invoke demo-advance           # only if ready reports that demo-main differs from main
uv run invoke demo-stage --force     # builds the staged capability branch, without the service
uv run invoke ready                  # confirm all PASS
```

- **Infrahub sign-in:** Sign in to the Infrahub UI as `alex`. The password is `INFRAHUB_NETWORK_ADMIN_PASSWORD` in `.env`.
- **Claude Code for act two:** Start it from a shell that has loaded `.env`: `set -a; source .env; set +a; claude`.
- **Task workers:** Do not restart a task worker in the minutes before a release.

## Act one: a request through the portal

1. In the Backstage portal, request an **Exposed application, with access**.
2. In Infrahub, open the proposed change and wait for every validator to pass.
3. Merge it in the Infrahub UI as `alex`.

## Act two: Grafana access through an agent

1. In Claude Code, ask for the branch office to get access to Grafana (`otternet-metrics`).
2. The agent opens a proposed change on an `mcp/session-*` branch. Make sure the agent re-runs the checks
   (`check_type: ALL`) before you merge.
3. Merge it in the Infrahub UI as `alex`. The agent never merges.

## Act three: the builder branch

```bash
uv run invoke demo-internet-evidence --phase before       # nobody has internet
uv run invoke demo-release                                # skip if bootstrap already released; prints Ready: <link> after 2 to 8 minutes
```

1. Review the proposed change and merge it as `alex`.
2. Run `uv run invoke demo-internet-evidence --phase capability`. No router changed, and nobody has internet.
3. Run `uv run invoke demo-request-internet`. It prints `Ready: <link>`. Review the one new node and merge it as `alex`.
4. About 90 seconds later, run `uv run invoke demo-internet-evidence --phase request`. Only acme has internet.

## After the demo

```bash
uv run invoke demo-reset       # takes the capability back out, about 5 minutes
uv run invoke demo-restore     # the whole lab back to baseline
make -C lab verify             # expects 121 passed
```

## Delete demo branches on GitHub

`demo-reset` and `demo-restore` delete the `demo/*` branches in Infrahub and on the remote. Use these commands only
to clear branches they left behind. Delete the Infrahub branch first, then the remote one, so Infrahub does not
re-import a branch that is gone or keep one whose remote copy is missing. Never delete `demo-main`.

```bash
git ls-remote --heads origin 'demo/*'                  # list the demo branches on GitHub
uv run infrahubctl branch list                         # list the Infrahub branches
uv run infrahubctl branch delete <name>                # delete one Infrahub branch
git push origin --delete demo/<name>                   # delete one branch on GitHub
git ls-remote --heads origin 'demo/*' | awk '{sub("refs/heads/","",$2); print $2}' | xargs -r git push origin --delete   # delete every demo/* branch on GitHub
git fetch --prune origin                               # drop the stale local tracking refs
git branch --list 'demo/*' | xargs -r git branch -D   # delete local demo/* branches
```

`demo-main` does not match `demo/*`, so these commands leave it alone.

## Rehearse everything without a person

```bash
uv run invoke demo-run                    # acts one, two and three; merges through the API
uv run invoke demo-run --restore          # and finish with demo-restore
uv run invoke demo-run --acts builder     # act three only
```

`demo-run` changes the live lab.

## Not measured

- The timings of `demo-request-internet` and of the second merge are not measured in the two-part version.
- The builder timings in `demo-builder.md` are from 2026-10-05, from the single-merge version.
