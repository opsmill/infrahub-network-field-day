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
* ``_assert_junos_scope`` -- a ``system`` stanza in the artifact would make the
  push overwrite the firewall's credentials with whatever the model holds.
* ``_junos_replace_tagged`` -- without the ``replace:`` tags the load stops being
  confined to the modelled hierarchies, and ``load override``/``load update``
  were both measured deleting ``system`` including the ssh service this code
  arrives on.
"""

from __future__ import annotations

import pytest

from solution_arista_avd.deployment.devices import (
    ProvisionError,
    Target,
    _assert_eos_lifeline,  # noqa: PLC2701 - these guards are the point of this file
    _assert_junos_scope,  # noqa: PLC2701
    _assert_srl_lifeline,  # noqa: PLC2701
    _eos_config_lines,  # noqa: PLC2701
    _junos_replace_tagged,  # noqa: PLC2701
    push_srl,
    srl_candidate_script,
)

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


class TestJunosScope:
    def test_the_current_artifact_shape_passes(self) -> None:
        _assert_junos_scope(_target("fw1"), "interfaces {\n}\nsecurity {\n}\n")

    @pytest.mark.parametrize("stanza", ["system {", "system {\n    host-name fw1;\n}"])
    def test_a_system_stanza_is_refused(self, stanza: str) -> None:
        with pytest.raises(ProvisionError) as error:
            _assert_junos_scope(_target("fw1"), f"interfaces {{\n}}\n{stanza}\n")
        assert "credentials" in str(error.value)

    def test_an_indented_system_keyword_is_not_a_top_level_stanza(self) -> None:
        """`system-services` inside a zone is not the `system` hierarchy. Refusing
        it would block a legitimate artifact."""
        _assert_junos_scope(_target("fw1"), "security {\n    zones {\n        system-services;\n    }\n}\n")


class TestJunosReplaceTagged:
    def test_every_top_level_stanza_gets_a_replace_tag(self) -> None:
        """Two rendered stanzas, plus the empty `applications` appended so an
        omitted model-owned hierarchy is deleted rather than left behind."""
        out = _junos_replace_tagged("interfaces {\n}\nsecurity {\n}\n")
        assert out.count("replace:") == 3
        assert out.startswith("replace:\ninterfaces {")

    def test_interfaces_is_replaced_wholesale_and_that_needs_fxp0_modelled(self) -> None:
        """Replacing the hierarchy deletes everything the artifact omits.

        That is the point -- it is what makes removing an interface from the
        model remove it from the device. It is also why `fxp0` must be in the
        artifact: while it was not, every push deleted the firewall's management
        interface and vrnetlab restored it as root before the commit had to be
        confirmed.
        """
        out = _junos_replace_tagged("interfaces {\n    fxp0 {\n    }\n    ge-0/0/0 {\n    }\n}\n")
        assert out.startswith("replace:\ninterfaces {")
        assert "fxp0" in out, "the artifact must carry the management interface"
        assert "    replace:" not in out, "interfaces are not tagged individually"

    def test_nested_stanzas_do_not_get_tagged(self) -> None:
        """A tag on a nested hierarchy would replace only part of a stanza, which
        is not what `load replace` is being asked to do."""
        out = _junos_replace_tagged("security {\n    zones {\n    }\n}\n")
        # One for `security`, one for the appended empty `applications`. The
        # nested `zones` gets none, which is what this asserts.
        assert out.count("replace:") == 2
        assert "    replace:" not in out

    def test_bang_comment_lines_are_dropped(self) -> None:
        """A compatibility fallback, not the fix: a stored artifact predating the
        `#` provenance header would otherwise fail at line 1, and Junos error
        recovery then skips ahead and still reports 'load complete'."""
        out = _junos_replace_tagged("! Rendered by Infrahub\nsecurity {\n}\n")
        assert "! Rendered" not in out
        assert "replace:\nsecurity {" in out

    def test_a_hash_comment_is_kept_because_junos_understands_it(self) -> None:
        out = _junos_replace_tagged("# Rendered by Infrahub\ninterfaces {\n}\n")
        assert "# Rendered by Infrahub" in out


def test_an_omitted_applications_stanza_is_emitted_empty_and_replaced() -> None:
    """Removing the last generated service must remove it from the device.

    `load replace` acts only on hierarchies the payload tags, so a stanza the
    artifact stops rendering is simply left alone. Measured: revoking an access
    grant removed its policy and left `applications` behind, declaring a service
    nothing referenced -- and the next grant would have added another.
    """
    out = _junos_replace_tagged("interfaces {\n}\nsecurity {\n}\n")
    assert "replace:\napplications {\n}" in out


def test_a_rendered_applications_stanza_is_not_duplicated() -> None:
    """When the artifact does render one, it is tagged like any other stanza and
    no empty stanza is appended after it."""
    out = _junos_replace_tagged("interfaces {\n}\nsecurity {\n}\napplications {\n    application svc-x {\n    }\n}\n")
    assert out.count("applications {") == 1
    assert "    application svc-x {" in out


def test_routing_options_is_not_force_deleted() -> None:
    """Deliberately excluded. Its absence means "no static routes in the model",
    and making the model authoritative for that is a separate decision from
    stopping generated objects accumulating.
    """
    out = _junos_replace_tagged("interfaces {\n}\nsecurity {\n}\n")
    assert "routing-options {" not in out
