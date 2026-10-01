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
* ``_assert_frr_lifeline`` -- ``frr-reload.py`` applies the difference between the
  running configuration and the file, so an empty artifact is an instruction to
  **delete everything the router is running**, not a no-op.
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
    _assert_frr_lifeline,  # noqa: PLC2701
    _assert_junos_lifeline,  # noqa: PLC2701
    _eos_config_lines,  # noqa: PLC2701
    _junos_override_payload,  # noqa: PLC2701
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


class TestFrrLifeline:
    """The guard EOS had and FRR did not.

    `frr-reload.py --reload` applies the difference between the running
    configuration and the file, so an empty file means "delete everything the
    router is running" rather than "change nothing". Artifact generation is
    asynchronous and an artifact that has not rendered yet exists, reports
    `Ready`, and is empty -- so a provision run at the wrong moment would erase
    all six WAN routers and report success.
    """

    def test_a_real_configuration_passes(self) -> None:
        _assert_frr_lifeline(_target("branch-rtr"), "frr defaults traditional\nhostname branch-rtr\n")

    def test_an_empty_artifact_is_refused(self) -> None:
        """The case that motivated it."""
        with pytest.raises(ProvisionError) as error:
            _assert_frr_lifeline(_target("branch-rtr"), "")
        assert "delete the running configuration" in str(error.value)

    def test_a_whitespace_only_artifact_is_refused(self) -> None:
        with pytest.raises(ProvisionError):
            _assert_frr_lifeline(_target("branch-rtr"), "\n   \n")

    def test_the_refusal_names_the_device(self) -> None:
        with pytest.raises(ProvisionError) as error:
            _assert_frr_lifeline(_target("isp-pe1"), "! only a comment\n")
        assert "isp-pe1" in str(error.value)

    def test_a_router_running_no_bgp_is_still_allowed(self) -> None:
        """`hostname` rather than `router bgp` is the marker on purpose.

        Every FRR template emits a hostname; a future FRR device that runs no BGP
        is entirely plausible, and a guard that refuses a legitimate
        configuration is a worse failure than the one it prevents.
        """
        _assert_frr_lifeline(_target("mgmt-rtr"), "hostname mgmt-rtr\nip route 0.0.0.0/0 10.0.0.1\n")


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
