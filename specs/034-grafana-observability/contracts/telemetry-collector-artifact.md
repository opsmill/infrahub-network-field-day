# Contract: the `Telemetry Collector Configuration` artifact

## Artifact definition (`.infrahub.yml`)

| Key | Value |
| --- | --- |
| `name` | `telemetry_collector_config` |
| `artifact_name` | `Telemetry Collector Configuration` |
| `parameters` | `name: name__value` |
| `content_type` | `application/yaml` |
| `targets` | `monitoring_collectors` |
| `transformation` | `telemetry_collector_config` (Python transform, query `telemetry_collector_config.gql`) |

## Shape: exactly one YAML document

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: <MonitoringCollector.config_map_name>      # telegraf-intent
  namespace: <MonitoringCollector.namespace_name>  # otternet-telemetry
  labels:
    app.kubernetes.io/managed-by: infrahub
    otternet.lab/collector: <collector name>
data:
  telegraf.conf: |
    # Rendered by Infrahub from MonitoringProfile intent. Do not edit.
    [agent] ...
    [[outputs.prometheus_client]] listen = ":9273" ...
    [[inputs.gnmi]] ...      # one block per (device, interval) for EOS
    [[inputs.snmp]] ...      # Junos, numeric OIDs with translator "gosmi" (no MIB files in the image)
    [[inputs.prometheus]] ...# FRR exporters, node-exporters
    [[inputs.file]]          # files = ["/etc/telegraf-intent/intended.prom"], data_format = "prometheus"
  intended.prom: |
    # TYPE otternet_intended_bgp_neighbor gauge
    otternet_intended_bgp_neighbor{device="...",peer_address="...",vrf="..."} 1
    ...
```

## Credentials

No credential appears in the artifact. The one stated exception is the SNMP community, which is
also on the device (see the plan's Complexity Tracking).

The gNMI username and password are referenced as `${GNMI_USERNAME}` and `${GNMI_PASSWORD}`.
Telegraf substitutes environment variables, and the telemetry application's values load them from
the Secret `telemetry-credentials` with `envFromSecret`.

## Intended-state series (names and labels are stable)

| Metric | Labels | Source |
| --- | --- | --- |
| `otternet_intended_bgp_neighbor` | `device`, `peer_address`, `vrf`, `peer_device` (when resolvable) | EOS: stored `AvdStructuredConfigFile` `router_bgp`. FRR: the same neighbour derivation `frr_config` uses |
| `otternet_intended_link` | `device`, `interface`, `peer_device`, `peer_interface` | cabled `DcimInterface` pairs |
| `otternet_intended_interface_up` | `device`, `interface` | the cabled interface's `status`: 1 when `active`, else 0. *Changed at implementation*: `DcimInterface` has no `enabled` attribute |

All values are `1` unless stated. A dashboard computes "intended but down" as
`otternet_intended_bgp_neighbor unless on(device,peer_address) <established series>`, and the
inverse for "up but unintended".

## Invariants (unit-tested)

1. The output is a single YAML document whose `data` holds exactly the two keys above.
2. `telegraf.conf` parses as TOML, and the transform raises rather than emitting an empty
   configuration.
3. Two renders of the same input are byte-identical.
4. The collector's own group membership never appears in the targets.
5. A device with no address (`mgmt_ip` on a switch, `telemetry_address` on any other kind) is skipped and reported, never emitted with an
   empty address.

## Delivery

A third entry in `vidra/infrahub-syncs.yaml`:

- `artefactName: "Telemetry Collector Configuration"`
- destination namespace `otternet-telemetry`
- same Infrahub address and credentials as the existing two syncs

The telemetry application's values mount ConfigMap `telegraf-intent` at `/etc/telegraf-intent`
and run Telegraf with `--config /etc/telegraf-intent/telegraf.conf --watch-config poll`. A
ConfigMap update reaches the mounted volume within about a minute, and Telegraf reloads it.

## Freshness

The `generate-monitoring-collector` generator (targets `monitoring_collectors`,
`execute_in_proposed_change: true`, `execute_after_merge: true`) requests this artifact's
regeneration on its own branch:

- It writes **no** nodes.
- It is never the target of a trigger rule on a `Monitoring*` kind.
