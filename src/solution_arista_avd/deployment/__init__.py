"""Deployment reconciliation: make the devices match what Infrahub renders.

Cycle 029 built the place to record deployment state. This package is what
writes to it -- a loop that asks each device to compare itself against its
rendered artifact, pushes when they genuinely differ, and records the last time
each device was *confirmed to match*.

    devices    the push path, lifted verbatim from scripts/provision_lab.py
    normalise  the per-family rules that make "differs" mean something
    compare    ask a device for its own diff
    state      read and write the Deployment kinds
    reconcile  the cycle

**Read `normalise` before changing anything here.** Two of the three device
families report a non-empty difference against an artifact the device already
matches, so "the device reported a diff" is not the same as "the device needs
pushing". Treating them as the same replaces the configuration of every FRR
router and the firewall on every cycle, forever, while logging success.
"""
