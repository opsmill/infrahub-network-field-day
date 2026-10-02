import {
  buildTopology,
  ConnectorNode,
  domainOf,
  filterTopology,
  groupOf,
  shortPort,
  summarise,
  tierOf,
  TopologyData,
} from './topologyLayout';

type Dev = { id: string; name: string; role: string; kind?: string };

const SPINE1: Dev = { id: 's1', name: 'spine1', role: 'spine' };
const SPINE2: Dev = { id: 's2', name: 'spine2', role: 'spine' };
const LEAF1: Dev = { id: 'l1', name: 'leaf1', role: 'leaf' };
const LEAF2: Dev = { id: 'l2', name: 'leaf2', role: 'leaf' };
const HOST: Dev = {
  id: 'h1',
  name: 'host1',
  role: 'compute',
  kind: 'ComputePhysicalServer',
};

const end = (dev: Dev, port: string, status = 'active') => ({
  node: {
    id: `${dev.id}-${port}`,
    name: { value: port },
    status: { value: status },
    device: {
      node: {
        id: dev.id,
        display_label: dev.name,
        __typename: dev.kind ?? 'DcimFabricSwitch',
        role: { value: dev.role },
      },
    },
  },
});

const cable = (
  name: string,
  a: ReturnType<typeof end>,
  b: ReturnType<typeof end>,
): ConnectorNode => ({
  id: name,
  display_label: name,
  medium: { value: 'copper' },
  connected_endpoints: { edges: [a, b] },
});

const data = (...cables: ConnectorNode[]): TopologyData => ({
  DcimConnector: {
    count: cables.length,
    edges: cables.map(node => ({ node })),
  },
});

describe('tierOf', () => {
  it('puts spines above leaves above servers', () => {
    expect(tierOf('spine')).toBe(0);
    expect(tierOf('leaf')).toBe(1);
    expect(tierOf('compute')).toBe(2);
  });

  it('keeps an unknown role on the leaf tier rather than losing the device', () => {
    expect(tierOf('mystery')).toBe(1);
    expect(tierOf(null)).toBe(1);
  });
});

describe('buildTopology', () => {
  const full = data(
    cable('a', end(LEAF1, 'Ethernet1'), end(SPINE1, 'Ethernet1')),
    cable('b', end(SPINE2, 'Ethernet1'), end(LEAF1, 'Ethernet2')),
    cable('c', end(LEAF2, 'Ethernet1'), end(SPINE1, 'Ethernet2')),
    cable('d', end(LEAF2, 'Ethernet2'), end(SPINE2, 'Ethernet2')),
    cable('e', end(HOST, 'eth1'), end(LEAF2, 'Ethernet10')),
  );

  it('orients every cable top to bottom whichever end Infrahub listed first', () => {
    const topology = buildTopology(full);
    const tier = (id: string) => topology.devices.find(d => d.id === id)!.tier;
    for (const link of topology.links) {
      expect(tier(link.from)).toBeLessThan(tier(link.to));
    }
    const a = topology.links.find(l => l.id === 'a')!;
    expect([a.from, a.fromPort, a.to, a.toPort]).toEqual([
      's1',
      'Ethernet1',
      'l1',
      'Ethernet1',
    ]);
  });

  it('is the same drawing however the cables arrive', () => {
    const forward = buildTopology(full);
    const reversed = buildTopology({
      DcimConnector: {
        count: 5,
        edges: [...full.DcimConnector.edges].reverse(),
      },
    });
    const positions = (t: typeof forward) =>
      Object.fromEntries(t.devices.map(d => [d.id, [d.x, d.y]]));
    expect(positions(reversed)).toEqual(positions(forward));
  });

  it('puts each tier on its own row and keeps nodes in a row apart', () => {
    const { devices } = buildTopology(full);
    const rows = new Set(devices.map(d => `${d.tier}:${d.y}`));
    expect(rows.size).toBe(3);
    for (const tier of [0, 1, 2]) {
      const xs = devices.filter(d => d.tier === tier).map(d => d.x);
      expect(new Set(xs).size).toBe(xs.length);
    }
  });

  it('gives every cable end its own handle, numbered from zero', () => {
    const topology = buildTopology(full);
    const spine1 = topology.devices.find(d => d.id === 's1')!;
    expect(spine1.down).toBe(2);
    const handles = topology.links
      .filter(l => l.from === 's1')
      .map(l => l.fromHandle)
      .sort();
    expect(handles).toEqual(['out-0', 'out-1']);
    const leaf2 = topology.devices.find(d => d.id === 'l2')!;
    expect(leaf2.up).toBe(2);
    expect(leaf2.down).toBe(1);
  });

  it('orders a node handles by where the far ends are, so cables do not cross at the node', () => {
    const topology = buildTopology(full);
    const x = (id: string) => topology.devices.find(d => d.id === id)!.x;
    const fromSpine1 = topology.links
      .filter(l => l.from === 's1')
      .sort((l, r) => l.fromHandle.localeCompare(r.fromHandle));
    expect(x(fromSpine1[0].to)).toBeLessThan(x(fromSpine1[1].to));
  });

  it('draws a cable with an inactive end as a fault', () => {
    const topology = buildTopology(
      data(
        cable(
          'x',
          end(LEAF1, 'Ethernet1', 'maintenance'),
          end(SPINE1, 'Ethernet1'),
        ),
      ),
    );
    expect(topology.links[0].healthy).toBe(false);
    expect(summarise(topology)).toContain('1 not active');
  });

  it('names a cable it cannot draw instead of dropping it silently', () => {
    const odd: ConnectorNode = {
      id: 'odd',
      display_label: 'odd-link',
      connected_endpoints: { edges: [end(LEAF1, 'Ethernet1')] },
    };
    const topology = buildTopology(data(odd));
    expect(topology.links).toHaveLength(0);
    expect(topology.skipped).toEqual(['odd-link: 1 endpoints, expected 2']);
  });

  it('handles a fabric with no cables', () => {
    const topology = buildTopology(data());
    expect(topology.devices).toEqual([]);
    expect(summarise(topology)).toBe('0 cables');
  });
});

describe('the perimeter and the WAN', () => {
  const FW: Dev = { id: 'f1', name: 'fw1', role: '', kind: 'SecurityFirewall' };
  const PE2: Dev = {
    id: 'p2',
    name: 'isp-pe2',
    role: 'isp_core',
    kind: 'DcimDevice',
  };
  const PE1: Dev = {
    id: 'p1',
    name: 'isp-pe1',
    role: 'isp_edge',
    kind: 'DcimDevice',
  };
  const CE: Dev = {
    id: 'c1',
    name: 'acme-ce',
    role: 'customer_edge',
    kind: 'DcimDevice',
  };

  // A firewall has no role attribute, so it arrives without one.
  const fwEnd = (port: string) => {
    const e = end(FW, port);
    delete (e.node.device.node as { role?: unknown }).role;
    return e;
  };

  const wan = data(
    cable('a', end(SPINE1, 'Ethernet1'), end(LEAF1, 'Ethernet1')),
    cable('b', end(LEAF1, 'Ethernet10'), fwEnd('ge-0/0/0')),
    cable('c', end(LEAF1, 'Ethernet12'), end(PE2, 'ethernet-1/2')),
    cable('d', end(PE2, 'ethernet-1/1'), end(PE1, 'ethernet-1/1')),
    cable('e', end(PE1, 'ethernet-1/2'), end(CE, 'ethernet-1/1')),
  );

  it('reads a firewall with no role as a firewall', () => {
    const fw = buildTopology(wan).devices.find(d => d.id === 'f1')!;
    expect(fw.role).toBe('firewall');
    expect(fw.group).toBe('firewall');
    expect(groupOf('SecurityFirewall', 'unknown')).toBe('firewall');
  });

  it('hangs the firewall and the first WAN hop below the leaf, then walks out to the customer', () => {
    const { devices } = buildTopology(wan);
    const y = (id: string) => devices.find(d => d.id === id)!.y;
    expect(y('s1')).toBeLessThan(y('l1'));
    expect(y('l1')).toBeLessThan(y('f1'));
    expect(y('f1')).toBe(y('p2'));
    expect(y('p2')).toBeLessThan(y('p1'));
    expect(y('p1')).toBeLessThan(y('c1'));
  });

  it('leaves no blank band when a tier is unused', () => {
    const ys = [...new Set(buildTopology(wan).devices.map(d => d.y))].sort(
      (l, r) => l - r,
    );
    ys.forEach((y, i) => expect(y).toBe(i * ys[1]));
  });

  it('puts the firewall under the leaf it is cabled to', () => {
    const { devices } = buildTopology(wan);
    const x = (id: string) => devices.find(d => d.id === id)!.x;
    // Alone in its row with the provider router, both hang off the one leaf.
    expect(Math.abs(x('f1') - x('l1'))).toBeLessThanOrEqual(260);
  });

  it('counts each group in the summary', () => {
    expect(summarise(buildTopology(wan))).toBe(
      '1 spine · 1 leaf · 1 firewall · 3 WAN routers · 5 cables',
    );
  });
});

describe('cables between devices in one row', () => {
  const peers = data(
    cable('m1', end(LEAF1, 'Ethernet3'), end(LEAF2, 'Ethernet3')),
    cable('m2', end(LEAF2, 'Ethernet4'), end(LEAF1, 'Ethernet4')),
    cable('u1', end(SPINE1, 'Ethernet1'), end(LEAF1, 'Ethernet1')),
    cable('u2', end(SPINE1, 'Ethernet2'), end(LEAF2, 'Ethernet1')),
  );

  it('runs sideways, left to right, whichever end was listed first', () => {
    const topology = buildTopology(peers);
    const x = (id: string) => topology.devices.find(d => d.id === id)!.x;
    for (const id of ['m1', 'm2']) {
      const link = topology.links.find(l => l.id === id)!;
      expect(link.sideways).toBe(true);
      expect(x(link.from)).toBeLessThan(x(link.to));
    }
  });

  it('gives each sideways cable its own handle on each side', () => {
    const topology = buildTopology(peers);
    const left = topology.devices.find(d => d.right > 0)!;
    const right = topology.devices.find(d => d.left > 0)!;
    expect([left.right, right.left]).toEqual([2, 2]);
    const sideways = topology.links.filter(l => l.sideways);
    expect(sideways.map(l => l.fromHandle).sort()).toEqual(['r-0', 'r-1']);
    expect(sideways.map(l => l.toHandle).sort()).toEqual(['l-0', 'l-1']);
  });

  it('keeps the cables between rows on the top and bottom handles', () => {
    const link = buildTopology(peers).links.find(l => l.id === 'u1')!;
    expect(link.sideways).toBe(false);
    expect(link.fromHandle).toMatch(/^out-/);
    expect(link.toHandle).toMatch(/^in-/);
  });
});

describe('domainOf', () => {
  it('splits the lab into data centre, WAN and branch', () => {
    expect(domainOf('DcimFabricSwitch', 'leaf')).toBe('dc');
    expect(domainOf('ComputePhysicalServer', 'compute')).toBe('dc');
    expect(domainOf('SecurityFirewall', 'firewall')).toBe('dc');
    expect(domainOf('DcimDevice', 'isp_core')).toBe('wan');
    expect(domainOf('DcimDevice', 'customer_edge')).toBe('wan');
    expect(domainOf('DcimDevice', 'internet_edge')).toBe('wan');
    expect(domainOf('DcimDevice', 'branch_router')).toBe('branch');
  });

  it('puts an unrecognised router with the WAN rather than the fabric', () => {
    expect(domainOf('DcimDevice', 'mystery')).toBe('wan');
  });
});

describe('filterTopology', () => {
  const BR: Dev = {
    id: 'b1',
    name: 'branch-rtr',
    role: 'branch_router',
    kind: 'DcimDevice',
  };
  const PE2: Dev = {
    id: 'p2',
    name: 'isp-pe2',
    role: 'isp_core',
    kind: 'DcimDevice',
  };
  const all = buildTopology(
    data(
      cable('a', end(SPINE1, 'Ethernet1'), end(LEAF1, 'Ethernet1')),
      cable('b', end(LEAF1, 'Ethernet12'), end(PE2, 'ethernet-1/2')),
      cable('c', end(LEAF1, 'Ethernet13'), end(BR, 'ethernet-1/1')),
    ),
  );

  it('keeps everything when every domain is on', () => {
    const t = filterTopology(all, new Set(['dc', 'wan', 'branch']));
    expect(t.devices).toHaveLength(4);
    expect(t.links).toHaveLength(3);
  });

  it('drops a domain and the cables that ran to it, and only those', () => {
    const t = filterTopology(all, new Set(['dc', 'branch']));
    expect(t.devices.map(d => d.id).sort()).toEqual(['b1', 'l1', 's1']);
    expect(t.links.map(l => l.id).sort()).toEqual(['a', 'c']);
  });

  it('shows no cable between devices when one end is hidden', () => {
    expect(filterTopology(all, new Set(['wan'])).links).toEqual([]);
  });

  it('leaves positions alone, so toggling never moves what is still there', () => {
    const t = filterTopology(all, new Set(['dc']));
    for (const d of t.devices) {
      const before = all.devices.find(x => x.id === d.id)!;
      expect([d.x, d.y]).toEqual([before.x, before.y]);
    }
  });
});

describe('shortPort', () => {
  it('shortens EOS and SR Linux names and leaves others alone', () => {
    expect(shortPort('Ethernet10')).toBe('Et10');
    expect(shortPort('ethernet-1/3')).toBe('e-1/3');
    expect(shortPort('eth1')).toBe('eth1');
  });
});
