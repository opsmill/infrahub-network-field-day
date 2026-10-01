# Contract: Infrahub exporter (organisation metrics)

## Service

| Item | Value |
| --- | --- |
| Compose service | `infrahub-exporter` |
| Build | git context `https://github.com/opsmill/infrahub-exporter.git#80974df`, `development/Dockerfile` |
| Command | `python -m infrahub_exporter.main -c /config/exporter.yml` |
| Port | host `8002` → container `8001` (8001 on the host is `infrahub-mcp`) |
| Account | `metrics-exporter`, view-only role. It is never `admin` and never `agent` |
| Token | `.env` `INFRAHUB_EXPORTER_TOKEN`, written by `scripts/provision_metrics_exporter.py` (idempotent) |
| Started by | `uv run invoke metrics-exporter`, which bootstrap calls after `mcp` |
| Stopped by | `invoke stop` / `invoke destroy` (already `--profile '*'`) |

## Configuration (`metrics/exporter.yml`, committed without the token)

| Kind | `include` |
| --- | --- |
| `DcimGenericDevice` | `name`, `status`, `member_of_groups` |
| `ServiceGeneric` | `name`, `status`, `owner` |
| `OrganizationTenant` | `name` |
| `CoreProposedChange` | `name`, `state` |
| `DeploymentState` | `name`, `in_sync`, `suspend` ¹ |

¹ Field names follow `schemas/deployment.yml`. **Verify** them at implementation.

- The poll interval is `60` seconds.
- Service discovery is disabled (research R5/R6).

## Series consumed by dashboards

- `count by (hfid) (infrahub_dcimgenericdevice_info)`: the device inventory. The kind comes from
  the HFID prefix.
- `count by (status) (infrahub_servicegeneric_info)`: services by status.
- `count by (state) (infrahub_coreproposedchange_info)`: open and merged changes.
- `infrahub_deploymentstate_info{in_sync="false"}`: devices drifting from their artifacts.

## Prometheus scrape (in the `otternet-metrics` values)

```yaml
prometheus:
  prometheusSpec:
    additionalScrapeConfigs:
      - job_name: infrahub-exporter
        scrape_interval: 60s
        static_configs: [{targets: ["172.20.41.1:8002"]}]
      - job_name: telemetry
        static_configs: [{targets: ["telegraf.otternet-telemetry.svc:9273"]}]
```

## Failure behaviour

- If the Infrahub API is unreachable, the exporter empties that kind's series. Dashboards show a
  gap, and Grafana and sign-in are unaffected. The organisation dashboard carries a "data age"
  panel built on `up{job="infrahub-exporter"}`.
