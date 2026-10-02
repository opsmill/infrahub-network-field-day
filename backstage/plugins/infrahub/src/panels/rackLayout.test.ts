import fixture from './__fixtures__/rack-schema.json';
import {
  layoutRack,
  RACK_QUERY,
  RackNode,
  ServerNode,
  SERVERS_QUERY,
  serversIn,
  SITE_RACKS_QUERY,
  summarise,
} from './rackLayout';
import { DETAIL_QUERY, LIST_QUERY } from '../pages/RacksPage';

/**
 * The rack queries, walked against a schema captured from the live instance
 * (`scripts/portal/capture_rack_schema.py`). The elevation once asked for
 * `facility_id`, `height` and `mounted_devices`, none of which this schema has,
 * and the page was the first thing to say so. Now a test is.
 */

type KindSchema = {
  attributes: { name: string; kind: string }[];
  relationships: { name: string; peer: string; cardinality: string }[];
};
const KINDS = (fixture as { kinds: Record<string, KindSchema> }).kinds;

/** Fields every Infrahub node answers, whatever its schema. */
const BUILTIN = new Set(['id', 'display_label', '__typename', 'hfid']);
/** Arguments every root field takes, whatever its schema. */
const ROOT_ARGS = new Set(['ids', 'limit', 'offset', 'partial_match', 'order']);
/** Sub-fields an attribute offers. */
const ATTRIBUTE_FIELDS = new Set(['value', 'id', 'is_default', 'source']);

type Selection = {
  name: string;
  args: string[];
  /** For `... on Kind`. */
  on?: string;
  children?: Selection[];
};

/**
 * A deliberately small parser: fields, arguments, nested selections and inline
 * fragments, which is all these queries use. Enough to name every field a query
 * asks for; not a GraphQL implementation.
 */
function parse(query: string): Selection[] {
  const source = query.replace(/#[^\n]*/g, '');
  const tokens =
    source.match(
      /\.\.\.|[_A-Za-z][_0-9A-Za-z]*|\$[_A-Za-z0-9]+|[{}()[\]:!,]|"[^"]*"/g,
    ) ?? [];
  let at = 0;

  const args = (): string[] => {
    // At '('; collect names followed by ':' at depth one.
    const names: string[] = [];
    let depth = 0;
    do {
      const token = tokens[at];
      if (token === '(' || token === '{' || token === '[') depth += 1;
      else if (token === ')' || token === '}' || token === ']') depth -= 1;
      else if (
        depth === 1 &&
        tokens[at + 1] === ':' &&
        /^[_A-Za-z]/.test(token)
      ) {
        names.push(token);
      }
      at += 1;
    } while (depth > 0);
    return names;
  };

  const selectionSet = (): Selection[] => {
    expect(tokens[at]).toBe('{');
    at += 1;
    const out: Selection[] = [];
    while (tokens[at] !== '}') {
      if (tokens[at] === '...') {
        expect(tokens[at + 1]).toBe('on');
        const on = tokens[at + 2];
        at += 3;
        out.push({ name: '...', args: [], on, children: selectionSet() });
        continue;
      }
      const field: Selection = { name: tokens[at], args: [] };
      at += 1;
      if (tokens[at] === '(') field.args = args();
      if (tokens[at] === '{') field.children = selectionSet();
      out.push(field);
    }
    at += 1;
    return out;
  };

  // Skip `query (...)` to the operation's own selection set.
  if (tokens[at] === 'query') {
    at += 1;
    if (tokens[at] !== '(' && tokens[at] !== '{') at += 1;
    if (tokens[at] === '(') args();
  }
  return selectionSet();
}

/** Every path the query names that the schema does not have. */
function missing(query: string): string[] {
  const problems: string[] = [];

  function node(kind: string, selections: Selection[], path: string) {
    const schema = KINDS[kind];
    if (!schema) {
      problems.push(`${path}: kind ${kind} is not in the fixture`);
      return;
    }
    for (const selection of selections) {
      const here = `${path}.${selection.name}`;
      if (selection.on) {
        node(
          selection.on,
          selection.children ?? [],
          `${path}(on ${selection.on})`,
        );
        continue;
      }
      if (BUILTIN.has(selection.name)) continue;
      const attribute = schema.attributes.find(a => a.name === selection.name);
      if (attribute) {
        for (const child of selection.children ?? []) {
          if (!ATTRIBUTE_FIELDS.has(child.name)) {
            problems.push(`${here}.${child.name}: not an attribute field`);
          }
        }
        continue;
      }
      const relationship = schema.relationships.find(
        r => r.name === selection.name,
      );
      if (!relationship) {
        problems.push(`${here}: ${kind} has no field ${selection.name}`);
        continue;
      }
      peer(relationship.peer, relationship.cardinality, selection, here);
    }
  }

  function peer(
    kind: string,
    cardinality: string,
    selection: Selection,
    path: string,
  ) {
    for (const child of selection.children ?? []) {
      if (cardinality === 'one') {
        if (child.name === 'node')
          node(kind, child.children ?? [], `${path}.node`);
        else
          problems.push(
            `${path}.${child.name}: a cardinality-one relationship has only node`,
          );
      } else if (child.name === 'count') {
        continue;
      } else if (child.name === 'edges') {
        for (const edge of child.children ?? []) {
          if (edge.name === 'node')
            node(kind, edge.children ?? [], `${path}.edges.node`);
          else
            problems.push(`${path}.edges.${edge.name}: edges have only node`);
        }
      } else {
        problems.push(
          `${path}.${child.name}: a cardinality-many relationship has count and edges`,
        );
      }
    }
  }

  /** `name__value`, `parent__ids`, `rack__name__value`, ... */
  const filter = (kind: string, argument: string, path: string) => {
    if (ROOT_ARGS.has(argument)) return;
    const schema = KINDS[kind];
    const [first, second, third] = argument.split('__');
    if (
      schema.attributes.some(a => a.name === first) &&
      /^values?$/.test(second) &&
      !third
    ) {
      return;
    }
    const relationship = schema.relationships.find(r => r.name === first);
    if (relationship && second === 'ids' && !third) return;
    if (relationship && third && /^values?$/.test(third)) {
      if (KINDS[relationship.peer]?.attributes.some(a => a.name === second))
        return;
    }
    problems.push(`${path}(${argument}): not a filter ${kind} offers`);
  };

  for (const root of parse(query)) {
    if (!KINDS[root.name]) {
      problems.push(`${root.name}: kind is not in the fixture`);
      continue;
    }
    root.args.forEach(argument => filter(root.name, argument, root.name));
    peer(root.name, 'many', root, root.name);
  }
  return problems;
}

describe('the rack queries against the captured schema', () => {
  it.each([
    ['SITE_RACKS_QUERY', SITE_RACKS_QUERY],
    ['RACK_QUERY', RACK_QUERY],
    ['SERVERS_QUERY', SERVERS_QUERY],
    ['RacksPage LIST_QUERY', LIST_QUERY],
    ['RacksPage DETAIL_QUERY', DETAIL_QUERY],
  ])('%s names only fields LocationRack and its peers have', (_name, query) => {
    expect(missing(query)).toEqual([]);
  });

  it('would have caught the fields that broke the page', () => {
    // Proven non-empty beside the empty results above: a walker that reported
    // nothing for everything would pass them all.
    const broken = `
      query ($id: ID!) {
        LocationRack(ids: [$id], shortname__value: "x", height__value: 2) {
          edges { node {
            facility_id { value }
            height { value }
            mounted_devices { edges { node { id } } }
            devices { edges { node { position { value } role { value } } } }
          } }
        }
      }
    `;
    expect(missing(broken)).toEqual([
      'LocationRack(height__value): not a filter LocationRack offers',
      'LocationRack.edges.node.facility_id: LocationRack has no field facility_id',
      'LocationRack.edges.node.height: LocationRack has no field height',
      'LocationRack.edges.node.mounted_devices: LocationRack has no field mounted_devices',
      'LocationRack.edges.node.devices.edges.node.role: DcimPhysicalDevice has no field role',
    ]);
  });
});

const device = (
  label: string,
  position: number | null,
  options: { typename?: string; height?: number | null; face?: string } = {},
) => ({
  node: {
    id: label,
    display_label: label,
    __typename: options.typename ?? 'DcimFabricSwitch',
    position: { value: position },
    rack_face: { value: options.face ?? 'front' },
    device_type: {
      node: {
        name: { value: 'Arista cEOS-LAB' },
        height: { value: options.height ?? 1 },
      },
    },
  },
});

const rack = (...devices: ReturnType<typeof device>[]): RackNode => ({
  id: 'rack',
  display_label: 'K8S_LEAFS',
  name: { value: 'K8S_LEAFS' },
  parent: { node: { display_label: 'Hall-OTTERNET' } },
  devices: { edges: devices },
});

const server = (label: string, rackId = 'rack'): ServerNode => ({
  id: label,
  display_label: label,
  __typename: 'ComputePhysicalServer',
  role: { value: 'compute' },
  rack: { node: { id: rackId } },
});

describe('layoutRack', () => {
  it('lists a rack with no positions, switches before servers, in name order', () => {
    // The shape of every rack in this lab: no position on anything.
    const layout = layoutRack(
      rack(
        device('leaf-otternet-pod1-1-2', null),
        device('leaf-otternet-pod1-1-1', null),
      ),
      [server('k8s-node10'), server('k8s-node2')],
    );

    expect(layout.units).toBe(0);
    expect(layout.positioned).toEqual([]);
    expect(layout.unpositioned.map(slot => slot.label)).toEqual([
      'leaf-otternet-pod1-1-1',
      'leaf-otternet-pod1-1-2',
      'k8s-node2',
      'k8s-node10',
    ]);
    expect(summarise(layout)).toBe('2 network devices · 2 servers');
  });

  it('draws positioned devices at their U and sizes the elevation to the highest', () => {
    const layout = layoutRack(
      rack(device('b', 3, { height: 2 }), device('a', 1), device('c', null)),
      [],
    );

    expect(layout.positioned.map(slot => [slot.label, slot.position])).toEqual([
      ['a', 1],
      ['b', 3],
    ]);
    expect(layout.units).toBe(4);
    expect(layout.unpositioned.map(slot => slot.label)).toEqual(['c']);
    expect(summarise(layout)).toBe(
      '3 network devices · 0 servers · 2 at a rack position',
    );
  });

  it('tells routers, firewalls, switches and servers apart', () => {
    const layout = layoutRack(
      rack(
        device('r', null, { typename: 'DcimDevice' }),
        device('f', null, { typename: 'SecurityFirewall' }),
        device('s', null),
      ),
      [server('h')],
    );

    expect(
      Object.fromEntries(
        layout.unpositioned.map(slot => [slot.label, slot.family]),
      ),
    ).toEqual({ f: 'firewall', r: 'router', s: 'switch', h: 'server' });
  });

  it('treats a type with no height as 1U, and keeps the face', () => {
    const [slot] = layoutRack(
      rack(device('a', 5, { height: null, face: 'rear' })),
      [],
    ).positioned;

    expect(slot.height).toBe(1);
    expect(slot.face).toBe('rear');
  });
});

describe('serversIn', () => {
  it('keeps only the servers pointing at that rack', () => {
    const servers = [server('a', 'r1'), server('b', 'r2'), server('c', 'r1')];

    expect(serversIn('r1', servers).map(s => s.id)).toEqual(['a', 'c']);
  });
});
