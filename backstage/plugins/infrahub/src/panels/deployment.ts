/**
 * What the topology page shows about whether a device matches the
 * configuration Infrahub renders for it. `DeploymentState` is written by the
 * reconciler and is agnostic to branches, so this reads the same records on
 * every branch. No React here, so the wording and the staleness rule are tested
 * directly.
 */

export const DEPLOYMENT_QUERY = `
  query {
    DeploymentState {
      edges {
        node {
          name { value }
          status { value }
          last_checked_at { value }
          last_confirmed_at { value }
        }
      }
    }
  }
`;

export type DeploymentData = {
  DeploymentState: {
    edges: {
      node: {
        name: { value: string | null };
        status: { value: string | null };
        last_checked_at?: { value: string | null } | null;
        last_confirmed_at?: { value: string | null } | null;
      };
    }[];
  };
};

export type Tone = 'ok' | 'pending' | 'warn' | 'error' | 'idle';

export type Badge = { label: string; tone: Tone; detail: string };

/**
 * The reconciler's loop is at most ten minutes. A record checked longer ago
 * than twice that is not evidence of anything: the loop may be dead while the
 * last thing it wrote still says `in_sync`.
 */
export const STALE_AFTER_MS = 20 * 60 * 1000;

const TONES: Record<string, { label: string; tone: Tone }> = {
  in_sync: { label: 'in sync', tone: 'ok' },
  pending: { label: 'pending', tone: 'pending' },
  drifted: { label: 'drifted', tone: 'warn' },
  failed: { label: 'failed', tone: 'error' },
  never_deployed: { label: 'never deployed', tone: 'idle' },
};

/** `3m ago`, for a tooltip. */
export function ago(from: string | null | undefined, now: number): string {
  if (!from) return 'never';
  const seconds = Math.max(0, Math.round((now - Date.parse(from)) / 1000));
  if (Number.isNaN(seconds)) return 'unknown';
  if (seconds < 90) return `${seconds}s ago`;
  if (seconds < 90 * 60) return `${Math.round(seconds / 60)}m ago`;
  return `${Math.round(seconds / 3600)}h ago`;
}

type State = DeploymentData['DeploymentState']['edges'][number]['node'];

export function indexByName(data: DeploymentData): Map<string, State> {
  const byName = new Map<string, State>();
  for (const edge of data.DeploymentState.edges) {
    if (edge.node.name.value) byName.set(edge.node.name.value, edge.node);
  }
  return byName;
}

/**
 * A device with no record is its own answer -- nothing has ever looked at it --
 * and a stale `in_sync` is reported as stale rather than as in sync.
 */
export function describeState(state: State | undefined, now: number): Badge {
  if (!state) {
    return {
      label: 'no record',
      tone: 'idle',
      detail:
        'No deployment record: the reconciler does not manage this device, or has not run yet.',
    };
  }
  const checked = state.last_checked_at?.value;
  const known = TONES[state.status.value ?? ''] ?? {
    label: state.status.value ?? 'unknown',
    tone: 'idle' as Tone,
  };
  const detail = `Checked ${ago(checked, now)}, last confirmed ${ago(
    state.last_confirmed_at?.value,
    now,
  )}.`;
  const age = checked ? now - Date.parse(checked) : Infinity;
  if (age > STALE_AFTER_MS && known.tone === 'ok') {
    return {
      label: 'stale',
      tone: 'idle',
      detail: `Reported in sync, but not checked for a while. ${detail}`,
    };
  }
  return { ...known, detail };
}
