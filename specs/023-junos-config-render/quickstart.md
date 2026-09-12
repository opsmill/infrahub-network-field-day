# Quickstart: Validating the Junos Render

**Feature**: `specs/023-junos-config-render` | **Date**: 2026-09-12

## Prerequisites

No cycle dependencies — cycle 010's security model is merged and seeded.

```bash
uv sync --all-packages
uv run infrahubctl info                     # Connection Status must be ✅
export INFRAHUB_API_TOKEN="$INFRAHUB_INITIAL_ADMIN_TOKEN"
export INFRAHUB_ADDRESS="${INFRAHUB_ADDRESS:-$(uv run infrahubctl info | awk '/Address/{print $2}')}"

uv run infrahubctl branch create fw-render --sync-with-git
uv run infrahubctl schema load schemas --branch fw-render
uv run infrahubctl object load objects/ --branch fw-render
```

## 1. The seed is a transcription — check this first

Nothing downstream is meaningful until the data matches the oracle. This is US1's gate and needs
no server:

```bash
uv run pytest tests/unit/test_junos_seed_data.py -v
```

It compares every rule's source addresses, destination addresses and applications, and every
interface's description and MTU, against `../lab/configs/fw/vsrx/junos.conf` **in both
directions** — an invented value fails as loudly as a missing one.

Then confirm the load is idempotent, by counting rather than by reading the log:

```bash
uv run infrahubctl object load objects/ --branch fw-render   # twice
```

`infrahubctl` prints "Created node" for an upsert, so the log is not evidence. Compare the object
counts before and after the second run.

## 2. Offline — the golden-file test

```bash
uv run pytest tests/unit/test_junos_config.py -v
```

The gate. Renders from a captured fixture and compares for equality against the in-scope stanzas
of `../lab/configs/fw/vsrx/junos.conf`. Needs no server.

## 3. Render it

```bash
uv run infrahubctl transform junos_config device=fw1 --branch fw-render > /tmp/fw1.conf
```

Then diff against the in-scope portion of the golden file:

```bash
python3 - <<'PY'
import re
gold = open('../lab/configs/fw/vsrx/junos.conf').read().splitlines()
# keep only the interfaces and security stanzas, dropping the unmodelled flow block
keep, depth, stanza = [], 0, None
for line in gold:
    m = re.match(r'^([a-z-]+) \{', line)
    if m: stanza = m.group(1)
    if stanza in ('interfaces', 'security'): keep.append(line)
    if line == '}': stanza = None
print('\n'.join(keep))
PY
```

Expect a difference only in the provenance line and the `flow` block.

**Failure modes worth recognising:**

| Symptom | Cause |
| --- | --- |
| `UndefinedError: 'dict object' has no attribute 'X'` | a context gap — `StrictUndefined` doing its job; the message names the template line |
| `Cannot query field 'prefix' on type 'SecurityIPAMIPPrefix'` | the value field differs per concrete kind — it is `ip_prefix` there |
| A typed field is `None` that should not be | the inline fragment names a generic instead of the concrete kind; the model fell back silently |
| One extra address-book line | `any` is being rendered; it is a Junos keyword and must only ever be referenced |
| `application [ junos-http ]` with one member | the bracket form is for several; one member is bare |
| Policies correct but in the wrong order | rules must be sorted by `index` within each zone pair |

## 4. The counts

```bash
grep -cE "^        security-zone " /tmp/fw1.conf          # 6
grep -cE "^                address [a-z]" /tmp/fw1.conf    # 13, not 14
grep -cE "^                address-set " /tmp/fw1.conf     # 4
grep -cE "^        from-zone " /tmp/fw1.conf               # 11
grep -cE "^            policy " /tmp/fw1.conf              # 19
grep -c "deny-spoofed-infra" /tmp/fw1.conf                 # 6
```

## 5. No credentials, anywhere

The check that matters most, and the one worth running by hand as well as in the suite:

```bash
grep -icE "encrypted-password|ssh-rsa|ssh-ed25519|BEGIN [A-Z ]*PRIVATE KEY" /tmp/fw1.conf
```

Must be `0`. Then confirm the model never acquired them either:

```bash
grep -ri "encrypted-password" objects/ schemas/ transforms/ | grep -v "specs/"
```

Also empty. The requirement is about the graph, not only the artifact — an artifact can be
diffed, a graph is harder to audit.

## 6. It would actually load

```bash
python3 -c "
s=open('/tmp/fw1.conf').read()
d=0; bad=0
for ch in s:
    if ch=='{': d+=1
    elif ch=='}':
        d-=1
        if d<0: bad=1
print('brace depth at EOF:', d, '| never negative:', not bad)
print('ends with newline:', s.endswith(chr(10)))
"
```

Depth must return to `0`, never go negative, and the file must end with a newline.

## 7. One artifact, for one firewall

```bash
curl -s -H "X-INFRAHUB-KEY: $INFRAHUB_API_TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"query { CoreStandardGroup(name__value: \"junos_firewalls\") { edges { node { members { count edges { node { display_label } } } } } } }"}' \
  "$INFRAHUB_ADDRESS/graphql/fw-render" | python3 -m json.tool
```

One member, `fw1`.

## 8. Gates

```bash
uv run invoke test
uv run invoke lint
```

## 9. SC-010 — what is not covered, and does it add up?

The criterion is arithmetic, not prose:

```bash
python3 - <<'PY'
import re
lines = open('../lab/configs/fw/vsrx/junos.conf').read().splitlines()
spans, cur = {}, None
for i, l in enumerate(lines, 1):
    m = re.match(r'^([a-z-]+) \{', l)
    if m: cur, start = m.group(1), i
    if l == '}' and cur: spans[cur] = i - start + 1; cur = None
flow = 7
inscope = spans['interfaces'] + spans['security'] - flow
out = len(lines) - inscope
print(f"in scope {inscope} | out {out}")
print(f"out = system {spans['system']} + routing-options {spans['routing-options']}"
      f" + flow {flow} + outside {out - spans['system'] - spans['routing-options'] - flow}")
PY
```

Expect `in scope 573 | out 104`, and the breakdown to sum to 104. If it does not, either the lab
file changed or the render's scope drifted — both worth knowing.

## Rollback

```bash
git checkout transforms/ objects/00_groups.yml .infrahub.yml
uv run infrahubctl branch delete fw-render
```

Nothing outside the repository and the throwaway branch is touched; no device is configured.
