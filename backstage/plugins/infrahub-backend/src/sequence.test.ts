import {
  awaitGenerators,
  infrahubQuery,
} from '@opsmill/backstage-plugin-infrahub-node';
import {
  readPath,
  runSequence,
  SequenceStep,
  validateSequence,
  wrapRelatedNodeLists,
} from './sequence';

jest.mock('@opsmill/backstage-plugin-infrahub-node', () => ({
  ...jest.requireActual('@opsmill/backstage-plugin-infrahub-node'),
  infrahubQuery: jest.fn(),
  awaitGenerators: jest.fn(),
}));

const query = infrahubQuery as jest.Mock;
const wait = awaitGenerators as jest.Mock;

const config = {
  address: 'http://infrahub:8000',
  externalAddress: 'https://infrahub.example',
  token: 'not-a-real-token',
} as any;

function logger() {
  const lines: string[] = [];
  return {
    lines,
    info: (line: string) => lines.push(line),
    warn: (line: string) => lines.push(`WARN ${line}`),
  };
}

const create: SequenceStep = {
  id: 'create_app',
  name: 'Create the application',
  action: 'infrahub:graphql:execute',
  input: {
    query:
      'mutation ($name: String!) { AppCreate(data: {name: $name}) { ok } }',
    variables: { name: 'shop' },
  },
};
const barrier: SequenceStep = {
  id: 'await_app',
  name: 'Wait for the VIP block to be allocated',
  action: 'infrahub:generators:await',
  input: {
    node: { fromStep: 'create_app', path: 'data.AppCreate.object.id' },
  },
};
const assertVip: SequenceStep = {
  id: 'assert_vip',
  name: 'Prove the block exists before granting access to it',
  action: 'infrahub:graphql:execute',
  input: {
    query: 'query ($vip: ID!) { IpamPrefix(ids: [$vip]) { count } }',
    variables: {
      vip: { fromStep: 'create_app', path: 'data.AppCreate.vip.node.id' },
    },
  },
};

beforeEach(() => {
  query.mockReset();
  wait.mockReset();
});

describe('infrahub:sequence', () => {
  it('runs the steps in order, on the sequence branch unless a step names one', async () => {
    query.mockResolvedValue({ ok: true });
    wait.mockResolvedValue({ waited: true, tasks: 2 });
    const log = logger();

    await runSequence({
      config,
      branch: 'implement_shop_r1',
      logger: log,
      steps: [
        {
          ...create,
          id: 'branch',
          name: 'Create the branch',
          input: { ...create.input, branch: 'main' },
        },
        { ...create, input: { ...create.input } },
        {
          ...barrier,
          input: { node: 'abc', quietPeriod: 1, timeout: 30 },
        },
      ],
    });

    expect(query.mock.calls.map(call => call[0].branch)).toEqual([
      'main',
      'implement_shop_r1',
    ]);
    expect(wait).toHaveBeenCalledWith(
      expect.objectContaining({
        branch: 'implement_shop_r1',
        node: 'abc',
        quietPeriod: 1,
        timeout: 30,
        pollInterval: 5,
      }),
    );
    // One line per step, with its position, then how long it took.
    expect(log.lines).toEqual(
      expect.arrayContaining([
        '1/3 Create the branch',
        '2/3 Create the application',
        '3/3 Wait for the VIP block to be allocated',
      ]),
    );
    expect(
      log.lines.filter(line => /^\d\/3 .*: done in /.test(line)),
    ).toHaveLength(3);
  });

  it('passes a step result to a later step and returns every result', async () => {
    query
      .mockResolvedValueOnce({
        AppCreate: { object: { id: 'app-1' }, vip: { node: { id: 'vip-9' } } },
      })
      .mockResolvedValueOnce({ IpamPrefix: { count: 1 } });
    wait.mockResolvedValue({ waited: true, tasks: 3 });

    const output = await runSequence({
      config,
      logger: logger(),
      steps: [create, barrier, assertVip],
    });

    expect(wait.mock.calls[0][0].node).toBe('app-1');
    expect(query.mock.calls[1][0].variables).toEqual({ vip: 'vip-9' });
    expect(output.address).toBe('https://infrahub.example');
    expect(output.results.create_app.data.AppCreate.object.id).toBe('app-1');
    expect(output.results.await_app).toEqual({ waited: true, tasks: 3 });
    expect(output.results.assert_vip.data.IpamPrefix.count).toBe(1);
  });

  it('leaves a variable out when a reference finds nothing, so a required variable is refused', async () => {
    query.mockResolvedValueOnce({ AppCreate: { object: { id: 'app-1' } } });
    // What Infrahub does with a missing required variable.
    query.mockImplementationOnce(async ({ variables }) => {
      if (!('vip' in variables)) {
        throw new Error(
          'Variable "$vip" of required type "ID!" was not provided.',
        );
      }
      return {};
    });
    const log = logger();

    await expect(
      runSequence({ config, logger: log, steps: [create, assertVip] }),
    ).rejects.toThrow(
      'Step 2/2 Prove the block exists before granting access to it failed: ' +
        'Variable "$vip" of required type "ID!" was not provided.',
    );
    expect(query.mock.calls[1][0].variables).toEqual({});
    expect(log.lines.some(line => line.startsWith('WARN 2/2'))).toBe(true);
  });

  it('names the failing step with the original error and runs nothing after it', async () => {
    query
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(
        new Error('Infrahub rejected the mutation: unknown cluster'),
      );
    wait.mockResolvedValue({ waited: true, tasks: 0 });

    await expect(
      runSequence({
        config,
        logger: logger(),
        steps: [
          { ...create, id: 'one', name: 'First' },
          { ...create, id: 'two', name: 'Second' },
          { ...barrier, id: 'three', name: 'Third', input: { node: 'n' } },
        ],
      }),
    ).rejects.toThrow(
      'Step 2/3 Second failed: Infrahub rejected the mutation: unknown cluster',
    );
    expect(wait).not.toHaveBeenCalled();
  });

  it('reports a generator wait that times out under the wait step', async () => {
    query.mockResolvedValue({ AppCreate: { object: { id: 'app-1' } } });
    wait.mockRejectedValue(
      new Error('Timed out after 1200s waiting for generators on b.'),
    );

    await expect(
      runSequence({ config, logger: logger(), steps: [create, barrier] }),
    ).rejects.toThrow(
      'Step 2/2 Wait for the VIP block to be allocated failed: Timed out after 1200s',
    );
  });

  it('refuses a bad sequence before running anything', async () => {
    const ahead: SequenceStep = {
      ...assertVip,
      input: {
        ...assertVip.input,
        variables: { vip: { fromStep: 'later', path: 'x' } },
      },
    };

    await expect(
      runSequence({
        config,
        logger: logger(),
        steps: [ahead, { ...create, id: 'later' }],
      }),
    ).rejects.toThrow('refers to "later", which does not come before it');
    await expect(
      runSequence({ config, logger: logger(), steps: [create, create] }),
    ).rejects.toThrow('two steps with the id "create_app"');
    await expect(
      runSequence({ config, logger: logger(), steps: [] }),
    ).rejects.toThrow('no steps');
    expect(() =>
      validateSequence([{ ...create, action: 'infrahub:file:upload' as any }]),
    ).toThrow('does not run');
    expect(query).not.toHaveBeenCalled();
    expect(wait).not.toHaveBeenCalled();
  });

  it('wraps relatedNodeLists the way infrahub:graphql:execute does', async () => {
    query.mockResolvedValue({});
    await runSequence({
      config,
      logger: logger(),
      steps: [
        {
          ...create,
          input: {
            ...create.input,
            variables: { services: ['a', '', 'b'] },
            relatedNodeLists: ['services'],
          },
        },
      ],
    });
    expect(query.mock.calls[0][0].variables).toEqual({
      services: [{ hfid: ['a'] }, { hfid: ['b'] }],
    });
    expect(wrapRelatedNodeLists({ x: 'y' }, undefined)).toEqual({ x: 'y' });
  });
});

describe('readPath', () => {
  it('follows keys and list positions, and gives undefined for a gap or a null', () => {
    const root = { data: { edges: [{ node: { id: 'n1', vip: null } }] } };
    expect(readPath(root, 'data.edges[0].node.id')).toBe('n1');
    expect(readPath(root, 'data.edges[1].node.id')).toBeUndefined();
    expect(readPath(root, 'data.edges[0].node.vip.node.id')).toBeUndefined();
    expect(readPath(undefined, 'a.b')).toBeUndefined();
  });
});
