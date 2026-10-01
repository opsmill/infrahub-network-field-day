# Contract: Grafana sign-in through Dex

## Dex static client (`tooling/10-dex.yaml`)

```yaml
- id: grafana
  name: Grafana
  secret: <GRAFANA_DEX_CLIENT_SECRET, default "grafana-dex-secret">   # same literal-default pattern as the infrahub client
  redirectURIs:
    - http://10.112.240.81/login/generic_oauth
```

## Values merged by `crossplane_fabric_app` when `sso_provider: dex`

These keys are merged under `grafana:` in the chart values. They override the values file on
conflict, because they are intent rather than tuning.

```yaml
grafana:
  envValueFrom:
    GF_AUTH_GENERIC_OAUTH_CLIENT_SECRET:
      secretKeyRef: {name: grafana-oidc, key: client-secret}
  admin:
    existingSecret: grafana-admin
    userKey: admin-user
    passwordKey: admin-password
  grafana.ini:
    server:
      root_url: http://<VIP>/                      # derived from the app's pinned LB address
    auth:
      disable_login_form: true
    auth.generic_oauth:
      enabled: true
      name: Dex
      client_id: grafana
      scopes: openid email profile
      auth_url:  http://10.90.0.11:32556/dex/auth        # browser-facing: the issuer
      token_url: http://172.20.41.101:32556/dex/token    # server-to-server: management network
      api_url:   http://172.20.41.101:32556/dex/userinfo
      login_attribute_path: email
      email_attribute_path: email
      role_attribute_path: "'Viewer'"
      role_attribute_strict: true
      allow_assign_grafana_admin: false
      skip_org_role_sync: false
      allow_sign_up: true
      auto_login: true
      use_pkce: true
```

The issuer and back-channel addresses are **renderer constants** this cycle. They are not schema
attributes: there is one issuer, and AGENTS.md argues against a second.

## Secrets

`invoke cluster` creates these in namespace `otternet-metrics` once it exists:

| Secret | Keys | Source |
| --- | --- | --- |
| `grafana-oidc` | `client-secret` | `GRAFANA_DEX_CLIENT_SECRET` (default literal, as for Infrahub's client) |
| `grafana-admin` | `admin-user`, `admin-password` | generated once, persisted in `.env` as `GRAFANA_ADMIN_PASSWORD` |

## Observable behaviour (acceptance)

1. An unauthenticated GET of `http://10.112.240.81/` redirects to
   `http://10.90.0.11:32556/dex/auth?...client_id=grafana...`.
2. After Dex login as alice, `GET /api/user` returns `login=alice@otternet.lab`, and
   `GET /api/user/orgs` returns role `Viewer`.
3. No user reaches role `Admin` or `GrafanaAdmin` through sign-in.
4. `POST /login` with a password is refused, because the login form is disabled.
5. Neither the graph nor any rendered artifact contains the client secret or the admin
   password (grep test over the `crossplane_fabric_app` render).
