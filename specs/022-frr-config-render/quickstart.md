# Quickstart: Validating the FRR Render

**Feature**: `specs/022-frr-config-render` | **Date**: 2026-09-11

## Prerequisites

Cycle 021's object data must be committed and loaded — this cycle renders from it.

```bash
uv sync --all-packages
uv run infrahubctl info                     # Connection Status must be ✅
export INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_ADMIN_TOKEN"
export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-$(uv run infrahubctl info | awk '/Address/{print $2}')}"

uv run infrahubctl branch create wan-render --sync-with-git
uv run infrahubctl schema load schemas --branch wan-render
uv run infrahubctl object load objects/ --branch wan-render
```

## 1. Offline first — the golden-file tests

```bash
uv run pytest tests/unit/test_frr_config.py -v
```

This is the gate. Six devices, each compared for equality against
`../lab/wan/rendered/<device>/frr.conf`. It needs no server, because the fixtures are captured
graph responses.

## 2. Render one device by hand

```bash
uv run infrahubctl transform frr_config device=cust-acme-ce --branch wan-render
```

Then the one that matters:

```bash
uv run infrahubctl transform frr_config device=isp-pe1 --branch wan-render \
  > /tmp/isp-pe1.rendered
diff <(grep -v 'Rendered by' ../lab/wan/rendered/isp-pe1/frr.conf) \
     <(grep -v 'Rendered by' /tmp/isp-pe1.rendered) && echo "ZERO DIFF"
```

Phase 0 already got this to zero diff from live data with the lab's template, so a diff here
means the transform's context assembly differs from the probe's — not that the data is missing.

## 3. All six

```bash
for d in isp-pe1 isp-pe2 internet-rtr cust-acme-ce cust-globex-ce branch-rtr; do
  uv run infrahubctl transform frr_config device=$d --branch wan-render > /tmp/$d.frr
  if diff -q <(grep -v 'Rendered by' ../lab/wan/rendered/$d/frr.conf) \
             <(grep -v 'Rendered by' /tmp/$d.frr) >/dev/null; then
    echo "  ZERO DIFF  $d"
  else
    echo "  DIFF       $d"; diff <(grep -v 'Rendered by' ../lab/wan/rendered/$d/frr.conf) \
                                 <(grep -v 'Rendered by' /tmp/$d.frr) | head -20
  fi
done
```

All six must say ZERO DIFF. 448 lines of golden output, whitespace and comments included.

**Failure modes worth recognising:**

| Symptom | Cause |
| --- | --- |
| `UndefinedError: 'dict object' has no attribute 'X'` | a context gap — `StrictUndefined` doing its job. The message names the template line |
| `Cannot query field 'ip_addresses' on type 'DcimInterface'` | missing inline fragment, interface → address |
| `Cannot query field 'name' on type 'InterfaceLayer3'` | missing inline fragment, address → interface |
| Only the site-inventory comment block differs | site ordering — BGP before static, each by name |
| Whole file off by trailing whitespace | `trim_blocks` / `lstrip_blocks` / `keep_trailing_newline` not all set |

## 4. The artifact definition generates six, not seven

```bash
uv run infrahubctl object load objects/00_groups.yml --branch wan-render
```

Then check the group and the artifacts:

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { CoreStandardGroup(name__value: \"frr_routers\") { edges { node { members { count edges { node { display_label } } } } } } }"}' \
  "$INFRAHUB_ADDRESS/graphql/wan-render" | python3 -m json.tool
```

Six members. `cust-acme-dr-ce` must **not** be one — it shares the `customer_edge` role but the
lab renders no FRR config for it.

## 5. The service layer is visible — SC-003

The demonstration this whole chain was built for. On a throwaway branch, delete acme's
internet-access service and re-render:

```bash
uv run infrahubctl branch create no-internet --sync-with-git
# delete ServiceInternetAccess 'acme-internet' on that branch via the UI or the API
uv run infrahubctl transform frr_config device=isp-pe1 --branch no-internet > /tmp/pe1-without.frr
diff /tmp/isp-pe1.frr /tmp/pe1-without.frr
```

Expect exactly the six-line change SC-003 names — the four-line `permit 30` clause gone, and the
tenant header re-rendered from `internet: yes` to `internet: no`. Nothing else moves.

That diff is the point: one service object, removed, and a real device's routing policy and its
human-readable summary both change.

## 6. Gates

```bash
uv run invoke test
uv run invoke lint
```

## 7. SC-009 — is the lab's renderer redundant?

Answered by a person, not a command. For each of the six devices, every line of
`../lab/wan/rendered/<device>/frr.conf` is now produced from Infrahub. Then ask what
`../lab/wan/tenants.yml` still holds that the graph does not:

```bash
grep -nE "^[a-z_]+:|^  [a-z_]+:" ../lab/wan/tenants.yml | head -40
```

Expected answer: the host entries and the branch's bridged access ports, both deliberately out
of scope (cycle 021, assumptions 2 and 3), and `mtu`, which is on every interface. Everything
that drives a routing decision is in the graph.

If that holds, the lab could delete `render.py`, `templates/` and `tenants.yml` and lose
nothing — which is what SC-009 asserts and what "contain all of the information that is in the
lab" meant for the WAN.

## Rollback

```bash
git checkout transforms/ objects/00_groups.yml .infrahub.yml
uv run infrahubctl branch delete wan-render
uv run infrahubctl branch delete no-internet
```

Nothing outside the repository and the throwaway branches is touched; no device is configured.
