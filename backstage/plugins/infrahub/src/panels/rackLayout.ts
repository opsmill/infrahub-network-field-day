/**
 * What the rack drawings ask Infrahub for, and how the answer is laid out.
 * No React here, so the queries and the layout are tested directly -- the
 * queries against a schema fixture captured from the live instance.
 *
 * This schema's `LocationRack` has no `height`, no `facility_id` and no
 * `mounted_devices`; those came from an upstream example schema and asking for
 * any of them fails the whole query. What it does have:
 *
 *  - `devices`, peering the `DcimPhysicalDevice` generic, which carries
 *    `position`, `rack_face` and `device_type` for the fabric switches, the WAN
 *    routers and the firewall alike -- so no fragment per kind is needed.
 *  - Servers are NOT among them. `ComputePhysicalServer` inherits
 *    `DcimGenericDevice` only and points at its rack through its own `rack`
 *    relationship, which has no reverse on the rack. They are fetched by a
 *    second root field filtered on that relationship.
 */

export const DEVICE_FIELDS = `
  id
  display_label
  __typename
  position { value }
  rack_face { value }
  device_type { node { name { value } height { value } } }
`;

export const SERVER_FIELDS = `
  id
  display_label
  __typename
  role { value }
  rack { node { id } }
`;

export const RACK_FIELDS = `
  id
  display_label
  name { value }
  parent { node { display_label } }
  devices { edges { node { ${DEVICE_FIELDS} } } }
`;

/** On a site: every rack whose parent it is. */
export const SITE_RACKS_QUERY = `
  query ($id: ID!) {
    LocationRack(parent__ids: [$id]) {
      edges { node { ${RACK_FIELDS} } }
    }
  }
`;

/** The servers in a set of racks, once the racks are known. */
export const SERVERS_QUERY = `
  query ($ids: [ID]) {
    ComputePhysicalServer(rack__ids: $ids) {
      edges { node { ${SERVER_FIELDS} } }
    }
  }
`;

/** On a rack's own page: that rack and its servers, in one request. */
export const RACK_QUERY = `
  query ($id: ID!) {
    LocationRack(ids: [$id]) {
      edges { node { ${RACK_FIELDS} } }
    }
    ComputePhysicalServer(rack__ids: [$id]) {
      edges { node { ${SERVER_FIELDS} } }
    }
  }
`;

export type DeviceNode = {
  id: string;
  display_label: string;
  __typename: string;
  position: { value: number | null };
  rack_face: { value: string | null };
  device_type: {
    node: {
      name: { value: string };
      height: { value: number | null };
    } | null;
  } | null;
};

export type ServerNode = {
  id: string;
  display_label: string;
  __typename: string;
  role: { value: string | null };
  rack: { node: { id: string } | null } | null;
};

export type RackNode = {
  id: string;
  display_label: string;
  name: { value: string };
  parent: { node: { display_label: string } | null } | null;
  devices: { edges: { node: DeviceNode }[] };
};

export type RacksResult = { LocationRack: { edges: { node: RackNode }[] } };
export type ServersResult = {
  ComputePhysicalServer: { edges: { node: ServerNode }[] };
};

/** One thing to draw, whichever kind it came from. */
export type Slot = {
  id: string;
  label: string;
  /** `switch`, `router`, `firewall` or `server`, for the colour and the caption. */
  family: 'switch' | 'router' | 'firewall' | 'server' | 'device';
  /** What it is, for the right-hand side of the bar. */
  detail?: string;
  position: number | null;
  height: number;
  face: string;
};

export type RackLayout = {
  /** Height of the drawn elevation: the top of the highest positioned device. */
  units: number;
  /** Drawn at their U. */
  positioned: Slot[];
  /** No `position` in Infrahub: listed in name order rather than guessed. */
  unpositioned: Slot[];
};

const byName = new Intl.Collator(undefined, { numeric: true });

function family(typename: string, typeName?: string): Slot['family'] {
  if (typename === 'ComputePhysicalServer') return 'server';
  if (typename === 'SecurityFirewall') return 'firewall';
  if (typename === 'DcimFabricSwitch') return 'switch';
  if (typeName?.toLowerCase().includes('router')) return 'router';
  return typename === 'DcimDevice' ? 'router' : 'device';
}

export function deviceSlot(device: DeviceNode): Slot {
  const type = device.device_type?.node;
  return {
    id: device.id,
    label: device.display_label,
    family: family(device.__typename, type?.name.value),
    detail: type?.name.value?.replace('Generic ', ''),
    position: device.position.value,
    height: Math.max(1, type?.height.value ?? 1),
    face: device.rack_face.value ?? 'front',
  };
}

export function serverSlot(server: ServerNode): Slot {
  return {
    id: server.id,
    label: server.display_label,
    family: 'server',
    detail: server.role.value ?? 'server',
    position: null,
    height: 1,
    face: 'front',
  };
}

/**
 * Positioned devices are drawn where Infrahub says they are; the rest are
 * listed, switches and routers before servers, each in name order. Nothing in
 * this lab records a position, and a made-up U would read as a fact.
 */
export function layoutRack(rack: RackNode, servers: ServerNode[]): RackLayout {
  const slots = [
    ...rack.devices.edges.map(edge => deviceSlot(edge.node)),
    ...servers.map(serverSlot),
  ];
  const positioned = slots
    .filter(slot => slot.position !== null && slot.position > 0)
    .sort((a, b) => a.position! - b.position!);
  const unpositioned = slots
    .filter(slot => !positioned.includes(slot))
    .sort(
      (a, b) =>
        Number(a.family === 'server') - Number(b.family === 'server') ||
        byName.compare(a.label, b.label),
    );
  const units = positioned.reduce(
    (top, slot) => Math.max(top, slot.position! + slot.height - 1),
    0,
  );
  return { units, positioned, unpositioned };
}

/** The servers that belong to one rack, out of a result covering several. */
export function serversIn(rackId: string, servers: ServerNode[]) {
  return servers.filter(server => server.rack?.node?.id === rackId);
}

/** One line saying what a rack holds, without claiming a capacity nobody modelled. */
export function summarise(layout: RackLayout) {
  const all = [...layout.positioned, ...layout.unpositioned];
  const servers = all.filter(slot => slot.family === 'server').length;
  const network = all.length - servers;
  const parts = [
    `${network} network device${network === 1 ? '' : 's'}`,
    `${servers} server${servers === 1 ? '' : 's'}`,
  ];
  if (layout.positioned.length > 0) {
    parts.push(`${layout.positioned.length} at a rack position`);
  }
  return parts.join(' · ');
}
