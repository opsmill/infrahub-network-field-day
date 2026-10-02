import {
  ago,
  describeState as badge,
  indexByName,
  STALE_AFTER_MS,
} from './deployment';

const NOW = Date.parse('2026-10-02T12:00:00Z');
const at = (msAgo: number) => new Date(NOW - msAgo).toISOString();

const state = (status: string, checkedMsAgo = 60_000) => ({
  name: { value: 'leaf1' },
  status: { value: status },
  last_checked_at: { value: at(checkedMsAgo) },
  last_confirmed_at: { value: at(checkedMsAgo) },
});

describe('deployment badge', () => {
  it.each([
    ['in_sync', 'in sync', 'ok'],
    ['pending', 'pending', 'pending'],
    ['drifted', 'drifted', 'warn'],
    ['failed', 'failed', 'error'],
    ['never_deployed', 'never deployed', 'idle'],
  ])('reads %s', (status, label, tone) => {
    expect(badge(state(status), NOW)).toMatchObject({ label, tone });
  });

  it('says a device nothing has looked at has no record', () => {
    expect(badge(undefined, NOW)).toMatchObject({
      label: 'no record',
      tone: 'idle',
    });
  });

  it('does not trust an in_sync that has not been checked since the loop could have died', () => {
    const result = badge(state('in_sync', STALE_AFTER_MS + 1000), NOW);
    expect(result).toMatchObject({ label: 'stale', tone: 'idle' });
    expect(result.detail).toContain('in sync');
  });

  it('still reports a failure that is old: a stale failure is not an improvement', () => {
    expect(badge(state('failed', STALE_AFTER_MS * 3), NOW).tone).toBe('error');
  });

  it('keeps an unrecognised status visible rather than inventing one', () => {
    expect(badge(state('weird'), NOW)).toMatchObject({
      label: 'weird',
      tone: 'idle',
    });
  });
});

describe('ago', () => {
  it('reads seconds, minutes and hours', () => {
    expect(ago(at(30_000), NOW)).toBe('30s ago');
    expect(ago(at(10 * 60_000), NOW)).toBe('10m ago');
    expect(ago(at(3 * 3_600_000), NOW)).toBe('3h ago');
  });
  it('handles a missing time', () => {
    expect(ago(null, NOW)).toBe('never');
  });
});

describe('indexByName', () => {
  it('keys the records by device name and skips nameless ones', () => {
    const map = indexByName({
      DeploymentState: {
        edges: [
          { node: state('in_sync') },
          { node: { ...state('failed'), name: { value: null } } },
        ],
      },
    });
    expect([...map.keys()]).toEqual(['leaf1']);
  });
});
