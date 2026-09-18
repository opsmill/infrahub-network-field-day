# OTTERNET golden configuration

The EOS configuration the OTTERNET fabric renders to, and the reference both parity
tests compare against. Where it comes from matters, so:

It is **not** Infrahub output — that would make the tests circular. It is
rendered from the OTTERNET lab's own Ansible `group_vars`, which are the design's
source of truth and which reproduce the deployed switch configurations byte for
byte.

The one transformation applied is the hostnames. The lab's containerlab nodes are
called `spine1` / `k8s-leaf1`; Infrahub's pod and rack generators name devices
`spine-{pod}-{index}` / `leaf-{pod}-{rack_index}-{index}`. Rather than teach the
generators the lab's names, the lab is redeployed under the generated ones.

Regenerate with:

```bash
uv run python scripts/regenerate_otternet_golden.py --lab <otternet-lab>          # check
uv run python scripts/regenerate_otternet_golden.py --lab <otternet-lab> --write  # update
```

That script *proves* the rename is cosmetic: it substitutes the new names back
out of each rendered config and asserts the result equals the deployed
configuration exactly. If a PyAVD upgrade or a lab design change introduces a
real difference it fails and says where, rather than quietly baking the change
into the reference the tests trust.

## What compares against this

- `tests/unit/test_otternet_golden_config.py` — renders the generator's host_vars
  through PyAVD. About a second, no containers. This is the one that catches a
  PyAVD version bump.
- `tests/integration/test_otternet_fabric.py` — boots a real Infrahub stack, runs
  the generator chain, and renders the artifacts the pipeline actually produces.
  This is the one that catches a data-model or generator regression.

## Two things these files pin

- **PyAVD version.** The lab renders with PyAVD 6.4, which is why this fork pins
  `pyavd>=6.4.0,<6.5.0`. 6.3 rejects two keys the lab uses
  (`ntp_settings.set_first_ntp_server_as_preferred`, and `logging_settings`
  without `hosts`), so it cannot reproduce these files at all.
- **The BGP type-7 ciphertext.** Type 7 is keyed by the peer-group name, so the
  hashes here are only valid for AVD's default peer-group names.
