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
    _eos_config_lines,  # noqa: PLC2701
    _junos_replace_tagged,  # noqa: PLC2701
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
    def test_top_level_stanzas_other_than_interfaces_get_a_replace_tag(self) -> None:
        out = _junos_replace_tagged("security {\n}\nrouting-options {\n}\n")
        assert out.count("replace:") == 2
        assert out.startswith("replace:\nsecurity {")

    def test_interfaces_is_tagged_per_interface_not_wholesale(self) -> None:
        """The stanza itself must NOT be replaced.

        The model owns the data interfaces and not `fxp0` -- the lab's own
        junos.conf says init.conf owns it. Replacing the whole hierarchy deleted
        the firewall's management interface on every push, and it survived only
        because vrnetlab restored it as root seconds later.
        """
        out = _junos_replace_tagged("interfaces {\n    ge-0/0/0 {\n        mtu 9192;\n    }\n}\n")
        assert "replace:\ninterfaces {" not in out, "the interfaces stanza must not be replaced wholesale"
        assert "    replace:\n    ge-0/0/0 {" in out, "each modelled interface is replaced"

    def test_an_unmodelled_interface_is_left_alone(self) -> None:
        """Nothing tags a hierarchy the artifact does not mention, so fxp0
        survives the load. That is the whole fix."""
        out = _junos_replace_tagged("interfaces {\n    ge-0/0/0 {\n    }\n}\n")
        assert "fxp0" not in out

    def test_nested_stanzas_do_not_get_tagged(self) -> None:
        """A tag on a nested hierarchy would replace only part of a stanza, which
        is not what `load replace` is being asked to do."""
        out = _junos_replace_tagged("security {\n    zones {\n    }\n}\n")
        assert out.count("replace:") == 1

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
