# Contract: DNS zone artifact

## Artifact definition

| Property | Value |
| --- | --- |
| Artifact name | `DNS Zone Configuration` |
| Content type | `application/yaml` |
| Target group | `dns_resolvers` (the resolver application only) |
| Transform | `dns_zone_config` |
| Delivered by | Vidra `InfrahubSync` named `dns-zone-config`, into the resolver's namespace |

## Content

One Kubernetes `ConfigMap` document with two keys:

- `Corefile`: one server block for the zone, with the `file` and `reload` plugins, and `forward` for no other zone (nothing outside the zone is answered here, per spec FR-020).
- `<zone>.db`: the zone file. An SOA record, one NS record for the resolver, and one A record per live application.

## Rules the renderer enforces

- It raises, so the artifact is in error and the last good ConfigMap stays in the cluster, when there are no A records.
- It raises when two applications produce the same label.
- It skips an application with no block, or an invalid label, and writes a comment line saying so in the zone file. It never drops one silently.
- The SOA serial changes whenever the records change and not otherwise, so a no-change render is byte-identical.

## What is not decided

- The exact Corefile plugin set and the chart values that mount the ConfigMap ([research.md](../research.md#r-2)).
