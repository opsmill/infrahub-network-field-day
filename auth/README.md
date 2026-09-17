# On-prem OIDC for the lab

Dex is the lab's identity provider and **Infrahub is the relying party**. Infrahub drives the
whole flow itself and mints its own token; nothing downstream ever sees a Dex token.

```text
browser ──▶ /api/oidc/provider1/authorize?final_url=…
              └─▶ Dex login ──▶ /auth/oidc/provider1/callback?code&state
                                  └─▶ UI calls /api/oidc/provider1/token
                                        └─▶ {access_token, refresh_token, final_url}
```

## Signing in

| User | Password |
| --- | --- |
| `alice@nfd41.lab` | `password` |
| `bob@nfd41.lab` | `password` |

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
