# On-prem OIDC for the lab

Dex is the lab's identity provider and **Infrahub is the relying party**. Infrahub drives the
whole flow itself and mints its own token; nothing downstream ever sees a Dex token.

## One Dex, in the tooling cluster

`tooling/10-dex.yaml` is the whole identity provider. Its issuer is
`http://10.90.0.11:32556/dex`, and everything that trusts it — Infrahub and Backstage — names
that one URL.

**SSO is a branch-side flow.** `10.90.0.11` is reachable from the branch desktop through
WAN → border-leaf1 → fw1 → zone `tooling`, and from the Infrahub container over the host's
bridge. It is *not* reachable from an operator's own machine, which arrives over Tailscale and
has no route into `10.90.0.0/24`.

That boundary is deliberate. The people who sign in with SSO are end users at the branch, asking
for services as themselves; an operator signs in to Infrahub with the local `admin` account,
which sits on the same login page beside the SSO button and needs no identity provider at all.

A second Dex on the host was built to serve operators over Tailscale and then removed. Two
issuers is two identities for one person: the same `alice` would be a different Infrahub account
depending on which network she came in on, and the accounts could not be merged afterwards.
Having one directory is worth more than having SSO on every path into the lab.

**Before changing which address Dex publishes, test from every browser that has to reach it.**
An earlier consolidation was tested from the host, the Infrahub container and the branch desktop
— every party except a remote operator — and broke Infrahub login at the IdP redirect rather
than at Infrahub, so nothing in Infrahub's logs pointed at the cause.

Infrahub has **no `depends_on`** for its Dex. Dex is needed only when someone signs in, and
Infrahub was measured booting cleanly with its discovery URL unreachable: discovery is fetched on
first use, not at startup.

```text
browser ──▶ /api/oidc/provider1/authorize?final_url=…
              └─▶ Dex login ──▶ /auth/oidc/provider1/callback?code&state
                                  └─▶ UI calls /api/oidc/provider1/token
                                        └─▶ {access_token, refresh_token, final_url}
```

## Signing in

| User | Password |
| --- | --- |
| `alice@otternet.lab` | `password` |
| `bob@otternet.lab` | `password` |

These are **fake, committed, lab-only credentials**. A lab that cannot be rebuilt from its own
repository is not reproducible, which is why they are here rather than in someone's notes.

## The three things that make this work, each of which failed first

**The issuer must resolve identically from three places.** The Infrahub container fetches the
discovery document server-side, and the URLs *inside* it are followed by the browser — which may
be on this VM or on someone else's machine over Tailscale. `localhost` fails for the container,
`172.20.41.1` fails for a remote browser. The Tailscale name is the only address that satisfies
all three, and each was measured.

**The redirect URI is the UI route, not the API route.** The OpenAPI spec documents
`GET /api/oidc/{provider}/token`, which is what the frontend calls *after* the browser returns.
What Infrahub actually sends as `redirect_uri` is `/auth/oidc/{provider}/callback`. Dex names the
exact string it expected when this is wrong, so read its log rather than the API docs:

```text
failed to parse authorization request
err="Unregistered redirect_uri (\"http://…/auth/oidc/provider1/callback\")."
```

**`INFRAHUB_SECURITY_OIDC_PROVIDERS` is a JSON array.** It is a list field, so pydantic-settings
parses it as JSON, and a bare `provider1` makes the server refuse to boot with
`error parsing value for field "oidc_providers"` — naming the field but not the format. Refusing
to boot is the right failure; silently ignoring it would leave a login page with no SSO button
and nothing to explain why.

## What this does not yet do

The **service portal still authenticates as the admin token**, so a request it writes is
attributed to that service account rather than to the person who asked. `final_url` does not
carry the token: the UI keeps it and does a client-side redirect, so the portal cannot ride
Infrahub's flow. See the portal notes in `service_catalog/` for where that stands.

## Backstage

The service portal is [Backstage](../backstage/), and it is a **separate relying party** from
Infrahub rather than a client of it. Both trust the same Dex, so one identity signs in to each,
and each mints its own session.

| | |
| --- | --- |
| Portal | `https://10.90.0.11:32001`, from the branch desktop |
| Sign-in | the same `alice` / `bob` accounts |
| Resolves to | a catalog `User` entity, via `emailLocalPartMatchingUserEntityName` |

There is **no guest provider**. The upstream example this portal is based on ships one, and a
guest cannot be recorded as having asked for anything — which is the point of putting requests
behind a catalogue. `GET /api/catalog/entities` without credentials returns `401`.

### Three things that failed first

**`auth.session.secret` is required.** The openid-client passport strategy keeps its state and
nonce in an express session, and the auth router only installs `express-session` when that key is
set. Without it every sign-in fails with `Authentication failed, authentication requires session
support` — a 500 from `/api/auth/oidc/start` naming neither the setting nor the provider.

**`ApiBlueprint.make` needs the callback form.** `params: defineParams => defineParams(...)`
rather than `params: <factory>`. The type error says so in full, which is the only reason it took
one attempt rather than several.

**There is no `oidcAuthApiRef` in Backstage.** `@backstage/core-plugin-api` ships refs for
GitHub, Google, Okta and the rest; a *generic* OIDC provider has none, and you build it from
`OAuth2.create()` against the provider id in `app-config.yaml`. See
`backstage/packages/app/src/modules/auth/`.

### A known Infrahub bug this runs into

`GET /api/schema/json_schema/<kind>` returns **500 for any kind with a `List` attribute**:

```text
PydanticSchemaGenerationError: Unable to generate pydantic-core schema
for <class 'infrahub.types.Any'>
```

Reproduced on Infrahub 1.10.6 against `ServiceFabricPeering`, whose only attribute kind is
`List`. Kinds with no `List` attribute return 200.

Backstage reads that endpoint to generate a request form, so `ServiceAppAccess`,
`ServiceFabricApp` and `ServiceFabricPeering` appear in the catalogue with **no generated form**
until it is fixed. The catalog provider warns and carries on rather than failing the poll.
