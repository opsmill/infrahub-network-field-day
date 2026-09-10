# NFD41 golden configuration

These are the EOS configurations the **deployed** NFD41 lab is running. They are
copied verbatim from `lab/avd/intended/configs/` in the NFD41 lab repository,
where Ansible + `arista.avd` renders them from static `group_vars` and
`make avd-deploy` pushes them to the running cEOS switches.

Two tests assert that the Infrahub data model produces these files byte for
byte. That is the whole point of the fork: the source of truth moves from static
YAML files into Infrahub without the configuration on the wire changing at all.

- `tests/unit/test_nfd41_golden_config.py` — renders the generator's host_vars
  through PyAVD. About a second, no containers. This is the one that catches a
  PyAVD version bump.
- `tests/integration/test_nfd41_fabric.py` — boots a real Infrahub stack, runs
  the generator chain, and renders the artifacts the pipeline actually produces.
  This is the one that catches a data-model or generator regression.

Regenerating them (only when the lab design itself changes):

```bash
cd <nfd41-lab>/lab && make avd-build
cp avd/intended/configs/*.cfg <this-repo>/tests/integration/golden/nfd41/
```

Two things they pin, beyond the obvious:

- **PyAVD version.** The lab renders with PyAVD 6.4, which is why this fork pins
  `pyavd>=6.4.0,<6.5.0`. 6.3 rejects two keys the lab uses
  (`ntp_settings.set_first_ntp_server_as_preferred`, and `logging_settings`
  without `hosts`), so it cannot reproduce these files.
- **The BGP type-7 ciphertext.** Type 7 is keyed by the peer-group name, so the
  hashes in these files are only valid for AVD's default peer-group names.
