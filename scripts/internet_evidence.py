#!/usr/bin/env python3
"""Show, in one run, whether each tenant has internet access, with a summary and every raw output.

Run it before the capability is merged, after it is merged, and after the request is merged. For
each tenant it reads four places on the routers and runs a packet test:

1. the tenant's routing policy on `isp-pe1`: is there a `statement 30` that imports a default route?
2. the tenant's VRF on `isp-pe1`: does it hold `0.0.0.0/0`?
3. the tenant's customer router: does it hold `0.0.0.0/0`?
4. `internet-rtr`: does it hold a route back to the tenant's site LAN? A reply needs one.
5. the tenant's host: does `curl` to the internet host answer, and with which HTTP status?

The output has two parts: a summary table, then the unedited output of every command that fed it, one
panel per command, so the audience can read the router's own words. A tenant is consistent when all five
signals agree, so a router that changed but does not forward is reported instead of hidden.

    uv run invoke demo-internet-evidence                    # summary and raw output
    uv run invoke demo-internet-evidence --expect none      # also fail unless nobody has internet
    uv run invoke demo-internet-evidence --expect acme      # also fail unless only acme has it
    uv run invoke demo-internet-evidence --summary-only     # leave out the raw output

The demonstration has two merges, and the second is made by a person, never by a command:

    --phase before       the baseline: nobody has internet
    --phase capability   part 1 merged (the schema, transform and check): still nobody has internet
    --phase request      part 2 merged (acme's request, merged by the person): only acme has internet

A phase sets the expectation and prints what comes next. Nothing here merges anything.

Needs the lab's containers (`docker`) and the `rich` package (a dependency of infrahub-sdk). It reads
nothing from Infrahub, so it can be run at any time.
"""

from __future__ import annotations

import argparse
import re
import subprocess  # noqa: S404
import sys
from dataclasses import dataclass, field

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

LAB = "clab-otternet"
INTERNET_HOST = "198.51.100.10"

# From lab/wan/tenants.yml. The tenant's own site LAN is what internet-rtr must hold a route to.
TENANTS = {
    "acme": {"vrf": "CUST_ACME", "ce": "cust-acme-ce", "host": "cust-acme-host", "lan": "10.60.10.0/24"},
    "globex": {"vrf": "CUST_GLOBEX", "ce": "cust-globex-ce", "host": "cust-globex-host", "lan": "10.60.20.0/24"},
}

PHASES = {
    "before": ("none", "Baseline. Next: release and merge part 1, the capability (`uv run invoke demo-release`)."),
    "capability": (
        "none",
        "Part 1 is merged and no router changed. Next: request Internet Access for acme on a branch, and merge"
        " that proposed change yourself (part 2). No command merges it.",
    ),
    "request": ("acme", "Part 2 is merged. Acme has internet and globex, the control, does not."),
}

console = Console(highlight=False)


def run(*cmd: str, timeout: int = 30) -> str:
    """Output of a command, stdout and stderr together; an unreachable container gives an empty string."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)  # noqa: S603
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout + proc.stderr


def sr_cli(node: str, command: str) -> str:
    return run("docker", "exec", f"{LAB}-{node}", "sr_cli", "-d", command)


def route_lines(raw: str) -> list[str]:
    """Rows of a route table, as printed: those that start with a prefix."""
    return [line.strip() for line in raw.splitlines() if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+\s", line)]


def has_prefix(raw: str, prefix: str) -> bool:
    return any(row.split()[0] == prefix for row in route_lines(raw))


def curl(host: str) -> tuple[str, str, str]:
    """Raw verbose curl output, then the HTTP status and total time. Status 000 means no answer."""
    raw = run(
        "docker", "exec", f"{LAB}-{host}", "sh", "-c",
        f"curl -sv -m 5 -o /dev/null -w '\\nHTTP %{{http_code}} %{{time_total}}\\n' http://{INTERNET_HOST}/ 2>&1 || true",
    )  # fmt: skip
    match = re.search(r"^HTTP (\d{3}) (\S+)$", raw, re.MULTILINE)
    return (raw.strip(), match.group(1), f"{float(match.group(2)):.2f}") if match else (raw.strip(), "000", "-")


@dataclass
class Command:
    """One command that was run, and what it printed."""

    where: str
    command: str
    output: str
    when_empty: str = "(no output: the container did not answer)"


@dataclass
class Evidence:
    tenant: str
    policy_statement: bool = False
    pe_default_route: bool = False
    ce_default_route: bool = False
    return_route: bool = False
    http_status: str = "000"
    http_seconds: str = "-"
    commands: list[Command] = field(default_factory=list)

    @property
    def answered(self) -> bool:
        return self.http_status.startswith(("2", "3"))

    @property
    def signals(self) -> list[bool]:
        return [self.policy_statement, self.pe_default_route, self.ce_default_route, self.return_route, self.answered]

    @property
    def has_internet(self) -> bool:
        return all(self.signals)

    @property
    def consistent(self) -> bool:
        return all(self.signals) or not any(self.signals)

    @property
    def verdict(self) -> str:
        return "internet" if self.has_internet else "no internet" if not any(self.signals) else "INCONSISTENT"


def gather(tenant: str, internet_rtr_raw: str) -> Evidence:
    spec = TENANTS[tenant]
    policy_cmd = f"info from running /routing-policy policy RM-{tenant.upper()}-IMPORT statement 30"
    pe_cmd = f"show network-instance {spec['vrf']} ipv4 route"
    ce_cmd = "show network-instance default ipv4 route"
    policy_raw, pe_raw, ce_raw = sr_cli("isp-pe1", policy_cmd), sr_cli("isp-pe1", pe_cmd), sr_cli(spec["ce"], ce_cmd)
    curl_raw, status, seconds = curl(spec["host"])
    return Evidence(
        tenant=tenant,
        policy_statement="PL-DEFAULT" in policy_raw,
        pe_default_route=has_prefix(pe_raw, "0.0.0.0/0"),
        ce_default_route=has_prefix(ce_raw, "0.0.0.0/0"),
        return_route=has_prefix(internet_rtr_raw, spec["lan"]),
        http_status=status,
        http_seconds=seconds,
        commands=[
            Command(
                "isp-pe1",
                policy_cmd,
                policy_raw,
                "(empty: this statement is not configured, so no default route is imported)",
            ),
            Command("isp-pe1", pe_cmd, pe_raw),
            Command(spec["ce"], ce_cmd, ce_raw),
            Command(spec["host"], f"curl -v -m 5 http://{INTERNET_HOST}/", curl_raw),
        ],
    )


def mark(flag: bool) -> Text:
    return Text("yes", style="bold green") if flag else Text("no", style="red")


def summary_table(results: list[Evidence]) -> Table:
    table = Table(title=f"Internet access: each tenant's host to {INTERNET_HOST}", header_style="bold", show_lines=True)
    table.add_column("Tenant", style="bold")
    table.add_column("PE import policy\nstatement 30", justify="center")
    table.add_column("Default route\non PE VRF", justify="center")
    table.add_column("Default route\non customer router", justify="center")
    table.add_column("Route back\non internet-rtr", justify="center")
    table.add_column("curl from\ncustomer host", justify="center")
    table.add_column("Verdict", justify="center")
    for ev in results:
        verdict_style = {"internet": "bold green", "no internet": "bold yellow"}.get(ev.verdict, "bold red")
        table.add_row(
            ev.tenant,
            mark(ev.policy_statement),
            mark(ev.pe_default_route),
            mark(ev.ce_default_route),
            mark(ev.return_route),
            Text(f"{ev.http_status}  ({ev.http_seconds}s)", style="bold green" if ev.answered else "red"),
            Text(ev.verdict, style=verdict_style),
        )
    return table


def highlight_default(output: str, when_empty: str) -> Text:
    """The router's own output, with the default route and the policy statement picked out.

    Only the router's long separator lines are shortened, so the panels fit a normal terminal."""
    lines = [("-" * 60 if re.fullmatch(r"[=\-]{40,}", line) else line) for line in output.splitlines()]
    text = Text("\n".join(lines) or when_empty, no_wrap=True, overflow="ellipsis")
    text.highlight_regex(r"^0\.0\.0\.0/0.*$", "bold green")
    text.highlight_regex(r"PL-DEFAULT", "bold green")
    text.highlight_regex(r"^HTTP \d{3}.*$", "bold cyan")
    return text


def raw_section(title: str, commands: list[Command]) -> Group:
    panels = [
        Panel(
            highlight_default(cmd.output, cmd.when_empty),
            title=f"[bold]{cmd.where}[/bold]  [dim]{cmd.command}[/dim]",
            title_align="left",
            border_style="blue",
        )
        for cmd in commands
    ]
    return Group(Rule(title, style="bold"), *panels)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--expect", choices=("none", *TENANTS), help="fail unless exactly this tenant (or nobody) has internet"
    )
    parser.add_argument(
        "--phase", choices=tuple(PHASES), help="the stage of the two-merge demonstration; sets --expect"
    )
    parser.add_argument("--summary-only", action="store_true", help="leave out the raw output of each command")
    args = parser.parse_args()

    if args.phase:
        args.expect = args.expect or PHASES[args.phase][0]

    if not run("docker", "ps", "--filter", f"name={LAB}-isp-pe1", "--format", "{{.Names}}").strip():
        console.print(
            f"[bold red]The lab is not running:[/] no container named {LAB}-isp-pe1. Start it with `uv run invoke lab`."
        )
        return 2

    internet_cmd = "show network-instance default ipv4 route"
    internet_raw = sr_cli("internet-rtr", internet_cmd)
    results = [gather(tenant, internet_raw) for tenant in TENANTS]

    title = f" ({args.phase})" if args.phase else ""
    console.print(Rule(f"Internet access evidence{title}", style="bold"))
    console.print(summary_table(results))

    if not args.summary_only:
        console.print(
            raw_section(
                "Raw output: the internet router (the route back to each tenant)",
                [Command("internet-rtr", internet_cmd, internet_raw)],
            )
        )
        for ev in results:
            console.print(raw_section(f"Raw output: {ev.tenant}", ev.commands))

    failures = [
        f"{ev.tenant}: the five signals disagree "
        f"(policy {ev.policy_statement}, PE {ev.pe_default_route}, CE {ev.ce_default_route}, "
        f"return {ev.return_route}, packet {ev.http_status})"
        for ev in results
        if not ev.consistent
    ]
    if args.expect:
        wanted = set() if args.expect == "none" else {args.expect}
        got = {ev.tenant for ev in results if ev.has_internet}
        if got != wanted:
            failures.append(f"expected internet for {sorted(wanted) or 'nobody'}, found {sorted(got) or 'nobody'}")

    console.print()
    if failures:
        for failure in failures:
            console.print(f"[bold red]FAIL[/]  {failure}")
        return 1
    console.print(
        "[bold green]PASS[/]  every tenant's router state and packet test agree"
        + (f", and match --expect {args.expect}" if args.expect else "")
    )
    if args.phase:
        console.print(PHASES[args.phase][1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
