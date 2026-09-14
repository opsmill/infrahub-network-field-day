"""Push Infrahub-rendered configuration onto the running ContainerLab devices.

The lab comes up with management connectivity and nothing else -- the cEOS nodes
in `../lab/nfd41.clab.yml` are given no `startup-config`, only `CLAB_MGMT_VRF`
and a management address. This script is the second half: it fetches each
device's rendered artifact from Infrahub and makes the device match it, so the
running lab's configuration comes from the model rather than from a file
somebody edited.

Three device families, three delivery paths, because the lab gives them three
different front doors:

    DcimFabricSwitch  AVD EOS Configuration  eAPI over the management network
    DcimDevice        FRR Configuration      docker exec + frr-reload.py
    SecurityFirewall  Junos Configuration    docker exec + ssh to the vSRX VM

**The switches are addressed by IP, the others by name, and that is deliberate.**
Infrahub calls the switches `leaf-nfd41-pod1-1-1`; ContainerLab calls the same
box `k8s-leaf1`. There is no renaming layer, so matching them by name is not
possible -- but every switch carries a `mgmt_ip` that equals its ContainerLab
management address, so eAPI reaches them without knowing the lab's name for
them. The FRR routers and the firewall have no address modelled at all, and
their Infrahub names *do* equal their ContainerLab node names, so they are
reached through the container instead. Each family uses the identifier it
actually has.

Usage:

    uv run python scripts/provision_lab.py                    # push everything
    uv run python scripts/provision_lab.py --dry-run          # show, change nothing
    uv run python scripts/provision_lab.py --only spine1      # one device
    uv run python scripts/provision_lab.py --kind eos         # one family
    uv run python scripts/provision_lab.py --branch my-change # from a branch

Normally invoked as `uv run invoke provision`.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import re
import subprocess  # noqa: S404 - every call is a fixed argv, never a shell string
import sys
import time
from dataclasses import dataclass
from typing import Any

import httpx

INFRAHUB_ADDRESS = os.getenv("INFRAHUB_ADDRESS", "http://localhost:8000")
INFRAHUB_API_TOKEN = os.getenv("INFRAHUB_API_TOKEN", "")

# The ContainerLab lab name, which prefixes every container: clab-<lab>-<node>.
LAB_NAME = os.getenv("NFD41_LAB", "nfd41")

# eAPI credentials. The AVD artifact itself defines `username admin`, so these
# have to match what the rendered configuration sets, not what the device
# happens to have booted with.
EOS_USERNAME = os.getenv("NFD41_EOS_USERNAME", "admin")
EOS_PASSWORD = os.getenv("NFD41_EOS_PASSWORD", "admin")

# The vSRX's own credentials, matching `make fw-console` in the lab repository.
VSRX_USERNAME = os.getenv("NFD41_VSRX_USERNAME", "admin")
VSRX_PASSWORD = os.getenv("NFD41_VSRX_PASSWORD", "admin@123")

ARTIFACT_EOS = "AVD EOS Configuration"
ARTIFACT_FRR = "FRR Configuration"
ARTIFACT_JUNOS = "Junos Configuration"

# Which artifact each family is rendered into, and the short name --kind takes.
KINDS = {
    "eos": ARTIFACT_EOS,
    "frr": ARTIFACT_FRR,
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


def push_frr(target: Target, config: str) -> str:
    """Reload an FRR router onto the rendered configuration.

    `frr-reload.py` computes the difference between the running configuration and
    the file and applies only that, which is what makes this safe to re-run while
    the lab carries traffic: adding a tenant does not bounce the BGP sessions of
    the tenants already there. `vtysh -f` would MERGE instead, quietly leaving a
    removed tenant's VRF and session in place.

    The configuration is staged in a directory of our own rather than written
    over /etc/frr/frr.conf, because the lab repository bind-mounts that file
    read-only -- writing to it fails with "device or resource busy", and
    succeeding would mean this repository silently editing a sibling
    repository's working tree.

    `--confdir` points at that staging directory for a specific reason. At the
    end of a reload frr-reload.py runs `vtysh write` unless the file it was given
    *is* `<confdir>/frr.conf`, and that write fails on the read-only mount -- the
    reload having already succeeded, so the device is correct and the run reports
    failure. Naming the staging directory as the confdir makes the two paths
    equal, so the persistence step is skipped deliberately rather than attempted
    and failed. Skipping it is right: /etc/frr belongs to the lab repository, and
    the durable copy of this configuration is the artifact in Infrahub.
    """
    if not _container_running(target.container):
        raise ProvisionError(f"{target.device}: container {target.container} is not running")

    staged_dir = "/tmp/infrahub-frr"  # noqa: S108 - inside the node's own container
    staged = f"{staged_dir}/frr.conf"
    write = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "exec",
            "-i",
            target.container,
            "sh",
            "-c",
            f"mkdir -p {staged_dir} && cat > {staged}",
        ],
        input=config,
        capture_output=True,
        text=True,
        check=False,
    )
    if write.returncode != 0:
        raise ProvisionError(f"{target.device}: could not stage the configuration: {write.stderr.strip()}")

    reload_result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "docker",
            "exec",
            target.container,
            "/usr/lib/frr/frr-reload.py",
            "--reload",
            "--stdout",
            "--confdir",
            staged_dir,
            staged,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if reload_result.returncode != 0:
        detail = (reload_result.stderr or reload_result.stdout).strip().splitlines()
        tail = " / ".join(detail[-3:]) if detail else "no output"
        raise ProvisionError(f"{target.device}: frr-reload failed: {tail}")

    return f"reloaded in {target.container}"


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
    for line in lines:
        if _TOP_LEVEL_STANZA.match(line):
            out.append("replace:")
        out.append(line)
    return "\n".join(out) + "\n"


# A top-level Junos stanza opener: unindented, lowercase, ending in ` {`.
_TOP_LEVEL_STANZA = re.compile(r"^[a-z][a-z0-9-]* \{$")


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
    ARTIFACT_FRR: push_frr,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--branch", default="", help="Infrahub branch to read artifacts from (default: main)")
    parser.add_argument("--dry-run", action="store_true", help="List what would be pushed, change nothing")
    parser.add_argument("--only", default="", help="Provision a single device by its Infrahub name")
    parser.add_argument("--kind", choices=sorted(KINDS), default="", help="Provision one device family only")
    args = parser.parse_args()

    if not INFRAHUB_API_TOKEN:
        print("INFRAHUB_API_TOKEN is not set; Infrahub will reject the artifact download.", file=sys.stderr)
        return 2

    try:
        targets = discover(args.branch)
    except (httpx.HTTPError, ProvisionError) as error:
        print(f"Could not read the artifact list from Infrahub: {error}", file=sys.stderr)
        return 2

    if args.kind:
        targets = [t for t in targets if t.artifact_name == KINDS[args.kind]]
    if args.only:
        targets = [t for t in targets if t.device == args.only]

    if not targets:
        print("Nothing to provision. Has `invoke avd` run, so the artifacts exist?", file=sys.stderr)
        return 1

    where = f"branch '{args.branch}'" if args.branch else "main"
    print(f"Provisioning {len(targets)} device(s) from {where}:")
    failures = provision(targets, args.branch, args.dry_run)

    if failures:
        print(f"\n{failures} of {len(targets)} device(s) failed.", file=sys.stderr)
        return 1
    if not args.dry_run:
        print(f"\nAll {len(targets)} device(s) now match Infrahub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
