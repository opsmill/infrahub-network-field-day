#!/usr/bin/env python3
"""Give the Backstage portal its own least-privilege Infrahub account.

The portal used to talk to Infrahub with the stack's initial ADMIN token -- a
Super Administrator's credential, committed in `tooling/20-backstage.yaml` and
held by a long-running process on a cluster that branch users reach. Anything
able to read that Secret could write straight to `main`, load a schema, or merge
a branch without review. The portal needs none of that, so it gets
`backstage-portal`, in the `Portal Services` group, holding the `Portal Access`
role.

WHAT THE PORTAL DOES, and the grant each step needs (decision 6 = allow
everywhere, 4 = allow on branches other than the default):

- read everything: the catalogue provider mirrors every service kind, its peers,
  open proposed changes and their branches; `generators:await` reads tasks
  -- `view` on `*` (6);
- `BranchCreate`, every service create and update, the AVD
  `CoreGeneratorDefinitionRun` steps and the chart-values upload -- all on the
  request's branch -- `any` on `*` (4). A write on `main` is still refused;
- open the proposed change, which is an object ON MAIN: the global
  `edit_default_branch`, which admits the request to the default branch at all,
  plus `create` on `CoreProposedChange` (6). Object permissions still narrow
  everything else, which is why `any` stays at 4. The same pair `mcp-agent`
  needs; see `provision_mcp_agent.py`;
- write AS THE SIGNED-IN USER through the mutation `context`: the global
  `override_context` (6). Without it every create that carries
  `context: { account: ... }` is refused.

What it may NOT do: merge, approve, review, rebase or delete a branch, change
the schema, manage accounts or permissions, or write any other kind on `main`.
(`CoreProposedChangeMerge` on 1.10.6 never consults `merge_proposed_change`, so,
as for `mcp-agent`, the merge gate is the portal's own code: it has no merge
step.)

**`override_context` is the one grant that looks broad, and is.** It lets the
caller attribute a write to ANY account, so the portal is the authorization
boundary for who a request is attributed to -- exactly as it already was with
the admin token, which bypasses the check. What changes is everything else the
credential could do.

WHY A TOKEN. The portal authenticates with `X-INFRAHUB-KEY` only. Infrahub
1.10.6 mints a token only for the account that asks, so this signs in AS
`backstage-portal` to mint its own. Password and token both live in the main
checkout's `.env` (gitignored); `scripts/deploy_tooling.sh` renders the token
into the `backstage-secrets` Secret at deploy time, so it is never committed.

Idempotent: a token that still authenticates is kept, so a re-run does not
rotate the credential a running portal holds.

    uv run python scripts/provision_portal_account.py
    uv run python scripts/provision_portal_account.py --check   # report only
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from infrahub_sdk import Config, InfrahubClientSync

from solution_arista_avd import envfile

REPO = Path(__file__).resolve().parents[1]
# The MAIN checkout's `.env`, not one beside this file: from a git worktree that
# would be a file nothing reads. See `envfile.main_checkout`.
ENV_FILE = envfile.env_file(REPO)

ACCOUNT = "backstage-portal"
GROUP = "Portal Services"
ROLE = "Portal Access"
PASSWORD_VAR = "INFRAHUB_PORTAL_PASSWORD"  # noqa: S105 -- the variable's name, not a password
TOKEN_VAR = "INFRAHUB_PORTAL_TOKEN"  # noqa: S105 -- the variable's name, not a token

ALLOW_ALL, ALLOW_OTHER_BRANCHES = 6, 4

OBJECT_PERMISSIONS: list[dict[str, Any]] = [
    {"namespace": "*", "name": "*", "action": "view", "decision": ALLOW_ALL},
    {"namespace": "*", "name": "*", "action": "any", "decision": ALLOW_OTHER_BRANCHES},
    {"namespace": "Core", "name": "ProposedChange", "action": "create", "decision": ALLOW_ALL},
]
GLOBAL_PERMISSIONS: list[dict[str, Any]] = [
    {"action": "edit_default_branch", "decision": ALLOW_ALL},
    {"action": "override_context", "decision": ALLOW_ALL},
]

FORBIDDEN_GROUPS = ("Super Administrators",)


def read_env(name: str) -> str:
    return envfile.read_env(ENV_FILE, name)


def write_env(name: str, value: str, comment: str) -> None:
    envfile.upsert_env(ENV_FILE, name, value, comment)


def _address() -> str:
    return os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")


def admin_client() -> InfrahubClientSync:
    """The provisioning client, with ONE credential (see provision_mcp_agent.py)."""
    token = os.getenv("INFRAHUB_API_TOKEN")
    if token:
        return InfrahubClientSync(config=Config(address=_address(), api_token=token))
    return InfrahubClientSync(
        config=Config(
            address=_address(),
            username=os.getenv("INFRAHUB_USERNAME", "admin"),
            password=os.getenv("INFRAHUB_PASSWORD", "infrahub"),
        )
    )


def provision(client: InfrahubClientSync, password: str) -> None:
    permissions = []
    for data in OBJECT_PERMISSIONS:
        node = client.create("CoreObjectPermission", **data)
        node.save(allow_upsert=True)
        permissions.append(node)
    for data in GLOBAL_PERMISSIONS:
        node = client.create("CoreGlobalPermission", **data)
        node.save(allow_upsert=True)
        permissions.append(node)

    role = client.create("CoreAccountRole", name=ROLE, permissions=permissions)
    role.save(allow_upsert=True)

    account = client.create(
        "CoreAccount", name=ACCOUNT, label="Backstage portal", account_type="Script", password=password
    )
    account.save(allow_upsert=True)

    group = client.create("CoreAccountGroup", name=GROUP, roles=[role], members=[account])
    group.save(allow_upsert=True)


def token_works(token: str) -> bool:
    if not token:
        return False
    try:
        own = InfrahubClientSync(config=Config(address=_address(), api_token=token))
        result = own.execute_graphql("query { AccountProfile { name { value } } }")
    except Exception:  # noqa: BLE001 -- any failure means the portal could not authenticate either
        return False
    # A token that authenticates as someone ELSE -- an admin token pasted into
    # the variable by hand -- is the exact thing this script exists to remove.
    return bool(result.get("AccountProfile", {}).get("name", {}).get("value") == ACCOUNT)


def mint_token(password: str) -> str:
    """Sign in AS the account and mint a token for it -- the only way 1.10.6 allows."""
    own = InfrahubClientSync(config=Config(address=_address(), username=ACCOUNT, password=password))
    result = own.execute_graphql(
        'mutation { InfrahubAccountTokenCreate(data: {name: "backstage-portal"}) { ok object { token { value } } } }'
    )
    return str(result["InfrahubAccountTokenCreate"]["object"]["token"]["value"])


def check(client: InfrahubClientSync, token: str) -> list[str]:
    problems = []
    account = client.get("CoreAccount", name__value=ACCOUNT, raise_when_missing=False, include=["member_of_groups"])
    if account is None:
        return [f"{ACCOUNT} does not exist"]
    groups: Any = account.member_of_groups
    groups.fetch()
    names = sorted(group.display_label or "" for group in groups.peers)
    if GROUP not in names:
        problems.append(f"{ACCOUNT} is not in {GROUP!r} (groups: {names or 'none'})")
    problems += [f"{ACCOUNT} is in {g!r}, which defeats the point of it" for g in FORBIDDEN_GROUPS if g in names]
    if not token_works(token):
        problems.append(f"{TOKEN_VAR} in {ENV_FILE} does not authenticate as {ACCOUNT}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="report only; change nothing")
    args = parser.parse_args()

    client = admin_client()
    password = read_env(PASSWORD_VAR)
    token = read_env(TOKEN_VAR)

    if not args.check:
        if not password:
            password = secrets.token_urlsafe(24)
            write_env(PASSWORD_VAR, password, "The Backstage portal's account, written by provision_portal_account.py.")
            print(f"Generated {PASSWORD_VAR} in {ENV_FILE}")
        provision(client, password)
        print(f"{ACCOUNT} is in {GROUP!r} with role {ROLE!r}")
        if token_works(token):
            print(f"{TOKEN_VAR} still authenticates; kept")
        else:
            token = mint_token(password)
            write_env(TOKEN_VAR, token, "The portal's API token; deploy_tooling.sh renders it into backstage-secrets.")
            print(f"Minted {TOKEN_VAR} in {ENV_FILE}")

    problems = check(client, token)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(f"{ACCOUNT} authenticates with its own token and holds only the {ROLE!r} role.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
