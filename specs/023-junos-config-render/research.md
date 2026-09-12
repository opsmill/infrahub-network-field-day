# Phase 0 Research: Junos Configuration for the Perimeter Firewall

**Feature**: `023-junos-config-render` | **Date**: 2026-09-12

The question worth answering in Phase 0 was whether the model, seeded by cycle 010 and never
read since, actually holds the 573 lines this cycle must produce. It does, and the hardest part
of it — the eleven zone pairs with their evaluation order — was verified against the live graph
rather than reasoned about.

One finding overturned the specification's central argument, which is recorded here in full
because the corrected version is less flattering than the original.

## R1 — The model reproduces the zone pairs and their ordering exactly

**Decision**: group rules into zone pairs from `source_zone` and `destination_zone`; order within
a pair by `index`.

**Evidence**: every rule was queried from the live graph, grouped, and compared to the golden
file's own grouping and order:

```text
model:  19 rules across 11 zone pairs
golden: 19 rules across 11 zone pairs

OK  app-prod    ->k8s-prod      ['deny-spoofed-infra', 'app-to-k8s-services', 'app-to-k8s-icmp']
OK  k8s-prod    ->app-prod      ['deny-spoofed-infra', 'k8s-to-app']
OK  wan         ->k8s-prod      ['deny-spoofed-infra', 'wan-to-k8s-services']
OK  branch      ->k8s-prod      ['deny-spoofed-infra', 'branch-to-access-portal', 'branch-to-k8s-icmp']
OK  wan         ->acme-cloud    ['deny-spoofed-infra', 'acme-sites-to-acme-cloud']
OK  wan         ->globex-cloud  ['deny-spoofed-infra', 'globex-sites-to-globex-cloud']
OK  acme-cloud  ->wan           ['acme-cloud-to-acme-sites']
OK  globex-cloud->wan           ['globex-cloud-to-globex-sites']
OK  wan         ->app-prod      ['deny-wan-to-app']
OK  wan         ->branch        ['deny-wan-to-branch']
OK  branch      ->wan           ['deny-branch-to-wan']
```

Eleven for eleven, nineteen for nineteen, order matching in every pair. This is the riskiest
thing in the cycle — Junos evaluates first-match within a pair, so a wrong order produces a
configuration that loads cleanly and enforces something different — and it is settled before
implementation starts.

`index` is `10` for every anti-spoofing rule and higher for what follows, so ordering is a plain
sort rather than an inference.

## R2 — WITHDRAWN: the render does not remove the copy-paste

**The specification's original argument was wrong.** It claimed `deny-spoofed-infra` would be
"stored once and emitted six times", turning six hand-written copies into one. That is not what
the model holds and not what the schema permits.

**Evidence**: the six rules are six distinct objects with six distinct ids:

```text
deny-spoofed-infra objects in the model: 6   (distinct ids: 6)
  idx 10 app-prod    ->k8s-prod      src=['fabric-infra'] deny log
  idx 10 branch      ->k8s-prod      src=['fabric-infra'] deny log
  idx 10 k8s-prod    ->app-prod      src=['fabric-infra'] deny log
  idx 10 wan         ->acme-cloud    src=['fabric-infra'] deny log
  idx 10 wan         ->globex-cloud  src=['fabric-infra'] deny log
  idx 10 wan         ->k8s-prod      src=['fabric-infra'] deny log
```

**And it is structural, not a seeding choice**:

```text
source_zone:      cardinality one, optional False
destination_zone: cardinality one, optional False
uniqueness:       [index, source_zone, destination_zone, policy]
```

A `SecurityPolicyRule` belongs to exactly one zone pair by construction. The kind comes from
`infrahub/security` 1.0.2, which `schemas/MARKETPLACE.md` keeps byte-identical and forbids
hand-editing, so the cardinality is not this repository's to change.

**What the cycle actually delivers**, stated without the overclaim: the six copies stop being
text in a 677-line file and become objects in a graph — queryable, diffable, and changeable
together. That is 010's assumption 8, and it stands on its own.

**Follow-ups this suggests**, neither of them a renderer:

- *A check* asserting the six `deny-spoofed-infra` rules stay byte-identical. This is the direct
  remedy for "a change applies to five pairs and misses the sixth", and it is small.
- *A generator* materialising the six from one intent object, which is 010's FR-081 territory
  and the only way to genuinely remove the repetition without touching an adopted schema.

## R3 — The rule model carries everything a policy statement needs

**Decision**: no schema change, and no object data beyond the target group.

`SecurityPolicyRule` holds `name`, `index`, `action`, `log`, `managed_by_service`, plus
cardinality-many `source_address`, `destination_address`, `source_services` and
`destination_services`, and cardinality-one `source_zone`, `destination_zone` and `policy`.

That is a one-to-one match with a Junos policy statement: `match { source-address …
destination-address … application … }` and `then { deny|permit; log { … } }`.

The address and service relationships peer with **generics** — `SecurityGenericAddress` and
`SecurityGenericService` — which is what makes the address book polymorphic. The query will need
inline fragments on the concrete kinds, and cycle 022 established that the fragment must name
the kind the server actually returns, not an intermediate generic, or the generated Pydantic
model silently falls back to a variant missing the fields.

## R4 — The counts, measured

The specification's line accounting was wrong on its first pass and is recorded corrected:

```text
file total          677
system               13   credentials — permanent exclusion
interfaces           76   IN SCOPE
routing-options      12   needs a device-level static route, so a schema cycle first
security            504   IN SCOPE, less the 7-line `flow` block which nothing models
outside any stanza   72   blank lines and file-level comments

IN SCOPE  = 76 + 504 - 7 = 573
OUT       = 13 + 12 + 7 + 72 = 104
```

The original draft said 580 in and 97 out, and separately excluded a `flow` block it had already
counted inside the in-scope `security` stanza. This is the fourth cycle in a row where a counted
claim was wrong until measured, which is why SC-010 requires the enumeration to total rather than
merely to exist.

## R5 — The credentials, and why the requirement is about the model rather than the output

`system { root-authentication }` and `system { login }` hold two `encrypted-password` hashes.

The requirement (FR-015, FR-043, SC-005) is deliberately stronger than "the artifact must not
contain them": **the model must never acquire them and the query must never ask.** An artifact
can be read and diffed; a graph is harder to audit, and a credential that reaches it has reached
every branch, every export and every backup of it.

This is the one exclusion in the Out of Scope list that is permanent rather than deferred.

## R6 — This cycle has no templates to inherit, and that is the standing risk

Cycle 022 was a port: five known-correct Jinja2 templates fed from Infrahub and diffed, with
three of six devices already rendering zero-diff before implementation began.

`junos.conf` is hand-written and pushed as-is. There are no templates, so they are authored
against the golden file with no prior art and no "the lab already proved this renders" safety
net. Phase 0 can establish that the *data* suffices — it does — but not that the *render* is
faithful. Expect iteration against the diff, and expect the first failures to be Junos syntax
rather than missing data.

The specific traps the file shows:

- **List bracket form.** `application junos-http;` for one, `application [ junos-http junos-https ];`
  for several. Wrong on the multi path is a syntax error; wrong on the single path renders
  something Junos accepts with different meaning.
- **Address groups have the same problem**, with the same two forms.
- **Junos comments** `/* … */` appear in the file and carry intent. Cycle 022 kept the FRR
  comments and it cost nothing; the same applies here.

## Open risks carried to implementation

1. **The render is unproven.** R1 proves the data and the ordering; nothing yet proves a
   generated brace tree matches the golden file. This is the whole of the implementation risk.
2. **Polymorphic address and service references** need inline fragments on concrete kinds, and
   cycle 022 showed the failure is silent when the fragment names a generic instead.
3. **The artifact is not a complete `junos.conf`.** 104 lines are excluded, 12 of them only
   because a device-level static route has nowhere to live. SC-010 makes the gap explicit so a
   reader does not mistake the artifact for the whole file.
4. **The `any` exclusion is a one-line trap** (R8). It is the kind of difference that produces a
   single unexplained diff line and an hour of looking in the wrong place.

## R7 — `fw1` is a `SecurityFirewall`, and it can be an artifact target

**Decision**: the artifact targets `SecurityFirewall`, not `DcimDevice`.

The specification assumed `fw1` was a `DcimDevice` with role `edge_firewall`. It is not —
`DcimDevice(name__value: "fw1")` returns nothing. `objects/31_nfd41_offfabric_devices.yml`
declares it under `kind: SecurityFirewall`, in its own document above the `DcimDevice` block that
holds the routers.

This was worth checking rather than assuming, because it could have been a blocker. It is not:

```text
SecurityFirewall inherit_from:
  ['DcimGenericDevice', 'DcimPhysicalDevice', 'CoreArtifactTarget', 'SecurityPolicyAssignment']
```

`CoreArtifactTarget` is there, so the kind can carry artifacts with no schema change — which
matters, because `security/security.yml` is marketplace-adopted and could not have been changed
to add it.

It also makes the query simpler than planned: `SecurityPolicy.device_target` resolves to the
firewall, so the policy is reachable from the device rather than needing to be looked up
separately.

## R8 — `any` is in the model but must not be in the address book

**Decision**: exclude the address named `any` when rendering the address book; still emit it
where a rule references it.

Comparing every modelled address against the golden file, by name and by value:

```text
model 14 | golden 13
IN MODEL ONLY : {'any': '0.0.0.0/0'}
IN CONFIG ONLY: none
VALUE MISMATCH: none
```

Thirteen for thirteen with no value drift — and one extra. `any` is Junos' built-in keyword. A
rule says `destination-address any;` and the address book never defines it; defining it would be
both redundant and wrong.

The model holds it as an object because a rule's `destination_address` relationship needs
something to point at. So the render needs one rule the golden file cannot teach it: **`any` is
referenced, never defined.**

Left undiscovered, this produces a single unexplained line in the address-book diff.

## R9 — BLOCKING: the seeded data does not transcribe `junos.conf`

**Found during implementation, after the query and fixture were built. Implementation stopped at
T011; the cycle was then re-scoped to include the seed repair rather than defer it.**

Phase 0 checked that the model's *structure* matched the config, and that the rules' identity —
names, zone pairs, evaluation order — matched exactly. It did, and that remains true. What Phase
0 did not check was whether each rule's *contents* and each interface's *attributes* match the
file. They do not.

### The match blocks are partly unseeded

A first count overstated this, because the extractor did not handle Junos' bracket form
(`destination-address [ a b c ];`) and read those rules as empty. Re-counted with the bracket
form handled, the gap is smaller and precisely bounded:

```text
rules needing a fix, by field: {'source': 3, 'destination': 3, 'application': 14}
total: 20 field corrections across 15 of the 19 rules
```

**All six of the source and destination gaps are address-GROUP references**, and the pattern is
consistent: **all four groups are seeded, and not one is referenced by any rule.** The groups
exist as objects; nothing points at them. `acme-cloud-to-acme-sites` is the clearest case:

```text
golden:  source-address acme-cloud;  destination-address acme-sites;  application any;
model:   source_address [acme-cloud]  destination_address []          services []
```

### Every interface attribute differs

```text
ge-0/0/0  desc  'Zone k8s-prod, toward the border leaf' != 'ZONE-K8S-PROD handoff - border-leaf1 Et10'
ge-0/0/0  mtu   1514 != 9192
… the same for all six interfaces
```

The descriptions are paraphrases rather than transcriptions, and every MTU is the schema default
`1514` rather than the configured `9192`.

### What this means

Cycle 010 modelled the firewall's **structure** faithfully and seeded its **values**
approximately. The structure is right — 6 zones, 6 interfaces, 13 addresses, 4 groups, 11 zone
pairs, 19 rules, correct order — and the address book is exact, matching by name and value with
no drift. The gaps are in the rule contents and the interface attributes.

So SC-001 — byte-for-byte parity over 573 lines — is unreachable by a renderer alone. No template
can emit `destination-address acme-sites;` from an empty relationship.

**This is the same shape as the start of this chain.** Cycle 019 set out to render FRR, found the
addresses were prose in description fields, and correctly became a schema cycle followed by an
objects cycle and then the transform. The firewall needs the middle step it never had.

### Recommended re-scope

**The seed repair is now inside this cycle** (see plan.md, "Re-scope"). It corrects
`objects/32_nfd41_security.yml` against `../lab/configs/fw/vsrx/junos.conf` as the oracle:

- link the six missing address-**group** references — 3 source, 3 destination
- link the 14 missing applications, 11 of which are just `any`
- correct the six interface descriptions to the file's strings
- set the six interface MTUs to 9192
- add `any` as a service object; it is referenced by 11 rules and is the only named application
  the model lacks (`junos-http`, `junos-https` and `junos-ping` are all seeded)

**33 corrections in total** — 20 rule fields, 12 interface fields, 1 new object. No value is
invented; every one is transcribed from the oracle.

No schema change is needed: `SecurityPolicyRule.source_address` and `.destination_address` peer
with `SecurityGenericAddress`, and `SecurityAddressGroup` is one of its concrete kinds, so groups
are already linkable. `mtu` and `description` already exist on `SecurityFirewallInterface`.

**Then the transform**, in the same cycle. The query, generated types and fixture already built
serve it unchanged — they are correct, and they are what revealed the gap.

### What was salvaged

- `transforms/junos_config.gql` — accepted by the server, every address resolving a value, with
  the concrete-kind fragments the polymorphic address book and the firewall's interfaces both
  need.
- `transforms/junos_config_query.py` — generated from it.
- `tests/unit/fixtures/junos/fw1.json` — a captured response, verified credential-free.

A third fragment lesson was learned on the way: `SecurityFirewall.interfaces` peers with the
`DcimInterface` generic, so `security_zone` and `ip_addresses` need `... on
SecurityFirewallInterface`. That is the third distinct place in three cycles where a
relationship's declared peer is a generic and the fields wanted live on the concrete kind.

## R10 — CORRECTION: the group references were never missing

**R9's headline figure was wrong, and the error was mine twice over.**

R9 reported that "all four address groups are seeded and not one is referenced by any rule", and
counted six missing source/destination references among 20 rule-field corrections. Both claims
are false. All six group references were present in cycle 010's seed, on the correct fields, and
had been all along.

Two mistakes compounded to produce it:

1. **The first schema query filtered them out of view.** It listed `SecurityPolicyRule`'s
   relationships with `if not r['name'].endswith('groups')`, which excluded exactly
   `source_groups`, `destination_groups`, `source_service_groups` and
   `destination_service_groups`.
2. **The comparison then queried only `source_address` and `destination_address`.** Reading a
   subset of the relationships and concluding the data was absent is not a measurement; it is a
   restatement of the query.

The adopted schema separates them deliberately: `source_address` peers with
`SecurityGenericAddress`, `source_groups` with `SecurityGenericAddressGroup`, and
`SecurityAddressGroup` inherits the latter, not the former. A group **cannot** be referenced
through the address field. Cycle 010 had it right.

**Worse, I acted on the wrong conclusion before verifying it** — deleting 14 lines of correct
`source_groups`/`destination_groups` data on the grounds that they were "invalid fields the
schema does not have". They were restored from git.

### The actual repair, verified

```text
field gaps: {'application': 14} — and every one of the 14 is the same value, `any`
source:      0 gaps
destination: 0 gaps
```

| Correction | Count |
| --- | --- |
| Rule `application` links, all of them `any` | 14 |
| Interface descriptions | 6 |
| Interface MTUs (`1514` → `9192`) | 6 |
| New `SecurityService` `any` | 1 |
| **Total** | **27** |

Not 33, and not a rewrite. Cycle 010's seed was substantially faithful; what it lacked was the
application links and the device's own interface strings.

### Two real findings survive

- **`SecurityGenericService` declares no `human_friendly_id`**, so a service cannot be referenced
  by a scalar name. The inline concrete-kind form is required — the same shape cycle 021 found
  for `InterfaceLayer3`, and the reason cycle 010's existing service links use it. The inline
  block must also carry `port`, which is mandatory.
- **`infrahubctl object load` accepts an unknown field without complaint.** It is what would have
  made a genuine `source_groups` typo silent, and `test_no_rule_uses_a_field_the_schema_does_not_have`
  now guards it — with the allowed list taken from the schema rather than written from memory.

### Method note

Three counted claims in this cycle were wrong before they were right: the line accounting
(580/97 → 573/104), the rule-field gap (a broken bracket parser), and this one. The pattern is
the same each time — a measurement derived from an incomplete read, stated with more confidence
than it had earned. The tests written in US1 now pin all three.

## R11 — The address book's order is authoring order, and SC-001 needs a decision

**Found at the start of US2. It is a spec-level question, not an implementation choice, so
implementation paused rather than resolving it unilaterally.**

Junos writes the address book in a deliberate order — infrastructure addresses, then per-tenant
ones, then the sets:

```text
gold:  k8s-nodes k8s-pods k8s-services access-portal app-hosts fabric-infra
       wan-customers branch-users acme-hq acme-dr acme-cloud globex-hq globex-cloud
graph: k8s-nodes k8s-pods k8s-services app-hosts fabric-infra wan-customers
       branch-users acme-hq acme-dr acme-cloud globex-hq globex-cloud access-portal
```

`access-portal` sits fourth in the file and last in the graph, because it is a
`SecurityIPAMIPAddress` (a `/32`) while the rest are `SecurityIPAMIPPrefix`, and the query
returns each concrete kind as its own block.

**No rule reproduces the file's order.** Tested: not alphabetical, not by network address, not by
prefix length. It is the order someone wrote it in, and Infrahub stores no authoring order — the
same limitation cycle 022 hit with site ordering (R6), where a rule happened to exist. Here none
does.

**The address groups are fine**: the file's order is alphabetical, so `sorted()` reproduces it.

### Why this is a decision rather than a bug

Junos does not care. Address-book entries are name-keyed definitions and the order is cosmetic —
unlike policies within a zone pair, which are first-match and whose order the model *does* carry,
in `index`. So the rendered configuration would be **semantically identical and textually
different**, in one stanza, in a way that affects nothing on the device.

That collides with SC-001, which asks for byte-for-byte parity over 573 lines. Three ways out:

1. **Relax SC-001 for the address book**: compare that stanza as a set of statements plus brace
   structure rather than line for line, and keep byte-for-byte everywhere else — including
   policies, where order is semantic. Cheapest, and honest about what Junos actually reads.
2. **Add an ordering attribute** to the address kinds via `security_extensions.yml`. Restores
   full byte-for-byte parity and makes the order explicit data, but it is a schema change, which
   this cycle does not currently have, and it extends adopted marketplace kinds.
3. **Hardcode the order in the template.** Rejected: it violates SC-007 and puts thirteen names
   in a template where the graph should supply them.

Option 1 is the recommendation. Option 2 is defensible if byte-for-byte is the point.

### RESOLVED: option 2, an ordering attribute

The requester chose the ordering attribute, so **byte-for-byte parity stands** and this cycle
now spans three artifact types — schema, objects, transform.

`book_index` is added to **`SecurityGenericAddress`** in `schemas/security_extensions.yml`, not
to each of the six concrete address kinds: extending the generic propagates it to all of them,
which a `schema check` confirmed. It is `Number`, optional, and seeded in the file's order.

Verified against the live graph:

```text
rendered order: k8s-nodes k8s-pods k8s-services access-portal app-hosts fabric-infra
                wan-customers branch-users acme-hq acme-dr acme-cloud globex-hq globex-cloud
golden order:   (identical)
ORDER MATCHES
unindexed: ['any']
```

**An absent index is doing double duty**, and pleasingly so: `any` is the one address object with
no position in the rendered file, because Junos declares it in neither the address book nor the
applications stanza. So "has no `book_index`" *is* the rule for excluding it from the book —
FR-017 and this attribute turn out to be the same fact.

Why upstream does not model it: `SecurityPolicyRule.index` exists because policy order inside a
zone pair is first-match and therefore semantic. Address-book order is presentational, so the
marketplace schema has no reason to carry it. This repository does, because its acceptance test
is a diff against the device's own file.

Two things the change caught on the way:

- **`tests/unit/test_security_schema_contract.py` asserted that exactly two kinds were extended.**
  It failed, correctly, and was updated deliberately to three rather than loosened — with a
  second test pinning that `book_index` is optional and numeric.
- **`export-schema` reads Infrahub `main` and has no `--branch`**, so `generate-return-types`
  rejected the new attribute until the schema was loaded into `main` as well. The same trip-up as
  cycle 022.

## R12 — The policies stanza renders correctly; two presentational gaps remain

**Every non-comment line matches.** Compared as a multiset, the rendered `policies` stanza and
the device's are identical: all 19 rules, with the right source addresses, destination addresses,
address-group references, applications, actions and log events.

```text
non-comment lines as a multiset: identical = True
zone pairs: same set = True | same ORDER = False
comment lines: golden 71 | rendered 11 -> 60 missing
```

Two things remain, both presentational:

### 1. Zone-pair order is authoring order — the third occurrence

```text
golden:   app-prod->k8s-prod  k8s-prod->app-prod  wan->k8s-prod  branch->k8s-prod
          wan->acme-cloud  wan->globex-cloud  acme-cloud->wan  globex-cloud->wan
          wan->app-prod  wan->branch  branch->wan
rendered: alphabetical
```

No rule derives it — not by source zone, not by destination, not by the zones stanza's own
order, all of which were checked. As with the address book, it is the order someone wrote it in.

**Unlike the address book, there is no object to hang an index on.** Zone pairs are *derived*
from each rule's `source_zone` and `destination_zone`; they are not stored. An index would have
to go on every rule and be identical across each pair — denormalised, and a new way for the data
to contradict itself.

Junos is order-insensitive **between** pairs: it selects the pair by from-zone/to-zone and
evaluates only within it. Order **inside** a pair is first-match and therefore semantic, and that
the model already carries in `index` — and the render already reproduces it.

So the options differ from R11's:

1. **Relax SC-001 for zone-pair sequence**: assert the set of pairs and byte-for-byte equality
   within each, rather than the order between them. Nothing about the firewall's behaviour goes
   unchecked.
2. **A `pair_index` on every rule**, denormalised across each pair, with a test that the values
   agree. Restores full parity at the cost of a field that can disagree with itself.
3. Order pairs by their first rule's creation order. Rejected: not deterministic across reloads.

Option 1 is the recommendation here, where option 2 was right for the address book — because
there the index had a natural home on the address object, and here it does not.

### 2. Sixty comment lines

The policies stanza carries per-section commentary the other stanzas do not. Lifting it into the
template is mechanical, exactly as the three blocks already reproduced in `interfaces.j2`,
`address-book.j2` and `zones.j2`. It is work, not a decision.

### Also added this session: `log_session_close`

Upstream models `log` as a Boolean, and the device distinguishes two behaviours — every rule logs
`session-init`, and the eight long-lived permits also log `session-close`. The two ICMP permits do
not.

It could have been inferred ("permit, unless the application is `junos-ping`"), which would
reproduce the file today while encoding an unstated policy in the renderer. Which events a
firewall logs is behaviour rather than formatting, so it was modelled instead — a second
attribute on `SecurityPolicyRule` in `security_extensions.yml`, seeded on the eight rules that
have it.
