"""Submit a request the way the portal would, on a throwaway branch.

WHY THIS EXISTS. The catalogue check proves a template was ingested; it says
nothing about whether the mutation inside it is one Infrahub will accept. Every
defect found in this path was of exactly that shape, and all four were invisible
from the portal itself -- the catalogue looked healthy and the scaffolder step
failed:

  * `status: { value: "draft" }`, a value this schema does not have
  * `ports` dropped as untypeable, so a grant opened nothing
  * `hfid: [$vip]` against a peer whose hfid has two elements
  * the kind missing entirely, because json_schema 500s on a List attribute

So this takes the create mutation OUT OF THE RENDERED TEMPLATE and runs it. A
literal copy of the mutation here would pass while the portal shipped something
else, which is the whole failure mode being guarded against.

Everything happens on a branch that is deleted afterwards, so a verification run
leaves no grant behind and never reaches a device.
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid

import httpx

ADDRESS = os.environ.get("INFRAHUB_ADDRESS", "http://localhost:8000")
HEADERS = {"X-INFRAHUB-KEY": os.environ.get("INFRAHUB_API_TOKEN", "")}
BRANCH = f"verify-portal-request-{uuid.uuid4().hex[:8]}"
# An account that exists, because the mutation context is resolved by name.
ACCOUNT = os.environ.get("INFRAHUB_VERIFY_ACCOUNT", "alice")


def gql(
    query: str,
    variables: dict | None = None,
    branch: str = "main",
    phase: str = "request",
) -> dict:
    response = httpx.post(
        f"{ADDRESS}/graphql/{branch}",
        json={"query": query, "variables": variables or {}},
        headers=HEADERS,
        timeout=60,
    )
    try:
        payload = response.json()
    except ValueError:
        # A refused mutation does not always come back as a GraphQL `errors`
        # array -- an HFID of the wrong length is an HTTP error with a body that
        # is not JSON at all. Reporting "Expecting value: line 1 column 1" for
        # that is useless; the status and the body are what name the cause.
        msg = f"{phase}: HTTP {response.status_code}, body {response.text[:200]!r}"
        raise RuntimeError(msg) from None
    if payload.get("errors"):
        raise RuntimeError(f"{phase}: {json.dumps(payload['errors'])[:350]}")
    return payload["data"]


def main() -> int:
    template = json.load(sys.stdin)
    step = next(s for s in template["spec"]["steps"] if s.get("id") == "create")
    mutation = step["input"]["query"]

    # The values a requester would supply. `destination_vip` is two elements
    # because IpamIPAddress is keyed that way -- if the template stops asking for
    # both, this call fails, which is the point.
    variables = {
        "requester": "verify@nfd41.lab",
        "name": f"verify-{uuid.uuid4().hex[:8]}",
        "application": "nfd41-demo",
        "destination_vip": ["10.112.240.10/32", "default"],
        "source_zone": "branch",
        "source_address": "branch-users",
        "owner": "branch",
    }
    missing = [name for name in variables if f"${name}" not in mutation]
    if missing:
        print(f"the template no longer asks for {missing}; update this check")
        return 1

    gql(
        "mutation ($name: String!) { BranchCreate(data: { name: $name, sync_with_git: false }) { ok } }",
        {"name": BRANCH},
        phase="creating the throwaway branch",
    )
    proposed_change = None
    try:
        # EVERY unguarded GraphQL step, not only the create. `proposed_change` is
        # the LAST one, and it named a `tags` field `CoreProposedChange` does not
        # have -- so the object, the branch and the generators all succeeded and
        # no proposed change opened. A request that reaches nobody looks, from
        # the catalogue, exactly like one waiting for review.
        #
        # The per-field steps in between are skipped: each is guarded on the
        # requester having filled that field in, and supplying all of them would
        # be testing the scaffolder rather than the mutations.
        for step in template["spec"]["steps"]:
            if step.get("action") != "infrahub:graphql:execute":
                continue
            if step["id"] == "create":
                values = dict(variables)
            elif step["id"] == "proposed_change":
                values = {"source_branch": BRANCH, "name": f"verify {BRANCH}"}
            else:
                continue

            # EVERY DECLARED VARIABLE, filled from what we know and defaulted
            # otherwise. Hardcoding the list broke this check twice against a
            # portal that was correct: once when `proposed_change` gained a
            # `description`, and again when every mutation gained the account
            # context. A checker that fails whenever the thing it checks
            # improves costs more than it catches.
            for name in re.findall(r"\$(\w+):", step["input"]["query"]):
                if name in values:
                    continue
                # The account context has to name an account that exists --
                # Infrahub refuses an unknown one, which is itself worth
                # exercising rather than stubbing.
                values[name] = ACCOUNT if name.endswith("_account") else f"verify {BRANCH}"
            data = gql(
                step["input"]["query"],
                values,
                branch=BRANCH,
                phase=f"the portal's {step['id']} step",
            )
            result = next(iter(data.values()))
            if not result.get("ok"):
                print(f"the portal's {step['id']} step was refused")
                return 1
            if step["id"] == "proposed_change":
                proposed_change = (result.get("object") or {}).get("id")
    finally:
        if proposed_change:
            gql(
                "mutation ($id: String!) { CoreProposedChangeDelete(data: { id: $id }) { ok } }",
                {"id": proposed_change},
                phase="deleting the throwaway proposed change",
            )
        gql(
            "mutation ($name: String!) { BranchDelete(data: { name: $name }) { ok } }",
            {"name": BRANCH},
            phase="deleting the throwaway branch",
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - the message is the whole output
        print(str(exc)[:300])
        sys.exit(1)
