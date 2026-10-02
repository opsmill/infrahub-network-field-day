/**
 * What the topology drawing asks Infrahub for, and how the answer is laid out.
 * No React here, so the layout is tested directly.
 *
 * A cable is a `DcimConnector` (`NetworkLink` here) whose `connected_endpoints`
 * are the two interfaces it joins. The interface's `device` is a generic, and
 * `role` is not on the generic -- asking for it there fails the whole query --
 * so it is read through a fragment per concrete device kind. Only the kinds that
 * carry connectors in this lab are named; the WAN routers and the firewall have
 * no connector objects, so they do not appear here.
 */

export const TOPOLOGY_QUERY = `
  query {
    DcimConnector {
      count
      edges {
        node {
          id
          display_label
          medium { value }
          connected_endpoints {
            edges {
              node {
                id
                ... on DcimInterface {
                  name { value }
                  status { value }
                  device {
                    node {
                      id
                      display_label
                      __typename
                      ... on DcimFabricSwitch { role { value } }
                      ... on DcimDevice { role { value } }
                      ... on ComputePhysicalServer { role { value } }
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
`;

export type EndpointNode = {
  id: string;
  name?: { value: string | null };
  status?: { value: string | null };
  device?: {
    node: {
      id: string;
      display_label: string;
      __typename: string;
      role?: { value: string | null };
    } | null;
  } | null;
};

export type ConnectorNode = {
  id: string;
  display_label: string;
  medium?: { value: string | null } | null;
  connected_endpoints: { edges: { node: EndpointNode }[] };
};

export type TopologyData = {
  DcimConnector: { count: number; edges: { node: ConnectorNode }[] };
};

/**
 * Rows, top to bottom. The fabric sits on top -- spines, then leaves -- and
 * everything that hangs off the leaves sits below: servers, the firewall and
 * the first WAN hop in one row, then each further hop out to the customer.
 * Which row a device is on is its distance from the fabric, not its importance,
 * which is what lets one picture hold the fabric, the perimeter and the WAN.
 */
export type Tier = number;

const TIER_BY_ROLE: Record<string, Tier> = {
  super_spine: 0,
  spine: 0,
  leaf: 1,
  border_leaf: 1,
  l2leaf: 1,
  compute: 2,
  firewall: 2,
  isp_core: 2,
  branch_router: 2,
  isp_edge: 3,
  internet_edge: 3,
  customer_edge: 4,
};

/** An unrecognised role is a leaf-level thing: it has to sit somewhere. */
export function tierOf(role: string | null | undefined): Tier {
  return (role ? TIER_BY_ROLE[role] : undefined) ?? 1;
}

/** What a device is, for colour and for the summary. */
export type Group = 'spine' | 'leaf' | 'firewall' | 'wan' | 'server';

/**
 * Where a device lives, for the toggles. Decided by kind and role rather than
 * by `location`, which most devices here do not have. The firewall is the data
 * centre's perimeter, so it belongs to the data centre.
 */
export type Domain = 'dc' | 'wan' | 'branch';

export const DOMAINS: Domain[] = ['dc', 'wan', 'branch'];

export const DOMAIN_LABELS: Record<Domain, string> = {
  dc: 'Data centre',
  wan: 'WAN',
  branch: 'Branch',
};

const WAN_ROLES = new Set([
  'isp_edge',
  'isp_core',
  'internet_edge',
  'customer_edge',
]);

export function domainOf(kind: string, role: string): Domain {
  if (role === 'branch_router') return 'branch';
  if (kind === 'DcimDevice' && WAN_ROLES.has(role)) return 'wan';
  // An unrecognised router is not the data centre's; showing it with the WAN is
  // wrong less often than hiding it with the fabric.
  if (kind === 'DcimDevice') return 'wan';
  return 'dc';
}

export const GROUP_LABELS: Record<Group, string> = {
  spine: 'Spine',
  leaf: 'Leaf',
  firewall: 'Firewall',
  wan: 'WAN router',
  server: 'Server',
};

/** By kind first: a firewall has no role at all, and `leaf` is a switch. */
export function groupOf(kind: string, role: string): Group {
  if (kind === 'SecurityFirewall') return 'firewall';
  if (kind === 'ComputePhysicalServer') return 'server';
  if (kind === 'DcimDevice') return 'wan';
  return role.includes('spine') ? 'spine' : 'leaf';
}

export type TopologyDevice = {
  id: string;
  label: string;
  kind: string;
  role: string;
  group: Group;
  domain: Domain;
  tier: Tier;
  /** Cables on each side of the node, for handle spacing. */
  up: number;
  down: number;
  left: number;
  right: number;
  x: number;
  y: number;
};

export type TopologyLink = {
  id: string;
  label: string;
  medium: string;
  /** The upper end, or the left one for a cable between two devices in a row. */
  from: string;
  to: string;
  fromPort: string;
  toPort: string;
  /** Handle ids, one per cable, so parallel links do not draw on one line. */
  fromHandle: string;
  toHandle: string;
  /** Joins two devices in the same row, so it runs side to side. */
  sideways: boolean;
  /** Either interface not active: the cable is drawn as a fault. */
  healthy: boolean;
};

export type Topology = {
  devices: TopologyDevice[];
  links: TopologyLink[];
  /** Cables that could not be drawn, and why, rather than silently dropped. */
  skipped: string[];
};

export const NODE_WIDTH = 170;
export const NODE_HEIGHT = 58;
const X_GAP = 70;
const Y_GAP = 170;

type Device = NonNullable<NonNullable<EndpointNode['device']>['node']>;
type End = { device: Device; port: string; active: boolean };
type Raw = { id: string; label: string; medium: string; a: End; b: End };

function readConnector(node: ConnectorNode): Raw | string {
  const ends = node.connected_endpoints.edges.map(edge => edge.node);
  if (ends.length !== 2) {
    return `${node.display_label}: ${ends.length} endpoints, expected 2`;
  }
  const [a, b] = ends.map(end => ({
    device: end.device?.node ?? null,
    port: end.name?.value ?? '?',
    active: (end.status?.value ?? 'active') === 'active',
  }));
  if (!a.device || !b.device) {
    return `${node.display_label}: an endpoint is not on a device`;
  }
  return {
    id: node.id,
    label: node.display_label,
    medium: node.medium?.value ?? '',
    a: { ...a, device: a.device },
    b: { ...b, device: b.device },
  };
}

/** The mean x of a device's neighbours, so each row lines up under its peers. */
function barycentre(
  id: string,
  neighbours: Map<string, string[]>,
  xs: Map<string, number>,
): number | undefined {
  const known = (neighbours.get(id) ?? [])
    .map(peer => xs.get(peer))
    .filter((x): x is number => x !== undefined);
  if (known.length === 0) return undefined;
  return known.reduce((sum, x) => sum + x, 0) / known.length;
}

/**
 * Pushes neighbours apart until each is a node-width from the next, in order,
 * moving both sides of a collision equally. A cluster that wanted one spot ends
 * up centred on it rather than shoved to one side, which is what keeps a
 * device under the peer it hangs from.
 */
function spread(xs: number[]) {
  const gap = NODE_WIDTH + X_GAP;
  for (let pass = 0; pass < 200; pass++) {
    let moved = false;
    for (let i = 1; i < xs.length; i++) {
      const overlap = gap - (xs[i] - xs[i - 1]);
      if (overlap > 0.5) {
        xs[i - 1] -= overlap / 2;
        xs[i] += overlap / 2;
        moved = true;
      }
    }
    if (!moved) return;
  }
}

type Oriented = { raw: Raw; first: End; second: End; sideways: boolean };

/**
 * Rows by role, cables between them. Deterministic: names order the first row,
 * and every later row is ordered by where its neighbours already are, so the
 * drawing is the same on every load and cables cross as little as a strictly
 * layered drawing allows.
 */
export function buildTopology(data: TopologyData): Topology {
  const skipped: string[] = [];
  const raws: Raw[] = [];
  for (const edge of data.DcimConnector.edges) {
    const raw = readConnector(edge.node);
    if (typeof raw === 'string') skipped.push(raw);
    else raws.push(raw);
  }

  const byId = new Map<string, TopologyDevice>();
  const add = (device: Device) => {
    if (byId.has(device.id)) return;
    // A firewall has no role attribute; its kind is the only thing that says so.
    const role =
      device.role?.value ??
      (device.__typename === 'SecurityFirewall' ? 'firewall' : 'unknown');
    byId.set(device.id, {
      id: device.id,
      label: device.display_label,
      kind: device.__typename,
      role,
      group: groupOf(device.__typename, role),
      domain: domainOf(device.__typename, role),
      tier: tierOf(role),
      up: 0,
      down: 0,
      left: 0,
      right: 0,
      x: 0,
      y: 0,
    });
  };
  raws.forEach(raw => {
    add(raw.a.device);
    add(raw.b.device);
  });

  const neighbours = new Map<string, string[]>();
  const link = (from: string, to: string) =>
    neighbours.set(from, [...(neighbours.get(from) ?? []), to]);
  raws.forEach(({ a, b }) => {
    link(a.device.id, b.device.id);
    link(b.device.id, a.device.id);
  });

  // Rows are the tiers in use, so a missing tier leaves no blank band.
  const tiers = [...new Set([...byId.values()].map(d => d.tier))].sort(
    (l, r) => l - r,
  );
  const rows: TopologyDevice[][] = [];
  const xs = new Map<string, number>();
  tiers.forEach((tier, rank) => {
    const row = [...byId.values()].filter(d => d.tier === tier);
    row.sort((l, r) => {
      const lx = barycentre(l.id, neighbours, xs);
      const rx = barycentre(r.id, neighbours, xs);
      if (lx !== undefined && rx !== undefined && lx !== rx) return lx - rx;
      return l.label.localeCompare(r.label);
    });
    row.forEach((device, index) => {
      device.x = index * (NODE_WIDTH + X_GAP);
      device.y = rank * Y_GAP;
      xs.set(device.id, device.x);
    });
    rows.push(row);
  });

  // The pass above fixed each row's ORDER. Positions come next: a row sits
  // under the devices it is cabled to, so the WAN hangs off the border leaf and
  // the spines sit over the leaves rather than every row being centred on the
  // widest. Rows are placed top down, then the top row is re-centred over its
  // own neighbours, which only exist once the rows below are placed.
  const desired = (device: TopologyDevice, above: boolean) => {
    const known = (neighbours.get(device.id) ?? [])
      .map(id => byId.get(id)!)
      .filter(peer =>
        above ? peer.tier < device.tier : peer.tier > device.tier,
      )
      .map(peer => peer.x);
    return known.length
      ? known.reduce((sum, x) => sum + x, 0) / known.length
      : undefined;
  };
  const place = (row: TopologyDevice[], above: boolean) => {
    const wanted = row.map(device => desired(device, above) ?? device.x);
    spread(wanted);
    row.forEach((device, index) => {
      device.x = wanted[index];
    });
  };
  rows.slice(1).forEach(row => place(row, true));
  if (rows.length > 0) place(rows[0], false);
  const leftmost = Math.min(...[...byId.values()].map(d => d.x), 0);
  for (const device of byId.values())
    device.x = Math.round(device.x - leftmost);

  // Orient every cable. Between rows it runs top to bottom; inside a row, left
  // to right by where placement put the devices, so the choice never depends on
  // which endpoint Infrahub listed first.
  const oriented: Oriented[] = raws
    .map(raw => {
      const da = byId.get(raw.a.device.id)!;
      const db = byId.get(raw.b.device.id)!;
      const sideways = da.tier === db.tier;
      const swap = sideways ? da.x > db.x : da.tier > db.tier;
      return swap
        ? { raw, first: raw.b, second: raw.a, sideways }
        : { raw, first: raw.a, second: raw.b, sideways };
    })
    .sort((l, r) => l.raw.label.localeCompare(r.raw.label));

  // One handle per cable at each end, ordered by the peer's x, so cables leave
  // a node in the same left-to-right order as the nodes they run to.
  const groups = new Map<string, Oriented[]>();
  const bucket = (id: string, kind: string, item: Oriented) =>
    groups.set(`${id}:${kind}`, [...(groups.get(`${id}:${kind}`) ?? []), item]);
  oriented.forEach(item => {
    const f = item.first.device.id;
    const s = item.second.device.id;
    bucket(f, item.sideways ? 'right' : 'down', item);
    bucket(s, item.sideways ? 'left' : 'up', item);
  });
  const handleIndex = new Map<string, number>();
  for (const [key, items] of groups) {
    const [id, kind] = key.split(':') as [
      string,
      'down' | 'up' | 'right' | 'left',
    ];
    const peer = (item: Oriented) =>
      item.first.device.id === id
        ? item.second.device.id
        : item.first.device.id;
    items.sort((l, r) => byId.get(peer(l))!.x - byId.get(peer(r))!.x);
    items.forEach((item, index) =>
      handleIndex.set(`${key}:${item.raw.id}`, index),
    );
    byId.get(id)![kind] = items.length;
  }

  const links: TopologyLink[] = oriented.map(
    ({ raw, first, second, sideways }) => {
      const fromKind = sideways ? 'right' : 'down';
      const toKind = sideways ? 'left' : 'up';
      const index = (id: string, kind: string) =>
        handleIndex.get(`${id}:${kind}:${raw.id}`);
      return {
        id: raw.id,
        label: raw.label,
        medium: raw.medium,
        from: first.device.id,
        to: second.device.id,
        fromPort: first.port,
        toPort: second.port,
        fromHandle: `${sideways ? 'r' : 'out'}-${index(
          first.device.id,
          fromKind,
        )}`,
        toHandle: `${sideways ? 'l' : 'in'}-${index(second.device.id, toKind)}`,
        sideways,
        healthy: first.active && second.active,
      };
    },
  );

  return { devices: [...byId.values()], links, skipped };
}

/** `Ethernet10` is long on a cable; `Et10` is what an operator types. */
export function shortPort(name: string): string {
  return name.replace(/^Ethernet/, 'Et').replace(/^ethernet-/, 'e-');
}

const NOUNS: Record<Group, [string, string]> = {
  spine: ['spine', 'spines'],
  leaf: ['leaf', 'leaves'],
  firewall: ['firewall', 'firewalls'],
  wan: ['WAN router', 'WAN routers'],
  server: ['server', 'servers'],
};

/** The sentence under the title. */
export function summarise(topology: Topology): string {
  const parts = (Object.keys(NOUNS) as Group[])
    .map(group => ({
      group,
      count: topology.devices.filter(d => d.group === group).length,
    }))
    .filter(entry => entry.count > 0)
    .map(({ group, count }) => `${count} ${NOUNS[group][count === 1 ? 0 : 1]}`);
  parts.push(`${topology.links.length} cables`);
  const down = topology.links.filter(l => !l.healthy).length;
  if (down) parts.push(`${down} not active`);
  return parts.join(' · ');
}

/**
 * Only the devices in the chosen domains, and only the cables with both ends
 * still showing. Positions are untouched: toggling a domain hides it rather than
 * redrawing the rest, so nothing jumps while you look at it.
 */
export function filterTopology(
  topology: Topology,
  domains: Set<Domain>,
): Topology {
  const shown = new Set(
    topology.devices.filter(d => domains.has(d.domain)).map(d => d.id),
  );
  return {
    devices: topology.devices.filter(d => shown.has(d.id)),
    links: topology.links.filter(l => shown.has(l.from) && shown.has(l.to)),
    skipped: topology.skipped,
  };
}
