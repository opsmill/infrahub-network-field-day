"""Ask a device to compare itself against its rendered artifact.

Every family computes its own diff -- that is what makes this a reconciler
rather than a deployment trigger. Comparing an artifact checksum to a
last-applied checksum detects a change in *intent*; it cannot see that someone
edited a switch by hand, which is the case this exists for.

**The result of a comparison is `Comparison.differs`, and that is computed from
the normalised output, never the raw text.** Two of the three families report a
difference against an artifact the device already matches -- see `normalise`.

Each comparison leaves the device exactly as it found it: the EOS session is
aborted, the Junos candidate is rolled back, and the SR Linux candidate is
discarded. Nothing here commits.
"""

from __future__ import annotations

import subprocess  # noqa: S404 - every call is a fixed argv, never a shell string
import time
from dataclasses import dataclass
from typing import Any

import httpx

from solution_arista_avd.deployment import devices as dv
from solution_arista_avd.deployment.normalise import normalise

# Every configuration session and staging path this service creates carries this
# prefix, so the sweep can recognise its own leftovers and leave everything
# else alone.
SESSION_PREFIX = "infrahub-reconcile-"

JUNOS_STAGE = "/tmp/infrahub-reconcile.conf"  # noqa: S108 - inside the node's own container
JUNOS_REMOTE = "/var/tmp/infrahub-reconcile.conf"  # noqa: S108 - on the vSRX


@dataclass(frozen=True)
class Comparison:
    """What a device said about itself, and what that means."""

    target: dv.Target
    raw: str
    normalised: list[str]

    @property
    def differs(self) -> bool:
        return bool(self.normalised)


def read_intent(target: dv.Target, branch: str = "") -> str:
    """The rendered artifact, or a refusal.

    **`Ready` is not consulted**, deliberately. `provision_lab.py` used to skip
    anything whose status was not `Ready` and push anything that was; this
    repository documents twice that `Ready` is not evidence an artifact has
    content, and `scripts/verify_bootstrap.sh` exists because of it. For a
    human-triggered command the risk is a wasted run. For a loop that pushes
    replaces every ten minutes, an empty artifact treated as intent erases a
    device.
    """
    config = dv.download(target, branch)
    if not config.strip():
        raise dv.ProvisionError(
            f"{target.device}: the rendered artifact is empty (status {target.status!r}). "
            "Refusing to treat that as intent -- a replace would erase the device."
        )
    return config


def _eapi(target: dv.Target, cmds: list[str], fmt: str = "text") -> dict[str, Any]:
    response = httpx.post(
        f"https://{target.mgmt_ip}/command-api",
        json={
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {"version": 1, "cmds": cmds, "format": fmt},
            "id": "infrahub-reconcile",
        },
        auth=(dv.EOS_USERNAME, dv.EOS_PASSWORD),
        verify=False,  # noqa: S501 - lab devices carry self-signed certificates
        timeout=180,
    )
    response.raise_for_status()
    return response.json()


def compare_eos(target: dv.Target, config: str) -> str:
    """The switch's own diff between its running config and the artifact.

    A configuration session loaded with `rollback clean-config` is the artifact
    as a candidate; `show session-config named <s> diffs` is the device
    comparing the two. The session is always aborted -- this never commits.

    The session name is unique per comparison because EOS keeps one *completed*
    session per name and refuses to re-enter that name, so a fixed name works
    exactly once per device and fails forever after.
    """
    if target.mgmt_ip is None:
        raise dv.ProvisionError(f"{target.device}: no mgmt_ip modelled, cannot reach it over eAPI")

    session = f"{SESSION_PREFIX}{int(time.time() * 1000)}"
    try:
        payload = _eapi(
            target,
            [
                "enable",
                f"configure session {session}",
                "rollback clean-config",
                *dv.eos_config_lines(config),
                "end",
                f"show session-config named {session} diffs",
            ],
        )
        if "error" in payload:
            detail = payload["error"].get("message", "unknown eAPI error")
            raise dv.ProvisionError(f"{target.device}: eAPI rejected the comparison: {detail}")
        return str(payload["result"][-1].get("output", ""))
    finally:
        # try/finally covers an exception; it does not cover SIGKILL, which is
        # why the cycle also sweeps at start.
        _eapi(target, ["enable", f"configure session {session} abort"], "json")


def _dexec(target: dv.Target, argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, *argv],  # noqa: S607
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def compare_srl(target: dv.Target, config: str) -> str:
    """The router's own `diff flat` of the artifact, loaded as a replace, against running.

    The same candidate script the push runs, ending in `discard now` instead of
    `commit now`, so the comparison measures exactly what a push would do.

    **A non-zero exit is never "in sync".** sr_cli stops at the first error and
    prints nothing more -- no diff -- so an artifact SR Linux cannot parse
    would otherwise read as an empty difference. It raises instead, after
    clearing the candidate the abort leaves behind.
    """
    if not dv.container_running(target.container):
        raise dv.ProvisionError(f"{target.device}: container {target.container} is not running")
    dv.assert_srl_lifeline(target, config)
    dv.assert_srl_scope(target, config)

    name = dv.srl_candidate_name("reconcile")
    result = dv.srl_run(target, dv.srl_candidate_script(name, config, commit=False))
    out = result.stdout or ""
    if result.returncode != 0 or "All changes have been discarded" not in out:
        dv.srl_clear_candidate(target, name)
        detail = ((result.stderr or "") + out).strip().splitlines()
        raise dv.ProvisionError(
            f"{target.device}: the candidate never loaded, so the comparison is meaningless: "
            f"{' / '.join(detail[-3:]) if detail else 'no output'}"
        )
    return out


def compare_junos(target: dv.Target, config: str) -> str:
    """The firewall's own `show | compare` for the artifact as a candidate.

    `scp -O` is load-bearing. Without it the copy fails with "problem checking
    file: No such file or directory", `load replace` does nothing, and
    `show | compare` comes back empty -- which reads exactly like "in sync".

    The candidate is rolled back and the CLI exited, which releases the
    exclusive lock. Taking that lock is why the firewall is compared on one
    cycle in four rather than every cycle.
    """
    if not dv.container_running(target.container):
        raise dv.ProvisionError(f"{target.device}: container {target.container} is not running")

    # Wait for the CLI before comparing, not just before pushing. `push_junos`
    # has always waited; the comparison did not, because it was written against
    # a fabric that was already up. On a cold lab the vSRX takes minutes to boot,
    # so an unwaited comparison fails on fw1 and the device never gets as far as
    # the push that would have waited for it.
    dv.wait_for_vsrx(target)

    dv.assert_junos_scope(target, config)
    tagged = dv.junos_replace_tagged(config)

    staged = _dexec(target, ["sh", "-c", f"cat > {JUNOS_STAGE}"], stdin=tagged)
    if staged.returncode != 0:
        raise dv.ProvisionError(f"{target.device}: could not stage the configuration: {staged.stderr.strip()}")

    copy = dv.vsrx(target, ["scp", "-O", *dv.SSH_OPTS, JUNOS_STAGE, f"{dv.VSRX_USERNAME}@127.0.0.1:{JUNOS_REMOTE}"])
    if copy.returncode != 0:
        raise dv.ProvisionError(f"{target.device}: could not copy the configuration: {copy.stderr.strip()[:200]}")

    result = dv.vsrx_cli(
        target,
        f"configure exclusive\nload replace {JUNOS_REMOTE}\nshow | compare\nrollback 0\nexit\nexit\n",
    )
    out = result.stdout or ""
    if "No such file" in out:
        raise dv.ProvisionError(
            f"{target.device}: the candidate never loaded, so the comparison is meaningless. "
            "An empty `show | compare` here reads as 'in sync' and is not."
        )
    if "show | compare" not in out:
        raise dv.ProvisionError(f"{target.device}: unexpected CLI output from the comparison")
    return out.split("show | compare")[1].split("rollback 0")[0]


COMPARATORS = {
    dv.ARTIFACT_EOS: compare_eos,
    dv.ARTIFACT_SRL: compare_srl,
    dv.ARTIFACT_JUNOS: compare_junos,
}


def compare(target: dv.Target, config: str) -> Comparison:
    """Ask one device whether it matches, and say what that means."""
    raw = COMPARATORS[target.artifact_name](target, config)
    return Comparison(target=target, raw=raw, normalised=normalise(target.artifact_name, raw))


# --------------------------------------------------------------------------
# Sweeping this service's own leftovers
# --------------------------------------------------------------------------


def sweep_eos(target: dv.Target) -> list[str]:
    """Abort configuration sessions this service left behind.

    EOS holds a finite number of sessions, so a comparator that dies often
    enough removes the ability to deploy at all. `show configuration sessions`
    returns an object keyed by name, so matching the prefix is exact rather than
    textual -- and only this service's prefix is touched (FR-031).
    """
    if target.mgmt_ip is None:
        return []
    payload = _eapi(target, ["enable", "show configuration sessions"], "json")
    if "error" in payload:
        return []
    names = [name for name in payload["result"][-1].get("sessions", {}) if name.startswith(SESSION_PREFIX)]
    for name in names:
        _eapi(target, ["enable", f"configure session {name} abort"], "json")
    return names


def sweep_junos(target: dv.Target) -> bool:
    """Release an exclusive lock this service is still holding.

    Entering and leaving configuration mode is enough: if a previous cycle died
    holding the lock, its CLI session is gone and the lock with it; if one is
    genuinely held, this rolls the candidate back and exits cleanly.
    """
    if not dv.container_running(target.container):
        return False
    result = dv.vsrx_cli(target, "configure exclusive\nrollback 0\nexit\nexit\n")
    return "error" not in (result.stdout or "").lower()


def sweep_srl(target: dv.Target) -> list[str]:
    """Clear named candidates this service left behind.

    A run that sr_cli aborts -- a parse error, a refused commit -- exits without
    leaving candidate mode, and the named candidate outlives the session.
    SR Linux holds at most ten. Only this service's prefix is touched.
    """
    if not dv.container_running(target.container):
        return []
    listed = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "exec",
            target.container,
            "sr_cli",
            "-d",
            "info from state system configuration candidate *",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    names = [
        line.split()[1]
        for line in (listed.stdout or "").splitlines()
        if line.strip().startswith("candidate ") and line.split()[1].startswith(dv.SRL_CANDIDATE_PREFIX)
    ]
    for name in names:
        dv.srl_clear_candidate(target, name)
    return names
