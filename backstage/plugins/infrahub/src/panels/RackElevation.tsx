import { useTheme } from '@material-ui/core/styles';
import {
  InfoCard,
  Progress,
  ResponseErrorPanel,
} from '@backstage/core-components';
import { useInfrahubNode, useInfrahubQuery } from '../client';
import { useKindColours } from '../colours';
import {
  layoutRack,
  RACK_QUERY,
  RackNode,
  RacksResult,
  ServerNode,
  ServersResult,
  serversIn,
  SERVERS_QUERY,
  SITE_RACKS_QUERY,
  Slot,
  summarise,
} from './rackLayout';

export type { RackNode, ServerNode } from './rackLayout';

const U_HEIGHT = 22;

/** Routers, switches and servers read differently at a glance. */
function colourFor(colours: ReturnType<typeof useKindColours>, slot: Slot) {
  switch (slot.family) {
    case 'router':
    case 'firewall':
      return colours.device;
    case 'switch':
      return colours.deviceAlt;
    case 'server':
      return colours.place;
    default:
      return colours.neutral;
  }
}

function Bar(props: { slot: Slot; colour: string; style: object }) {
  const { slot } = props;
  return (
    <div
      title={`${slot.label}${
        slot.position !== null
          ? ` — U${slot.position}${
              slot.height > 1 ? `-${slot.position + slot.height - 1}` : ''
            }`
          : ''
      }, ${slot.face}`}
      style={{
        background: props.colour,
        borderRadius: 3,
        color: '#fff',
        fontSize: 11,
        fontWeight: 600,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 8px',
        // A rear-mounted device is hatched, so both faces can share one
        // elevation without a second drawing.
        backgroundImage:
          slot.face === 'rear'
            ? 'repeating-linear-gradient(45deg, rgba(0,0,0,.25) 0 4px, transparent 4px 8px)'
            : undefined,
        ...props.style,
      }}
    >
      <span>{slot.label}</span>
      <span style={{ opacity: 0.8, fontWeight: 400 }}>{slot.detail}</span>
    </div>
  );
}

export function Rack(props: { rack: RackNode; servers: ServerNode[] }) {
  const theme = useTheme();
  const colours = useKindColours();
  const layout = layoutRack(props.rack, props.servers);
  const { units } = layout;
  const parent = props.rack.parent?.node?.display_label;

  return (
    <div style={{ marginRight: 32, marginBottom: 16, width: 260 }}>
      <div style={{ fontWeight: 600, fontSize: 13 }}>
        {props.rack.display_label}
      </div>
      <div
        style={{
          fontSize: 11,
          opacity: 0.7,
          marginBottom: 6,
          fontFamily: 'ui-monospace, monospace',
        }}
      >
        {[parent, summarise(layout)].filter(Boolean).join(' · ')}
      </div>

      {units > 0 && (
        <div
          style={{
            position: 'relative',
            height: units * U_HEIGHT,
            border: `2px solid ${theme.palette.divider}`,
            borderRadius: 4,
            background: theme.palette.background.default,
            marginBottom: 8,
          }}
        >
          {/* U numbering runs bottom to top, the way a rack is actually counted. */}
          {Array.from({ length: units }, (_, index) => (
            <div
              key={index}
              style={{
                position: 'absolute',
                bottom: index * U_HEIGHT,
                left: 0,
                right: 0,
                height: U_HEIGHT,
                borderTop:
                  index === units - 1
                    ? 'none'
                    : `1px solid ${theme.palette.divider}`,
                display: 'flex',
                alignItems: 'center',
                paddingLeft: 4,
                fontSize: 9,
                color: theme.palette.text.disabled,
                fontFamily: 'ui-monospace, monospace',
              }}
            >
              {index + 1}
            </div>
          ))}

          {layout.positioned.map(slot => (
            <Bar
              key={slot.id}
              slot={slot}
              colour={colourFor(colours, slot)}
              style={{
                position: 'absolute',
                bottom: (slot.position! - 1) * U_HEIGHT + 1,
                left: 22,
                right: 4,
                height: slot.height * U_HEIGHT - 2,
              }}
            />
          ))}
        </div>
      )}

      {layout.unpositioned.length > 0 && (
        <>
          <div style={{ fontSize: 11, opacity: 0.7, marginBottom: 4 }}>
            {units > 0
              ? 'Not at a rack position in Infrahub:'
              : 'Infrahub records no rack positions here; listed by name:'}
          </div>
          <div
            style={{
              border: `2px dashed ${theme.palette.divider}`,
              borderRadius: 4,
              padding: 3,
            }}
          >
            {layout.unpositioned.map(slot => (
              <Bar
                key={slot.id}
                slot={slot}
                colour={colourFor(colours, slot)}
                style={{ height: U_HEIGHT - 2, marginBottom: 2 }}
              />
            ))}
          </div>
        </>
      )}

      {units === 0 && layout.unpositioned.length === 0 && (
        <div style={{ fontSize: 12, opacity: 0.7 }}>Nothing in this rack.</div>
      )}
    </div>
  );
}

export function RackElevation() {
  const { id, kind, title } = useInfrahubNode();
  const onRack = kind === 'LocationRack';

  // On a rack, the rack and its servers come back together. On a site, the
  // servers can only be asked for once the racks' ids are known.
  const racksQuery = useInfrahubQuery<RacksResult & Partial<ServersResult>>(
    onRack ? RACK_QUERY : SITE_RACKS_QUERY,
    { id },
    [id, onRack],
    !id,
  );
  const racks = racksQuery.data?.LocationRack.edges.map(edge => edge.node);
  const rackIds = racks?.map(rack => rack.id) ?? [];
  const serversQuery = useInfrahubQuery<ServersResult>(
    SERVERS_QUERY,
    { ids: rackIds },
    [rackIds.join(',')],
    onRack || rackIds.length === 0,
  );

  if (!id) {
    return <InfoCard title="Racks">No Infrahub id on this entity.</InfoCard>;
  }
  const error = racksQuery.error ?? serversQuery.error;
  if (error) return <ResponseErrorPanel error={error} />;
  // The second clause covers the render between the racks arriving and the
  // servers query starting, which would otherwise draw racks with no servers.
  const awaitingServers = !onRack && rackIds.length > 0 && !serversQuery.data;
  if (racksQuery.loading || serversQuery.loading || !racks || awaitingServers) {
    return <Progress />;
  }

  const servers = (
    (onRack ? racksQuery.data : serversQuery.data)?.ComputePhysicalServer
      ?.edges ?? []
  ).map(edge => edge.node);
  const heading = onRack ? `Elevation: ${title}` : `Racks: ${title}`;

  if (racks.length === 0) {
    return (
      <InfoCard title={heading}>
        {onRack
          ? 'This rack was not found in Infrahub.'
          : 'No racks at this site yet.'}
      </InfoCard>
    );
  }

  const mounted =
    racks.reduce((total, rack) => total + rack.devices.edges.length, 0) +
    servers.length;

  return (
    <InfoCard
      title={heading}
      subheader={`${racks.length} rack${
        racks.length === 1 ? '' : 's'
      }, ${mounted} devices — hatched is rear-facing`}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        {racks.map(rack => (
          <Rack
            key={rack.id}
            rack={rack}
            servers={onRack ? servers : serversIn(rack.id, servers)}
          />
        ))}
      </div>
    </InfoCard>
  );
}
