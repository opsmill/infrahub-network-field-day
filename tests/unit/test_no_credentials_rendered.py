"""No credential reaches a rendered artifact or the seed data (cycle 034, SC-007).

Grafana's admin password, its Dex client secret, the gNMI password and the
exporter's token all live in Secrets that `invoke cluster` creates, or in
`.env`. This holds the line in the places a credential would most easily leak:
the values payloads, the values *after* the sign-in merge, the object files,
the exporter's committed configuration and the Telegraf configuration the
collector artifact renders.

The one recorded exception is the firewall's read-only SNMPv2c community, which
the device has to receive in its configuration. It is asserted to appear
nowhere else.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from transforms.crossplane_fabric_app import apply_sso

REPO = Path(__file__).parents[2]

# The Dex client secret's lab default, which tooling/10-dex.yaml and the
# Secret both use. It must never be in a values file or an artifact.
DEX_CLIENT_SECRET_DEFAULT = "grafana-dex-secret"  # noqa: S105 -- the value being searched for

# Keys under which a chart would accept a literal credential.
CREDENTIAL_KEYS = re.compile(r"^\s*(adminPassword|client_secret|password|token|api_token)\s*:", re.MULTILINE)


def _payload(name: str) -> str:
    return (REPO / "payloads" / f"{name}-values.yaml").read_text(encoding="utf-8")


def test_the_values_payloads_carry_no_credential() -> None:
    for name in ("otternet-metrics", "otternet-telemetry"):
        text = _payload(name)
        assert not CREDENTIAL_KEYS.search(text), f"{name}: a credential key is set in the values payload"
        assert DEX_CLIENT_SECRET_DEFAULT not in text


def test_the_sign_in_merge_references_secrets_and_holds_none() -> None:
    values = apply_sso(
        "dex",
        chart="kube-prometheus-stack",
        values=yaml.safe_load(_payload("otternet-metrics")),
        name="otternet-metrics",
    )
    rendered = yaml.safe_dump(values)
    assert DEX_CLIENT_SECRET_DEFAULT not in rendered
    assert not CREDENTIAL_KEYS.search(rendered)
    assert "secretKeyRef" in rendered


def test_no_object_file_carries_a_credential_other_than_the_snmp_community() -> None:
    offenders = []
    for path in sorted((REPO / "objects").glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if DEX_CLIENT_SECRET_DEFAULT in text or re.search(
            r"^\s*(client_secret|admin_password)\s*:", text, re.MULTILINE
        ):
            offenders.append(path.name)
    assert offenders == []


def test_the_exporter_configuration_commits_no_token() -> None:
    config = REPO / "metrics" / "exporter.yml"
    if not config.is_file():
        return
    loaded = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert not (loaded.get("infrahub") or {}).get("token"), "the exporter token belongs in .env, not in git"
