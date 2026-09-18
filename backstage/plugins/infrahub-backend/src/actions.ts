import {
  coreServices,
  createBackendModule,
} from '@backstage/backend-plugin-api';
import {
  createTemplateAction,
  scaffolderActionsExtensionPoint,
} from '@backstage/plugin-scaffolder-node';
import { refreshInfrahubCatalog } from './provider';
import {
  awaitGenerators,
  infrahubQuery,
  readInfrahubConfig,
} from '@opsmill/backstage-plugin-infrahub-node';

/**
 * Runs a GraphQL query or mutation against Infrahub, on a given branch.
 *
 * ponytail: one generic action instead of one action per service — the
 * service-specific mutations live in the templates.
 */
export const infrahubActionsModule = createBackendModule({
  pluginId: 'scaffolder',
  moduleId: 'infrahub-actions',
  register(env) {
    env.registerInit({
      deps: {
        actions: scaffolderActionsExtensionPoint,
        config: coreServices.rootConfig,
      },
      async init({ actions, config }) {
        const infrahub = readInfrahubConfig(config);

        actions.addActions(
          createTemplateAction({
            id: 'infrahub:generators:await',
            description:
              'Wait for the generators expanding a node to finish on its branch',
            schema: {
              input: {
                branch: z => z.string().describe('The branch they run on'),
                node: z =>
                  z.string().describe('The id of the node they expand'),
                quietPeriod: z =>
                  z
                    .number()
                    .optional()
                    .describe(
                      'Seconds of no activity before calling it finished, ' +
                        'because one wave can enqueue the next (default 15)',
                    ),
                timeout: z =>
                  z
                    .number()
                    .optional()
                    .describe('Seconds before giving up (default 1200)'),
                pollInterval: z =>
                  z
                    .number()
                    .optional()
                    .describe('Seconds between polls (default 5)'),
                trigger: z =>
                  z
                    .boolean()
                    .optional()
                    .describe(
                      'Run the definitions first (default true); false waits ' +
                        'for a run someone else started',
                    ),
              },
              output: {
                waited: z =>
                  z
                    .boolean()
                    .describe('False when no generator runs on a branch here'),
                tasks: z => z.number().describe('How many tasks were seen'),
              },
            },
            async handler(ctx) {
              const result = await awaitGenerators({
                config: infrahub,
                branch: ctx.input.branch,
                node: ctx.input.node,
                quietPeriod: ctx.input.quietPeriod ?? 15,
                timeout: ctx.input.timeout ?? 1200,
                pollInterval: ctx.input.pollInterval ?? 5,
                trigger: ctx.input.trigger,
                logger: ctx.logger,
              });

              ctx.output('waited', result.waited);
              ctx.output('tasks', result.tasks);
            },
          }),
          createTemplateAction({
            id: 'infrahub:catalog:refresh',
            description:
              'Read Infrahub into the catalog now, so a service this run ' +
              'created is there when the run finishes',
            async handler(ctx) {
              await refreshInfrahubCatalog();
              ctx.logger.info('Infrahub catalog refreshed');
            },
          }),
          createTemplateAction({
            id: 'infrahub:file:upload',
            description:
              'Attach a file payload to a node, as a CoreFileObject child',
            schema: {
              input: {
                kind: z =>
                  z
                    .string()
                    .describe(
                      'The CoreFileObject kind to create, e.g. ' +
                        'ServiceFabricAppManifestsFile',
                    ),
                parentField: z =>
                  z
                    .string()
                    .describe(
                      'The relationship on that kind pointing back at its ' +
                        'owner, e.g. `app`',
                    ),
                parentId: z =>
                  z.string().describe('The owning node, by id'),
                content: z => z.string().describe('The file content'),
                fileName: z => z.string().describe('The stored file name'),
                branch: z =>
                  z
                    .string()
                    .optional()
                    .describe('Infrahub branch, defaults to main'),
              },
              output: {
                id: z => z.string().describe('The created file node'),
                size: z => z.number().describe('Bytes stored'),
              },
            },
            async handler(ctx) {
              const branch = ctx.input.branch ?? 'main';

              // WHY THIS IS NOT `infrahub:graphql:execute` WITH A VARIABLE.
              // A CoreFileObject's content fields -- `storage_id`, `checksum`,
              // `file_name`, `file_size` -- are ALL read-only on the Create
              // input, which accepts only `id`, the parent relationship and
              // the group relationships. Content arrives through the
              // mutation's own `file: Upload!` argument instead, which is a
              // GraphQL multipart request: a JSON `operations` part, a `map`
              // part binding a file to a variable path, and the bytes.
              // `infrahubQuery` posts JSON, so it cannot express this.
              //
              // `Upload` is NON-NULL, which is the useful half: the node and
              // its content are created in ONE call, so there is no window in
              // which a file node exists with nothing in it.
              const body = new FormData();
              const query = [
                `mutation ($parent: String!, $file: Upload!) {`,
                `  ${ctx.input.kind}Create(`,
                `    data: { ${ctx.input.parentField}: { id: $parent } }`,
                `    file: $file`,
                `  ) {`,
                `    ok`,
                `    object { id file_size { value } }`,
                `  }`,
                `}`,
              ].join('\n');
              body.append(
                'operations',
                JSON.stringify({
                  query,
                  variables: { parent: ctx.input.parentId, file: null },
                }),
              );
              body.append('map', JSON.stringify({ '0': ['variables.file'] }));
              body.append(
                '0',
                new Blob([ctx.input.content], { type: 'application/x-yaml' }),
                ctx.input.fileName,
              );

              const response = await fetch(
                `${infrahub.address}/graphql/${encodeURIComponent(branch)}`,
                {
                  method: 'POST',
                  // NO Content-Type HEADER. fetch derives multipart/form-data
                  // and appends the boundary; setting it by hand omits the
                  // boundary and the server cannot parse a single part.
                  headers: { 'X-INFRAHUB-KEY': infrahub.token },
                  body,
                },
              );

              const payload: any = await response.json().catch(() => undefined);
              if (!response.ok || payload?.errors) {
                const detail = payload?.errors
                  ? JSON.stringify(payload.errors).slice(0, 300)
                  : `HTTP ${response.status}`;
                throw new Error(
                  `Uploading ${ctx.input.fileName} as ${ctx.input.kind} failed: ${detail}`,
                );
              }

              const object = payload?.data?.[`${ctx.input.kind}Create`]?.object;
              if (!object?.id) {
                throw new Error(
                  `Uploading ${ctx.input.fileName} returned no object; ` +
                    'the payload was not attached',
                );
              }

              ctx.logger.info(
                `Attached ${ctx.input.fileName} to ${ctx.input.parentId} ` +
                  `as ${ctx.input.kind} on branch ${branch}`,
              );
              ctx.output('id', object.id);
              ctx.output('size', object.file_size?.value ?? 0);
            },
          }),

          createTemplateAction({
            id: 'infrahub:graphql:execute',
            description: 'Execute a GraphQL query or mutation against Infrahub',
            schema: {
              input: {
                query: z =>
                  z.string().describe('The GraphQL query or mutation'),
                variables: z =>
                  z.record(z.any()).optional().describe('GraphQL variables'),
                branch: z =>
                  z
                    .string()
                    .optional()
                    .describe('Infrahub branch, defaults to main'),
                relatedNodeLists: z =>
                  z
                    .array(z.string())
                    .optional()
                    .describe(
                      'Variables holding a list of hfids to wrap as ' +
                        '[{ hfid: [value] }], for a cardinality-many relationship',
                    ),
              },
              output: {
                data: z =>
                  z.record(z.any()).describe('The GraphQL response data'),
                address: z =>
                  z
                    .string()
                    .describe(
                      'The browser-facing Infrahub base URL, for building links',
                    ),
              },
            },
            async handler(ctx) {
              const branch = ctx.input.branch ?? 'main';

              // A cardinality-many relationship takes `[RelatedNodeInput]`, so
              // `["k8s", "app"]` has to become `[{hfid: ["k8s"]}, ...]`. The
              // scaffolder templates a parameter to its own value and cannot
              // build objects, so the wrapping happens here and the step says
              // which variables need it.
              const variables = { ...(ctx.input.variables ?? {}) };
              for (const name of ctx.input.relatedNodeLists ?? []) {
                const value = variables[name];
                if (Array.isArray(value)) {
                  variables[name] = value
                    .filter(entry => entry !== undefined && entry !== null && entry !== '')
                    .map(entry => ({ hfid: [String(entry)] }));
                }
              }

              const data = await infrahubQuery({
                config: infrahub,
                query: ctx.input.query,
                variables,
                branch,
              });

              ctx.logger.info(
                `Infrahub mutation succeeded on branch ${branch}`,
              );
              ctx.output('data', data);
              ctx.output('address', infrahub.externalAddress);
            },
          }),
        );
      },
    });
  },
});
