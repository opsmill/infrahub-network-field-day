# metrics

Configuration for the Infrahub exporter, which turns the graph into
Prometheus metrics for the organisation dashboards in Grafana.

The exporter runs beside Infrahub in the compose stack (service
`infrahub-exporter`, host port 8002) and reads as the `metrics-exporter`
account. `scripts/provision_metrics_exporter.py` creates that account and writes
its token into `.env` as `INFRAHUB_EXPORTER_TOKEN`.

**The token is never committed here.** `exporter.yml` carries everything except
the credential, which the container receives from the environment.
