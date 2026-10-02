---
title: Services expand on their branch by event rule
description: How triggers.yml fires each service generator on its branch, and why the loop terminates.
audience: developer
sidebar_position: 32
---

# Services expand on their branch by event rule

`triggers.yml` fires each service generator on `created`, scoped to
`other_branches`. Until that existed a service was expanded only because the PORTAL
asked for it, so one created any other way — the API, a human in the UI — sat unbuilt, and the branch diff showed a request with none of its consequences.
That reads as "nothing happened" rather than "not built yet".

**The point is that the proposed change carries the outcome before anyone merges it.** The
alternative is `execute_after_merge`, where the technical objects and the rendered configuration
appear only once the decision has already been taken — which hides exactly what the review is
for.

**`ServiceAppAccess` is just another service kind now.** It had a second rule watching `approved`,
because nothing was composed until someone flipped that field. The field is gone, so the grant
builds on creation like the rest: the reviewer sees the rule, the service objects and the
re-rendered Junos artifact in the proposed change, and merging it is the approval.

That last part only works because `generate-app-access` asks for the artifact to be re-rendered
**on its own branch**. Without that the proposed change shows new firewall objects against an
unchanged configuration, which is worse than showing nothing.

**Every service kind with a generator also fires on `updated`.** `created` alone covers
requesting a service and not withdrawing one: `status` is how every kind in the table above is
withdrawn, and for a long time nothing watched it, so setting `decommissioning` through the UI or
the portal fired no generator and the branch diff showed a status change with none of its
consequences — the same failure the `created` rules exist to prevent, reached from the other end.
`ServiceAppAccess` got its rules first; `ServiceNetworkSegment`, `ServiceFabricApp`,
`ServiceTenantOnboarding`, `ServiceServerPlacement` and `ServiceFabricPeering` followed, and
withdrawing any of them no longer needs `infrahubctl generator` by hand. The WAN kinds have no
generator and need none: `srl_config` reads their status at render time.

**The rules are scoped to the INPUTS, one per field, rather than a bare `updated`.** Each
generator writes back to its own target — a status, plus a record of what it built — so an
unscoped rule fires on the generator's own output. The records are deliberately unwatched for
exactly that reason: `granted_rules`/`granted_source_prefixes`, `subnet`/`vlan`/`svi`,
`vip_block`/`vip_block_managed`, `evpn_tenant`/`mac_vrf_vni_base`, `server`, `peerings`. So are
fields another generator writes: `ServiceFabricApp.allowed_source_prefixes` belongs to
`generate-app-access`, and a rule on it would run `generate-fabric-app` on every grant.
`tests/unit/test_service_trigger_contract.py` pins the watched set per kind, asserts none of it
is a write-back, and asserts each watched field is selected by the generator's own query.

**It terminates because every write-back is guarded, not because the trigger is clever.**
Every `_set_status` returns before saving when the status already matches, and every record step
(`_link_granted_rules`, `_link_to_service`, and each generator's `_record`) saves only when what
it records changed, so the run after a build or a withdrawal emits no event. Measured on a
branch, counting `action-run-generator` runs: a create costs two (the build, then one no-op
fired by `provisioning → active`) and so does a decommission (`decommissioning → decommissioned`)
for segments, applications, onboardings and placements; an edit to a field the generator does
not write back to costs one, and so does decommissioning a peering, whose generator writes no
status at all. Anything that removes a guard turns this into a loop, which is why they are
load bearing rather than tidy.

**Two runs of one withdrawal at once is normal, so a withdrawal must tolerate its twin.** The
portal's Revoke template sets `status` — which fires the `updated` rule — and then its
`infrahub:generators:await` step runs `generate-app-access` again. Both read the same rule, both
delete it, and the loser was refused `Unable to find the node ... SecurityPolicyRule`, failing the
template at its wait step after the winner had withdrawn everything. Measured: two Revoke runs in
three. `_delete_if_present` treats "already gone" as done; any other refusal still fails the run.
Infrahub runs generators from the repository's `main`, so the template keeps failing until that
reaches it.

**Deleting a service object leaves its `CoreGeneratorInstance` behind, and that breaks the
generator for everyone.** Infrahub's `request_generator_definition_run` reads every instance's
`object.peer.id`, and on one whose object is gone raises `Node must have at least one identifier
(ID or HFID) to query it` — so the generator's validator is red on every proposed change, the
unrelated ones included, and Infrahub refuses to merge them. Measured: deleting one
decommissioned grant on `main` did exactly that. Delete the instance, and the generator's empty
tracking `CoreGeneratorGroup` (description `name: <service>`), with the object.
`scripts/demo_rehearsal.py` does, and its preflight looks for a dangling instance.

**A generator that refuses must not record `error` from a withdrawn state.** `error` is not a
withdrawn status, so the status rule's next run takes the BUILD path. Measured with a VRF still
on the tenant: decommissioning an onboarding ran three times and ended `active` with the EVPN
tenant intact — a refused withdrawal silently reverted into a live service. The refusal now raises
and leaves the status at `decommissioning`, which is true (asked for, not done) and fires
nothing.
