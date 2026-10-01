# Contract: Measurement catalogue → per-family rendering

The renderer dispatches on `MonitoringMeasurement.name` and on the matched device's **kind**. This
table is the contract. A unit test asserts that the code's dispatch table equals it, both ways.

| Measurement | EOS (`DcimFabricSwitch`) | FRR (`DcimDevice`, `frr_routers`) | Junos (`SecurityFirewall`) | k3s node (`ComputePhysicalServer`) |
| --- | --- | --- | --- | --- |
| `interface-counters` | gNMI `openconfig:/interfaces/interface/state/counters`, sample | — | SNMP IF-MIB `ifHCInOctets`, `ifHCOutOctets`, `ifInErrors`, `ifOutErrors`, `ifOperStatus` (table, indexed by `ifName`) | — |
| `bgp-neighbor-state` | gNMI `openconfig:/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/state`, on_change | frr_exporter `frr_bgp_peer_*` (Telegraf `fieldinclude`) | — | — |
| `evpn-routes` | gNMI `openconfig:/network-instances/network-instance/protocols/protocol/bgp/neighbors/neighbor/afi-safis/afi-safi/state/prefixes` ¹ | — | — | — |
| `system-resources` | gNMI `openconfig:/components/component/cpu/utilization/state`, `/components/component/state/memory` | — ² | SNMP `jnxOperatingCPU`, `jnxOperatingBuffer` | — |
| `security-sessions` | — | — | SNMP `jnxJsSPUMonitoringCurrentFlowSession` | — |
| `node-resources` | — | — | — | node-exporter `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, `node_network_*_bytes_total` (`namepass`) |

¹ *Decided at implementation*: the OpenConfig per-AFI prefix counts were taken directly instead
of an EOS-native Sysdb path, because they are stable across EOS releases. **Verify** against a
live cEOS that the `l2vpn-evpn` AFI reports, during T082.

² *Changed at implementation*: frr_exporter's `process_*` series describe the exporter, not the
router, so FRR has no honest source for `system-resources`. The `wan-routing` profile watches
`bgp-neighbor-state` only.

Rendering rules:

- **Inputs.** One Telegraf input block per (device, family, interval). Measurements sharing a
  device and interval share a block.
- **Tags.** Every input carries these tags from the graph, so dashboards group by intent, not by
  address:
  - `device`: the Infrahub name
  - `kind`
  - `role`
  - `rack` and `pod` (EOS only)
  - `collector`
  - `profile`
- **Not applicable.** A measurement marked `—` for a matched device is skipped for that device,
  and recorded in the artifact as `# skipped: <profile>/<measurement> on <device> (<kind>)`.
- **Ordering.** Devices are sorted by name, measurements by name, and profiles by name. The
  render is deterministic, so a checksum moves only when intent moves.
