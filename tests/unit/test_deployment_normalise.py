"""Tests for the normalisation that makes "differs" mean something.

**These run against real device output**, captured in `fixtures/deployment/`
from the running lab minutes after `invoke provision` had made every device
match its artifact. The `_clean` fixtures are therefore what an in-sync device
actually says, and the `_control` fixtures are the same device with one known
line injected.

Both halves matter and neither is sufficient alone:

* Without the `_clean` assertions, a normaliser that suppressed everything would
  pass -- and the reconciler would never push anything.
* Without the `_control` assertions, a normaliser that suppressed everything
  would *also* pass -- and the reconciler would push nothing while reporting
  in-sync. An empty result is only evidence when something non-empty is proven
  alongside it, which is the same reason this repository never trusts an
  artifact's `Ready` status.

The defect these tests exist to prevent: Junos reports a non-empty difference
against an artifact the device already matches -- as FRR did before the WAN
moved to SR Linux -- so a reconciler reading raw output replaces the firewall's
configuration on every cycle, forever, logging success throughout.

The SR Linux fixtures (`srl_*`) come from a throwaway six-router prototype, not
the lab, which still ran FRR when they were captured: `_clean_<router>` is each
router's own `diff flat` straight after booting its rendered artifact,
`srl_drifted` is isp-pe1 after a hand edit, and `srl_changed` is the artifact
moving while the device stands still.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from solution_arista_avd.deployment.normalise import (
    normalise,
    normalise_eos,
    normalise_junos,
    normalise_srl,
)

FIXTURES = Path(__file__).parent / "fixtures" / "deployment"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestInSyncDevicesAreSilent:
    """The assertion the whole feature rests on."""

    def test_eos_in_sync_normalises_to_empty(self) -> None:
        assert normalise_eos(_fixture("eos_clean.diff")) == []

    @pytest.mark.parametrize(
        "router", ["isp-pe1", "isp-pe2", "internet-rtr", "cust-acme-ce", "cust-globex-ce", "branch-rtr"]
    )
    def test_srl_in_sync_normalises_to_empty(self, router: str) -> None:
        """No suppression rule is needed for this: the router prints only its status line."""
        raw = _fixture(f"srl_clean_{router}.txt")
        assert raw.strip(), "the fixture must hold real output, not nothing"
        assert normalise_srl(raw) == []

    def test_junos_in_sync_normalises_to_empty(self) -> None:
        """An in-sync firewall reports 55 changed lines. Also the point."""
        raw = _fixture("junos_clean.diff")
        assert len(raw.splitlines()) > 40, "fixture should carry the real non-empty output"
        assert normalise_junos(raw) == []


class TestTelemetryEnablementIsSilent:
    """Cycle 034 added device-side telemetry, and a line a device does not echo
    back verbatim would read as a permanent difference -- a push on every cycle.

    Both captured live, from devices whose artifacts carry the new stanza: a leaf
    with `management api gnmi`, and fw1 with its `snmp` stanza bound to
    mgmt_junos. The capture script asserted the stanza was in the artifact it
    compared against, so these are not empty for want of the stanza.
    """

    def test_eos_with_gnmi_normalises_to_empty(self) -> None:
        assert normalise_eos(_fixture("eos_clean_gnmi.diff")) == []

    def test_junos_with_snmp_normalises_to_empty(self) -> None:
        assert normalise_junos(_fixture("junos_clean_snmp.diff")) == []


class TestRealChangesSurvive:
    """Without these, a normaliser that suppressed everything would pass."""

    def test_eos_control_line_survives(self) -> None:
        result = normalise_eos(_fixture("eos_control.diff"))
        assert result
        assert any("probe-marker" in line for line in result)

    def test_srl_drift_on_the_device_survives(self) -> None:
        """A static added and a description changed by hand, the artifact unchanged.

        The diff is what a push would do to undo it: delete the route, put the
        description back.
        """
        assert normalise_srl(_fixture("srl_drifted.txt")) == [
            "delete / network-instance CUST_ACME static-routes route 10.60.99.0/24",
            'insert / network-instance default protocols bgp neighbor 10.50.255.2 description "isp-pe2 (core)"',
        ]

    def test_srl_a_moved_artifact_survives(self) -> None:
        """Intent changed: four ip-mtu values, a route, a description and a deleted prefix-set."""
        result = normalise_srl(_fixture("srl_changed.txt"))
        assert len(result) == 7
        assert "delete / routing-policy prefix-set PL-GLOBEX-HQ-IN" in result
        assert "insert / interface ethernet-1/1 subinterface 0 ip-mtu 9000" in result

    def test_junos_control_line_survives(self) -> None:
        """The control injects a real static route, NOT a comment.

        A comment-based control passes trivially against a broken normaliser,
        because a comment is exactly what Junos does not round-trip and what the
        suppression rules are meant to drop. The first version of this fixture
        made that mistake and tested nothing.
        """
        result = normalise_junos(_fixture("junos_control.diff"))
        assert result
        assert any("10.255.255.0/24" in line for line in result)


class TestFailNoisy:
    """An unrecognised line must count as a difference (FR-011a)."""

    def test_an_unknown_srl_line_is_not_suppressed(self) -> None:
        raw = "Warning: something unforeseen\nAll changes have been discarded. Leaving candidate mode.\n"
        assert normalise_srl(raw) == ["Warning: something unforeseen"]

    def test_the_commit_status_line_is_not_a_difference(self) -> None:
        """The push prints its diff and then this; only the diff is configuration."""
        assert normalise_srl(_fixture("srl_commit_ok.txt")) == [
            "insert / network-instance CUST_ACME static-routes route 10.60.99.0/24 next-hop-group acme-dr",
            'insert / network-instance default protocols bgp neighbor 10.50.255.2 description "isp-pe2 (core link)"',
        ]

    def test_an_unknown_junos_line_is_not_suppressed(self) -> None:
        raw = "[edit security]\n+   some-new-stanza {\n"
        assert normalise_junos(raw) == ["+   some-new-stanza {"]

    def test_a_deletion_counts_as_a_difference(self) -> None:
        """Drift that removes configuration matters as much as drift that adds."""
        assert normalise_eos("--- system:/running-config\n-ip host gone 10.0.0.1\n") == ["-ip host gone 10.0.0.1"]

    def test_an_unknown_family_raises_rather_than_guessing(self) -> None:
        with pytest.raises(ValueError, match="no normaliser"):
            normalise("IOS-XR Configuration", "anything")


class TestSuppressionReasons:
    """Each suppression is here for a stated reason. These pin the reasons."""

    def test_junos_zone_pair_reordering_is_suppressed(self) -> None:
        raw = "[edit security policies]\n!    from-zone wan to-zone branch { ... }\n"
        assert normalise_junos(raw) == []

    def test_an_fxp0_deletion_is_never_suppressed_because_it_signals_a_regression(self) -> None:
        """This assertion is the inverse of what it used to be, deliberately.

        `load replace` on the whole `interfaces` hierarchy deleted the vSRX's
        management interface on every push; vrnetlab restored it as root, so an
        in-sync firewall reported `- fxp0 {...}` forever and this module
        suppressed it. `_junos_replace_tagged` now tags each modelled interface
        instead of the stanza, so the candidate leaves fxp0 alone and the diff
        no longer mentions it.

        If it ever appears again, the tagging has regressed and the firewall's
        management path is being deleted on every push. That must be reported,
        not hidden.
        """
        raw = (
            "[edit interfaces]\n"
            "-   fxp0 {\n"
            "-       unit 0 {\n"
            "-           family inet {\n"
            "-               address 10.0.0.15/24;\n"
            "-           }\n"
            "-       }\n"
            "-   }\n"
        )
        assert normalise_junos(raw), "an fxp0 deletion must surface as a difference"

    def test_a_different_interface_is_not_suppressed(self) -> None:
        """The fxp0 rule must not become "ignore interface changes"."""
        raw = "[edit interfaces]\n-   ge-0/0/1 {\n-       unit 0;\n-   }\n"
        assert normalise_junos(raw)
