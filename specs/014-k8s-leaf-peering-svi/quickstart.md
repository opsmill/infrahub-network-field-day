# Quickstart — Validating the k8s Leaf Peering SVIs

**Feature**: `specs/014-k8s-leaf-peering-svi`

How to prove this cycle did what it claims, from a clean shell. Every command here was run to
produce `acceptance-evidence.md`.

## Prerequisites

```bash
export INFRAHUB_API_TOKEN=<token>
export INFRAHUB_ADDRESS=http://localhost:8000
uv sync --all-packages
```

An Infrahub branch to work on. `--sync-with-git` is **mandatory** — without it the repository
never reads `.infrahub.yml` for the branch, so transforms cannot be rendered:

```bash
uv run infrahubctl branch create svi-model --sync-with-git
```

## 1. Capture the regression baseline FIRST

Do this before loading the new objects. Cycles 011 and 012 both recorded the same digest for
this artifact; the whole cycle is invalid if it moves.

```bash
uv run infrahubctl schema load schemas --branch svi-model --wait 120
uv run infrahubctl object load objects/ --branch svi-model     # at the pre-change commit
uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
  --branch svi-model > /tmp/svi-baseline.yaml
```

Note that `infrahubctl transform` prints **one extra trailing newline** versus the bytes Infrahub
stores for the artifact. Normalise before comparing to the recorded digest:

```bash
python3 -c "
import hashlib
b = open('/tmp/svi-baseline.yaml','rb').read()
print(hashlib.md5(b.rstrip(b'\n') + b'\n').hexdigest())
"
# expect 0d800c9d5005b5fdb6b371bb5627d143
```

## 2. Load the change

Schema first, then objects — always, and even though this cycle changes no schema:

```bash
uv run infrahubctl schema load schemas --branch svi-model --wait 120
uv run infrahubctl object load objects/ --branch svi-model
```

## 3. Prove the traversal exists (SC-003)

The question the cycle exists to answer — "which device owns 10.110.0.2?":

```bash
curl -s -X POST "$INFRAHUB_ADDRESS/graphql/svi-model" \
  -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"query { IpamIPAddress(address__values: [\"10.110.0.2/24\",\"10.110.0.3/24\"]) { edges { node { address { value } interface { node { display_label ... on InterfaceVirtual { device { node { display_label } } } } } } } } }"}'
```

Expect each address to resolve through `interface` to a `Vlan110` on the matching
`leaf-nfd41-pod1-1-*`. Before the change, `interface` is `null` for both — that null is the
defect.

## 4. Prove the derivation is unambiguous (SC-005, contract C2)

For each leaf, exactly one address inside `10.110.0.0/24`, and it equals the session's declared
`peer_address`:

```bash
curl -s -X POST "$INFRAHUB_ADDRESS/graphql/svi-model" \
  -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"query { ClusterFabricPeering { edges { node { name { value } peer_address { node { address { value } } } peer_device { node { display_label ... on DcimDevice { interfaces { edges { node { __typename ... on InterfaceVirtual { name { value } ip_addresses { edges { node { address { value } } } } } } } } } } } } } } }"}'
```

## 5. Prove the VARP gateway is not a candidate (SC-004)

`10.110.0.1` is present on both leaves in intent, so it can never identify one peer. It must be
attached to no interface:

```bash
curl -s -X POST "$INFRAHUB_ADDRESS/graphql/svi-model" \
  -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H 'Content-Type: application/json' \
  -d '{"query":"query { IpamIPAddress(address__value: \"10.110.0.1/24\") { count } }"}'
```

## 6. Prove nothing that reaches the cluster moved (SC-006)

```bash
uv run infrahubctl transform crossplane_fabric_peering name=nfd41-fabric-peering \
  --branch svi-model > /tmp/svi-after.yaml
diff /tmp/svi-baseline.yaml /tmp/svi-after.yaml && echo "BYTE-IDENTICAL"
```

Also re-render one affected leaf's AVD config, which the declared oracle does not cover but which
the new interfaces sit closest to:

```bash
uv run infrahubctl transform avd_eos_config device=leaf-nfd41-pod1-1-1 --branch svi-model
```

## 7. Prove the load is idempotent (SC-007)

```bash
uv run infrahubctl object load objects/ --branch svi-model
uv run infrahubctl object load objects/ --branch svi-model
```

Then re-count the SVIs — still 2 — and re-run step 6.

## 8. Quality gates

```bash
uv run pytest tests/unit
uv run invoke lint-ruff lint-yaml lint-mypy lint-markdown
uv run invoke lint-prose      # known baseline: 7 errors / 4 warnings
```

## Cleanup

```bash
uv run infrahubctl branch delete svi-model
```
