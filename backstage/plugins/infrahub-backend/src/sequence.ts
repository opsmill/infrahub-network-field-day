import { LoggerService } from '@backstage/backend-plugin-api';
import {
  awaitGenerators,
  infrahubQuery,
} from '@opsmill/backstage-plugin-infrahub-node';
import type { InfrahubConfig } from '@opsmill/backstage-plugin-infrahub-node';

/**
 * `infrahub:sequence`: run an ordered list of Infrahub sub-steps inside ONE
 * scaffolder step.
 *
 * WHY THIS EXISTS. The Backstage task page lists one line per template step, and
 * Backstage cannot group or collapse them. The curated "Exposed application, with
 * access" template needs eleven Infrahub operations in a fixed order, which made
 * the page a list of fourteen. Splitting nothing and removing nothing: this runs
 * the same operations, in the same order, and writes one log line per operation,
 * so the run page shows the whole plan and the live position inside it.
 *
 * WHAT A SUB-STEP IS. Exactly the inputs the two existing actions already take:
 *
 * - `infrahub:graphql:execute`  query, variables, branch, relatedNodeLists
 * - `infrahub:generators:await` branch, node, quietPeriod, timeout, pollInterval, trigger
 *
 * THE ONE NEW IDEA IS THE REFERENCE. The scaffolder renders the whole input of a
 * step before the step runs, so a `${{ steps.x.output... }}` expression cannot
 * name another sub-step: it would be rendered, empty, before the first sub-step
 * ran. A value that comes from an earlier sub-step is written
 * `{ fromStep: <sub-step id>, path: <dot path into its result> }` instead, and
 * is resolved here, immediately before the sub-step that uses it. Everything
 * that comes from the form or the signed-in user keeps the ordinary
 * `${{ ... }}` expression.
 *
 * A reference that resolves to nothing leaves the variable out, exactly as an
 * unresolved expression does in a separate step. A required GraphQL variable
 * that is missing is then refused by Infrahub, which is how the template's
 * gates (the block exists, the catalogue entry is requestable) stop the run.
 */

export type SequenceAction =
  | 'infrahub:graphql:execute'
  | 'infrahub:generators:await';

export type SequenceStep = {
  id: string;
  name: string;
  action: SequenceAction;
  input: Record<string, any>;
};

/** What one sub-step leaves behind for the references of later ones. */
export type SequenceResult = Record<string, any>;

export type SequenceOptions = {
  config: InfrahubConfig;
  steps: SequenceStep[];
  /** The branch a sub-step runs on when it names none. */
  branch?: string;
  logger: Pick<LoggerService, 'info' | 'warn'>;
  /** Injected so tests do not need a clock. */
  now?: () => number;
};

export type SequenceOutput = {
  /** One entry per sub-step, by its id. */
  results: Record<string, SequenceResult>;
  /** The browser-facing Infrahub base URL, for building links. */
  address: string;
};

const isReference = (
  value: unknown,
): value is { fromStep: string; path: string } =>
  typeof value === 'object' &&
  value !== null &&
  !Array.isArray(value) &&
  typeof (value as any).fromStep === 'string' &&
  typeof (value as any).path === 'string' &&
  Object.keys(value).length === 2;

/** Reads `a.b[0].c` out of a value; undefined when any link is missing. */
export function readPath(root: unknown, path: string): unknown {
  const parts = path.match(/[^.[\]]+/g) ?? [];
  let current: any = root;
  for (const part of parts) {
    if (current === null || current === undefined) {
      return undefined;
    }
    current = current[part];
  }
  return current === null ? undefined : current;
}

/** Every reference inside a value, so they can be checked before anything runs. */
function referencesIn(value: unknown): string[] {
  if (isReference(value)) {
    return [value.fromStep];
  }
  if (Array.isArray(value)) {
    return value.flatMap(referencesIn);
  }
  if (typeof value === 'object' && value !== null) {
    return Object.values(value).flatMap(referencesIn);
  }
  return [];
}

type Unresolved = { variable: string };

function resolve(
  value: unknown,
  results: Record<string, SequenceResult>,
  where: string,
  unresolved: Unresolved[],
): unknown {
  if (isReference(value)) {
    const found = readPath(results[value.fromStep], value.path);
    if (found === undefined) {
      unresolved.push({
        variable: `${where} (${value.fromStep}.${value.path})`,
      });
    }
    return found;
  }
  if (Array.isArray(value)) {
    return value.map((entry, index) =>
      resolve(entry, results, `${where}[${index}]`, unresolved),
    );
  }
  if (typeof value === 'object' && value !== null) {
    // A key whose reference found nothing is left out, not sent as null.
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, entry]) => [
          key,
          resolve(entry, results, where ? `${where}.${key}` : key, unresolved),
        ])
        .filter(([, entry]) => entry !== undefined),
    );
  }
  return value;
}

/**
 * The relationship-list wrapping `infrahub:graphql:execute` has always done:
 * `["a", "b"]` becomes `[{ hfid: ["a"] }, { hfid: ["b"] }]`.
 */
export function wrapRelatedNodeLists(
  variables: Record<string, any>,
  names: string[] | undefined,
): Record<string, any> {
  const wrapped = { ...variables };
  for (const name of names ?? []) {
    const value = wrapped[name];
    if (Array.isArray(value)) {
      wrapped[name] = value
        .filter(entry => entry !== undefined && entry !== null && entry !== '')
        .map(entry => ({ hfid: [String(entry)] }));
    }
  }
  return wrapped;
}

const seconds = (milliseconds: number) => (milliseconds / 1000).toFixed(1);

/** Checks the whole list before the first sub-step runs, so a typo costs nothing. */
export function validateSequence(steps: SequenceStep[]): void {
  if (steps.length === 0) {
    throw new Error('infrahub:sequence was given no steps');
  }
  const seen = new Set<string>();
  for (const step of steps) {
    if (seen.has(step.id)) {
      throw new Error(
        `infrahub:sequence has two steps with the id "${step.id}"`,
      );
    }
    for (const reference of referencesIn(step.input)) {
      if (!seen.has(reference)) {
        throw new Error(
          `Step "${step.id}" refers to "${reference}", which does not come ` +
            'before it in the sequence',
        );
      }
    }
    if (step.action === 'infrahub:graphql:execute') {
      if (typeof step.input.query !== 'string') {
        throw new Error(`Step "${step.id}" has no GraphQL query`);
      }
    } else if (step.action === 'infrahub:generators:await') {
      // A reference counts as present here; it is resolved when the step runs.
      if (step.input.node === undefined) {
        throw new Error(`Step "${step.id}" needs a node to wait for`);
      }
    } else {
      throw new Error(
        `Step "${step.id}" uses the action "${String(step.action)}", which a ` +
          'sequence does not run',
      );
    }
    seen.add(step.id);
  }
}

export async function runSequence(
  options: SequenceOptions,
): Promise<SequenceOutput> {
  const { config, steps, logger } = options;
  const now = options.now ?? (() => Date.now());

  validateSequence(steps);

  const total = steps.length;
  const results: Record<string, SequenceResult> = {};
  const started = now();

  logger.info(`${total} steps, in this order:`);
  steps.forEach((step, index) => {
    logger.info(`  ${index + 1}/${total} ${step.name}`);
  });

  for (const [index, step] of steps.entries()) {
    const label = `${index + 1}/${total} ${step.name}`;
    logger.info(`${label}`);
    const stepStarted = now();

    try {
      const unresolved: Unresolved[] = [];
      const input = resolve(step.input, results, '', unresolved) as Record<
        string,
        any
      >;
      for (const missing of unresolved) {
        logger.warn(
          `${label}: nothing was found for ${missing.variable}, so it is not sent`,
        );
      }
      const branch: string = input.branch ?? options.branch ?? 'main';

      if (step.action === 'infrahub:graphql:execute') {
        const data = await infrahubQuery({
          config,
          query: input.query,
          variables: wrapRelatedNodeLists(
            input.variables ?? {},
            input.relatedNodeLists,
          ),
          branch,
        });
        results[step.id] = { data };
      } else {
        const awaited = await awaitGenerators({
          config,
          branch,
          node: input.node,
          quietPeriod: input.quietPeriod ?? 15,
          timeout: input.timeout ?? 1200,
          pollInterval: input.pollInterval ?? 5,
          trigger: input.trigger,
          logger,
        });
        results[step.id] = { waited: awaited.waited, tasks: awaited.tasks };
      }
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error);
      throw new Error(`Step ${label} failed: ${reason}`);
    }

    logger.info(`${label}: done in ${seconds(now() - stepStarted)}s`);
  }

  logger.info(`All ${total} steps done in ${seconds(now() - started)}s`);
  return { results, address: config.externalAddress };
}
