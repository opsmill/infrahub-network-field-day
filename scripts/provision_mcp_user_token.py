#!/usr/bin/env python3
"""Mint an Infrahub API token for a named user, so an MCP client can act as that user.

WHY. The MCP server runs in `token-passthrough` mode: each client sends its own
Infrahub API token as `Authorization: Bearer <token>`, and Infrahub attributes
every write to the account that owns the token. With the `mcp-agent` token the
requests are recorded as `mcp-agent`. With a token that belongs to `alice`, they
are recorded as `alice`.

HOW. A portal user such as `alice` has no password in Infrahub: the account exists
because she signed in through Dex (OIDC). This script drives the same sign-in as
`scripts/provision_portal_accounts.py`, then, with the Infrahub access token that
sign-in returns, calls `InfrahubAccountTokenCreate`. Infrahub 1.10.6 mints a token
only for the account that asks, so the operator token cannot do it for her.

The Infrahub access token from the sign-in is NOT sent to the MCP server. Measured:
the server answers `Invalid token` for it, and accepts only an API token.

The token goes into `.env` (gitignored, main checkout) as `INFRAHUB_MCP_TOKEN_<USER>`
(upper case, `-` becomes `_`). A token already in `.env` that still authenticates as
the user is kept. The script never prints the token unless `--show` is given.

    uv run python scripts/provision_mcp_user_token.py --user alice
    uv run python scripts/provision_mcp_user_token.py --user alice --check
    uv run python scripts/provision_mcp_user_token.py --user alice --show   # prints the token
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yaml
from infrahub_sdk import Config, InfrahubClientSync

from solution_arista_avd import envfile
from solution_arista_avd.envfile import read_env, upsert_env

REPO = Path(__file__).resolve().parents[1]
ENV_FILE = envfile.env_file(REPO)
DEX_CONFIG = REPO / "tooling/10-dex.yaml"

INFRAHUB = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
# The issuer Infrahub and the sign-in both use; see provision_portal_accounts.py.
DEX = os.getenv("OTTERNET_DEX_ADDRESS", "http://10.90.0.11:32556")
PROVIDER = os.getenv("OTTERNET_OIDC_PROVIDER", "provider1")
DEX_PASSWORD = os.getenv("OTTERNET_DEX_PASSWORD", "password")
TOKEN_NAME_PREFIX = "mcp-client-"  # noqa: S105 -- the token's label in Infrahub, not a token
USER_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


def token_var(user: str) -> str:
    """The `.env` variable that holds the user's token, for example INFRAHUB_MCP_TOKEN_ALICE."""
    return "INFRAHUB_MCP_TOKEN_" + user.upper().replace("-", "_")


def dex_email(user: str) -> str:
    """The Dex identity whose local part is `user`, from the Dex configuration."""
    for document in yaml.safe_load_all(DEX_CONFIG.read_text(encoding="utf-8")):
        if not isinstance(document, dict):
            continue
        data = (document.get("data") or {}).get("config.yaml")
        if not data:
            continue
        for entry in yaml.safe_load(data).get("staticPasswords") or []:
            if entry["email"].split("@", 1)[0] == user:
                return str(entry["email"])
    return ""


def token_account(token: str) -> str:
    """The account name the API token authenticates as, or the empty string."""
    if not token:
        return ""
    try:
        own = InfrahubClientSync(config=Config(address=INFRAHUB, api_token=token))
        result = own.execute_graphql("query { AccountProfile { name { value } } }")
    except Exception:  # noqa: BLE001 -- any failure means the token does not authenticate
        return ""
    return str(result["AccountProfile"]["name"]["value"])


def oidc_access_token(email: str) -> str:
    """Sign in through Dex and return Infrahub's access token (a JWT), or the empty string."""
    with httpx.Client(follow_redirects=False, timeout=30) as client:
        authorize = client.get(f"{INFRAHUB}/api/oidc/{PROVIDER}/authorize").headers.get("location")
        if not authorize:
            return ""
        page = client.get(authorize, follow_redirects=True)
        match = re.search(r'action="([^"]*)"', page.text)
        if not match:
            return ""
        action = match.group(1).replace("&amp;", "&")
        posted = client.post(
            f"{DEX}{action}",
            data={"login": email, "password": DEX_PASSWORD},
            follow_redirects=True,
        )
        query = urlparse(str(posted.url)).query
        if "code=" not in query:
            return ""
        token = client.get(f"{INFRAHUB}/api/oidc/{PROVIDER}/token?{query}", follow_redirects=True)
        return str(token.json().get("access_token", "")) if token.status_code == 200 else ""


def mint_api_token(user: str, access_token: str) -> str:
    """Create an API token for the account that owns `access_token`."""
    mutation = (
        f'mutation {{ InfrahubAccountTokenCreate(data: {{name: "{TOKEN_NAME_PREFIX}{user}"}}) '
        "{ ok object { token { value } } } }"
    )
    response = httpx.post(
        f"{INFRAHUB}/graphql",
        json={"query": mutation},
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    payload = response.json()
    if payload.get("errors"):
        message = payload["errors"][0].get("message", "")
        raise RuntimeError(f"InfrahubAccountTokenCreate was refused: {message}")
    return str(payload["data"]["InfrahubAccountTokenCreate"]["object"]["token"]["value"])


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--user", required=True, help="Infrahub account name, for example alice")
    parser.add_argument("--check", action="store_true", help="report only; mint nothing")
    parser.add_argument("--show", action="store_true", help="print the token to stdout (otherwise it is never printed)")
    args = parser.parse_args()

    user = args.user
    if not USER_PATTERN.match(user):
        print(f"PROBLEM: {user!r} is not a valid account name", file=sys.stderr)
        return 1
    variable = token_var(user)
    token = read_env(ENV_FILE, variable)

    if token_account(token) == user:
        print(f"{variable} in {ENV_FILE} authenticates as {user}; kept.", file=sys.stderr)
    elif args.check:
        print(f"PROBLEM: {variable} is missing or does not authenticate as {user}", file=sys.stderr)
        return 1
    else:
        email = dex_email(user)
        if not email:
            print(f"PROBLEM: no Dex user named {user} in {DEX_CONFIG}", file=sys.stderr)
            return 1
        access_token = oidc_access_token(email)
        if not access_token:
            print(f"PROBLEM: the Dex sign-in for {email} returned no access token", file=sys.stderr)
            return 1
        token = mint_api_token(user, access_token)
        if token_account(token) != user:
            print(f"PROBLEM: the minted token does not authenticate as {user}", file=sys.stderr)
            return 1
        upsert_env(
            ENV_FILE,
            variable,
            token,
            f"The {user} API token an MCP client sends as a Bearer header; written by scripts/provision_mcp_user_token.py.",
        )
        print(f"Minted {variable} for {user} in {ENV_FILE}", file=sys.stderr)

    if args.show:
        print(token)
    return 0


if __name__ == "__main__":
    sys.exit(main())
