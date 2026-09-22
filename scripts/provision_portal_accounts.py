#!/usr/bin/env python3
"""Give every Dex user an Infrahub account, by signing them in once.

WHY THIS EXISTS. The portal writes as the signed-in user, through the mutation's
`context: { account: { id } }`. Infrahub resolves that by name, and an SSO login
PROVISIONS the account -- so the account exists only after that person has signed
in to Infrahub at least once. Before that, their first request fails with

    Unable to set context for account that doesn't exist

and it fails at the create step, AFTER `BranchCreate` has already succeeded: a
red run in the portal, an orphan branch, and a message naming the account rather
than the thing to do about it.

Nothing in `invoke bootstrap` signed anybody in. The only thing that ever created
an account was `scripts/verify_bootstrap.sh`'s "alice signs in through Dex"
check -- which means the defect was invisible to the one script whose job is to
catch it, because that script's check is what created the account it then used.

This drives the same flow the browser drives, per user, and is idempotent: an
account that already exists is left alone.

    uv run python scripts/provision_portal_accounts.py
    uv run python scripts/provision_portal_accounts.py --check   # report only
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

REPO = Path(__file__).resolve().parents[1]
DEX_CONFIG = REPO / "tooling/10-dex.yaml"

INFRAHUB = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
TOKEN = os.getenv("INFRAHUB_API_TOKEN", "")
# The issuer every party is configured with. Infrahub redirects the browser here
# and Dex redirects it back, so both have to be reachable from wherever this runs.
DEX = os.getenv("OTTERNET_DEX_ADDRESS", "http://10.90.0.11:32556")
PROVIDER = os.getenv("OTTERNET_OIDC_PROVIDER", "provider1")
PASSWORD = os.getenv("OTTERNET_DEX_PASSWORD", "password")


def dex_users() -> list[str]:
    """The static users Dex is configured with, as e-mail addresses."""
    for document in yaml.safe_load_all(DEX_CONFIG.read_text(encoding="utf-8")):
        if not isinstance(document, dict):
            continue
        data = (document.get("data") or {}).get("config.yaml")
        if not data:
            continue
        config = yaml.safe_load(data)
        return [entry["email"] for entry in config.get("staticPasswords") or []]
    return []


def existing_accounts() -> set[str]:
    response = httpx.post(
        f"{INFRAHUB}/graphql",
        json={"query": "{CoreGenericAccount{edges{node{name{value}}}}}"},
        headers={"X-INFRAHUB-KEY": TOKEN},
        timeout=30,
    )
    response.raise_for_status()
    edges = response.json()["data"]["CoreGenericAccount"]["edges"]
    return {edge["node"]["name"]["value"] for edge in edges}


def sign_in(email: str) -> bool:
    """Drive authorize -> Dex login -> token, which provisions the account.

    Returns True when Infrahub minted its own token at the end, which is the
    only evidence that the whole round trip worked rather than merely answering.
    """
    with httpx.Client(follow_redirects=False, timeout=30) as client:
        start = client.get(f"{INFRAHUB}/api/oidc/{PROVIDER}/authorize")
        authorize = start.headers.get("location")
        if not authorize:
            print(f"   {email}: Infrahub did not redirect to the identity provider", file=sys.stderr)
            return False

        # Follow to Dex's login form, keeping its cookies.
        page = client.get(authorize, follow_redirects=True)
        match = re.search(r'action="([^"]*)"', page.text)
        if not match:
            print(f"   {email}: no login form at the identity provider", file=sys.stderr)
            return False
        action = match.group(1).replace("&amp;", "&")

        posted = client.post(
            f"{DEX}{action}",
            data={"login": email, "password": PASSWORD},
            follow_redirects=True,
        )
        # Dex ends on Infrahub's callback; the code is in the final URL.
        callback = str(posted.url)
        query = urlparse(callback).query
        if "code=" not in query:
            print(f"   {email}: the identity provider returned no authorization code", file=sys.stderr)
            return False

        token = client.get(f"{INFRAHUB}/api/oidc/{PROVIDER}/token?{query}", follow_redirects=True)
        return "access_token" in token.text


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report who is missing, change nothing")
    args = parser.parse_args()

    users = dex_users()
    if not users:
        print(f"No static users found in {DEX_CONFIG}", file=sys.stderr)
        return 1

    accounts = existing_accounts()
    # An SSO login provisions the account named for the identity's local part,
    # which is the same rule the Backstage sign-in resolver matches on.
    missing = [email for email in users if email.split("@", 1)[0] not in accounts]

    print(f"Dex users: {', '.join(users)}")
    print(f"Infrahub accounts: {', '.join(sorted(accounts))}")
    if not missing:
        print("Every portal user already has an account.")
        return 0

    print(f"Missing an account: {', '.join(missing)}")
    if args.check:
        return 1

    failed = []
    for email in missing:
        print(f" - signing in {email}")
        if not sign_in(email):
            failed.append(email)

    after = existing_accounts()
    still = [email for email in users if email.split("@", 1)[0] not in after]
    if still:
        print(f"Still missing after sign-in: {', '.join(still)}", file=sys.stderr)
        return 1
    if failed:
        print(f"Sign-in reported a problem for {', '.join(failed)}, but the accounts exist", file=sys.stderr)
    print(f"Provisioned: {', '.join(missing)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
