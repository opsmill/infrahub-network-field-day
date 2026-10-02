import { memo, useMemo, useState } from 'react';
import { useTheme } from '@material-ui/core/styles';
import {
  Background,
  BaseEdge,
  Controls,
  Edge,
  EdgeLabelRenderer,
  EdgeProps,
  getBezierPath,
  Handle,
  MiniMap,
  Node,
  NodeProps,
  Position,
  ReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Content,
  ContentHeader,
  Header,
  Page,
  Progress,
  ResponseErrorPanel,
  SupportButton,
} from '@backstage/core-components';
import { useInfrahubQuery } from '../client';
import { useKindColours, useStatusColours } from '../colours';
import {
  buildTopology,
  NODE_HEIGHT,
  NODE_WIDTH,
  shortPort,
  summarise,
  Group,
  GROUP_LABELS,
  Topology,
  TOPOLOGY_QUERY,
  TopologyData,
} from '../panels/topologyLayout';

type DeviceData = {
  label: string;
  role: string;
  kind: string;
  up: number;
  down: number;
  left: number;
  right: number;
  colour: string;
  dimmed: boolean;
};

type CableData = {
  fromPort: string;
  toPort: string;
  healthy: boolean;
  sideways: boolean;
  dimmed: boolean;
  colour: string;
};

/** Evenly spaced along an edge, so each cable gets a handle of its own. */
const spread = (index: number, count: number) =>
  `${((index + 1) / (count + 1)) * 100}%`;

const hidden = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0 };

const DeviceNode = memo(({ data }: NodeProps<Node<DeviceData>>) => {
  const theme = useTheme();
  return (
    <div
      style={{
        width: NODE_WIDTH,
        height: NODE_HEIGHT,
        boxSizing: 'border-box',
        border: `2px solid ${data.colour}`,
        borderRadius: 8,
        padding: '6px 10px',
        background: theme.palette.background.paper,
        color: theme.palette.text.primary,
        opacity: data.dimmed ? 0.25 : 1,
        transition: 'opacity 120ms',
        // A coloured stripe is what tells a switch from a server at a glance.
        boxShadow: `inset 5px 0 0 ${data.colour}`,
        paddingLeft: 16,
      }}
    >
      {Array.from({ length: data.up }, (_, i) => (
        <Handle
          key={`in-${i}`}
          id={`in-${i}`}
          type="target"
          position={Position.Top}
          style={{ ...hidden, left: spread(i, data.up) }}
        />
      ))}
      <div style={{ fontSize: 10, opacity: 0.7, textTransform: 'uppercase' }}>
        {data.role.replace(/_/g, ' ')}
      </div>
      <div
        style={{
          fontWeight: 600,
          fontSize: 12.5,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
        title={data.label}
      >
        {data.label}
      </div>
      {Array.from({ length: data.left }, (_, i) => (
        <Handle
          key={`l-${i}`}
          id={`l-${i}`}
          type="target"
          position={Position.Left}
          style={{ ...hidden, top: spread(i, data.left) }}
        />
      ))}
      {Array.from({ length: data.right }, (_, i) => (
        <Handle
          key={`r-${i}`}
          id={`r-${i}`}
          type="source"
          position={Position.Right}
          style={{ ...hidden, top: spread(i, data.right) }}
        />
      ))}
      {Array.from({ length: data.down }, (_, i) => (
        <Handle
          key={`out-${i}`}
          id={`out-${i}`}
          type="source"
          position={Position.Bottom}
          style={{ ...hidden, left: spread(i, data.down) }}
        />
      ))}
    </div>
  );
});

/**
 * A cable, with the interface at each end named beside the device it is on.
 * Positioned at a fixed fraction along the path rather than at the middle: with
 * ten cables fanning out, a label per midpoint is a pile of text on one line.
 */
const CableEdge = memo((props: EdgeProps<Edge<CableData>>) => {
  const theme = useTheme();
  const data = props.data!;
  const [path] = getBezierPath(props);
  const text = {
    position: 'absolute' as const,
    pointerEvents: 'none' as const,
    fontSize: 10,
    padding: '0 3px',
    borderRadius: 3,
    background: theme.palette.background.paper,
    color: theme.palette.text.secondary,
    opacity: data.dimmed ? 0.2 : 1,
    transform: 'translate(-50%, -50%)',
  };
  // Near each end, nudged inwards so the label clears the node's border.
  const near = (t: number) => {
    const sx = props.sourceX;
    const sy = props.sourceY;
    const tx = props.targetX;
    const ty = props.targetY;
    return { x: sx + (tx - sx) * t, y: sy + (ty - sy) * t };
  };
  const start = near(0.16);
  const end = near(0.84);

  return (
    <>
      <BaseEdge
        id={props.id}
        path={path}
        style={{
          stroke: data.colour,
          strokeWidth: props.selected ? 3 : 2,
          strokeDasharray: data.healthy ? undefined : '6 4',
          opacity: data.dimmed ? 0.12 : 0.9,
          transition: 'opacity 120ms',
        }}
      />
      <EdgeLabelRenderer>
        {data.sideways ? (
          // Two devices in a row sit a short gap apart, so both ports share one
          // label rather than crowding the ends.
          <div
            style={{
              ...text,
              left: (props.sourceX + props.targetX) / 2,
              top: (props.sourceY + props.targetY) / 2,
            }}
          >
            {shortPort(data.fromPort)} ↔ {shortPort(data.toPort)}
          </div>
        ) : (
          <>
            <div style={{ ...text, left: start.x, top: start.y }}>
              {shortPort(data.fromPort)}
            </div>
            <div style={{ ...text, left: end.x, top: end.y }}>
              {shortPort(data.toPort)}
            </div>
          </>
        )}
      </EdgeLabelRenderer>
    </>
  );
});

/** One colour per kind of device, from the theme like every other panel. */
const groupColours = (kinds: ReturnType<typeof useKindColours>) => ({
  spine: kinds.service,
  leaf: kinds.deviceAlt,
  firewall: kinds.place,
  wan: kinds.device,
  server: kinds.address,
});

// Outside the component: React Flow warns, and remounts every node, when these
// objects change identity between renders.
const nodeTypes = { device: DeviceNode };
const edgeTypes = { cable: CableEdge };

export function TopologyView(props: { topology: Topology; height?: number }) {
  const theme = useTheme();
  const kinds = useKindColours();
  const status = useStatusColours();
  const [hovered, setHovered] = useState<string | undefined>();

  const colourFor = (group: Group) => groupColours(kinds)[group];

  // A hovered device lights its own cables and the devices at their far ends;
  // everything else steps back. Hovering nothing dims nothing.
  const related = useMemo(() => {
    if (!hovered) return undefined;
    const set = new Set<string>([hovered]);
    props.topology.links.forEach(link => {
      if (link.from === hovered) set.add(link.to);
      if (link.to === hovered) set.add(link.from);
    });
    return set;
  }, [hovered, props.topology.links]);

  const nodes: Node<DeviceData>[] = props.topology.devices.map(device => ({
    id: device.id,
    type: 'device',
    position: { x: device.x, y: device.y },
    draggable: true,
    data: {
      label: device.label,
      role: device.role,
      kind: device.kind,
      up: device.up,
      down: device.down,
      left: device.left,
      right: device.right,
      colour: colourFor(device.group),
      dimmed: related ? !related.has(device.id) : false,
    },
  }));

  const edges: Edge<CableData>[] = props.topology.links.map(link => {
    const lit = !hovered || link.from === hovered || link.to === hovered;
    return {
      id: link.id,
      type: 'cable',
      source: link.from,
      target: link.to,
      sourceHandle: link.fromHandle,
      targetHandle: link.toHandle,
      data: {
        fromPort: link.fromPort,
        toPort: link.toPort,
        healthy: link.healthy,
        sideways: link.sideways,
        dimmed: !lit,
        colour: link.healthy ? theme.palette.text.secondary : status.error,
      },
    };
  });

  return (
    <div
      style={{
        height: props.height ?? 640,
        border: `1px solid ${theme.palette.divider}`,
        borderRadius: 4,
      }}
    >
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.15 }}
        nodesConnectable={false}
        elementsSelectable
        proOptions={{ hideAttribution: true }}
        onNodeMouseEnter={(_event, node) => setHovered(node.id)}
        onNodeMouseLeave={() => setHovered(undefined)}
        colorMode={theme.palette.type === 'dark' ? 'dark' : 'light'}
      >
        <Background color={theme.palette.divider} />
        <Controls showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={node =>
            (node.data as DeviceData | undefined)?.colour ?? kinds.neutral
          }
        />
      </ReactFlow>
    </div>
  );
}

function Legend() {
  const kinds = useKindColours();
  const status = useStatusColours();
  const swatch = (colour: string, dashed = false) => (
    <span
      style={{
        display: 'inline-block',
        width: 22,
        height: 0,
        borderTop: `3px ${dashed ? 'dashed' : 'solid'} ${colour}`,
        marginRight: 6,
        verticalAlign: 'middle',
      }}
    />
  );
  return (
    <div style={{ fontSize: 12, opacity: 0.85, margin: '10px 0 14px' }}>
      {(Object.keys(GROUP_LABELS) as Group[]).map(group => (
        <span key={group} style={{ marginRight: 16 }}>
          {swatch(groupColours(kinds)[group])}
          {GROUP_LABELS[group]}
        </span>
      ))}
      <span style={{ marginRight: 16 }}>
        {swatch(status.error, true)}Not active
      </span>
      <span>Hover a device to follow its cables</span>
    </div>
  );
}

export function TopologyPage() {
  const { data, loading, error } = useInfrahubQuery<TopologyData>(
    TOPOLOGY_QUERY,
    {},
    [],
  );
  const topology = useMemo(
    () => (data ? buildTopology(data) : undefined),
    [data],
  );

  return (
    <Page themeId="tool">
      <Header
        title="Fabric topology"
        subtitle="Every cable, read straight from Infrahub"
      />
      <Content>
        <ContentHeader title={topology ? summarise(topology) : 'Topology'}>
          <SupportButton>
            Drawn from the cable objects on the selected branch, so a link added
            on a branch shows up here before it is merged. Only cables Infrahub
            models are drawn: a device wired to something with no Infrahub
            object, such as the tooling bridge, shows fewer cables than the lab
            has.
          </SupportButton>
        </ContentHeader>

        {loading && <Progress />}
        {error && <ResponseErrorPanel error={error} />}

        {topology && topology.devices.length > 0 && (
          <>
            <Legend />
            <TopologyView topology={topology} />
          </>
        )}
        {topology && topology.devices.length === 0 && (
          <div style={{ fontSize: 13, opacity: 0.7 }}>
            No cables in Infrahub on this branch yet. Run the topology
            generators to build the fabric.
          </div>
        )}
        {topology && topology.skipped.length > 0 && (
          <div style={{ fontSize: 12, opacity: 0.7, marginTop: 12 }}>
            Not drawn: {topology.skipped.join('; ')}
          </div>
        )}
      </Content>
    </Page>
  );
}
