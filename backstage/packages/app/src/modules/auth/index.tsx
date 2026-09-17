/**
 * Sign-in against the lab's own Dex.
 *
 * The upstream example this portal is based on ships `guest: {}`, which lets
 * anyone in as "Guest". A guest portal cannot record who asked for a service,
 * and recording that is the whole point of putting requests behind a
 * catalogue -- so this replaces it rather than adding to it.
 *
 * THERE IS NO `oidcAuthApiRef` IN BACKSTAGE, and that is the part that catches
 * people out. `@backstage/core-plugin-api` ships refs for GitHub, Google,
 * Okta and the rest, but a *generic* OIDC provider has none: you build it from
 * `OAuth2.create()` against the provider id configured in app-config. That id
 * -- `oidc` -- has to match `auth.providers.oidc` there and the
 * `plugin-auth-backend-module-oidc-provider` module in the backend, or sign-in
 * fails at a different layer depending on which one is wrong.
 */
import { jsx } from 'react/jsx-runtime';
import {
  ApiBlueprint,
  createApiFactory,
  createApiRef,
  configApiRef,
  discoveryApiRef,
  oauthRequestApiRef,
  createFrontendModule,
} from '@backstage/frontend-plugin-api';
import type {
  BackstageIdentityApi,
  OpenIdConnectApi,
  ProfileInfoApi,
  SessionApi,
} from '@backstage/core-plugin-api';
import { OAuth2 } from '@backstage/core-app-api';
import { SignInPageBlueprint } from '@backstage/plugin-app-react';
import { SignInPage } from '@backstage/core-components';

export const oidcAuthApiRef = createApiRef<
  OpenIdConnectApi & ProfileInfoApi & BackstageIdentityApi & SessionApi
>({
  id: 'auth.oidc',
});

const oidcAuthApi = ApiBlueprint.make({
  name: 'oidc-auth',
  // The callback form is required, not stylistic: ApiBlueprint uses advanced
  // parameter types, and passing the factory directly fails to typecheck with
  // an error that says so in full.
  params: defineParams =>
    defineParams(
      createApiFactory({
        api: oidcAuthApiRef,
        deps: {
          discoveryApi: discoveryApiRef,
          oauthRequestApi: oauthRequestApiRef,
          configApi: configApiRef,
        },
        factory: ({ discoveryApi, oauthRequestApi, configApi }) =>
          OAuth2.create({
            configApi,
            discoveryApi,
            oauthRequestApi,
            provider: {
              id: 'oidc',
              title: 'Dex',
              icon: () => null,
            },
            // Selects which block under `auth.providers.oidc` is used, and must
            // agree with `auth.environment` in app-config.
            environment: configApi.getOptionalString('auth.environment'),
            // `openid` is what makes it OIDC rather than bare OAuth2; `email` is
            // what the sign-in resolver matches a catalog User on, so dropping it
            // breaks sign-in at the resolver with an error about the identity
            // rather than about scopes.
            defaultScopes: ['openid', 'profile', 'email'],
          }),
      }),
    ),
});

const signInPage = SignInPageBlueprint.make({
  params: {
    loader: async () => (props: any) =>
      jsx(SignInPage, {
        ...props,
        // No `guest` alongside it, deliberately. Offering both means every
        // request can be attributed to "Guest" by anyone who prefers one
        // fewer click.
        provider: {
          id: 'oidc',
          title: 'NFD41 Single Sign-On',
          message: 'Sign in with your lab account',
          apiRef: oidcAuthApiRef,
        },
        auto: true,
      }),
  },
});

export const authModule = createFrontendModule({
  pluginId: 'app',
  extensions: [oidcAuthApi, signInPage],
});
