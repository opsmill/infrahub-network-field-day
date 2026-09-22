# Otter-net service portal

A Backstage portal over Infrahub, and an alternative front end to this demo's
Streamlit app. The catalog is Infrahub's data rather than a copy of it, and a
request submitted here opens a branch and a proposed change.

Run it from the repository root:

```sh
invoke backstage-install   # once, installs Node dependencies
invoke backstage           # dev server on http://localhost:3001
invoke backstage-test
```

## The catalogue items

Most templates are **generated**: `provider.ts` emits one per Infrahub service
kind, derived from the schema, so they cannot drift from it.

`catalog/exposed-app-with-access.yaml` is the exception — the two-for-one. It
creates an exposed application *and* the access grant that opens the way to it,
on one branch, under one proposed change. It is hand-written because nothing in
the generated path can emit a two-kind template.

Three things about it are deliberate and each looks like an oversight:

- **It waits between the two creates.** `generate-app-access` reads the
  application's `vip_block`, which `generate-fabric-app` allocates. Both fire on
  `created` through independent rules and nothing sequences them, so a grant
  created beside its application races the allocation — and losing is permanent:
  the generator raises, stamps the grant `error`, and never runs again.
  `infrahub:generators:await` is the barrier.
- **Everything the grant's generator reads is in the grant's create mutation**,
  never a follow-up update step, for the same reason: the generator fires on
  creation, so a source set afterwards arrives too late.
- **`exposed` is pinned true and the ports are required.** An unexposed
  application never gets a VIP, and a grant whose application advertises nothing
  is refused rather than guessed at.
- **It regenerates the fabric before opening the proposed change.** The grant writes a
  `permit <vip>` sequence into the border leaf's `avd_custom_hostvars`, and
  `generate-avd-device-hostvar` runs on no trigger, so without this the change shows a JSON
  blob and no configuration. Two `CoreGeneratorDefinitionRun` calls with `nodes` omitted and
  `wait_until_completion: true` cover all seven switches; the artifacts then render in the
  proposed change's own checks, because no GraphQL mutation can ask for an artifact.

Adding another hand-written item means three edits, not one: the file,
`catalog.locations` in **both** `app-config.yaml` and `app-config.docker.yaml`
(the docker one *replaces* the dev list and is what the lab reads), and a
`COPY` in `packages/backend/Dockerfile`, which copies only named paths.
`tests/unit/test_combined_app_template_contract.py` asserts all three, plus the
template's fields against the schema it was written from.

Rebuild with `invoke backstage-build`, never a bare `docker compose build` —
the bundle is compiled on the host and the image only unpacks it.
