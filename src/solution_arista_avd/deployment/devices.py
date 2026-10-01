"""Make a running ContainerLab device match the configuration Infrahub rendered.

Lifted verbatim from `scripts/provision_lab.py` in cycle 030 so that both the
manual command and the reconciler call the same code rather than two copies of
it. The CLI is still `scripts/provision_lab.py`; everything below it is here.

**Nothing in this module was rewritten during the lift.** Every comment is a
scar from something measured against the running lab, and the ones that look
like trivia are the expensive ones -- the trailing `end`, the per-run session
name, `load replace` rather than `override` or `update`, `scp -O`.

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
the one part of this module written rather than lifted, and every claim in its
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
    """Load and commit the firewall's configuration on the vSRX.

    **`load replace` with explicit `replace:` tags. The alternatives were tried
    against the running firewall and both are destructive.**

    The artifact holds only `interfaces`, `routing-options` and `security`. It
    has no `system` stanza, deliberately: that stanza carries two credential
    hashes which are never modelled, so the renderer cannot emit them and the
    query must never ask.

    - `load override` replaces the whole configuration, so it would commit a
      firewall with no `system` at all -- no root authentication, no admin user.
    - `load update` compares the *complete* file against the running
      configuration and deletes whatever the file omits. Measured on this device,
      it removed `system` including `services { ssh; netconf; }`, which is the
      management path this script arrives on. It looks like a partial-update verb
      and is not one.
    - `load merge` fails the other way: a security policy deleted from the model
      would stay on the firewall, still permitting traffic the model says is
      denied.

    `load replace` acts only on hierarchies carrying a `replace:` tag, which
    `_junos_replace_tagged` inserts before each top-level stanza. Each modelled
    hierarchy is replaced outright, so deletions propagate, and everything else
    -- `system` above all -- is untouched.

    One diff is expected and is not this script's doing: Junos re-serialises
    every `## SECRET-DATA` value with a fresh salt on any load. Re-loading the
    device's own unmodified configuration produces the identical diff, so the
    password hashes appearing to change is Junos, not a credential rewrite.

    The commit is `commit confirmed`, because a firewall is exactly the device
    where a mistaken policy can remove the path you would fix it over. If the
    confirmation below does not arrive, Junos rolls the change back by itself.

    The route in is indirect: the vSRX is a VM inside the ContainerLab container,
    not the container itself. The container reaches it on 127.0.0.1 and carries
    `sshpass`, so the file is staged there and copied across. The host has no
    sshpass, which is why this does not run against the management address.
    """
    if not _container_running(target.container):
        raise ProvisionError(f"{target.device}: container {target.container} is not running")

    _assert_junos_scope(target, config)
    _wait_for_vsrx(target)
    tagged = _junos_replace_tagged(config)
    remote_path = "/var/tmp/infrahub.conf"  # noqa: S108 - on the vSRX, the conventional load location
    staged_path = "/tmp/infrahub-fw.conf"  # noqa: S108 - inside the node's own container

    staged = subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, "sh", "-c", f"cat > {staged_path}"],  # noqa: S607
        input=tagged,
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

    # `commit confirmed 2` arms a two-minute automatic rollback; the second
    # commit below confirms it. Losing management access between the two leaves
    # the firewall on its previous configuration rather than unreachable.
    load = _vsrx_cli(
        target,
        f"configure exclusive\nload replace {remote_path}\ncommit confirmed 2\nexit\nexit\n",
    )
    _assert_junos_ok(target, load, "load")

    confirm = _vsrx_cli(target, "configure exclusive\ncommit\nexit\nexit\n")
    _assert_junos_ok(target, confirm, "confirm")

    return f"loaded and committed on {target.container} (replace: interfaces, routing-options, security)"


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


_SSH_OPTS = (
    "-o",
    "StrictHostKeyChecking=no",
    "-o",
    "UserKnownHostsFile=/dev/null",
    "-o",
    "ConnectTimeout=20",
)


def _vsrx(target: Target, argv: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command inside the node's container, authenticating to the vSRX."""
    return subprocess.run(  # noqa: S603
        ["docker", "exec", "-i", target.container, "sshpass", "-p", VSRX_PASSWORD, *argv],  # noqa: S607
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


def _junos_replace_tagged(config: str) -> str:
    """The artifact, prepared for `load replace`.

    A `replace:` tag is inserted before each top-level stanza. That is what
    confines the load to the modelled hierarchies and leaves `system` alone --
    see `push_junos` for why that matters.

    **`interfaces` is replaced wholesale, and the model carries `fxp0` so that is
    safe.** It was not always: the model owned only the data interfaces, so
    replacing the hierarchy deleted the firewall's management interface on every
    push. It survived because vrnetlab, running as root inside the container,
    restored it before the `commit confirmed` had to be confirmed -- the
    device's commit log showed the pair every time:

        16:49:01 admin via cli commit confirmed   <- fxp0 deleted here
        16:51:03 root via other                   <- vrnetlab puts it back
        16:51:10 admin via cli                    <- the confirm

    Modelling fxp0 closes that and keeps full deletion semantics: removing an
    interface from the model removes it from the device.

    **The cost, stated plainly.** The model is now AUTHORITATIVE for the
    firewall's management address, and its values came from an `init.conf` that
    vrnetlab generates inside the container and that no repository holds. If
    they ever drift from what vrnetlab assigns, this push sets the wrong
    management address and nothing restores it -- recovery is the container
    console. `tests/unit/test_junos_config.py::FXP0_FROM_INIT_CONF` is the only
    thing asserting they still agree.

    Lines beginning `!` are dropped as a **compatibility fallback, not the fix**.
    The renderer used to emit its provenance header as `! Rendered by
    Infrahub...`, which is EOS and FRR comment syntax and a syntax error in
    Junos: the load failed at line 1 and error recovery then skipped ahead, so
    the file loaded partially and still reported "load complete". The template
    now emits `#`, Junos's own comment character, which loads with no errors and
    is not stored in the configuration. This filter stays so that an instance
    whose stored artifact predates that fix still provisions instead of half
    loading; it is a no-op against a current artifact.
    """
    lines = [line for line in config.splitlines() if not line.startswith("!")]
    out: list[str] = []
    present: set[str] = set()
    for line in lines:
        match = _TOP_LEVEL_STANZA.match(line)
        if match:
            present.add(match.group(1))
            out.append("replace:")
        out.append(line)

    # A stanza the artifact OMITS is not replaced, because there is nothing to
    # tag -- so the device keeps whatever it had. That is invisible until a
    # stanza stops being rendered: revoking an access grant removed its policy
    # and left its `applications` declaration behind, and the next grant added
    # another. Emitting an empty replaced stanza deletes the hierarchy instead.
    for stanza in sorted(_OPTIONAL_MODEL_OWNED_STANZAS - present):
        out.extend(["replace:", f"{stanza} {{", "}"])

    return "\n".join(out) + "\n"


# A top-level Junos stanza opener: unindented, lowercase, ending in ` {`.
_TOP_LEVEL_STANZA = re.compile(r"^([a-z][a-z0-9-]*) \{$")

# Stanzas the model owns but renders only when it has content. Each is emitted
# empty-and-replaced when the artifact omits it, so removing the last object in
# a hierarchy removes the hierarchy from the device.
#
# `routing-options` is deliberately NOT here. Its absence today means "this
# firewall has no static routes in the model", and the device keeps the routes
# it has; making the model authoritative for that is a defensible change and a
# different one from this fix, which is about generated objects accumulating.
_OPTIONAL_MODEL_OWNED_STANZAS = frozenset({"applications"})


def _assert_junos_scope(target: Target, config: str) -> None:
    """Refuse a Junos artifact that has grown a `system` stanza.

    `load update` leaves `system` alone only because the artifact does not
    contain it. If a future schema change ever renders one, this push would start
    replacing the firewall's credentials with whatever the model holds -- which
    is the situation the model exists to avoid. Fail loudly instead, so the
    delivery path is reconsidered rather than silently changing meaning.
    """
    if any(line.startswith(("system {", "system ")) for line in config.splitlines()):
        raise ProvisionError(
            f"{target.device}: the Junos artifact now contains a 'system' stanza. "
            "This push replaces every hierarchy the artifact names, so it would overwrite the "
            "device's credentials. Review the renderer before provisioning the firewall again."
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
assert_junos_scope = _assert_junos_scope
junos_replace_tagged = _junos_replace_tagged
container_running = _container_running
vsrx = _vsrx
vsrx_cli = _vsrx_cli
wait_for_vsrx = _wait_for_vsrx
SSH_OPTS = _SSH_OPTS
