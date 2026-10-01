"""Tests for the push-path guards lifted in cycle 030.

These four functions are the difference between a push that works and a push
that silently breaks a device, and until this cycle **none of them had a test**.
That was tolerable while the push ran when a human chose to run it. It is not
tolerable now: the reconciler calls this code every ten minutes, so a regression
here reaches the whole fabric before anyone reads a log.

Each test names the failure it prevents, because in every case the failure is
quiet:

* ``_eos_config_lines`` -- a trailing ``end`` returns the CLI to enable mode, the
  commit that follows is rejected as an invalid command, the session is
  abandoned, and the switch **keeps its old configuration while the run reports
  the commands were sent**.
* ``_assert_eos_lifeline`` -- a replace that drops the management path commits
  successfully and takes the device off the network with it.
* ``_assert_srl_lifeline`` -- an SR Linux push is a FULL replace (``delete /``
  then the artifact), so an artifact without the management interface and VRF,
  the gNMI and SSH servers and the admin password commits successfully and
  **leaves the router unreachable or with no login**.
* ``push_srl``'s commit-confirm -- a commit that passes the lifeline and still
  breaks management is rejected at once, and one nobody confirms rolls back.
* ``_assert_junos_lifeline`` -- the firewall push is a full ``load override``,
  so an artifact missing fxp0, the ssh/netconf services or the login this code
  authenticates as would commit a firewall nothing can reach.
* ``push_junos``'s confirmation -- ``commit confirmed`` is only worth anything
  if the confirming ``commit`` waits for proof that management survived.
"""

from __future__ import annotations

import subprocess  # noqa: S404 - only to build CompletedProcess fakes; nothing is executed
from typing import TYPE_CHECKING

import pytest

from solution_arista_avd.deployment import devices
from solution_arista_avd.deployment.devices import (
    ProvisionError,
    Target,
    _assert_eos_lifeline,  # noqa: PLC2701 - these guards are the point of this file
    _assert_junos_lifeline,  # noqa: PLC2701
    _assert_srl_lifeline,  # noqa: PLC2701
    _eos_config_lines,  # noqa: PLC2701
    _junos_override_payload,  # noqa: PLC2701
    push_srl,
    srl_candidate_script,
)

if TYPE_CHECKING:
    from collections.abc import Callable

LIFELINE = "interface Management0\nmanagement api http-commands\nvrf MGMT\n"


def _target(name: str = "leaf-1") -> Target:
    return Target(
        device=name,
        artifact_name="AVD EOS Configuration",
        artifact_id="a" * 32,
        status="Ready",
        mgmt_ip="172.20.41.21",
    )


class TestEosConfigLines:
    def test_the_trailing_end_is_stripped(self) -> None:
        lines = _eos_config_lines("hostname leaf-1\ninterface Ethernet1\nend\n")
        assert lines == ["hostname leaf-1", "interface Ethernet1"]

    def test_every_trailing_end_is_stripped(self) -> None:
        """PyAVD emits one; a future version emitting two must not defeat this."""
        assert _eos_config_lines("hostname leaf-1\nend\nend\n") == ["hostname leaf-1"]

    def test_an_end_in_the_middle_is_kept(self) -> None:
        """Only a *trailing* end is the problem. One in the body is real configuration."""
        lines = _eos_config_lines("hostname leaf-1\nend\ninterface Ethernet1\nend\n")
        assert lines == ["hostname leaf-1", "end", "interface Ethernet1"]

    def test_blank_lines_are_dropped_because_eapi_rejects_them(self) -> None:
        assert _eos_config_lines("hostname leaf-1\n\n   \ninterface Ethernet1\n") == [
            "hostname leaf-1",
            "interface Ethernet1",
        ]

    def test_bang_separators_are_kept(self) -> None:
        """EOS accepts them, and dropping them makes the commands harder to match
        against the artifact when debugging a rejected line by index."""
        assert "!" in _eos_config_lines("hostname leaf-1\n!\ninterface Ethernet1\n")


class TestEosLifeline:
    def test_a_complete_artifact_passes(self) -> None:
        _assert_eos_lifeline(_target(), f"hostname leaf-1\n{LIFELINE}")

    @pytest.mark.parametrize(
        "missing",
        ["interface Management0", "management api http-commands", "vrf MGMT"],
    )
    def test_each_missing_element_is_refused(self, missing: str) -> None:
        config = LIFELINE.replace(missing, "")
        with pytest.raises(ProvisionError) as error:
            _assert_eos_lifeline(_target(), config)
        assert missing in str(error.value)

    def test_the_refusal_names_the_device_and_says_why(self) -> None:
        with pytest.raises(ProvisionError) as error:
            _assert_eos_lifeline(_target("spine-9"), "hostname spine-9\n")
        message = str(error.value)
        assert "spine-9" in message
        assert "management access" in message


SRL_LIFELINE = (
    "delete /\n"
    "set / system aaa authentication admin-user password $6$OtternetLab$hash\n"
    "set / system ssh-server mgmt admin-state enable\n"
    "set / system ssh-server mgmt network-instance mgmt\n"
    "set / system grpc-server mgmt admin-state enable\n"
    "set / system grpc-server mgmt network-instance mgmt\n"
    "set / interface mgmt0 admin-state enable\n"
    "set / interface mgmt0 subinterface 0 ipv4 dhcp-client\n"
    "set / network-instance mgmt type ip-vrf\n"
    "set / network-instance mgmt interface mgmt0.0\n"
)


class TestSrlLifeline:
    """What must survive a FULL replace for the router to stay reachable and manageable.

    An EMPTY artifact -- one that exists, reports `Ready` and has not rendered
    yet -- would otherwise delete the router's whole configuration, management
    and login included.
    """

    def test_a_real_configuration_passes(self) -> None:
        _assert_srl_lifeline(_target("branch-rtr"), SRL_LIFELINE + "set / interface lo0 admin-state enable\n")

    def test_an_empty_artifact_is_refused(self) -> None:
        with pytest.raises(ProvisionError) as error:
            _assert_srl_lifeline(_target("branch-rtr"), "")
        assert "unreachable" in str(error.value)

    @pytest.mark.parametrize(
        "dropped",
        [
            "set / interface mgmt0 ",
            "set / network-instance mgmt ",
            "set / system grpc-server mgmt ",
            "set / system ssh-server mgmt ",
            "set / system aaa authentication admin-user password",
        ],
    )
    def test_each_missing_element_is_refused(self, dropped: str) -> None:
        config = "\n".join(line for line in SRL_LIFELINE.splitlines() if not line.startswith(dropped))
        with pytest.raises(ProvisionError) as error:
            _assert_srl_lifeline(_target("isp-pe1"), config)
        assert "isp-pe1" in str(error.value)

    def test_a_comment_naming_mgmt0_does_not_satisfy_it(self) -> None:
        """The needles are whole commands, so prose about the lifeline is not the lifeline."""
        commented = "\n".join(f"# {line}" for line in SRL_LIFELINE.splitlines())
        with pytest.raises(ProvisionError):
            _assert_srl_lifeline(_target(), commented)

    def test_a_cleartext_password_does_not_satisfy_it(self) -> None:
        """The needle ends in `$`: the admin password must be a crypt hash."""
        config = SRL_LIFELINE.replace("password $6$OtternetLab$hash", "password admin")
        with pytest.raises(ProvisionError, match="admin-user password"):
            _assert_srl_lifeline(_target(), config)


class TestSrlCandidateScript:
    def test_the_whole_tree_is_deleted_before_the_artifact_is_set(self) -> None:
        """`delete /` then the artifact, in ONE candidate: EOS's `rollback clean-config`."""
        script = srl_candidate_script("infrahub-test-1", SRL_LIFELINE, commit=False).splitlines()

        assert script[0] == "enter candidate private name infrahub-test-1"
        assert script[1] == "delete /"
        assert script.index("set / interface mgmt0 admin-state enable") > 1
        assert script[-2:] == ["diff flat", "discard now"]

    def test_a_push_commits_confirmed_and_a_comparison_does_not_commit(self) -> None:
        push = srl_candidate_script("n", SRL_LIFELINE, commit=True).splitlines()
        assert push[-1].startswith("commit confirmed timeout ")
        assert "commit" not in srl_candidate_script("n", SRL_LIFELINE, commit=False)


class _Docker:
    """Stands in for `docker`: records each argv, answers like a router would."""

    def __init__(self, *, commit_out: str, listening: str) -> None:
        self.calls: list[list[str]] = []
        self.commit_out = commit_out
        self.listening = listening

    def __call__(self, argv: list[str], **_: object) -> object:
        import subprocess  # noqa: S404 - only CompletedProcess, to fake a docker answer

        self.calls.append(argv)
        if argv[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, "true\n", "")
        if argv[-1] == "sr_cli":
            return subprocess.CompletedProcess(argv, 0, self.commit_out, "")
        if "addr" in argv:
            return subprocess.CompletedProcess(argv, 0, "3: mgmt0.0    inet 172.20.41.61/24 brd x\n", "")
        if "ss" in argv:
            return subprocess.CompletedProcess(argv, 0, self.listening, "")
        return subprocess.CompletedProcess(argv, 0, "", "")

    def tools(self) -> list[str]:
        return [argv[-1] for argv in self.calls if "-d" in argv]


COMMITTED = (
    "Commit confirmed (automatic rollback in 2 minutes)\nAll changes have been committed. Leaving candidate mode.\n"
)


class TestSrlCommitConfirm:
    def test_a_healthy_commit_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        docker = _Docker(commit_out=COMMITTED, listening="*:57400 *:80 0.0.0.0:22 \n")
        monkeypatch.setattr("subprocess.run", docker)

        assert "confirmed" in push_srl(_target("isp-pe1"), SRL_LIFELINE)
        assert docker.tools() == ["tools system configuration confirmed-accept"]

    def test_a_commit_that_breaks_gnmi_is_rejected_not_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Measured on the prototype: gNMI moved off 57400, rejected, rolled back."""
        docker = _Docker(commit_out=COMMITTED, listening="*:57999 0.0.0.0:22 \n")
        monkeypatch.setattr("subprocess.run", docker)

        with pytest.raises(ProvisionError, match="rolled back"):
            push_srl(_target("isp-pe1"), SRL_LIFELINE)
        assert docker.tools() == ["tools system configuration confirmed-reject"]

    def test_the_lifeline_runs_before_anything_is_sent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        docker = _Docker(commit_out=COMMITTED, listening="")
        monkeypatch.setattr("subprocess.run", docker)

        with pytest.raises(ProvisionError):
            push_srl(_target("isp-pe1"), "delete /\n")
        assert docker.calls == []


LAB_HASH = "$6$otternetlab$1ni88meu2WmQvWmveReLJXVojb6LSSOmcM75qXpzCLKzUzoU63yFywA2YQLoFI2QDjo4RXF28DbWY9wg9gKT71"

# The smallest artifact a full replace can survive: every lifeline statement
# and nothing else. Built from the real artifact's own lines.
JUNOS_LIFELINE = f"""# Rendered by Infrahub for fw1 -- do not edit.
system {{
    host-name fw1;
    root-authentication {{
        encrypted-password "{LAB_HASH}";
    }}
    login {{
        user admin {{
            class super-user;
            authentication {{
                encrypted-password "{LAB_HASH}";
            }}
        }}
    }}
    services {{
        ssh {{
            root-login allow;
        }}
        netconf {{
            ssh;
        }}
    }}
    management-instance;
}}
interfaces {{
    fxp0 {{
        unit 0 {{
            family inet {{
                address 10.0.0.15/24;
            }}
        }}
    }}
}}
"""


class TestJunosLifeline:
    """Replaces the old scope guard, and inverts it.

    `_assert_junos_scope` refused a `system` stanza, because `load replace` on
    tagged hierarchies would have overwritten credentials the model did not
    hold. Under `load override` the danger is the opposite: an artifact WITHOUT
    `system` deletes the logins and the services this push arrives on.
    """

    def test_the_minimal_management_artifact_passes(self) -> None:
        _assert_junos_lifeline(_target("fw1"), JUNOS_LIFELINE)

    def test_an_empty_artifact_is_refused(self) -> None:
        """An empty override is an instruction to erase the firewall."""
        with pytest.raises(ProvisionError) as error:
            _assert_junos_lifeline(_target("fw1"), "")
        assert "fw1" in str(error.value)
        assert "load override" in str(error.value)

    @pytest.mark.parametrize(
        ("remove", "named"),
        [
            ("                address 10.0.0.15/24;\n", "fxp0"),
            ("        ssh {\n            root-login allow;\n        }\n", "services ssh"),
            ("        netconf {\n            ssh;\n        }\n", "netconf"),
            ("            class super-user;\n", "super-user"),
            ("    root-authentication {\n", "root-authentication"),
        ],
    )
    def test_each_missing_lifeline_statement_is_refused(self, remove: str, named: str) -> None:
        config = JUNOS_LIFELINE.replace(remove, "", 1)
        assert config != JUNOS_LIFELINE
        with pytest.raises(ProvisionError) as error:
            _assert_junos_lifeline(_target("fw1"), config)
        assert named in str(error.value)

    def test_a_login_for_another_user_does_not_count(self) -> None:
        """The reconciler authenticates as VSRX_USERNAME; a different account
        keeps the device reachable for someone, and not for this push."""
        config = JUNOS_LIFELINE.replace("user admin {", "user operator {")
        with pytest.raises(ProvisionError, match="login for 'admin'"):
            _assert_junos_lifeline(_target("fw1"), config)

    def test_an_inactive_fxp0_is_no_fxp0(self) -> None:
        config = JUNOS_LIFELINE.replace("    fxp0 {", "    inactive: fxp0 {")
        with pytest.raises(ProvisionError, match="fxp0"):
            _assert_junos_lifeline(_target("fw1"), config)

    def test_a_mention_in_a_comment_does_not_count(self) -> None:
        """Statements, not substrings: a comment naming `ssh` is not a service."""
        config = JUNOS_LIFELINE.replace(
            "        ssh {\n            root-login allow;\n        }\n",
            "        /* ssh {\n            root-login allow;\n        } */\n",
        )
        with pytest.raises(ProvisionError, match="services ssh"):
            _assert_junos_lifeline(_target("fw1"), config)

    def test_cleartext_is_refused(self) -> None:
        config = JUNOS_LIFELINE.replace(
            "            class super-user;\n",
            '            class super-user;\n            authentication {\n                plain-text-password-value "x";\n            }\n',
        )
        with pytest.raises(ProvisionError, match="plain-text-password-value"):
            _assert_junos_lifeline(_target("fw1"), config)


class TestJunosOverridePayload:
    def test_the_artifact_is_sent_as_is(self) -> None:
        """No `replace:` tags: `override` replaces everything, so there is
        nothing to confine -- and no empty `applications` is appended, because
        an omitted hierarchy is deleted by the verb itself."""
        out = _junos_override_payload(JUNOS_LIFELINE)
        assert out == JUNOS_LIFELINE
        assert "replace:" not in out
        assert "applications {" not in out

    def test_bang_comment_lines_are_dropped(self) -> None:
        """A compatibility fallback, not the fix: a stored artifact predating the
        `#` provenance header would otherwise fail at line 1, and Junos error
        recovery then skips ahead and still reports 'load complete' -- which
        under `override` is a partial firewall."""
        out = _junos_override_payload("! Rendered by Infrahub\nsecurity {\n}\n")
        assert "! Rendered" not in out
        assert out.startswith("security {")

    def test_a_hash_comment_is_kept_because_junos_understands_it(self) -> None:
        assert "# Rendered by Infrahub" in _junos_override_payload("# Rendered by Infrahub\ninterfaces {\n}\n")


def _completed(stdout: str = "", returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class _FakeVsrx:
    """Records every CLI script the push sends, and answers from a script."""

    def __init__(self, reachable: bool, commit_output: str = "commit complete\n") -> None:
        self.reachable = reachable
        self.commit_output = commit_output
        self.cli: list[str] = []

    def vsrx_cli(self, _target: Target, script: str) -> subprocess.CompletedProcess[str]:
        self.cli.append(script)
        if "load override" in script:
            return _completed(f"load complete\n{self.commit_output}")
        if script.startswith("show version"):
            return _completed("Hostname: fw1\n") if self.reachable else _completed("", 255)
        return _completed("commit complete\n")

    def vsrx(self, _target: Target, argv: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        if "netconf" in argv:
            return _completed("<hello xmlns=...>") if self.reachable else _completed("", 255)
        return _completed()


@pytest.fixture
def fake_vsrx(monkeypatch: pytest.MonkeyPatch) -> Callable[..., _FakeVsrx]:
    def install(reachable: bool, commit_output: str = "commit complete\n") -> _FakeVsrx:
        fake = _FakeVsrx(reachable, commit_output)
        monkeypatch.setattr(devices, "_container_running", lambda _name: True)
        monkeypatch.setattr(devices, "_wait_for_vsrx", lambda _target: None)
        monkeypatch.setattr(devices, "_vsrx_cli", fake.vsrx_cli)
        monkeypatch.setattr(devices, "_vsrx", fake.vsrx)
        monkeypatch.setattr(devices.subprocess, "run", lambda *_a, **_k: _completed())
        monkeypatch.setattr(devices, "_REACHABILITY_INTERVAL", 0)
        return fake

    return install


class TestJunosPushConfirmsOnlyWhatItProved:
    """The confirming commit is the dangerous line, so these pin when it is sent."""

    def test_a_reachable_device_is_overridden_then_confirmed(self, fake_vsrx: Callable[..., _FakeVsrx]) -> None:
        fake = fake_vsrx(reachable=True)
        devices.push_junos(_target("fw1"), JUNOS_LIFELINE)
        load = next(s for s in fake.cli if "load override" in s)
        assert f"commit confirmed {devices.JUNOS_CONFIRM_MINUTES}" in load
        assert "load replace" not in load
        assert fake.cli[-1] == "configure exclusive\ncommit\nexit\nexit\n"
        # The probe ran between the two commits, not before the first.
        probe = next(i for i, s in enumerate(fake.cli) if s.startswith("show version"))
        assert fake.cli.index(load) < probe < len(fake.cli) - 1

    def test_an_unreachable_device_is_never_confirmed(self, fake_vsrx: Callable[..., _FakeVsrx]) -> None:
        """Measured on the prototype: fxp0 moved off vrnetlab's address, the
        probe failed, nothing confirmed, Junos rolled back by itself."""
        fake = fake_vsrx(reachable=False)
        with pytest.raises(ProvisionError, match="rolls it back"):
            devices.push_junos(_target("fw1"), JUNOS_LIFELINE)
        assert not [s for s in fake.cli if s == "configure exclusive\ncommit\nexit\nexit\n"]

    def test_a_commit_that_did_not_report_completion_is_never_confirmed(
        self, fake_vsrx: Callable[..., _FakeVsrx]
    ) -> None:
        """The committing session may die with the commit. Confirming then would
        confirm blind -- possibly a candidate that was never committed."""
        fake = fake_vsrx(reachable=True, commit_output="")
        with pytest.raises(ProvisionError, match="not confirming"):
            devices.push_junos(_target("fw1"), JUNOS_LIFELINE)
        assert not [s for s in fake.cli if s.startswith("show version")]
        assert not [s for s in fake.cli if s == "configure exclusive\ncommit\nexit\nexit\n"]

    def test_a_refused_artifact_touches_nothing(self, fake_vsrx: Callable[..., _FakeVsrx]) -> None:
        fake = fake_vsrx(reachable=True)
        with pytest.raises(ProvisionError, match="fxp0"):
            devices.push_junos(_target("fw1"), JUNOS_LIFELINE.replace("address 10.0.0.15/24;", ""))
        assert fake.cli == []

    def test_a_late_answer_is_not_confirmed(
        self, fake_vsrx: Callable[..., _FakeVsrx], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A probe that succeeds near the rollback may be succeeding BECAUSE the
        rollback ran; the confirm would then commit nothing and print success."""
        fake = fake_vsrx(reachable=True)
        clock = iter([0.0, devices.JUNOS_CONFIRM_MINUTES * 60.0])
        monkeypatch.setattr(devices.time, "monotonic", lambda: next(clock))
        with pytest.raises(ProvisionError, match="too close"):
            devices.push_junos(_target("fw1"), JUNOS_LIFELINE)
        assert not [s for s in fake.cli if s == "configure exclusive\ncommit\nexit\nexit\n"]
