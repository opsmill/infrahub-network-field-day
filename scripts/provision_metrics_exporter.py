#!/usr/bin/env python3
"""Give the Infrahub exporter its own read-only Infrahub account (cycle 034).

The exporter turns the graph into Prometheus metrics for Grafana's organisation
dashboards. It needs to READ, and nothing else, so it gets an account that can
do nothing else: `metrics-exporter`, in the `Metrics Readers` group, holding
one object permission -- `view` on everything.

WHY NOT `admin` OR `agent`. Both are Super Administrators. `agent` is what the
task workers run as, so it cannot be demoted, and a token for either sitting in
a long-running container's environment would be a write credential for the
whole graph held by a process that only ever reads.

WHY A TOKEN, NOT A PASSWORD. The exporter authenticates with an API token and
supports nothing else. Infrahub 1.10.6 mints a token only for the account that
asks (`InfrahubAccountTokenCreate` takes a name and an expiry, never an
account), so this signs in AS `metrics-exporter` to mint its own. The account's
password and the token both live in `.env` (gitignored); compose reads the token
from there.

Idempotent: an existing token that still authenticates is kept, so a rebuild
does not rotate a credential a running container holds.

    uv run python scripts/provision_metrics_exporter.py
    uv run python scripts/provision_metrics_exporter.py --check   # report only
"""

from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path
from typing import Any

from infrahub_sdk import Config, InfrahubClientSync

REPO = Path(__file__).resolve().parents[1]
ENV_FILE = REPO / ".env"

ACCOUNT = "metrics-exporter"
GROUP = "Metrics Readers"
ROLE = "Metrics Read Only"
PASSWORD_VAR = "INFRAHUB_EXPORTER_PASSWORD"  # noqa: S105 -- the variable's name, not a password
TOKEN_VAR = "INFRAHUB_EXPORTER_TOKEN"  # noqa: S105 -- the variable's name, not a token

# decision 6 = allow everywhere. View only: no `any`, no `create`, no global
# permission at all -- in particular not `edit_default_branch`.
OBJECT_PERMISSIONS: list[dict[str, Any]] = [
    {"namespace": "*", "name": "*", "action": "view", "decision": 6},
]

FORBIDDEN_GROUPS = ("Super Administrators",)


def read_env(name: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return ""


def write_env(name: str, value: str, comment: str) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    lines = [line for line in lines if not line.startswith(f"{name}=")]
    lines += ["", f"# {comment}", f"{name}={value}"]
    ENV_FILE.write_text("\n".join(lines).lstrip("\n") + "\n", encoding="utf-8")


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

    role = client.create("CoreAccountRole", name=ROLE, permissions=permissions)
    role.save(allow_upsert=True)

    account = client.create(
        "CoreAccount", name=ACCOUNT, label="Metrics exporter", account_type="Script", password=password
    )
    account.save(allow_upsert=True)

    group = client.create("CoreAccountGroup", name=GROUP, roles=[role], members=[account])
    group.save(allow_upsert=True)


def token_works(token: str) -> bool:
    if not token:
        return False
    try:
        own = InfrahubClientSync(config=Config(address=_address(), api_token=token))
        own.execute_graphql("query { AccountProfile { name { value } } }")
    except Exception:  # noqa: BLE001 -- any failure means the container could not read either
        return False
    return True


def mint_token(password: str) -> str:
    """Sign in AS the account and mint a token for it -- the only way 1.10.6 allows."""
    own = InfrahubClientSync(config=Config(address=_address(), username=ACCOUNT, password=password))
    result = own.execute_graphql(
        'mutation { InfrahubAccountTokenCreate(data: {name: "infrahub-exporter"}) { ok object { token { value } } } }'
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
        problems.append(f"{TOKEN_VAR} in {ENV_FILE} does not authenticate")
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
            write_env(
                PASSWORD_VAR, password, "The Infrahub exporter's account, written by provision_metrics_exporter.py."
            )
            print(f"Generated {PASSWORD_VAR} in {ENV_FILE}")
        provision(client, password)
        print(f"{ACCOUNT} is in {GROUP!r} with role {ROLE!r}")
        if token_works(token):
            print(f"{TOKEN_VAR} still authenticates; kept")
        else:
            token = mint_token(password)
            write_env(TOKEN_VAR, token, "The exporter's API token; compose passes it to infrahub-exporter.")
            print(f"Minted {TOKEN_VAR} in {ENV_FILE}")

    problems = check(client, token)
    for problem in problems:
        print(f"PROBLEM: {problem}")
    if not problems:
        print(f"{ACCOUNT} reads with its own token and holds only the {ROLE!r} role.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
