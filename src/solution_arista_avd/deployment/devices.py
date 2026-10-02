"""Make a running ContainerLab device match the configuration Infrahub rendered.

Lifted verbatim from `scripts/provision_lab.py` in cycle 030 so that both the
manual command and the reconciler call the same code rather than two copies of
it. The CLI is still `scripts/provision_lab.py`; everything below it is here.

**Nothing in this module was rewritten during the lift.** Every comment is a
scar from something measured against the running lab, and the ones that look
like trivia are the expensive ones -- the trailing `end`, the per-run session
name, `scp -O`. Two paths were deliberately rewritten since: the WAN's SR Linux
push (below), and the firewall's, which was `load replace` on tagged hierarchies
and is now a full `load override`, because the artifact renders `system`.

Three device families, three delivery paths, because the lab gives them three
different front doors:

    DcimFabricSwitch  AVD EOS Configuration  eAPI over the management network
    DcimDevice        SR Linux Configuration docker exec + sr_cli candidate
    SecurityFirewall  Junos Configuration    docker exec + ssh to the vSRX VM

**The switches are addressed by IP, the others by name, and that is deliberate.**
Infrahub calls the switches `leaf-otternet-pod1-1-1`; ContainerLab calls the same
box `k8s-leaf1`. There is no renaming layer, so matching them by name is not
possible -- but every switch carries a `mgmt_ip` that equals its ContainerLab
management address, so eAPI reaches them without knowing the lab's name for
them. The SR Linux routers and the firewall are not reached by address -- the
address they carry is the telemetry collector's, which the push path never
reads -- and their Infrahub names *do* equal their ContainerLab node names, so they
are reached through the container instead. Each family uses the identifier it
actually has.

The SR Linux path replaced FRR's `frr-reload.py` in the WAN re-platform. It is
written rather than lifted, like the firewall's full replace, and every claim in its
comments was measured on a throwaway six-router prototype rather than on the
lab, which kept running FRR until the cutover.
"""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess  # noqa: S404 - every call is a fixed argv, never a shell string
import time
from dataclasses import dataclass
from typing import Any

import httpx

INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
INFRAHUB_API_TOKEN = os.getenv("INFRAHUB_API_TOKEN", "")

# The ContainerLab lab name, which prefixes every container: clab-<lab>-<node>.
LAB_NAME = os.getenv("OTTERNET_LAB", "otternet")

# eAPI credentials. The AVD artifact itself defines `username admin`, so these
# have to match what the rendered configuration sets, not what the device
# happens to have booted with.
EOS_USERNAME = os.getenv("OTTERNET_EOS_USERNAME", "admin")
EOS_PASSWORD = os.getenv("OTTERNET_EOS_PASSWORD", "admin")

# The vSRX's own credentials, matching `make fw-console` in the lab.
VSRX_USERNAME = os.getenv("OTTERNET_VSRX_USERNAME", "admin")
VSRX_PASSWORD = os.getenv("OTTERNET_VSRX_PASSWORD", "admin@123")

ARTIFACT_EOS = "AVD EOS Configuration"
ARTIFACT_SRL = "SR Linux Configuration"
ARTIFACT_JUNOS = "Junos Configuration"

# Which artifact each family is rendered into, and the short name --kind takes.
KINDS = {
    "eos": ARTIFACT_EOS,
    "srl": ARTIFACT_SRL,
    "junos": ARTIFACT_JUNOS,
}

# Every device carrying one of the three configuration artifacts, with whatever
# identifier that family can actually be reached by. `mgmt_ip` exists only on
# DcimFabricSwitch; asking the other two kinds for it is a GraphQL error, not an
# empty result, which is why the fragments differ.
DISCOVERY_QUERY = """
query ProvisionTargets($names: [String]) {
  CoreArtifact(name__values: $names) {
    edges {
      node {
        id
        name { value }
        status { value }
        checksum { value }
        object {
          node {
            __typename
            ... on DcimFabricSwitch { name { value } mgmt_ip { node { address { value } } } }
            ... on DcimDevice { name { value } }
            ... on SecurityFirewall { name { value } }
          }
        }
      }
    }
  }
}
"""


@dataclass(frozen=True)
class Target:
    """One device, its rendered artifact, and how to reach it."""

    device: str
    artifact_name: str
    artifact_id: str
    status: str
    mgmt_ip: str | None
    # The artifact's checksum. The discovery query has always selected it; cycle
    # 030 is the first caller to need it, to tell a change in *intent* (the
    # checksum moved) from drift in the *device* (it did not). It never decides
    # whether to push -- the device's own diff does that. This field is the one
    # deliberate addition to the otherwise verbatim lift.
    checksum: str = ""

    @property
    def container(self) -> str:
        """The ContainerLab container backing this device."""
        return f"clab-{LAB_NAME}-{self.device}"


class ProvisionError(RuntimeError):
    """A device could not be provisioned. Carries the device name for reporting."""


def _headers() -> dict[str, str]:
    return {"X-INFRAHUB-KEY": INFRAHUB_API_TOKEN}


def discover(branch: str = "") -> list[Target]:
    """Every device with a configuration artifact, as the given branch sees it."""
    url = f"{INFRAHUB_ADDRESS}/graphql/{branch}" if branch else f"{INFRAHUB_ADDRESS}/graphql"
    response = httpx.post(
        url,
        json={"query": DISCOVERY_QUERY, "variables": {"names": list(KINDS.values())}},
        headers=_headers(),
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    if "errors" in payload:
        raise ProvisionError(f"Infrahub rejected the discovery query: {payload['errors']}")

    targets: list[Target] = []
    for edge in payload["data"]["CoreArtifact"]["edges"]:
        node = edge["node"]
        obj = (node.get("object") or {}).get("node")
        if not obj:
            # An artifact whose target has been deleted. Nothing to push it to.
            continue
        targets.append(
            Target(
                device=obj["name"]["value"],
                artifact_name=node["name"]["value"],
                artifact_id=node["id"],
                status=node["status"]["value"],
                mgmt_ip=_bare_address(obj.get("mgmt_ip")),
                checksum=(node.get("checksum") or {}).get("value") or "",
            )
        )
    return sorted(targets, key=lambda t: (t.artifact_name, t.device))


def _bare_address(relationship: dict[str, Any] | None) -> str | None:
    """`172.20.41.11/24` -> `172.20.41.11`; None when the relationship is empty."""
    node = (relationship or {}).get("node") or {}
    value = (node.get("address") or {}).get("value")
    if not value:
        return None
    return str(ipaddress.ip_interface(value).ip)


def download(target: Target, branch: str = "") -> str:
    """The artifact's rendered content, as the device should end up matching."""
    response = httpx.get(
        f"{INFRAHUB_ADDRESS}/api/artifact/{target.artifact_id}",
        params={"branch": branch} if branch else None,
        headers=_headers(),
        timeout=120,
    )
    response.raise_for_status()
    content = response.text
    if not content.strip():
        raise ProvisionError(f"{target.device}: the {target.artifact_name} artifact is empty")
    return content


def _container_running(name: str) -> bool:
    result = subprocess.run(  # noqa: S603
        ["docker", "inspect", "-f", "{{.State.Running}}", name],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def push_eos(target: Target, config: str) -> str:
    """Replace a switch's running configuration over eAPI.

    A configuration *session* with `rollback clean-config` is what makes this a
    replace rather than a merge: without it, removing a VLAN from the model would
    leave the VLAN on the device forever. The session commits atomically, so a
    config that fails to parse leaves the running configuration untouched rather
    than half-applied.

    Replacing the whole configuration over the management network only works
    because the AVD artifact itself contains the lifeline -- `username admin`,
    `interface Management0`, the MGMT VRF, its default route, and
    `management api http-commands` in that VRF. Verified present in the rendered
    artifact; a future AVD change that dropped any of them would cut the session
    off mid-commit, which is why the check below is worth keeping.
    """
    if target.mgmt_ip is None:
        raise ProvisionError(f"{target.device}: no mgmt_ip modelled, cannot reach it over eAPI")

    _assert_eos_lifeline(target, config)

    lines = _eos_config_lines(config)
    # The session name is unique per run, and has to be. EOS keeps one *completed*
    # session per name, and entering a session whose name already has a committed
    # one fails with "could not run command" -- so a fixed name works exactly
    # once per device and every later run fails. Measured: the second
    # `invoke provision` against an already-provisioned switch. A fresh name each
    # time also lets EOS prune the previous one by itself.
    session = f"infrahub-{int(time.time())}"
    # `end` before the commit is load-bearing. The last rendered lines usually
    # leave the CLI inside a sub-mode -- an interface, a router instance -- and
    # `commit` is not a command there; eAPI rejects it as "invalid command" after
    # applying everything else, so the session is abandoned and the device keeps
    # its old configuration. `end` returns to enable mode, from which the session
    # is committed by name.
    commands = [
        "enable",
        f"configure session {session}",
        "rollback clean-config",
        *lines,
        "end",
        f"configure session {session} commit",
    ]

    response = httpx.post(
        f"https://{target.mgmt_ip}/command-api",
        json={
            "jsonrpc": "2.0",
            "method": "runCmds",
            "params": {"version": 1, "cmds": commands, "format": "json"},
            "id": "infrahub-provision",
        },
        auth=(EOS_USERNAME, EOS_PASSWORD),
        verify=False,  # noqa: S501 - lab devices carry self-signed certificates
        timeout=180,
    )
    response.raise_for_status()
    payload = response.json()
    if "error" in payload:
        # eAPI reports the offending command by index into `cmds`.
        error = payload["error"]
        detail = error.get("message", "unknown eAPI error")
        failed = error.get("data", [])
        offender = ""
        if isinstance(failed, list) and len(failed) <= len(commands):
            index = len(failed) - 1
            if 0 <= index < len(commands):
                offender = f" at {commands[index]!r}"
        raise ProvisionError(f"{target.device}: eAPI rejected the configuration{offender}: {detail}")

    return f"{len(lines)} lines replaced over eAPI at {target.mgmt_ip}"


def _eos_config_lines(config: str) -> list[str]:
    """The artifact as commands to feed a configuration session.

    Two things are removed. Blank lines, which eAPI rejects. And a trailing
    `end`, which PyAVD emits to close the file: left in place it returns the CLI
    to enable mode, and every command after it -- including the commit -- is then
    run in the wrong mode and rejected. Stripping it here and appending our own
    means the sequence is correct whether or not a future PyAVD keeps emitting
    it.

    `!` separator lines are kept: EOS accepts them as comments, and dropping them
    would make the commands harder to match against the artifact when debugging.
    """
    lines = [line for line in config.splitlines() if line.strip()]
    while lines and lines[-1].strip() == "end":
        lines.pop()
    return lines


# The configuration a replace must not drop, or the session commits and takes
# the management path down with it. Each entry is a substring match against the
# rendered artifact.
EOS_LIFELINE = (
    "interface Management0",
    "management api http-commands",
    "vrf MGMT",
)


def _assert_eos_lifeline(target: Target, config: str) -> None:
    missing = [needle for needle in EOS_LIFELINE if needle not in config]
    if missing:
        raise ProvisionError(
            f"{target.device}: refusing to replace the configuration -- the artifact is missing "
            f"{', '.join(repr(m) for m in missing)}, so the commit would drop management access"
        )


# The SR Linux equivalent, and a FULL replace like EOS's `rollback clean-config`.
#
# A push empties the candidate with `delete /` and rebuilds it from the artifact,
# so the artifact is the router's whole configuration and anything it omits is
# deleted -- /system included. An EMPTY artifact is therefore an instruction to
# delete everything, the management interface and the admin login with it.
# Artifact generation is asynchronous and an artifact that has not rendered yet
# exists, reports `Ready`, and is empty.
#
# So the lifeline names everything that keeps the router reachable and
# manageable after a replace: the management interface and the management
# network instance it sits in, the gNMI server in that instance (how it is
# watched, and the network path a human would use), SSH, and an admin password
# hash. Each is matched as a whole command, not a substring, so a comment that
# mentions mgmt0 does not satisfy it.
SRL_LIFELINE = (
    "set / interface mgmt0 admin-state enable",
    "set / interface mgmt0 subinterface 0 ipv4 dhcp-client",
    "set / network-instance mgmt type ip-vrf",
    "set / network-instance mgmt interface mgmt0.0",
    "set / system grpc-server mgmt admin-state enable",
    "set / system grpc-server mgmt network-instance mgmt",
    "set / system ssh-server mgmt admin-state enable",
    "set / system ssh-server mgmt network-instance mgmt",
    "set / system aaa authentication admin-user password $",
)

# How long a pushed configuration has to prove itself before SR Linux rolls it
# back on its own. Long enough for the management checks below, short enough
# that a reconciler that dies between commit and accept costs two minutes.
SRL_CONFIRM_TIMEOUT = 120

# What "still manageable" means after a commit, checked from inside the
# container -- the reconciler reaches the router with docker exec, never by
# address, so this is what it can see: an address on mgmt0.0, and the gNMI and
# SSH servers listening in the management namespace. Measured after a full
# replace on the prototype: all three present, and gNMI answering TLS with a
# certificate the router generated for itself.
SRL_MGMT_NAMESPACE = "srbase-mgmt"
SRL_MGMT_PORTS = (57400, 22)

SRL_CANDIDATE_PREFIX = "infrahub-"


def _assert_srl_lifeline(target: Target, config: str) -> None:
    commands = [line.strip() for line in config.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    missing = [needle for needle in SRL_LIFELINE if not any(line.startswith(needle) for line in commands)]
    if missing:
        raise ProvisionError(
            f"{target.device}: refusing to replace the configuration -- the artifact is missing "
            f"{', '.join(repr(m) for m in missing)}, so the commit would leave the router "
            "unreachable or unmanageable"
        )


def srl_candidate_script(name: str, config: str, *, commit: bool) -> str:
    """The sr_cli script that loads the artifact as a FULL replace, then diffs.

    One private, named candidate: `delete /` empties it, the artifact rebuilds
    it, and `diff flat` is the router's own comparison of the result against
    running. A push ends `commit confirmed`, so a commit that cut the router
    off rolls itself back; a comparison ends `discard now`.

    The commit applies only the NET difference, so a session the artifact did
    not change is not touched -- measured on the prototype: a full replace that
    changed one description left every BGP session's uptime running.
    """
    return "\n".join(
        [
            f"enter candidate private name {name}",
            "delete /",
            config.rstrip("\n"),
            "diff flat",
            f"commit confirmed timeout {SRL_CONFIRM_TIMEOUT}" if commit else "discard now",
            "",
        ]
    )


def srl_run(target: Target, script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, "sr_cli"],  # noqa: S607
        input=script,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _srl_tool(target: Target, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        ["docker", "exec", target.container, "sr_cli", "-d", command],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def srl_clear_candidate(target: Target, name: str) -> None:
    """Remove a named candidate a failed run left behind.

    sr_cli stops at the first error -- a parse error or a refused commit -- and
    exits non-zero WITHOUT leaving candidate mode, so the named candidate
    survives the session. SR Linux holds at most ten; a comparator that fails
    often enough would otherwise remove the ability to configure the router.
    """
    _srl_tool(target, f"tools system configuration candidate {name} clear")


def srl_candidate_name(purpose: str) -> str:
    return f"{SRL_CANDIDATE_PREFIX}{purpose}-{int(time.time() * 1000)}"


def srl_management_failures(target: Target) -> list[str]:
    """What is wrong with the router's management plane, or nothing."""
    failures: list[str] = []

    def netns(*argv: str) -> str:
        result = subprocess.run(  # noqa: S603
            ["docker", "exec", target.container, "ip", "netns", "exec", SRL_MGMT_NAMESPACE, *argv],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        return result.stdout or ""

    if "inet " not in netns("ip", "-4", "-o", "addr", "show", "dev", "mgmt0.0"):
        failures.append("mgmt0.0 has no IPv4 address")
    listening = netns("ss", "-ltnH")
    failures.extend(f"nothing listening on {port}" for port in SRL_MGMT_PORTS if f":{port} " not in listening)
    return failures


def push_srl(target: Target, config: str) -> str:
    """Replace an SR Linux router's ENTIRE configuration with the rendered one.

    **`docker exec sr_cli`, a private candidate, `delete /`, `commit confirmed`.**
    That is EOS's `rollback clean-config` with a safety net EOS's push lacks:
    SR Linux rolls an unconfirmed commit back by itself (measured: an unaccepted
    commit was gone at the timeout, its record marked `failed`). The reconciler
    confirms only after checking from inside the container that the management
    plane survived; if it did not, it rejects at once, and if the reconciler dies
    in between the router rolls back on its own.

    Why sr_cli rather than a gNMI Set Replace on `/`: both replace the whole
    tree atomically, but only sr_cli takes the artifact exactly as rendered --
    the same file ContainerLab boots from -- and it needs no credential and no
    address, which keeps `mgmt_ip` meaning eAPI and keeps the collector's
    address out of the reconciler. gNMI Set also has no confirm step.

    **sr_cli aborts at the first error and commits nothing.** A malformed line
    or a commit SR Linux refuses leaves running untouched and the process
    exiting 1 -- measured both ways. Both are failures, and the candidate the
    abort strands is cleared.

    The commit is not saved to startup, as FRR's was not: the durable copy is
    the artifact. A restarted container boots its ContainerLab startup file --
    the same artifact -- and was measured back in sync 16s after a `docker
    restart`. Its data-plane links were NOT back: a plain restart drops the
    container's veths and only `containerlab deploy` re-creates them, which is a
    property of ContainerLab rather than of this push.
    """
    _assert_srl_lifeline(target, config)

    if not _container_running(target.container):
        raise ProvisionError(f"{target.device}: container {target.container} is not running")

    name = srl_candidate_name("push")
    result = srl_run(target, srl_candidate_script(name, config, commit=True))
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0 or "Commit confirmed" not in output:
        srl_clear_candidate(target, name)
        detail = [line for line in output.strip().splitlines() if line.strip()]
        tail = " / ".join(detail[-3:]) if detail else "no output"
        raise ProvisionError(f"{target.device}: sr_cli refused the configuration: {tail}")

    failures = srl_management_failures(target)
    if failures:
        _srl_tool(target, "tools system configuration confirmed-reject")
        raise ProvisionError(
            f"{target.device}: the commit broke management ({'; '.join(failures)}) and was rolled back"
        )
    accepted = _srl_tool(target, "tools system configuration confirmed-accept")
    if accepted.returncode != 0:
        raise ProvisionError(
            f"{target.device}: could not confirm the commit; SR Linux rolls it back in "
            f"{SRL_CONFIRM_TIMEOUT}s: {(accepted.stderr or accepted.stdout).strip()[:200]}"
        )
    return f"committed and confirmed in {target.container}"


def push_junos(target: Target, config: str) -> str:
    """Replace the firewall's whole configuration with the rendered artifact.

    **`load override`, then `commit confirmed`, then a reachability check, and
    only then the confirming `commit`.** The Junos counterpart of EOS's
    `rollback clean-config`: the running configuration becomes the file, and
    anything the file omits is deleted -- a hand-added rule, a stray
    `applications` entry, vrnetlab's cleartext `plain-text-password-value`.

    That is only safe because the artifact is now COMPLETE. Until it rendered
    `system`, `override` would have committed a firewall with no logins and no
    `services { ssh; netconf; }` -- the management path this function arrives
    on -- which is why the push was `load replace` on tagged hierarchies, and
    why `load update` (measured deleting `system`) was rejected too. Two guards
    make the full replace survivable:

    - **`_assert_junos_lifeline`** refuses, before anything is staged, an
      artifact missing what management needs: an fxp0 address, `ssh` and
      `netconf` services, the login this module authenticates as, and root
      authentication. An empty artifact fails it, which matters more here
      than anywhere: an empty override is an instruction to erase the device.
    - **The confirmation is earned, not sent.** `commit confirmed` arms an
      automatic rollback; the confirming `commit` is issued only after a FRESH
      session has logged in over the same path -- container, vrnetlab's
      forward, fxp0 -- and NETCONF has answered a hello. If the new
      configuration broke management, that session never arrives, nothing
      confirms, and Junos restores the previous configuration by itself after
      `JUNOS_CONFIRM_MINUTES`.

    `## SECRET-DATA` values come back re-salted on every load -- measured on the
    prototype: the lab's `$6$otternetlab$...` hash is stored as `$6$<random>$...`
    of the same password. That is Junos, not a credential rewrite, and
    `normalise.junos_same_secret` is what keeps it from reading as drift.

    The route in is indirect: the vSRX is a VM inside the ContainerLab container,
    not the container itself. The container reaches it on 127.0.0.1 and carries
    `sshpass`, so the file is staged there and copied across. The host has no
    sshpass, which is why this does not run against the management address.
    """
    if not _container_running(target.container):
        raise ProvisionError(f"{target.device}: container {target.container} is not running")

    _assert_junos_lifeline(target, config)
    _wait_for_vsrx(target)
    payload = _junos_override_payload(config)
    remote_path = "/var/tmp/infrahub.conf"  # noqa: S108 - on the vSRX, the conventional load location
    staged_path = "/tmp/infrahub-fw.conf"  # noqa: S108 - inside the node's own container

    staged = subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, "sh", "-c", f"cat > {staged_path}"],  # noqa: S607
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    if staged.returncode != 0:
        raise ProvisionError(f"{target.device}: could not stage the configuration: {staged.stderr.strip()}")

    copy = _vsrx(target, ["scp", "-O", *_SSH_OPTS, staged_path, f"{VSRX_USERNAME}@127.0.0.1:{remote_path}"])
    if copy.returncode != 0:
        raise ProvisionError(
            f"{target.device}: could not copy the configuration to the vSRX: {copy.stderr.strip()[:200]}"
        )

    load = _vsrx_cli(
        target,
        f"configure exclusive\nload override {remote_path}\ncommit confirmed {JUNOS_CONFIRM_MINUTES}\nexit\nexit\n",
    )
    committed_at = time.monotonic()
    _assert_junos_ok(target, load, "load")
    if "commit complete" not in load.stdout:
        # The session may have died with the commit -- a configuration that
        # moves fxp0 takes this very connection with it. Whether or not it
        # committed, confirming now would be confirming blind.
        raise ProvisionError(
            f"{target.device}: the confirmed commit did not report completion; not confirming. "
            f"If it committed, Junos rolls it back within {JUNOS_CONFIRM_MINUTES} minute(s)."
        )

    _assert_vsrx_reachable(target)

    # A probe that only succeeds late may be succeeding BECAUSE the rollback
    # already ran -- and a confirming `commit` then commits nothing and still
    # prints "commit complete", reporting success for a push Junos undid.
    if time.monotonic() - committed_at > JUNOS_CONFIRM_MINUTES * 60 - _CONFIRM_MARGIN:
        raise ProvisionError(
            f"{target.device}: management answered too close to the {JUNOS_CONFIRM_MINUTES}-minute "
            "rollback to confirm safely; not confirming. Re-run once the device has settled."
        )

    confirm = _vsrx_cli(target, "configure exclusive\ncommit\nexit\nexit\n")
    _assert_junos_ok(target, confirm, "confirm")
    if "commit complete" not in confirm.stdout:
        raise ProvisionError(
            f"{target.device}: management came back but the confirming commit did not complete; "
            f"Junos rolls back within {JUNOS_CONFIRM_MINUTES} minute(s)."
        )

    return f"override committed and confirmed on {target.container} after a management check"


# Minutes Junos waits for the confirming commit before restoring the previous
# configuration. Long enough for `_assert_vsrx_reachable`'s retries -- three
# failing attempts measured 89s on the prototype, each waiting out ssh's
# connect and banner timeouts -- short enough that a push which broke
# management is undone before anyone has to reach for the console. Two minutes
# left 30s between the last probe and the rollback; three leaves a margin.
JUNOS_CONFIRM_MINUTES = 3

# Seconds before the rollback after which a confirmation is refused rather than
# raced -- see the check in `push_junos`.
_CONFIRM_MARGIN = 30

# Attempts and spacing for the post-commit management check. A false negative
# costs a rollback, never an outage, so this errs towards giving up.
_REACHABILITY_ATTEMPTS = 3
_REACHABILITY_INTERVAL = 10

# The smallest NETCONF exchange that proves the subsystem answers: the server's
# hello is printed before ours is read, and close-session ends it cleanly.
_NETCONF_PROBE = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<hello xmlns="urn:ietf:params:xml:ns:netconf:base:1.0">'
    "<capabilities><capability>urn:ietf:params:netconf:base:1.0</capability></capabilities>"
    "</hello>]]>]]>"
    '<rpc message-id="1" xmlns="urn:ietf:params:xml:ns:netconf:base:1.0"><close-session/></rpc>]]>]]>'
)


def _assert_vsrx_reachable(target: Target) -> None:
    """Log in again, over the path the reconciler uses, before confirming.

    A NEW session, deliberately: the one that committed was already
    authenticated, so it proves nothing about the configuration it installed.
    This one has to resolve through vrnetlab's forward to fxp0's address,
    authenticate as `VSRX_USERNAME` against the new `system login`, and reach
    the CLI -- and NETCONF on 830 has to answer, because vrnetlab forwards it
    and `services netconf` is in the lifeline.

    Raises:
        ProvisionError: when either probe fails every attempt. The commit is
            then left unconfirmed, and Junos rolls it back on its own.
    """
    failure = "no attempt made"
    for attempt in range(_REACHABILITY_ATTEMPTS):
        if attempt:
            time.sleep(_REACHABILITY_INTERVAL)
        try:
            cli = _vsrx_cli(target, "show version | match Hostname\nexit\n")
            if "Hostname:" not in cli.stdout:
                failure = f"CLI login failed: {(cli.stderr or cli.stdout).strip()[:160]}"
                continue
            netconf = _vsrx(
                target,
                ["ssh", "-T", *_SSH_OPTS, "-p", "830", "-s", f"{VSRX_USERNAME}@127.0.0.1", "netconf"],
                stdin=_NETCONF_PROBE,
            )
            if "<hello" not in netconf.stdout:
                failure = f"NETCONF did not answer: {(netconf.stderr or netconf.stdout).strip()[:160]}"
                continue
        except subprocess.TimeoutExpired:
            failure = "the probe timed out"
            continue
        return

    raise ProvisionError(
        f"{target.device}: management did not survive the new configuration ({failure}). "
        f"Not confirming; Junos rolls it back within {JUNOS_CONFIRM_MINUTES} minute(s)."
    )


def _wait_for_vsrx(target: Target, timeout: int = 600) -> None:
    """Block until the vSRX answers its CLI, or give up with a useful message.

    The container starts in seconds; the VM inside it takes minutes. Provisioning
    straight after `invoke lab` therefore hits a container that is running and a
    Junos that is not, and the failure reads "Connection timed out during banner
    exchange" -- which looks like a network or credential problem rather than a
    device that simply has not booted yet. Measured on a cold deploy: every other
    device was configured and committed before the vSRX would accept a session.

    Ten minutes because vrnetlab's vSRX boot is genuinely that slow on a busy
    host, and waiting costs nothing when the device is already up.
    """
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        probe = _vsrx_cli(target, "show version | match Hostname\nexit\n")
        if "Hostname:" in probe.stdout:
            if attempt > 1:
                print(f"        {target.device}: vSRX ready after {attempt} probe(s)")
            return
        time.sleep(15)

    raise ProvisionError(
        f"{target.device}: the vSRX did not answer its CLI within {timeout}s. "
        "The container is running but the VM inside it is still booting -- wait and re-run, "
        "or check `docker logs` for the node."
    )


# ServerAlive is for the push: a configuration that moves fxp0 takes the
# committing session with it, and without a keepalive ssh waits on that dead
# connection for longer than the confirmed commit's rollback window.
_SSH_OPTS = (
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "ConnectTimeout=20",
    "-o",
    "ServerAliveInterval=5",
    "-o",
    "ServerAliveCountMax=3",
)


def _vsrx(target: Target, argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command inside the node's container, authenticating to the vSRX."""
    return subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, "sshpass", "-p", VSRX_PASSWORD, *argv],  # noqa: S607
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _vsrx_cli(target: Target, script: str) -> subprocess.CompletedProcess[str]:
    """Feed a sequence of Junos CLI commands over stdin.

    Junos refuses `configure` as a non-interactive remote command -- "interactive
    commands not allowed" -- so the commands are written to the CLI's stdin
    instead, which it accepts. `-T` keeps ssh from asking for a tty it cannot get
    through `docker exec`.
    """
    return subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "exec",
            "-i",
            target.container,
            "sshpass",
            "-p",
            VSRX_PASSWORD,
            "ssh",
            "-T",
            *_SSH_OPTS,
            f"{VSRX_USERNAME}@127.0.0.1",
        ],
        input=script,
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
    )


def _assert_junos_ok(target: Target, result: subprocess.CompletedProcess[str], stage: str) -> None:
    """Junos reports failure in its output, not reliably in its exit status."""
    output = f"{result.stdout}\n{result.stderr}"
    for marker in ("commit failed", "syntax error", "error:", "unknown command"):
        if marker in output.lower():
            detail = [line.strip() for line in output.splitlines() if marker in line.lower()]
            raise ProvisionError(f"{target.device}: {stage} failed: {detail[0] if detail else marker}")
    if result.returncode != 0:
        raise ProvisionError(f"{target.device}: {stage} failed: {result.stderr.strip()[:200]}")


def _junos_override_payload(config: str) -> str:
    """The artifact, prepared for `load override`: the artifact itself.

    No `replace:` tags any more -- `override` replaces the whole configuration,
    so there is nothing to confine and nothing to tag. That also retires the
    empty-`applications` workaround, which existed because `load replace` left
    an omitted hierarchy alone: under `override` an omitted hierarchy is
    deleted, and so is `routing-options` when the model holds no route. The
    model is authoritative for every hierarchy now, not only the tagged ones.

    Lines beginning `!` are dropped as a **compatibility fallback, not the fix**.
    The renderer used to emit its provenance header as `! Rendered by
    Infrahub...`, which is EOS and FRR comment syntax and a syntax error in
    Junos: the load failed at line 1 and error recovery then skipped ahead, so
    the file loaded partially and still reported "load complete". Under
    `override` a partial load is a partial FIREWALL, so the filter matters more
    than it did. The template emits `#`, which Junos loads with no errors.
    """
    lines = [line for line in config.splitlines() if not line.startswith("!")]
    return "\n".join(lines) + "\n"


# What a full replace must never remove, as statement paths into the artifact.
# Each is something the reconciler's own route in depends on: vrnetlab forwards
# the container's 22 and 830 to fxp0's address, the reconciler authenticates as
# VSRX_USERNAME, and root authentication is what Junos refuses to commit
# without. A missing one is refused before anything reaches the device.
def _junos_lifeline() -> tuple[tuple[str, tuple[str, ...], str], ...]:
    """(description, path, required leaf prefix or "" for a block) per need."""
    return (
        ("an fxp0 IPv4 address", ("interfaces", "fxp0", "unit 0", "family inet"), "address "),
        ("system services ssh", ("system", "services", "ssh"), ""),
        ("system services netconf ssh", ("system", "services", "netconf", "ssh"), ""),
        (
            f"a login for {VSRX_USERNAME!r} with an encrypted password",
            ("system", "login", f"user {VSRX_USERNAME}", "authentication"),
            "encrypted-password ",
        ),
        (
            f"super-user class for {VSRX_USERNAME!r}",
            ("system", "login", f"user {VSRX_USERNAME}"),
            "class super-user",
        ),
        ("root-authentication", ("system", "root-authentication"), "encrypted-password "),
    )


def _junos_statements(config: str) -> set[tuple[str, ...]]:
    """Every statement in a braces-form Junos configuration, as a path.

    A block contributes its own path; a leaf contributes its path plus its
    text. Comments are skipped, `## SECRET-DATA` tails stripped, and anything
    under `inactive:` is left out -- an inactive fxp0 is no fxp0.

    Small on purpose: the lifeline asks "is this statement present?", and a
    textual substring match answered `ssh` for the `ssh-rsa` in a comment.
    """
    paths: set[tuple[str, ...]] = set()
    stack: list[str] = []
    inactive_depth: int | None = None
    in_comment = False
    for raw in config.splitlines():
        line = raw.strip()
        if in_comment:
            if "*/" in line:
                in_comment = False
            continue
        if line.startswith("/*"):
            in_comment = "*/" not in line
            continue
        if not line or line.startswith("#"):
            continue
        # Junos ignores runs of whitespace between words, and the artifact
        # pads its route lines into columns. Collapsing them is what makes a
        # statement from the artifact compare equal to the device's own.
        line = " ".join(re.sub(r"\s*(##.*|/\*.*\*/)$", "", line).split())
        inactive = line.startswith("inactive: ")
        line = line.removeprefix("inactive: ").removeprefix("replace: ")
        if line == "}":
            if stack:
                stack.pop()
            if inactive_depth is not None and len(stack) < inactive_depth:
                inactive_depth = None
            continue
        if line.endswith("{"):
            stack.append(line[:-1].strip())
            if inactive and inactive_depth is None:
                inactive_depth = len(stack)
            if inactive_depth is None:
                paths.add(tuple(stack))
            continue
        if line.endswith(";") and inactive_depth is None and not inactive:
            paths.add((*stack, line[:-1].strip()))
    return paths


def _assert_junos_lifeline(target: Target, config: str) -> None:
    """Refuse an artifact a full replace could not survive.

    Replaces `_assert_junos_scope`, which refused a `system` stanza because the
    push was then confined to the hierarchies the artifact named. Under
    `load override` the opposite holds: an artifact WITHOUT `system` is the
    dangerous one, because whatever it omits is deleted. Same role as
    `_assert_eos_lifeline`, which checks for `interface Management0`.

    Also refused: a `plain-text-password-value`, which Junos stores verbatim.
    vrnetlab's init.conf writes one, and a renderer that ever emitted one
    would be putting a cleartext credential into every stored artifact.
    """
    statements = _junos_statements(config)
    missing = []
    for description, path, leaf in _junos_lifeline():
        found = any(s[:-1] == path and s[-1].startswith(leaf) for s in statements) if leaf else path in statements
        if not found:
            missing.append(description)
    if missing:
        raise ProvisionError(
            f"{target.device}: refusing a full replace -- the artifact is missing {', '.join(missing)}, "
            "and `load override` deletes whatever the file omits, so the commit would cut the "
            "management path this push arrives on"
        )
    if any("plain-text-password-value" in s[-1] for s in statements):
        raise ProvisionError(
            f"{target.device}: refusing a Junos artifact carrying plain-text-password-value; "
            "Junos stores that verbatim, so the artifact would hold a cleartext credential"
        )


PUSHERS = {
    ARTIFACT_EOS: push_eos,
    ARTIFACT_SRL: push_srl,
    ARTIFACT_JUNOS: push_junos,
}


def provision(targets: list[Target], branch: str, dry_run: bool) -> int:
    """Push every target. Returns the number that failed."""
    failures = 0
    for target in targets:
        label = f"{target.device} ({target.artifact_name})"

        if target.status != "Ready":
            print(f"  skip  {label}: artifact status is {target.status}, not Ready")
            continue

        if dry_run:
            reach = target.mgmt_ip or target.container
            print(f"  would {label} -> {reach}")
            continue

        try:
            config = download(target, branch)
            detail = PUSHERS[target.artifact_name](target, config)
        except ProvisionError as error:
            print(f"  FAIL  {error}")
            failures += 1
        except (httpx.HTTPError, subprocess.SubprocessError, OSError) as error:
            print(f"  FAIL  {label}: {error}")
            failures += 1
        else:
            print(f"  ok    {label}: {detail}")

    return failures


# --------------------------------------------------------------------------
# Public surface for the rest of the package
# --------------------------------------------------------------------------
#
# These helpers were private while this file was a standalone script and nothing
# else could call them. The lift gave them a second consumer -- `compare`, which
# has to prepare exactly the same configuration and reach the devices by exactly
# the same route, or a comparison would be measuring something the push would
# not do. The private names are kept because the guard tests address them, and
# because renaming them would make the lift look like a rewrite in the diff.

eos_config_lines = _eos_config_lines
assert_eos_lifeline = _assert_eos_lifeline
assert_srl_lifeline = _assert_srl_lifeline
assert_junos_lifeline = _assert_junos_lifeline
junos_override_payload = _junos_override_payload
assert_vsrx_reachable = _assert_vsrx_reachable
container_running = _container_running
vsrx = _vsrx
vsrx_cli = _vsrx_cli
wait_for_vsrx = _wait_for_vsrx
SSH_OPTS = _SSH_OPTS
