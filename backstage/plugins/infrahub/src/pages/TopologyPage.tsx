import { memo, useEffect, useMemo, useState } from 'react';
import ToggleButton from '@material-ui/lab/ToggleButton';
import ToggleButtonGroup from '@material-ui/lab/ToggleButtonGroup';
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
  useReactFlow,
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
  Badge,
  DEPLOYMENT_QUERY,
  DeploymentData,
  describeState,
  indexByName,
  Tone,
} from '../panels/deployment';
import {
  buildTopology,
  Domain,
  DOMAIN_LABELS,
  DOMAINS,
  filterTopology,
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
  /** Deployment overlay: the state, and the colour the border takes for it. */
  badge?: Badge;
  ring?: string;
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
        border: `2px solid ${data.ring ?? data.colour}`,
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
      <div
        style={{ fontSize: 10, textTransform: 'uppercase' }}
        title={data.badge?.detail}
      >
        <span style={{ opacity: 0.7 }}>{data.role.replace(/_/g, ' ')}</span>
        {data.badge && (
          <span style={{ color: data.ring, fontWeight: 700 }}>
            {' · '}
            {data.badge.label}
          </span>
        )}
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

/** The colour each deployment tone is drawn in; `drifted` is a warning, not a fault. */
function useToneColours(): Record<Tone, string> {
  const status = useStatusColours();
  const theme = useTheme();
  return {
    ok: status.ok,
    pending: status.pending,
    warn: theme.palette.warning.main,
    error: status.error,
    idle: status.idle,
  };
}

/** What a device's node shows when the overlay is on. */
function overlay(
  state: Parameters<typeof describeState>[0],
  tones: Record<Tone, string>,
) {
  const badge = describeState(state, Date.now());
  return { badge, ring: tones[badge.tone] };
}

// Outside the component: React Flow warns, and remounts every node, when these
// objects change identity between renders.
const nodeTypes = { device: DeviceNode };
const edgeTypes = { cable: CableEdge };

/** Re-frames the view when a domain is toggled, so what is left fills the canvas. */
function FitOnChange(props: { watch: string }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    // After React Flow has taken the new nodes, not before.
    const timer = setTimeout(
      () => fitView({ padding: 0.15, duration: 300 }),
      50,
    );
    return () => clearTimeout(timer);
  }, [props.watch, fitView]);
  return null;
}

export function TopologyView(props: {
  topology: Topology;
  domains: Set<Domain>;
  /** When given, every device wears its deployment state. */
  deployment?: DeploymentData;
  height?: number;
}) {
  const theme = useTheme();
  const kinds = useKindColours();
  const status = useStatusColours();
  const [hovered, setHovered] = useState<string | undefined>();

  const colourFor = (group: Group) => groupColours(kinds)[group];
  const tones = useToneColours();
  const records = useMemo(
    () => (props.deployment ? indexByName(props.deployment) : undefined),
    [props.deployment],
  );
  const hiddenDevices = useMemo(
    () =>
      new Set(
        props.topology.devices
          .filter(d => !props.domains.has(d.domain))
          .map(d => d.id),
      ),
    [props.topology.devices, props.domains],
  );

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
    hidden: hiddenDevices.has(device.id),
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
      ...(records && overlay(records.get(device.label), tones)),
    },
  }));

  const edges: Edge<CableData>[] = props.topology.links.map(link => {
    const lit = !hovered || link.from === hovered || link.to === hovered;
    return {
      id: link.id,
      type: 'cable',
      hidden: hiddenDevices.has(link.from) || hiddenDevices.has(link.to),
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
        <FitOnChange watch={[...props.domains].sort().join(',')} />
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

const TONE_WORDS: Record<Tone, string> = {
  ok: 'in sync',
  pending: 'pending',
  warn: 'drifted',
  error: 'failed',
  idle: 'unknown or stale',
};

function Legend(props: { deployment: boolean }) {
  const kinds = useKindColours();
  const status = useStatusColours();
  const tones = useToneColours();
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
      {props.deployment &&
        (['ok', 'pending', 'warn', 'error', 'idle'] as Tone[]).map(tone => (
          <span key={tone} style={{ marginRight: 16 }}>
            <span
              style={{
                display: 'inline-block',
                width: 10,
                height: 10,
                borderRadius: '50%',
                background: tones[tone],
                marginRight: 6,
              }}
            />
            {TONE_WORDS[tone]}
          </span>
        ))}
      <span>Hover a device to follow its cables</span>
    </div>
  );
}

/** How often the deployment overlay re-reads; the reconciler's loop is minutes. */
const REFRESH_MS = 30_000;

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

  const [domains, setDomains] = useState<Domain[]>([...DOMAINS]);
  const [showDeployment, setShowDeployment] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!showDeployment) return undefined;
    const timer = setInterval(() => setTick(n => n + 1), REFRESH_MS);
    return () => clearInterval(timer);
  }, [showDeployment]);

  // Only asked for while the overlay is on, and re-asked as it stays on.
  const deployment = useInfrahubQuery<DeploymentData>(
    DEPLOYMENT_QUERY,
    {},
    [tick],
    !showDeployment,
  );

  const enabled = useMemo(() => new Set(domains), [domains]);
  const visible = useMemo(
    () => (topology ? filterTopology(topology, enabled) : undefined),
    [topology, enabled],
  );

  return (
    <Page themeId="tool">
      <Header
        title="Fabric topology"
        subtitle="Every cable, read straight from Infrahub"
      />
      <Content>
        <ContentHeader title={visible ? summarise(visible) : 'Topology'}>
          <SupportButton>
            Drawn from the cable objects on the selected branch, so a link added
            on a branch shows up here before it is merged. Only cables Infrahub
            models are drawn: a device wired to something with no Infrahub
            object, such as the tooling bridge, shows fewer cables than the lab
            has. Deployment state is the reconciler&apos;s last comparison of
            each device with the configuration Infrahub renders for it; it
            describes the devices as they are now, whichever branch is selected.
          </SupportButton>
        </ContentHeader>

        {loading && <Progress />}
        {error && <ResponseErrorPanel error={error} />}
        {showDeployment && deployment.error && (
          <ResponseErrorPanel error={deployment.error} />
        )}

        {topology && topology.devices.length > 0 && (
          <>
            <div
              style={{
                display: 'flex',
                gap: 16,
                alignItems: 'center',
                flexWrap: 'wrap',
                marginTop: 8,
              }}
            >
              <ToggleButtonGroup
                size="small"
                value={domains}
                // Never empty: a blank canvas is not a view, it is a mistake.
                onChange={(_event, next: Domain[]) =>
                  next.length > 0 && setDomains(next)
                }
                aria-label="Show"
              >
                {DOMAINS.map(domain => (
                  <ToggleButton key={domain} value={domain}>
                    {DOMAIN_LABELS[domain]}
                  </ToggleButton>
                ))}
              </ToggleButtonGroup>
              <ToggleButton
                size="small"
                value="deployment"
                selected={showDeployment}
                onChange={() => setShowDeployment(on => !on)}
              >
                Deployment state
              </ToggleButton>
            </div>
            <Legend deployment={showDeployment} />
            <TopologyView
              topology={topology}
              domains={enabled}
              deployment={showDeployment ? deployment.data : undefined}
            />
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
