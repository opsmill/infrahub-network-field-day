---
title: Deployment state and the one rule about it
description: The DeploymentState kinds, the rule that nothing may generate from them, and why each property is deliberate.
audience: developer
sidebar_position: 33
---

# Deployment state and the one rule about it

`DeploymentState` and `DeploymentDiffFile` (`schemas/deployment.yml`) record whether each
device matches the configuration Infrahub renders for it. **Nothing may generate from them:
no generator input, no artifact target, no trigger source.** Writing state onto a device
emits an event, `triggers.yml` turns node events into generator runs, a generator run
regenerates artifacts, and a moved artifact is what the reconciler acts on — so a trigger on
a deployment kind closes a loop that currently stays open only because nothing happens to
watch these kinds. `tests/unit/test_deployment_schema_contract.py` fails, naming the rule,
when someone adds one.

Three properties of that file are deliberate and each looks like an oversight:

- **No `on_delete`.** Its only value, `cascade`, deletes the *peer* when the node is deleted,
  so on `DeploymentState.device` it would mean deleting a deployment record deletes the
  switch. `infrahubctl schema check` accepts the line without complaint.
- **`device` is optional, and identity lives on a copied `name` attribute instead.** An
  `human_friendly_id` or uniqueness constraint over a relationship requires that relationship
  to be mandatory, and a mandatory `device` makes any device that has ever held a record
  permanently undeletable — Infrahub keeps refusing the delete *after* the record is gone,
  naming a record that no longer exists. The reconciler owns `name`, refreshing it from the
  device, and sweeps records whose device no longer resolves.
- **Both kinds are `branch: agnostic`.** Deployment state is a fact about the physical world,
  not about a branch: modelled branch-aware, a branch cut on Monday and merged on Friday
  would carry Monday's deployment state into `main`, and every proposed change would display
  deployment records as proposed intent.
