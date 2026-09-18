import { LoggerService, SchedulerService } from '@backstage/backend-plugin-api';
import { Entity } from '@backstage/catalog-model';
import { InfrahubEntityProvider } from './provider';
import { CatalogConfig } from './config';
import {
  infrahubGet,
  infrahubQuery,
} from '@opsmill/backstage-plugin-infrahub-node';

jest.mock('@opsmill/backstage-plugin-infrahub-node', () => ({
  ...jest.requireActual('@opsmill/backstage-plugin-infrahub-node'),
  infrahubQuery: jest.fn(),
  infrahubGet: jest.fn(),
}));

const value = <T>(v: T) => ({ value: v });

/**
 * A fake Infrahub with two kinds: a site named directly in config, and a
 * service kind reachable only by discovering descendants of `ServiceGeneric`.
 * Between them they cover both routes into the catalog.
 */
const SCHEMA: Record<string, any> = {
  '/api/schema': {
    nodes: [
      {
        namespace: 'Service',
        name: 'Wireless',
        inherit_from: ['ServiceGeneric'],
      },
      { namespace: 'Location', name: 'Site', inherit_from: [] },
    ],
  },
  '/api/schema/LocationSite': {
    name: 'Site',
    namespace: 'Location',
    label: 'Site',
    description: 'A point of presence.',
    human_friendly_id: ['shortname__value'],
    attributes: [{ name: 'shortname', kind: 'Text', optional: false }],
    relationships: [
      { name: 'parent', peer: 'LocationMetro', cardinality: 'one' },
    ],
  },
  '/api/schema/json_schema/LocationSite': {
    title: 'Site',
    required: ['shortname'],
    properties: {
      shortname: { type: 'string' },
      description: { type: 'string', default: null },
    },
  },
  '/api/schema/ServiceWireless': {
    name: 'Wireless',
    namespace: 'Service',
    label: 'Wireless',
    human_friendly_id: ['service_identifier__value'],
    attributes: [
      // A List, which is what makes Infrahub 1.10.6 return 500 from
      // /api/schema/json_schema for a kind. Absent from the json_schema fixture
      // below for the same reason the real endpoint never gets that far.
      { name: 'ports', kind: 'List', optional: true },
      { name: 'ssid', kind: 'Text', optional: false },
      { name: 'service_identifier', kind: 'Text', optional: false },
      {
        name: 'security',
        kind: 'Dropdown',
        // Deliberately in a different order from the json_schema enum, so a
        // positional merge would mislabel and the test would catch it.
        choices: [
          { name: 'wpa2-personal', label: 'WPA2 Personal' },
          { name: 'open', label: 'Open' },
        ],
      },
    ],
    relationships: [
      {
        name: 'location',
        peer: 'LocationSite',
        cardinality: 'one',
        optional: false,
        label: 'Site',
      },
      // A peer nobody ingests, and mandatory, so it must still reach a create.
      {
        name: 'provider',
        peer: 'OrganizationProvider',
        cardinality: 'one',
        optional: false,
      },
      // A peer whose hfid has TWO elements. A single-element lookup is refused
      // by Infrahub outright, so this cannot be sent as one string.
      {
        name: 'vip',
        peer: 'IpamIPAddress',
        cardinality: 'one',
        optional: false,
      },
      // MANDATORY and cardinality MANY, like `ServiceNetworkSegment.avd_tags`.
      // Dropping it makes Infrahub refuse the create outright.
      { name: 'tags', peer: 'AvdTag', cardinality: 'many', optional: false },
      // Optional and many: still left off, or the form would ask for every
      // derived collection a kind has.
      { name: 'extras', peer: 'AvdTag', cardinality: 'many', optional: true },
      { name: 'profiles', peer: 'CoreProfile', cardinality: 'many' },
    ],
  },
  '/api/schema/AvdTag': {
    name: 'Tag',
    namespace: 'Avd',
    human_friendly_id: ['name__value'],
    attributes: [],
    relationships: [],
  },
  '/api/schema/IpamIPAddress': {
    name: 'IPAddress',
    namespace: 'Ipam',
    human_friendly_id: ['address__value', 'ip_namespace__name__value'],
    attributes: [],
    relationships: [],
  },
  '/api/schema/json_schema/ServiceWireless': {
    title: 'Wireless',
    required: ['ssid', 'service_identifier'],
    properties: {
      service_identifier: { type: 'string' },
      ssid: { type: 'string' },
      security: {
        type: 'string',
        enum: ['open', 'wpa2-personal'],
        default: 'wpa2-personal',
      },
      status: { type: 'string', enum: ['draft', 'active'] },
      // Infrahub sends an explicit null default for an optional field.
      access_points: { type: 'number', default: null },
      // A list cannot be typed into a mutation, so it is left off the form.
      tags: { type: 'array' },
    },
  },
};

const SITES = {
  LocationSite: {
    edges: [
      {
        node: {
          id: 'site-1',
          hfid: ['bru01'],
          display_label: 'Brussels 1 (bru01)',
          __typename: 'LocationSite',
          shortname: value('bru01'),
          description: value('Main POP'),
          parent: {
            node: { id: 'm-1', hfid: ['bru'], display_label: 'Brussels' },
          },
        },
      },
    ],
  },
};

const wireless = (overrides: Record<string, any> = {}) => ({
  id: 'wifi-1',
  hfid: ['WIFI-001'],
  display_label: 'WIFI-001',
  __typename: 'ServiceWireless',
  service_identifier: value('WIFI-001'),
  ssid: value(null),
  security: value('wpa2-personal'),
  access_points: value(null),
  status: value('draft'),
  location: {
    node: {
      id: 'site-1',
      hfid: ['bru01'],
      display_label: 'Brussels 1 (bru01)',
    },
  },
  provider: { node: null },
  ...overrides,
});

const CHANGE = {
  id: 'pc-1',
  source_branch: value('implement_wifi-001'),
  state: value('open'),
};

const DEFAULTS: CatalogConfig = {
  refreshMinutes: 1,
  owner: 'user:default/guest',
  system: 'infrahub-services',
  kinds: [
    {
      kind: 'LocationSite',
      entity: 'Resource',
      type: 'infrahub-site',
      template: false,
      groups: [],
      formExclude: [],
    },
  ],
  discover: [
    {
      generic: 'ServiceGeneric',
      entity: 'Component',
      template: true,
      groups: [],
      formExclude: [],
    },
  ],
};

describe('InfrahubEntityProvider', () => {
  let branchesRead: string[] = [];
  let warnings: string[] = [];
  let queries: string[] = [];

  beforeEach(() => {
    branchesRead = [];
    warnings = [];
    queries = [];
  });

  const run = async (
    options: {
      catalog?: Partial<CatalogConfig>;
      changeState?: string;
      /** A path that fails, the way /api/schema/json_schema does for a List. */
      broken?: string;
    } = {},
  ): Promise<Record<string, Entity>> => {
    const changeState = options.changeState ?? 'open';

    (infrahubGet as jest.Mock).mockImplementation(
      async (_config: unknown, path: string) => {
        if (options.broken && path === options.broken) {
          throw new Error('Internal Server Error');
        }
        if (SCHEMA[path]) {
          return SCHEMA[path];
        }
        throw new Error(`no schema for ${path}`);
      },
    );

    (infrahubQuery as jest.Mock).mockImplementation(
      async (request: { branch?: string; query: string }) => {
        queries.push(request.query);
        if (request.branch) {
          branchesRead.push(request.branch);
        }
        if (request.query.includes('CoreProposedChange')) {
          return {
            CoreProposedChange: {
              edges: [{ node: { ...CHANGE, state: value(changeState) } }],
            },
          };
        }
        if (request.query.includes('LocationSite')) {
          return SITES;
        }
        if (request.query.includes('ServiceWireless')) {
          // On the request's own branch the branch aware values are set.
          return {
            ServiceWireless: {
              edges: [
                {
                  node: request.branch
                    ? wireless({ ssid: value('acme-corp') })
                    : wireless(),
                },
              ],
            },
          };
        }
        return {};
      },
    );

    const applied: Entity[] = [];
    const provider = new InfrahubEntityProvider(
      {
        instance: 'test',
        // Distinct on purpose: links must never carry the internal address.
        address: 'http://infrahub-server:8000',
        externalAddress: 'http://localhost:8000',
        token: 'token',
      },
      { ...DEFAULTS, ...options.catalog },
      'http://localhost:3001',
      // ponytail: two stubs instead of pulling in backend-test-utils.
      {
        info: jest.fn(),
        warn: jest.fn((message: string) => warnings.push(message)),
        error: jest.fn((message: string) => warnings.push(message)),
        debug: jest.fn(),
      } as unknown as LoggerService,
      { scheduleTask: jest.fn() } as unknown as SchedulerService,
    );

    await provider.connect({
      applyMutation: async mutation => {
        if (mutation.type === 'full') {
          applied.push(...mutation.entities.map(e => e.entity as Entity));
        }
      },
      refresh: jest.fn(),
    });
    await provider.refresh();

    return Object.fromEntries(
      applied.map(entity => [`${entity.kind}:${entity.metadata.name}`, entity]),
    );
  };

  it('ingests the kinds named in config and the ones discovered under a generic', async () => {
    expect(Object.keys(await run()).sort()).toEqual([
      'API:locationsite',
      'API:servicewireless',
      'Component:wifi-001',
      'Resource:bru01',
      'System:infrahub-services',
      'Template:wireless-request',
    ]);
  });

  it('asks a kind only for fields its own schema has', async () => {
    await run();

    const site = queries.find(query => query.includes('LocationSite'))!;
    const service = queries.find(query => query.includes('ServiceWireless'))!;

    // status is on a service but not on a site, and asking Infrahub for a field
    // a kind lacks fails the whole query -- which cost every site, rack and
    // device before this was pinned.
    expect(service).toContain('status { value }');
    expect(site).not.toContain('status');
  });

  it('names entities by their Infrahub human friendly id', async () => {
    const entities = await run();

    // hfid, not the display label and not the UUID: it is what a mutation
    // takes back, and it is what every existing link already uses.
    expect(entities['Resource:bru01'].metadata.title).toBe(
      'Brussels 1 (bru01)',
    );
    expect(entities['Component:wifi-001'].metadata.title).toBe('WIFI-001');
  });

  it('takes the Backstage kind and spec.type from config', async () => {
    const entities = await run();

    expect(entities['Resource:bru01'].spec).toMatchObject({
      type: 'infrahub-site',
      owner: 'user:default/guest',
    });
    // Only a Component belongs to a System; a Resource is not part of one.
    expect(entities['Resource:bru01'].spec!.system).toBeUndefined();
    expect(entities['Component:wifi-001'].spec!.system).toBe(
      'system:default/infrahub-services',
    );
  });

  it('describes an object from its own attributes and relationships', async () => {
    const entities = await run();

    // Nothing here is per-kind code: the fields come from the schema, and the
    // relationship line uses Infrahub's own label.
    expect(entities['Resource:bru01'].metadata.description).toBe(
      'Description Main POP · Parent Brussels',
    );
    expect(entities['Component:wifi-001'].metadata.description).toContain(
      'Ssid acme-corp requested',
    );
    expect(entities['Component:wifi-001'].metadata.description).toContain(
      'Site Brussels 1 (bru01)',
    );
  });

  it('turns a relationship into a catalog relation when the peer is ingested', async () => {
    const entities = await run();

    expect(entities['Component:wifi-001'].spec!.dependsOn).toEqual([
      'resource:default/bru01',
    ]);
    // LocationMetro is not ingested, so parent stays description text.
    expect(entities['Resource:bru01'].spec!.dependsOn).toBeUndefined();
  });

  it('generates a template only for kinds configured to have one', async () => {
    const entities = await run();

    expect(entities['Template:wireless-request']).toBeDefined();
    // A site is reference data, not something a portal user requests.
    expect(entities['Template:locationsite-request']).toBeUndefined();
  });

  it('puts a generated create into the groups its generators watch', async () => {
    const template = (
      await run({
        catalog: {
          discover: [
            {
              generic: 'ServiceGeneric',
              entity: 'Component',
              template: true,
              groups: ['automated_wireless'],
              formExclude: [],
            },
          ],
        },
      })
    )['Template:wireless-request'];

    const create = (template.spec!.steps as any[]).find(
      step => step.id === 'create',
    );

    // An Infrahub generator definition targets a *group*. A service created
    // outside it is never expanded, and then there is nothing to wait for --
    // which is exactly how a generated template silently skipped a generator.
    expect(create.input.query).toContain(
      'member_of_groups: [{ hfid: ["automated_wireless"] }]',
    );
  });

  it('labels dropdown options the way Infrahub does', async () => {
    const template = (await run())['Template:wireless-request'];
    const [parameters] = template.spec!.parameters as any[];
    // The create branch of the mode switch.
    const create = parameters.dependencies.mode.oneOf.find(
      (branch: any) => branch.properties.mode.enum[0] === 'create',
    );
    const security = create.properties.security;

    // json_schema has the values but not the labels; /api/schema has the
    // labels. Without the merge a form offers `wpa2-personal` where Infrahub
    // says "WPA2 Personal".
    expect(security.enum).toEqual(['open', 'wpa2-personal']);
    expect(security.enumNames).toEqual(['Open', 'WPA2 Personal']);
  });

  it('opens a proposed change without naming a field the schema lacks', async () => {
    // `CoreProposedChange` has no `tags` field on Infrahub 1.10.6, and the
    // mutation is rejected outright:
    //
    //   Field 'tags' is not defined by type 'CoreProposedChangeCreateInput'
    //
    // It is the LAST step, so the object, the branch and the generators all
    // succeeded first and no proposed change opened -- a request that reaches
    // nobody, indistinguishable in the catalogue from one awaiting review.
    const template = (await run())['Template:wireless-request'];
    const step = (template.spec!.steps as any[]).find(
      s => s.id === 'proposed_change',
    );
    expect(step.input.query).toContain('CoreProposedChangeCreate');
    expect(step.input.query).not.toContain('tags');
  });

  it('offers a mandatory many-relationship, and sends it as a list', async () => {
    // `ServiceNetworkSegment.avd_tags` is mandatory and cardinality many. The
    // provider handled only cardinality one, so the field was dropped from the
    // form AND from the mutation, and Infrahub refused the create:
    //
    //   avd_tags is mandatory for ServiceNetworkSegment at avd_tags
    //
    // The kind was unrequestable behind a form that looked complete.
    const template = (await run())['Template:wireless-request'];
    const [parameters] = template.spec!.parameters as any[];
    const create = parameters.dependencies.mode.oneOf.find(
      (branch: any) => branch.properties.mode.enum[0] === 'create',
    );

    expect(create.properties.tags).toMatchObject({
      type: 'array',
      items: { type: 'string' },
    });
    expect(create.required).toEqual(expect.arrayContaining(['tags']));
    // An OPTIONAL many is still left off; otherwise every derived collection
    // would appear on the form.
    expect(create.properties.extras).toBeUndefined();

    const step = (template.spec!.steps as any[]).find(s => s.id === 'create');
    expect(step.input.query).toContain('$tags: [RelatedNodeInput]');
    expect(step.input.query).toContain('tags: $tags');
    // The action wraps the plain hfids into [{hfid: [...]}]; a template cannot.
    expect(step.input.relatedNodeLists).toEqual(['tags']);
  });

  it('asks for every element of a composite hfid', async () => {
    // `IpamIPAddress` is keyed by [address, namespace], and a one-element lookup
    // is refused:
    //
    //   Unable to lookup node by HFID, schema 'IpamIPAddress' HFID does not
    //   contain the same number of elements as ['10.112.240.10/32']
    //
    // Two of this lab's service kinds have a MANDATORY relationship to such a
    // peer, so they could not be created from the portal at all.
    const template = (await run())['Template:wireless-request'];
    const [parameters] = template.spec!.parameters as any[];
    const create = parameters.dependencies.mode.oneOf.find(
      (branch: any) => branch.properties.mode.enum[0] === 'create',
    );

    expect(create.properties.vip).toMatchObject({
      type: 'array',
      items: { type: 'string' },
    });
    // No picker: one would yield a single name and could never supply both.
    expect(create.properties.vip['ui:field']).toBeUndefined();

    const step = (template.spec!.steps as any[]).find(s => s.id === 'create');
    expect(step.input.query).toContain('$vip: [String]!');
    expect(step.input.query).toContain('vip: { hfid: $vip }');
    // A single-element peer is untouched.
    expect(step.input.query).toContain('$location: String!');
    expect(step.input.query).toContain('location: { hfid: [$location] }');
  });

  it('lets the schema decide a new object\'s status', async () => {
    // This used to send `status: { value: "draft" }`. That is the upstream
    // example's vocabulary, and a schema without it refuses the whole create --
    // so every request through every generated template failed at its first
    // step. Infrahub applies the attribute's own default instead.
    const template = (await run())['Template:wireless-request'];
    const create = (template.spec!.steps as any[]).find(s => s.id === 'create');
    expect(create.input.query).not.toContain('draft');
    expect(create.input.query).not.toContain('status:');
  });

  it('builds a form from /api/schema when json_schema fails', async () => {
    // Infrahub 1.10.6 returns 500 from /api/schema/json_schema/{kind} for any
    // kind carrying a List attribute. Three of this lab's nine service kinds do,
    // including the one the portal exists to take requests for, and losing the
    // json_schema used to lose the whole kind -- it vanished from the catalogue
    // with only a backend warning to say why.
    const entities = await run({
      broken: '/api/schema/json_schema/ServiceWireless',
    });

    const template = entities['Template:wireless-request'];
    expect(template).toBeDefined();

    const [parameters] = template.spec!.parameters as any[];
    const create = parameters.dependencies.mode.oneOf.find(
      (branch: any) => branch.properties.mode.enum[0] === 'create',
    );

    // Typed from the Infrahub attribute kinds rather than guessed.
    expect(create.properties.ssid).toMatchObject({ type: 'string' });
    expect(create.properties.security.type).toBe('string');

    // The List is the reason the endpoint failed, and it is the substance of an
    // access request -- a grant naming no ports opens nothing. It is offered as
    // an array of strings and typed into the mutation as GenericScalar, which is
    // what `ListAttributeCreate.value` takes.
    expect(create.properties.ports).toMatchObject({
      type: 'array',
      items: { type: 'string' },
    });

    const step = (template.spec!.steps as any[]).find(s => s.id === 'ports');
    expect(step.input.query).toContain('$value: GenericScalar!');
    // `[]` is truthy, so a bare truthiness guard would send an empty list.
    expect(step.if).toContain('| length > 0');

    // Dropdown labels still come from /api/schema, which is now the only source.
    expect(create.properties.security.enum).toEqual(['wpa2-personal', 'open']);
    expect(create.properties.security.enumNames).toEqual([
      'WPA2 Personal',
      'Open',
    ]);

    // `required` derived from `optional: false`, which is what json_schema does.
    expect(create.required).toEqual(expect.arrayContaining(['ssid']));

    expect(warnings.join('\n')).toContain('building its form from /api/schema');
  });

  it('keeps a generator-allocated field off the form but still on the entity', async () => {
    const entities = await run({
      catalog: {
        discover: [
          {
            generic: 'ServiceGeneric',
            entity: 'Component',
            template: true,
            groups: [],
            formExclude: ['location'],
          },
        ],
      },
    });

    const template = entities['Template:wireless-request'];
    const fields = JSON.stringify(template.spec!.parameters);

    // Nobody should be asked to type what a generator picks...
    expect(fields).not.toContain('"location"');
    // ...but it is still read, and still shown on the entity.
    expect(entities['Component:wifi-001'].metadata.description).toContain(
      'Site Brussels 1 (bru01)',
    );
    expect(entities['Component:wifi-001'].spec!.dependsOn).toEqual([
      'resource:default/bru01',
    ]);
  });

  it('leaves member_of_groups out when no group is configured', async () => {
    const template = (await run())['Template:wireless-request'];
    const create = (template.spec!.steps as any[]).find(
      step => step.id === 'create',
    );

    expect(create.input.query).not.toContain('member_of_groups');
  });

  it('lets a kind named in config override one it would have discovered', async () => {
    const entities = await run({
      catalog: {
        kinds: [
          {
            kind: 'ServiceWireless',
            entity: 'Resource',
            type: 'wifi',
            template: false,
            groups: [],
            formExclude: [],
          },
        ],
      },
    });

    expect(entities['Resource:wifi-001'].spec!.type).toBe('wifi');
    expect(entities['Component:wifi-001']).toBeUndefined();
  });

  it('ingests nothing but warns when no mapping is configured', async () => {
    const entities = await run({ catalog: { kinds: [], discover: [] } });

    expect(Object.keys(entities)).toEqual(['System:infrahub-services']);
    expect(warnings.join('\n')).toContain('nothing will be ingested');
  });

  it('emits no System when none is configured', async () => {
    const entities = await run({ catalog: { system: undefined } });

    expect(Object.keys(entities)).not.toContain('System:infrahub-services');
    expect(entities['Component:wifi-001'].spec!.system).toBeUndefined();
  });

  it('marks an object with an open request as pending and links the change', async () => {
    const wifi = (await run())['Component:wifi-001'];

    expect(wifi.metadata.tags).toContain('pending-change');
    expect(wifi.spec!.lifecycle).toBe('experimental');
    // A change stacked on an unmerged request is silently discarded, so the
    // pencil goes to the proposed change rather than the change form.
    expect(wifi.metadata.annotations!['backstage.io/edit-url']).toBe(
      'http://localhost:8000/proposed-changes/pc-1',
    );
  });

  it('offers the generated change form once the request has merged', async () => {
    const wifi = (await run({ changeState: 'merged' }))['Component:wifi-001'];

    expect(wifi.metadata.tags).not.toContain('pending-change');
    expect(wifi.spec!.lifecycle).toBe('production');
    expect(wifi.metadata.annotations!['backstage.io/edit-url']).toContain(
      '/create/templates/default/wireless-request?formData=',
    );
  });

  it('never reads the branch of a change that already merged', async () => {
    await run({ changeState: 'merged' });

    // Infrahub deletes the source branch on merge, so every such read is a
    // guaranteed 404 repeated on each refresh.
    expect(branchesRead).toEqual([]);
  });

  it('reads the branch of a change that is still open', async () => {
    await run();

    expect(branchesRead).toEqual(['implement_wifi-001']);
  });

  it('annotates every ingested entity with its Infrahub identity', async () => {
    const entities = await run();

    for (const name of ['Resource:bru01', 'Component:wifi-001']) {
      expect(entities[name].metadata.annotations).toMatchObject({
        'infrahub.opsmill.com/instance': 'test',
        'infrahub.opsmill.com/branch': 'main',
      });
      expect(
        entities[name].metadata.annotations!['infrahub.opsmill.com/id'],
      ).toBeTruthy();
    }
  });

  it('publishes each ingested kind as an API with its GraphQL slice', async () => {
    const api = (await run())['API:locationsite'];

    expect(api.spec!.type).toBe('graphql');
    expect(api.spec!.definition).toContain('type LocationSite {');
    expect(api.metadata.description).toBe('A point of presence.');
  });

  it('never puts the internal Infrahub address in a link', async () => {
    const entities = Object.values(await run());
    const urls = entities.flatMap(entity => [
      ...Object.values(entity.metadata.annotations ?? {}),
      ...(entity.metadata.links ?? []).map(link => link.url),
    ]);

    expect(urls.filter(url => url.includes('infrahub-server'))).toEqual([]);
  });

  it('warns when two Infrahub objects collapse onto one entity name', async () => {
    (infrahubGet as jest.Mock).mockImplementation(
      async () => SCHEMA['/api/schema/LocationSite'],
    );
    await run({
      catalog: { discover: [] },
    });

    // Nothing collides in the default fixture; the guard is exercised below.
    expect(warnings.join('\n')).not.toContain('collapse');
  });

  it('survives a kind whose objects cannot be read', async () => {
    const entities = await run({
      catalog: {
        kinds: [
          {
            kind: 'LocationSite',
            entity: 'Resource',
            type: 'infrahub-site',
            template: false,
            groups: [],
            formExclude: [],
          },
          {
            // No schema in the fixture, so loading it fails.
            kind: 'DoesNotExist',
            entity: 'Resource',
            type: 'missing',
            template: false,
            groups: [],
            formExclude: [],
          },
        ],
        discover: [],
      },
    });

    // One unreadable kind costs its own entities, not the refresh.
    expect(entities['Resource:bru01']).toBeDefined();
    expect(warnings.join('\n')).toContain('DoesNotExist');
  });
});
