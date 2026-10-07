# Quickstart: Lab DNS Service

These checks prove the feature works end to end. They are run in this order; the first settles problem 2 and the second proves the decided firewall rule (problem 1) in the [plan](./plan.md#problems-that-need-a-decision) before any generator is written.

## Prerequisites

- The lab is up (`uv run invoke lab`) and the cluster is delivered (`uv run invoke cluster`).
- `export KUBECONFIG=/home/ubuntu/dev/nfd41/infrahub/lab/k8s/.kubeconfig/kubeconfig.yaml`

## 1. Settle which address a Service receives ([research R-3](./research.md#r-3))

1. View an existing application's Service in the cluster and compare its LoadBalancer address with the application's `vip_block` in Infrahub.
2. Expected if the plan holds: the Service address can be set to the first address of the block with a chart value. If not, stop and choose another option.

## 2. Prove the firewall path ([research R-1](./research.md#r-1))

1. After bootstrap, from `branch-desktop`, query the resolver's VIP on port 53 over UDP and TCP, with no request made.
2. Expected: an answer. Before this feature the same query gets none.
3. Confirm the reconciler reports `differed=0` for `fw1`, so the seeded rule and `junos.conf` agree.

## 3. A requested application gets a name (User Story 1)

1. Request an application through the portal and merge its proposed change.
2. Wait about one minute.
3. From `branch-desktop`: `dig +short <app>.int.otternet.lab`.
4. Expected: the address Infrahub holds in `fqdn` for that application.

## 4. A withdrawn application loses its name (User Story 2)

1. Set the application's `status` to `decommissioning`, open the proposed change, and view the zone artifact difference removing its record.
2. Merge, wait about one minute, and resolve the name again.
3. Expected: no answer.

## 5. The resolver serves only the artifact (User Story 3)

1. Compare the zone file in the cluster's ConfigMap with the artifact on `main`.
2. Expected: identical.

## 6. Names outside the zone are unchanged (User Story 4)

1. From `branch-desktop`, resolve a name outside `int.otternet.lab`.
2. Expected: the answer it gave before this feature.

## Automated checks

- `uv run invoke lint` and `uv run invoke test`, each run on its own.
- `uv run invoke test --integration`, because a generator is added.
