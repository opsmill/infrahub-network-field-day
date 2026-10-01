# Quickstart: validating Grafana observability end to end

This is a validation guide, not an implementation. It is for the designs in
[data-model.md](./data-model.md) and [contracts/](./contracts/).

## Prerequisites

- The lab repository is checked out beside this one, carrying the cycle-034 lab commits (R14):
  the installer opt-out, the `frr_exporter` sidecars, the `snmp` stanza, gNMI in `group_vars`,
  and the bookmark.
- Run `uv sync --all-packages`. Docker and ContainerLab must be available.

## 1. Offline gates (no lab needed)

```bash
uv run infrahubctl schema check schemas/
uv run pytest tests/unit -q
uv run invoke lint
```

Expected results:

- **Schema check**: zero errors.
- **Unit tests** cover:
  - the monitoring transform invariants in
    [telemetry-collector-artifact.md](./contracts/telemetry-collector-artifact.md)
  - the measurement dispatch table equalling
    [monitoring-measurements.md](./contracts/monitoring-measurements.md)
  - the `junos_config` and `frr_config` byte-for-byte pins against the updated lab files
  - the EOS golden files
  - the `crossplane_fabric_app` OIDC merge
  - the no-credential grep
  - `test_handover_scope`
  - `test_no_grant_is_seeded`
- **Lint**: clean.

## 2. A rebuild from nothing

```bash
scripts/verify_bootstrap.sh
```

The run must pass every stage. The new assertions, and how to show each one failing:

| Assertion | Prove it can fail by |
| --- | --- |
| three FabricApps and three composed namespaces | deleting `otternet-telemetry` from `objects/36_*` |
| Grafana refuses from the branch desktop before any grant | (it is the gate) temporarily seeding a grant on a scratch branch: the assertion flips |
| a Dex sign-in to Grafana completes as `alice` and lands as `Viewer` | changing the Dex redirect URI by one character |
| `infrahub_dcimgenericdevice_info` has 17 series | stopping `infrahub-exporter` |
| per-family telemetry counts 7 / 6 / 1 / 3 | disabling the `wan-routing` profile: FRR drops to 0 |

## 3. The demo act: alice asks for Grafana

1. From the branch desktop, open `http://10.112.240.81/`. **Expected**: no answer.
2. In the portal at `https://10.90.0.11:32001`, sign in as alice and request access to
   `otternet-metrics` from site `branch`.
3. Open the proposed change. **Expected**:
   - the `ServiceAppAccess`
   - a new `SecurityPolicyRule` (`branch → k8s-prod`, `junos-http`)
   - the border leaf's `PL-DC-ADVERTISED-BRANCH` gaining `10.112.240.81`'s block
   - the re-rendered `Junos Configuration` and the border leaf's EOS configuration
4. Merge it. Wait for the reconciler to confirm fw1 and the leaf.
5. Reload `http://10.112.240.81/`. **Expected**: a redirect to Dex. Sign in as alice and land in
   Grafana as Viewer. The organisation and fabric dashboards have data.
6. Set the grant to `decommissioning`. After convergence, **expected**: the VIP stops answering
   from the branch.

## 4. Infrahub decides what is monitored

1. On a branch, edit profile `fabric-core` and remove `bgp-neighbor-state`.
2. Open a proposed change. **Expected**: the `Telemetry Collector Configuration` artifact diff
   removes the gNMI BGP subscription blocks. Nothing else changes.
3. Merge. Within about 2 minutes (the ConfigMap propagates, then Telegraf reloads), the EOS
   `bgp_neighbor_state` series stop. The dashboard's "intended but unobserved" panel then lists
   every intended EOS session. This is the visible proof that intent and observation are
   separate inputs.
4. Revert the change the same way.

## 5. Intended versus observed

```bash
docker exec clab-otternet-<spine> Cli -p 15 -c 'configure
router bgp <asn>
neighbor <leaf peer> shutdown'
```

**Expected**: within one minute, the fabric dashboard shows that session as *intended, down*. The
next reconcile cycle reports the switch as differing and pushes it back, which also demonstrates
the reconciler.

## 6. Freshness

On a branch, add a k3s node's `telemetry_address`, or remove the firewall from `junos_firewalls`, and open
a proposed change. **Expected**: the collector artifact moves in that proposed change, which proves
`generate-monitoring-collector` re-rendered it. Delete the branch afterwards.
