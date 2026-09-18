import {
  coreServices,
  createBackendModule,
  LoggerService,
  SchedulerService,
} from '@backstage/backend-plugin-api';
import {
  ANNOTATION_EDIT_URL,
  ANNOTATION_LOCATION,
  ANNOTATION_ORIGIN_LOCATION,
  ANNOTATION_VIEW_URL,
  Entity,
} from '@backstage/catalog-model';
import {
  catalogProcessingExtensionPoint,
  EntityProvider,
  EntityProviderConnection,
} from '@backstage/plugin-catalog-node';
import {
  InfrahubConfig,
  infrahubGet,
  infrahubQuery,
  mapLimit,
  readInfrahubConfig,
} from '@opsmill/backstage-plugin-infrahub-node';
import {
  DEFAULT_BRANCH,
  INFRAHUB_ANNOTATIONS,
} from '@opsmill/backstage-plugin-infrahub-common';
import {
  CatalogConfig,
  KindMapping,
  readCatalogConfig,
  slugFor,
} from './config';

// Read from main: a service node itself is branch agnostic, so a request shows
// up here as soon as it is submitted, but its branch aware fields (bandwidth,
// ip_package, and everything the generator allocates) stay empty until the
// proposed change is merged.
type Value<T> = { value: T };

type ProposedChangeNode = {
  id: string;
  source_branch: Value<string>;
  state: Value<string | null>;
};

/** Only proposed changes are queried by hand now; everything else is mapped. */
const CHANGES_QUERY = `
  {
    CoreProposedChange {
      edges {
        node {
          id
          source_branch { value }
          state { value }
        }
      }
    }
  }
`;

/**
 * Where a relationship field's options come from, when we ingest its peer.
 * Derived at runtime from the configured mappings rather than kept as a second
 * list, so a peer we do not ingest falls back to a plain hfid text field and a
 * kind never loses a field -- or fails its create on a required relationship --
 * just because it points at something new.
 */
type Picker = { kind: string; type: string };

const JSON_TO_GRAPHQL: Record<string, string> = {
  string: 'String',
  number: 'BigInt',
  integer: 'BigInt',
  boolean: 'Boolean',
  // A List attribute's input is `ListAttributeCreate { value: GenericScalar }`,
  // and the scaffolder preserves a parameter's type when the whole value is one
  // expression -- so an array of strings arrives as an array, not as its
  // stringification.
  array: 'GenericScalar',
};

/**
 * An attribute whose json_schema type is not one of the above (a JSON blob, an
 * unrecognised Infrahub kind) cannot be typed into a mutation, and guessing
 * String would produce a form that fails on submit. Leave it out and say so.
 */
const isFormable = (property: any) =>
  JSON_TO_GRAPHQL[property.type] !== undefined;

/**
 * Infrahub's own attribute kinds, mapped to the json_schema types this provider
 * already understands. Used only when `/api/schema/json_schema/{kind}` cannot be
 * read -- see `synthesiseJsonSchema`.
 *
 * Anything absent maps to `object`, which `isFormable` rejects: an unrecognised
 * kind is left off the form rather than guessed at. `array` cannot serve as that
 * sentinel any more, because a List is now a real array field.
 */
const INFRAHUB_KIND_TO_JSON: Record<string, string> = {
  Text: 'string',
  TextArea: 'string',
  Dropdown: 'string',
  DateTime: 'string',
  Email: 'string',
  URL: 'string',
  File: 'string',
  Password: 'string',
  HashedPassword: 'string',
  IPHost: 'string',
  IPNetwork: 'string',
  MacAddress: 'string',
  Color: 'string',
  Number: 'integer',
  Bandwidth: 'integer',
  Boolean: 'boolean',
  Checkbox: 'boolean',
  List: 'array',
};

/**
 * Builds a json_schema-shaped payload out of `/api/schema/{kind}`.
 *
 * WHY THIS EXISTS: `GET /api/schema/json_schema/{kind}` returns **500 for any
 * kind carrying a `List` attribute** on Infrahub 1.10.6 --
 *
 *   PydanticSchemaGenerationError: Unable to generate pydantic-core schema
 *   for <class 'infrahub.types.Any'>
 *
 * -- and the whole kind was then dropped from the catalogue. In this lab that
 * is three of nine service kinds, including `ServiceAppAccess`, which is the
 * request the portal exists to take. The kinds appeared with no form and the
 * only clue was a warning in the backend log.
 *
 * `/api/schema/{kind}` answers 200 for the same kinds and carries everything a
 * form needs: names, kinds, optionality, defaults and a Dropdown's choices. The
 * List attribute itself is no obstacle -- `isFormable` already drops an
 * untypeable attribute and keeps the rest of the kind, which is exactly the
 * outcome wanted here.
 *
 * `required` is derived from `optional`, which is what json_schema does too.
 */
const synthesiseJsonSchema = (schema: KindSchema): any => {
  const properties: Record<string, any> = {};
  const required: string[] = [];

  for (const attribute of schema.attributes ?? []) {
    const property: any = {
      type: INFRAHUB_KIND_TO_JSON[attribute.kind] ?? 'object',
    };
    if (property.type === 'array') {
      // react-jsonschema-form needs `items` to know what to render, and an
      // Infrahub List is a list of strings -- the schema's own examples are
      // "443" and "key=value", never structured objects.
      property.items = { type: 'string' };
    }
    if (attribute.description) {
      property.description = attribute.description;
    }
    if (attribute.default_value !== undefined && attribute.default_value !== null) {
      property.default = attribute.default_value;
    }
    if (attribute.choices?.length) {
      // Values only. `withChoiceLabels` reads the labels off the same schema
      // and merges them in, so doing it here would duplicate that.
      property.enum = attribute.choices.map(choice => choice.name);
    }
    properties[attribute.name] = property;
    if (attribute.optional === false) {
      required.push(attribute.name);
    }
  }

  return { properties, required };
};

/**
 * Never on a request form, for any kind.
 *
 * `status`: the kind's own schema decides the initial value -- the create
 * leaves it out so the default applies -- and a request is only really
 * active once its proposed change is merged. Not a requester's field either
 * way.
 *
 * `checksum`: bookkeeping an Infrahub generator writes to detect that its input
 * changed. It sits on the service generic, so it was on the form of every
 * service kind -- asking a requester to type a checksum for the thing they are
 * asking for. Excluding it per kind would be the same line nine times.
 */
const GENERATED_FORM_EXCLUDES = ['status', 'checksum'];

/**
 * The relationships a form has to carry: cardinality one, and not Infrahub's own
 * bookkeeping. Shared so the hfid prefetch and the resolution below cannot drift
 * apart and leave a relationship with no looked-up peer.
 */
const relationshipsOf = (schema: KindSchema): SchemaRelationship[] =>
  (schema.relationships ?? []).filter(
    relationship =>
      relationship.cardinality === 'one' &&
      !relationship.peer.startsWith('Core'),
  );

/** A mapped kind with the schema needed to read it and form a template. */
type LoadedKind = {
  mapping: KindMapping;
  kind: string;
  tag: string;
  label: string;
  /**
   * The attribute that names an object of this kind, read off the schema's
   * human_friendly_id. `service_identifier` for a service, `shortname` for a
   * site -- so no kind's identifier is hardcoded anywhere.
   */
  identifier?: string;
  /**
   * Attributes kept out of the generated form but still worth reading, and only
   * the ones this kind actually has. `status` is on a service but not on a
   * site, and asking Infrahub for a field a kind lacks fails the whole query.
   */
  readOnly: string[];
  schema: KindSchema;
  required: string[];
  attributes: [string, any][];
  relationships: ResolvedRelationship[];
};

const GRAPHQL_SCALARS: Record<string, string> = {
  Number: 'Int',
  Bandwidth: 'Int',
  Boolean: 'Boolean',
  JSON: 'JSON',
};

type SchemaAttribute = {
  name: string;
  kind: string;
  optional?: boolean;
  description?: string;
  /** Present and null when there is no default, so absence proves nothing. */
  default_value?: unknown;
  /** A Dropdown's values, each with the label Infrahub shows for it. */
  choices?: { name: string; label?: string }[];
};

type SchemaRelationship = {
  name: string;
  peer: string;
  cardinality: string;
  optional?: boolean;
  /** Infrahub's own label, which reads better than a derived one. */
  label?: string;
};

/** A relationship plus where its field's options come from, if anywhere. */
type ResolvedRelationship = SchemaRelationship & {
  picker?: Picker;
  /**
   * How many elements the PEER's human_friendly_id has.
   *
   * `hfid: [$value]` is right only when that is one. `IpamIPAddress` is
   * `[address__value, ip_namespace__name__value]`, so a single-element lookup is
   * refused outright:
   *
   *   Unable to lookup node by HFID, schema 'IpamIPAddress' HFID does not
   *   contain the same number of elements as ['10.112.240.10/32']
   *
   * Five cardinality-one relationships across four service kinds have composite
   * HFIDs here, two of them mandatory -- so two kinds could not be created from
   * the portal at all.
   */
  hfidLength?: number;
};

type KindSchema = {
  name: string;
  namespace: string;
  label?: string;
  description?: string;
  /** e.g. ['service_identifier__value'] -- the attribute that names an object. */
  human_friendly_id?: string[];
  attributes?: SchemaAttribute[];
  relationships?: SchemaRelationship[];
};

/** How many Infrahub requests one refresh may have in flight. */
const CONCURRENCY = 5;

/**
 * Mirrors Infrahub into the Backstage catalog.
 *
 * Which kinds become which entities comes from `infrahub.catalog` config, and
 * what each entity *says* comes from that kind's own Infrahub schema. So there
 * is no per-kind code here: adding an attribute in Infrahub, or a whole kind
 * under a configured generic, needs no change to this file.
 */
let refreshNow: (() => Promise<void>) | undefined;

/**
 * Reads Infrahub now rather than on the next poll. The scaffolder uses it so a
 * service it just created is in the catalog by the time the run finishes, which
 * is the difference between a working link and a 404.
 */
export async function refreshInfrahubCatalog(): Promise<void> {
  if (!refreshNow) {
    throw new Error('The Infrahub catalog provider is not connected yet');
  }
  await refreshNow();
}

export class InfrahubEntityProvider implements EntityProvider {
  private connection?: EntityProviderConnection;

  constructor(
    private readonly infrahub: InfrahubConfig,
    private readonly catalog: CatalogConfig,
    private readonly appBaseUrl: string,
    private readonly logger: LoggerService,
    private readonly scheduler: SchedulerService,
  ) {}

  /** Peer kind -> how many elements its human_friendly_id has. */
  private readonly hfidLengths = new Map<string, number>();

  getProviderName(): string {
    return 'infrahub';
  }

  async connect(connection: EntityProviderConnection): Promise<void> {
    this.connection = connection;
    // So a scaffolder run can pull its own service into the catalog instead of
    // waiting out the poll -- see refreshInfrahubCatalog below.
    refreshNow = () => this.refresh();
    // Scheduled from connect(), otherwise the first run races the connection.
    await this.scheduler.scheduleTask({
      id: 'infrahub-catalog-refresh',
      // A minute, because services change whenever someone submits a request.
      // One GraphQL round trip, and an unchanged result is a no-op mutation.
      frequency: { minutes: this.catalog.refreshMinutes },
      timeout: { minutes: 1 },
      // ponytail: polling, not webhooks — swap for an Infrahub webhook if a
      // minute is ever too slow.
      fn: async () => {
        try {
          await this.refresh();
        } catch (error) {
          this.logger.error(`Failed to refresh the Infrahub catalog: ${error}`);
        }
      },
    });
  }

  async refresh(): Promise<void> {
    if (!this.connection) {
      throw new Error('Infrahub entity provider is not initialized');
    }

    const mappings = await this.resolveMappings();
    if (mappings.length === 0) {
      this.logger.warn(
        'No infrahub.catalog kinds or discover rules are configured, so ' +
          'nothing will be ingested',
      );
    }

    const kinds = await this.loadKindSchemas(mappings);

    // Proposed changes are read once and shared: every kind needs them to tell
    // a live object from a pending request.
    let changesByBranch = new Map<string, ProposedChangeNode>();
    try {
      const data = await infrahubQuery({
        config: this.infrahub,
        query: CHANGES_QUERY,
      });
      changesByBranch = new Map(
        (data.CoreProposedChange?.edges ?? []).map(
          (edge: { node: ProposedChangeNode }) => [
            edge.node.source_branch.value,
            edge.node,
          ],
        ),
      );
    } catch (error) {
      // Without them nothing is marked pending, which is worse than a hard
      // failure only if it goes unnoticed.
      this.logger.warn(
        `Could not read proposed changes, so no request will be marked ` +
          `pending: ${error}`,
      );
    }

    const ingested = await Promise.all(
      kinds.map(kind => this.ingestKind(kind, changesByBranch)),
    );
    const objects = ingested.flat();
    const templates = kinds
      .filter(kind => kind.mapping.template)
      .map(kind => this.serviceTemplate(kind));

    const componentCount = objects.filter(
      entity => entity.kind === 'Component',
    ).length;

    const entities = [
      ...(this.catalog.system ? [this.systemEntity(componentCount)] : []),
      ...(await this.apiEntities(mappings)),
      ...objects,
      ...templates,
    ];

    this.reportCollisions(entities);

    const summary = kinds
      .map(kind => `${kind.kind} (${kind.mapping.entity})`)
      .join(', ');
    this.logger.info(
      `Ingested ${objects.length} Infrahub objects and ${templates.length} ` +
        `template(s) across ${kinds.length} kind(s): ${summary}`,
    );

    await this.connection.applyMutation({
      type: 'full',
      entities: entities.map(entity => ({
        entity,
        locationKey: this.getProviderName(),
      })),
    });
  }

  /**
   * The branch a request is still readable on. Infrahub deletes the source
   * branch when a proposed change merges, so reading anything but an open
   * change is a guaranteed 404 on every refresh.
   */
  private openBranch(change?: ProposedChangeNode): string | undefined {
    return change?.state.value === 'open'
      ? change.source_branch.value
      : undefined;
  }

  private reportCollisions(entities: Entity[]): void {
    const seen = new Map<string, string[]>();

    for (const entity of entities) {
      const key = `${entity.kind}:${entity.metadata.name}`;
      const source =
        entity.metadata.annotations?.[INFRAHUB_ANNOTATIONS.id] ??
        entity.metadata.title ??
        entity.metadata.name;
      seen.set(key, [...(seen.get(key) ?? []), source]);
    }

    for (const [key, sources] of seen) {
      if (sources.length > 1) {
        this.logger.warn(
          `${sources.length} Infrahub objects map to the entity ${key}, so ` +
            `only one survives: ${sources.join(', ')}. Their identifiers ` +
            `differ only by case or by characters Backstage strips.`,
        );
      }
    }
  }

  private objectUrl(kind: string, id: string): string {
    return `${this.infrahub.externalAddress}/objects/${kind}/${id}`;
  }

  private base(
    viewUrl?: string,
    editUrl?: string,
    node?: { kind: string; id: string },
  ): Pick<Entity['metadata'], 'annotations'> {
    return {
      annotations: {
        [ANNOTATION_LOCATION]: `url:${this.infrahub.externalAddress}`,
        [ANNOTATION_ORIGIN_LOCATION]: `url:${this.infrahub.externalAddress}`,
        // The UUID is the stable key; hfid only gives a readable entity name.
        // The catalog shows main only, so that is what the branch records.
        ...(node
          ? {
              [INFRAHUB_ANNOTATIONS.instance]: this.infrahub.instance,
              [INFRAHUB_ANNOTATIONS.kind]: node.kind,
              [INFRAHUB_ANNOTATIONS.id]: node.id,
              [INFRAHUB_ANNOTATIONS.branch]: DEFAULT_BRANCH,
            }
          : {}),
        ...(viewUrl ? { [ANNOTATION_VIEW_URL]: viewUrl } : {}),
        // Sites and devices are only editable in Infrahub, so they fall back to
        // their object page; services get the Backstage change form.
        ...(editUrl ?? viewUrl
          ? { [ANNOTATION_EDIT_URL]: editUrl ?? viewUrl! }
          : {}),
      },
    };
  }

  private systemEntity(componentCount: number): Entity {
    return {
      apiVersion: 'backstage.io/v1alpha1',
      kind: 'System',
      metadata: {
        name: this.catalog.system!,
        title: this.fieldTitle(this.catalog.system!),
        description: `${componentCount} services, provisioned from Infrahub`,
        ...this.base(`${this.infrahub.externalAddress}/schema`),
      },
      spec: { owner: this.catalog.owner },
    };
  }

  /**
   * Every node kind inheriting ServiceGeneric, read off the schema, so a service
   * kind added to Infrahub turns up in the catalog without a code change here.
   */
  /**
   * Every kind this provider should ingest: the ones named in config, plus the
   * descendants of every configured generic, read off `/api/schema`.
   *
   * Discovery is the point of the generic form -- a kind added to Infrahub
   * under `ServiceGeneric` turns up on the next read with no config change --
   * while naming a kind directly is how reference data like sites gets in.
   */
  /**
   * Fields the generated form must not offer for a kind: `status`, which a
   * generator sets, plus whatever the mapping names. They stay in the query and
   * on the entity -- this is only about what a person is asked to type.
   */
  private offForm(mapping: KindMapping): string[] {
    return [...GENERATED_FORM_EXCLUDES, ...mapping.formExclude];
  }

  private async resolveMappings(): Promise<KindMapping[]> {
    const named = new Map(this.catalog.kinds.map(m => [m.kind, m]));

    if (this.catalog.discover.length === 0) {
      return [...named.values()];
    }

    let schema: {
      nodes?: { namespace: string; name: string; inherit_from?: string[] }[];
    };
    try {
      schema = await infrahubGet(this.infrahub, '/api/schema');
    } catch (error) {
      // Losing discovery should not cost the kinds we were told about.
      this.logger.error(
        `Could not read the Infrahub schema, so no kinds were discovered: ${error}`,
      );
      return [...named.values()];
    }

    for (const rule of this.catalog.discover) {
      const descendants = (schema.nodes ?? [])
        .filter(node => (node.inherit_from ?? []).includes(rule.generic))
        .map(node => `${node.namespace}${node.name}`)
        .sort();

      if (descendants.length === 0) {
        this.logger.warn(
          `No Infrahub kind inherits ${rule.generic}, so nothing was discovered for it`,
        );
      }

      for (const kind of descendants) {
        // A kind named directly in config wins: that is how someone overrides
        // one discovered kind without listing all of them.
        if (named.has(kind)) {
          continue;
        }
        named.set(kind, {
          kind,
          entity: rule.entity,
          type: slugFor(kind),
          template: rule.template,
          groups: rule.groups,
          formExclude: rule.formExclude,
          discoveredUnder: rule.generic,
        });
      }
    }

    return [...named.values()];
  }

  /**
   * Services of a kind we have no rich mapping for. They still get an entity,
   * built from the attributes ServiceGeneric guarantees, so a new kind is
   * visible and orderable-adjacent rather than silently missing.
   */
  /**
   * What a relationship's options come from. Service kinds are Components we
   * emit, sites and devices are Resources we emit, and anything else has no
   * entities behind it, so its field becomes a plain hfid instead of a picker.
   */
  /**
   * The peer's HFID length, fetched once per kind and cached.
   *
   * Peers are not necessarily ingested -- `IpamIPAddress` is not -- so this
   * cannot be read off the kinds already loaded. A peer whose schema cannot be
   * read is treated as single-element, which is the previous behaviour: no
   * worse than before, and it keeps one unreadable peer from dropping a field.
   */
  private async peerHfidLength(peer: string): Promise<number> {
    const cached = this.hfidLengths.get(peer);
    if (cached !== undefined) {
      return cached;
    }
    let length = 1;
    try {
      const schema: KindSchema = await infrahubGet(
        this.infrahub,
        `/api/schema/${peer}`,
      );
      length = schema.human_friendly_id?.length || 1;
    } catch (error) {
      this.logger.warn(
        `Could not read ${peer}'s schema (${error}); assuming a single-element hfid`,
      );
    }
    this.hfidLengths.set(peer, length);
    return length;
  }

  private pickerFor(peer: string, mappings: KindMapping[]): Picker | undefined {
    const exact = mappings.find(mapping => mapping.kind === peer);
    if (exact) {
      return { kind: exact.entity, type: exact.type };
    }

    // A relationship often names a generic's descendant while the mapping names
    // the generic -- `DcimDevice` against a mapped `DcimGenericDevice`. Both are
    // ingested as the same entity type, so the picker still resolves.
    const viaGeneric = mappings.find(mapping =>
      this.sharesFamily(peer, mapping.kind),
    );

    return viaGeneric
      ? { kind: viaGeneric.entity, type: viaGeneric.type }
      : undefined;
  }

  /**
   * Whether two kind names are the same thing at different levels of the
   * schema, which is how `DcimDevice` matches a mapping for
   * `DcimGenericDevice`. Compared on the slug with `generic` dropped, because
   * that is the only relationship Infrahub's naming actually encodes.
   */
  private sharesFamily(peer: string, mapped: string): boolean {
    const bare = (kind: string) =>
      slugFor(kind)
        .split('-')
        .filter(part => part !== 'generic')
        .join('-');

    return bare(peer) === bare(mapped);
  }

  /**
   * Loads each unmapped kind's schema once. Both payloads are needed: json_schema
   * types the attributes and says which are required, /api/schema carries the
   * relationships json_schema omits.
   */
  private async loadKindSchemas(
    mappings: KindMapping[],
  ): Promise<LoadedKind[]> {
    const loaded = await mapLimit<KindMapping, LoadedKind | undefined>(
      mappings,
      CONCURRENCY,
      async mapping => {
        const kind = mapping.kind;
        try {
          // `/api/schema/{kind}` FIRST, and deliberately: it is the one that
          // always answers, and it is what the fallback below is built from.
          const schema: KindSchema = await infrahubGet(
            this.infrahub,
            `/api/schema/${kind}`,
          );

          // Each peer's hfid length, before the relationships are resolved --
          // it decides whether a field is one string or an array of them.
          const peerHfids = new Map<string, number>();
          for (const relationship of relationshipsOf(schema)) {
            peerHfids.set(
              relationship.peer,
              await this.peerHfidLength(relationship.peer),
            );
          }

          let jsonSchema: any;
          try {
            jsonSchema = await infrahubGet(
              this.infrahub,
              `/api/schema/json_schema/${kind}`,
            );
          } catch (error) {
            // A kind with a List attribute 500s here on Infrahub 1.10.6. Losing
            // the kind over it costs more than losing the one attribute, and the
            // attribute was going to be dropped as untypeable anyway.
            this.logger.warn(
              `${kind}: /api/schema/json_schema returned ${error}; building its ` +
                `form from /api/schema instead`,
            );
            jsonSchema = synthesiseJsonSchema(schema);
          }

          return {
            mapping,
            kind,
            tag: mapping.type,
            identifier: schema.human_friendly_id?.[0]?.replace(/__value$/, ''),
            readOnly: this.offForm(mapping).filter(
              name => (jsonSchema.properties ?? {})[name] !== undefined,
            ),
            label: schema.label ?? kind,
            schema,
            required: jsonSchema.required ?? [],
            attributes: Object.entries(
              (jsonSchema.properties ?? {}) as Record<string, any>,
            )
              .map(
                ([name, property]) =>
                  [name, this.withChoiceLabels(name, property, schema)] as [
                    string,
                    any,
                  ],
              )
              .filter(([name]) => !this.offForm(mapping).includes(name))
              .filter(([name, property]) => {
                if (isFormable(property)) {
                  return true;
                }
                this.logger.warn(
                  `${kind}.${name} is a ${property.type}, which cannot be typed ` +
                    `into a mutation, so it is left off the generated form`,
                );
                return false;
              }),
            // Every cardinality-one relationship, whether or not we can offer a
            // picker for its peer. Dropping one would lose a field, and lose a
            // required one's value entirely.
            relationships: relationshipsOf(schema).map(relationship => ({
                ...relationship,
                // NO PICKER for a composite hfid: a picker yields one name, and
                // this peer needs every element. An array field is the only
                // thing that can carry them.
                picker:
                  (peerHfids.get(relationship.peer) ?? 1) > 1
                    ? undefined
                    : this.pickerFor(relationship.peer, mappings),
                hfidLength: peerHfids.get(relationship.peer) ?? 1,
              })),
          };
        } catch (error) {
          this.logger.warn(`Could not read the schema for ${kind}: ${error}`);
          return undefined;
        }
      },
    );

    return loaded.filter((kind): kind is LoadedKind => kind !== undefined);
  }

  /**
   * json_schema gives a Dropdown's values but not the labels Infrahub shows
   * for them, so a form built from it alone offers `1000` where Infrahub says
   * "One Gigabit". `/api/schema/{kind}` carries the labels, and we already
   * have it, so the two are merged into `enumNames` -- which is what
   * react-jsonschema-form reads for option text.
   *
   * Mapped value by value rather than positionally: the two payloads happen to
   * agree on order today, and relying on that would be a silent mislabelling
   * the moment they did not.
   */
  private withChoiceLabels(
    name: string,
    property: any,
    schema: KindSchema,
  ): any {
    const choices = (schema.attributes ?? []).find(
      attribute => attribute.name === name,
    )?.choices;

    if (!Array.isArray(property?.enum) || !choices?.length) {
      return property;
    }

    const labelFor = new Map(
      choices.map(choice => [choice.name, choice.label ?? choice.name]),
    );

    return {
      ...property,
      enumNames: property.enum.map(
        (option: unknown) => labelFor.get(String(option)) ?? String(option),
      ),
    };
  }

  /**
   * json_schema emits `"default": null` for an optional attribute with no
   * default, so presence of the key proves nothing.
   */
  private hasDefault(property: any): boolean {
    return property.default !== undefined && property.default !== null;
  }

  /**
   * A blank boolean is `false` and a blank number can be `0`, both falsy, so a
   * truthiness guard would silently drop them. Comparing against an unresolved
   * name is nunjucks' way of asking whether the field was set at all.
   */
  private providedGuard(name: string, type: string): string {
    if (type === 'boolean' || type === 'number' || type === 'integer') {
      // A blank boolean is `false` and a blank number can be `0`, both falsy.
      return `parameters.${name} !== unset`;
    }
    if (type === 'array') {
      // `[]` is truthy, so a bare truthiness check would send an empty list --
      // which `ServiceAppAccess.ports` documents as rejected rather than meaning
      // "all ports". Leaving the field unset is the honest way to say nothing.
      return `parameters.${name} and parameters.${name} | length > 0`;
    }
    return `parameters.${name}`;
  }

  /** Attributes safe to send in a create: required, or actually defaulted. */
  private upfrontAttributes(kind: LoadedKind): [string, any][] {
    return kind.attributes.filter(
      ([name, property]) =>
        kind.required.includes(name) || this.hasDefault(property),
    );
  }

  /**
   * Objects of one mapped kind, read with a query built from that kind's own
   * schema. This is the whole ingestion path: there is no per-kind code, so a
   * kind gains an attribute in Infrahub and the entity gains it here.
   */
  private async ingestKind(
    kind: LoadedKind,
    changesByBranch: Map<string, ProposedChangeNode>,
  ): Promise<Entity[]> {
    const fields = [
      ...kind.attributes.map(([name]) => `${name} { value }`),
      ...kind.readOnly.map(name => `${name} { value }`),
      // display_label as well as hfid: hfid names the entity, display_label is
      // what a person recognises in a description.
      ...kind.relationships.map(
        relationship =>
          `${relationship.name} { node { id hfid display_label } }`,
      ),
    ].join('\n              ');

    const query = `
      {
        ${kind.kind} {
          edges {
            node {
              id
              hfid
              display_label
              __typename
              ${fields}
            }
          }
        }
      }
    `;

    let data: Record<string, any>;
    try {
      data = await infrahubQuery({ config: this.infrahub, query });
    } catch (error) {
      // One unreadable kind should cost its own entities, not the refresh.
      this.logger.warn(`Could not read ${kind.kind}: ${error}`);
      return [];
    }

    const entities: Entity[] = [];

    for (const edge of data[kind.kind]?.edges ?? []) {
      const node = edge.node;
      const identifier = this.identifierFor(node);
      if (!identifier) {
        this.logger.warn(
          `A ${kind.kind} object has no hfid or display_label, so it cannot be ` +
            'named as an entity; skipping it',
        );
        continue;
      }

      const change = changesByBranch.get(
        `implement_${identifier.toLowerCase()}`,
      );

      // Branch aware attributes read as null, or as their schema default, on
      // main until the request merges -- and a default looks authoritative
      // while being wrong. Read what was actually asked for off the branch.
      let requested: Record<string, any> | undefined;
      const branch = this.openBranch(change);
      if (branch) {
        try {
          const branchData = await infrahubQuery({
            config: this.infrahub,
            query,
            branch,
          });
          requested = (branchData[kind.kind]?.edges ?? []).find(
            (candidate: any) =>
              this.identifierFor(candidate.node) === identifier,
          )?.node;
        } catch (error) {
          // The field list comes from main's schema, so a branch cut before a
          // schema change rejects it. Losing the prefill is the whole cost.
          // ponytail: read the branch's own schema if drift stops being rare.
          this.logger.info(
            `No prefill for ${identifier}: branch ${branch} did not accept ` +
              `the ${kind.kind} field list (${error})`,
          );
        }
      }

      entities.push(this.entityFor(kind, node, identifier, requested, change));
    }

    return entities;
  }

  /**
   * What names the entity. Infrahub's human friendly id, which is what a
   * template hands back to a mutation, falling back to the display label so an
   * object without an hfid is still ingested.
   */
  private identifierFor(node: Record<string, any>): string | undefined {
    return node.hfid?.[0] ?? node.display_label ?? undefined;
  }

  /**
   * One entity from one Infrahub object. Everything it says comes from the
   * kind's schema and the configured mapping -- the Backstage kind, the
   * `spec.type`, the description, the tags and the relations -- so this is the
   * only entity builder in the provider.
   */
  private entityFor(
    kind: LoadedKind,
    node: Record<string, any>,
    identifier: string,
    requested?: Record<string, any>,
    change?: ProposedChangeNode,
  ): Entity {
    const live = (name: string) => node[name]?.value ?? undefined;
    const attr = (name: string) =>
      requested?.[name]?.value ?? node[name]?.value ?? undefined;
    const pending = requested !== undefined;
    const isComponent = kind.mapping.entity === 'Component';

    // A relationship to a kind we ingest becomes a real catalog relation; the
    // rest are data, not references.
    const dependsOn = kind.relationships
      .map(relationship => {
        const hfid = node[relationship.name]?.node?.hfid?.[0];
        return hfid && relationship.picker
          ? `${relationship.picker.kind.toLowerCase()}:default/${hfid}`
          : undefined;
      })
      .filter((ref): ref is string => Boolean(ref));

    // Attributes first, then what this object points at, which is usually the
    // part someone is actually looking for -- the site, the VLAN, the prefix.
    const details = [
      ...kind.attributes
        .filter(([name]) => attr(name) !== undefined && attr(name) !== '')
        .filter(([name]) => String(attr(name)) !== identifier)
        .map(([name, property]) => {
          // Say so rather than presenting a request as live state.
          const asked =
            pending && requested?.[name]?.value !== undefined
              ? ' requested'
              : '';
          // The schema's own title, so a kind that labels a field carefully
          // gets that label rather than one derived from the field name.
          const title = property?.title ?? this.fieldTitle(name);
          return `${title} ${attr(name)}${asked}`;
        }),
      ...kind.relationships
        .map(relationship => {
          const peer = node[relationship.name]?.node?.display_label;
          return peer
            ? `${
                relationship.label ?? this.fieldTitle(relationship.name)
              } ${peer}`
            : undefined;
        })
        .filter((line): line is string => Boolean(line)),
    ];

    return {
      apiVersion: 'backstage.io/v1alpha1',
      kind: kind.mapping.entity,
      metadata: {
        // Lowercased because Backstage entity names are case-insensitive; the
        // real identifier stays in the title and the annotations.
        name: identifier.toLowerCase(),
        title: node.display_label ?? identifier,
        description: details.join(' · ') || `${kind.label} in Infrahub`,
        tags: [
          kind.tag,
          ...(live('status') ? [live('status')] : []),
          ...(pending ? ['pending-change'] : []),
        ],
        ...this.base(
          this.objectUrl(node.__typename, node.id),
          this.editUrl(kind, node, identifier, requested, change),
          { kind: node.__typename, id: node.id },
        ),
      },
      spec: {
        type: kind.tag,
        lifecycle: pending ? 'experimental' : 'production',
        owner: this.catalog.owner,
        // Only Components belong to a System; a Resource is not part of one.
        ...(isComponent && this.catalog.system
          ? { system: `system:default/${this.catalog.system}` }
          : {}),
        ...(dependsOn.length > 0 ? { dependsOn } : {}),
      },
    };
  }

  /**
   * Where the pencil goes.
   *
   * A change stacked on a request that has not merged is accepted by Infrahub
   * and then silently discarded, so while a request is *open* the pencil has to
   * go to that proposed change -- which is where a pending request is actually
   * edited. Keyed on the change being open rather than merely existing: a
   * merged one is history, and its link would be a dead end.
   */
  private editUrl(
    kind: LoadedKind,
    node: Record<string, any>,
    identifier: string,
    requested?: Record<string, any>,
    change?: ProposedChangeNode,
  ): string | undefined {
    if (change && this.openBranch(change)) {
      return `${this.infrahub.externalAddress}/proposed-changes/${change.id}`;
    }
    // A kind with no generated template has nowhere to go but Infrahub, which
    // base() falls back to.
    return kind.mapping.template
      ? this.generatedChangeFormUrl(kind, node, identifier, requested)
      : undefined;
  }

  /** The kind's generated template, in change mode, prefilled from main. */
  private generatedChangeFormUrl(
    kind: LoadedKind,
    node: Record<string, any>,
    identifier: string,
    requested?: Record<string, any>,
  ): string {
    const formData: Record<string, unknown> = {
      mode: 'change',
      target: `${kind.mapping.entity.toLowerCase()}:default/${identifier.toLowerCase()}`,
    };

    for (const [name] of kind.attributes) {
      // The identifier is what the form looks the object up by, so it is a
      // picker there rather than an editable field.
      if (String(node[name]?.value) === identifier) {
        continue;
      }
      const value = requested?.[name]?.value ?? node[name]?.value;
      if (value !== null && value !== undefined) {
        formData[name] = value;
      }
    }

    return `${this.appBaseUrl}/create/templates/default/${
      kind.tag
    }-request?formData=${encodeURIComponent(JSON.stringify(formData))}`;
  }

  /**
   * A scaffolder Template per discovered kind, doing create and change the way
   * the hand-written one does: a mode switch, per-mode required fields, and one
   * guarded step per field so a blank never overwrites a value.
   */
  private serviceTemplate(kind: LoadedKind): Entity {
    const upfront = this.upfrontAttributes(kind);
    // An optional relationship cannot go in the create: its variable would be
    // non-null and a blank field would fail the mutation.
    // A field a generator allocates is read and shown, but never asked for.
    const formRels = kind.relationships.filter(
      relationship => !this.offForm(kind.mapping).includes(relationship.name),
    );
    const requiredRels = formRels.filter(
      relationship => relationship.optional === false,
    );
    const optionalRels = formRels.filter(
      relationship => relationship.optional !== false,
    );
    // The attribute that names an object of this kind, from its schema.
    const idField = kind.identifier ?? 'name';
    const identifier = `\${{ parameters.${idField} if parameters.mode === "create" else steps.fetch.output.entity.metadata.title }}`;
    const branch = `\${{ ("implement_" + (parameters.${idField} | lower)) if parameters.mode === "create" else ("change_" + (steps.fetch.output.entity.metadata.title | lower) + "_" + parameters.change_reference) }}`;

    const createProperties: Record<string, any> = {};
    const changeProperties: Record<string, any> = {
      target: {
        title: kind.label,
        type: 'string',
        description: `The ${kind.label} to change`,
        'ui:field': 'EntityPicker',
        'ui:options': {
          catalogFilter: {
            kind: kind.mapping.entity,
            'spec.type': kind.tag,
          },
          defaultKind: kind.mapping.entity,
          allowArbitraryValues: false,
        },
      },
      change_reference: {
        title: 'Change reference',
        type: 'string',
        description: 'Short name for this change, used as the branch suffix',
        pattern: '^[a-z0-9-]+$',
      },
    };

    for (const [name, property] of kind.attributes) {
      const field = {
        // The schema's own title where it has one, so a carefully labelled
        // field keeps its label rather than one derived from the field name.
        title: property.title ?? this.fieldTitle(name),
        type: property.type,
        // An array field renders nothing without `items` -- rjsf has no way to
        // know what one element looks like, and the field silently disappears
        // from the form while the property is still in the schema.
        ...(property.items ? { items: property.items } : {}),
        ...(property.enum ? { enum: property.enum } : {}),
        // Infrahub's labels for those values -- see withChoiceLabels.
        ...(property.enumNames ? { enumNames: property.enumNames } : {}),
        ...(property.description ? { description: property.description } : {}),
      };
      createProperties[name] = {
        ...field,
        ...(this.hasDefault(property) ? { default: property.default } : {}),
      };
      // The identifier is what a change is looked up by, so it is not editable.
      if (name !== idField) {
        changeProperties[name] = {
          ...field,
          description: property.description
            ? `${property.description}. Leave empty to keep the current value`
            : 'Leave empty to keep the current value',
        };
      }
    }

    for (const relationship of formRels) {
      const widget = relationship.picker
        ? {
            'ui:field': 'EntityPicker',
            'ui:options': {
              catalogFilter: {
                kind: relationship.picker.kind,
                'spec.type': relationship.picker.type,
              },
              defaultKind: relationship.picker.kind,
              allowArbitraryValues: false,
            },
          }
        : // No entities behind this peer, so ask for the identifier Infrahub
          // uses. Less pretty than a picker, and better than losing the field.
          { 'ui:placeholder': `${relationship.peer} identifier` };

      const description = relationship.picker
        ? `The ${relationship.peer} this service belongs to`
        : `The ${relationship.peer} this service belongs to, by its Infrahub identifier`;

      // A composite hfid needs every element, so the field is an array and the
      // description says which parts, in order -- nothing else in the form
      // tells a requester that `10.112.240.10/32` alone will be refused.
      const composite = (relationship.hfidLength ?? 1) > 1;
      const shape = composite
        ? { type: 'array', items: { type: 'string' } }
        : { type: 'string', ...widget };
      const text = composite
        ? `${description}, as its ${relationship.hfidLength} hfid elements in order`
        : description;

      createProperties[relationship.name] = {
        title: this.fieldTitle(relationship.name),
        ...shape,
        description: text,
      };
      if (relationship.optional !== false) {
        changeProperties[relationship.name] = {
          ...createProperties[relationship.name],
          description: `${text}. Leave empty to keep the current value`,
        };
      }
    }

    return {
      apiVersion: 'scaffolder.backstage.io/v1beta3',
      kind: 'Template',
      metadata: {
        name: `${kind.tag}-request`,
        title: `${kind.label} (generated)`,
        description:
          `Request a new ${kind.label} service, or change an existing one. ` +
          `Generated from the Infrahub schema, so it follows the kind's own fields.`,
        tags: ['infrahub', 'service-request', 'generated'],
        ...this.base(`${this.infrahub.externalAddress}/schema`),
      },
      spec: {
        type: kind.tag,
        owner: this.catalog.owner,
        parameters: [
          {
            title: kind.label,
            required: ['mode'],
            properties: {
              mode: {
                title: 'What do you want to do?',
                type: 'string',
                default: 'create',
                enum: ['create', 'change'],
                enumNames: [
                  'Request a new service',
                  'Change an existing service',
                ],
              },
            },
            dependencies: {
              mode: {
                oneOf: [
                  {
                    required: [
                      ...kind.required.filter(
                        name => !GENERATED_FORM_EXCLUDES.includes(name),
                      ),
                      ...formRels
                        .filter(relationship => relationship.optional === false)
                        .map(relationship => relationship.name),
                    ],
                    properties: {
                      mode: { enum: ['create'] },
                      ...createProperties,
                    },
                  },
                  {
                    required: ['target', 'change_reference'],
                    properties: {
                      mode: { enum: ['change'] },
                      ...changeProperties,
                    },
                  },
                ],
              },
            },
          },
        ],
        steps: [
          {
            id: 'fetch',
            name: 'Read the service',
            if: '${{ parameters.mode === "change" }}',
            action: 'catalog:fetch',
            input: { entityRef: '${{ parameters.target }}' },
          },
          {
            id: 'branch',
            name: 'Create Infrahub branch',
            action: 'infrahub:graphql:execute',
            input: {
              query:
                'mutation ($name: String!) {\n' +
                '  BranchCreate(data: { name: $name, sync_with_git: false }) {\n' +
                '    ok\n  }\n}',
              variables: { name: branch },
            },
          },
          {
            id: 'create',
            name: 'Create service',
            if: '${{ parameters.mode === "create" }}',
            action: 'infrahub:graphql:execute',
            input: {
              branch,
              query: this.createMutation(
                kind.kind,
                upfront,
                requiredRels,
                kind.mapping.groups,
              ),
              variables: {
                ...Object.fromEntries(
                  upfront.map(([name]) => [name, `\${{ parameters.${name} }}`]),
                ),
                ...Object.fromEntries(
                  requiredRels.map(relationship => [
                    relationship.name,
                    this.relationshipValue(relationship),
                  ]),
                ),
              },
            },
          },
          // One guarded step per attribute. An upfront attribute is already set
          // by the create, so it only runs on a change; an optional one runs in
          // either mode, because the create leaves it out.
          ...kind.attributes
            .filter(([name]) => name !== idField)
            .map(([name, property]) => {
              const isUpfront = upfront.some(([field]) => field === name);
              const provided = this.providedGuard(name, property.type);
              return {
                id: name,
                name: `Set ${this.fieldTitle(name).toLowerCase()}`,
                if: isUpfront
                  ? `\${{ parameters.mode === "change" and ${provided} }}`
                  : `\${{ ${provided} }}`,
                action: 'infrahub:graphql:execute',
                input: {
                  branch,
                  query: this.updateMutation(kind.kind, name, property.type),
                  variables: {
                    id: identifier,
                    value: `\${{ parameters.${name} }}`,
                  },
                },
              };
            }),
          // An optional relationship is set the same guarded way, in either mode.
          ...optionalRels.map(relationship => ({
            id: relationship.name,
            name: `Set ${this.fieldTitle(relationship.name).toLowerCase()}`,
            if: `\${{ parameters.${relationship.name} }}`,
            action: 'infrahub:graphql:execute',
            input: {
              branch,
              query: this.relationshipMutation(
                kind.kind,
                relationship.name,
                relationship.hfidLength,
              ),
              variables: {
                id: identifier,
                value: this.relationshipValue(relationship),
              },
            },
          })),
          // A generator expands the service asynchronously, so hold the
          // proposed change until it has finished -- see generatorsAwait.ts.
          {
            id: 'generators',
            name: 'Wait for the generators',
            action: 'infrahub:generators:await',
            input: {
              branch,
              node: `\${{ steps.create.output.data.${kind.kind}Create.object.id if parameters.mode === "create" else steps.fetch.output.entity.metadata.annotations["${INFRAHUB_ANNOTATIONS.id}"] }}`,
            },
          },
          {
            id: 'proposed_change',
            name: 'Open proposed change',
            action: 'infrahub:graphql:execute',
            input: {
              query:
                'mutation ($name: String!, $source_branch: String!) {\n' +
                '  CoreProposedChangeCreate(\n' +
                '    data: {\n' +
                '      name: { value: $name }\n' +
                '      source_branch: { value: $source_branch }\n' +
                '      destination_branch: { value: "main" }\n' +
                '      tags: [{ hfid: ["service_request"] }]\n' +
                '    }\n  ) {\n    ok\n    object { id }\n  }\n}',
              variables: {
                name: `\${{ ("Implement ${kind.label} " + (parameters.${idField} | lower)) if parameters.mode === "create" else ("Change " + parameters.change_reference + " on " + steps.fetch.output.entity.metadata.title) }}`,
                source_branch: branch,
              },
            },
          },
          // Without this the service is not in the catalog until the next
          // poll, so the link below would 404 for up to a minute.
          {
            id: 'catalog',
            name: 'Refresh the catalog',
            action: 'infrahub:catalog:refresh',
          },
        ],
        output: {
          links: [
            {
              title: 'Proposed change in Infrahub',
              url: '${{ steps.proposed_change.output.address }}/proposed-changes/${{ steps.proposed_change.output.data.CoreProposedChangeCreate.object.id }}',
            },
            {
              title: `${kind.label} in the catalog`,
              url: `/catalog/default/${kind.mapping.entity.toLowerCase()}/\${{ parameters.${idField} | lower }}`,
            },
            {
              title: `${kind.label} in Infrahub`,
              url: `\${{ (steps.create.output.address + "/objects/${kind.kind}/" + steps.create.output.data.${kind.kind}Create.object.id) if parameters.mode === "create" else steps.fetch.output.entity.metadata.annotations["backstage.io/view-url"] }}`,
            },
          ],
        },
      },
    };
  }

  private createMutation(
    kind: string,
    attributes: [string, any][],
    relationships: ResolvedRelationship[],
    groups: string[],
  ): string {
    const declarations = [
      ...attributes.map(
        ([name, property]) =>
          `$${name}: ${JSON_TO_GRAPHQL[property.type] ?? 'String'}!`,
      ),
      // `[String]!` for a composite hfid, because the lookup needs every
      // element and Infrahub refuses a list of the wrong length outright.
      ...relationships.map(
        relationship =>
          `$${relationship.name}: ${
            (relationship.hfidLength ?? 1) > 1 ? '[String]' : 'String'
          }!`,
      ),
    ].join(', ');

    const fields = [
      ...attributes.map(([name]) => `      ${name}: { value: $${name} }`),
      // NO `status` HERE, and that is a fix rather than an omission.
      //
      // This used to send `status: { value: "draft" }`, which is a value the
      // upstream example's schema has and this one does not. Infrahub refuses
      // the whole create:
      //
      //   draft must be one of 'active, decommissioned, decommissioning,
      //   error, provisioning' at status
      //
      // -- so every request through every generated template failed at its
      // first step, for every kind. Leaving it out lets the schema's own
      // default apply, which here is `provisioning`: ordered, not yet
      // materialised, which is exactly what a new request is. Sending any
      // literal would just be a different schema's vocabulary hardcoded into
      // this one.
      ...relationships.map(relationship =>
        (relationship.hfidLength ?? 1) > 1
          ? `      ${relationship.name}: { hfid: $${relationship.name} }`
          : `      ${relationship.name}: { hfid: [$${relationship.name}] }`,
      ),
      // An Infrahub generator definition targets a group, so a new object has
      // to join it or nothing will ever expand the object.
      ...(groups.length
        ? [
            `      member_of_groups: [${groups
              .map(group => `{ hfid: ["${group}"] }`)
              .join(', ')}]`,
          ]
        : []),
    ].join('\n');

    return [
      `mutation (${declarations}) {`,
      `  ${kind}Create(`,
      '    data: {',
      fields,
      '    }',
      '  ) {',
      '    ok',
      '    object { id }',
      '  }',
      '}',
    ].join('\n');
  }

  private relationshipMutation(
    kind: string,
    field: string,
    hfidLength = 1,
  ): string {
    const composite = hfidLength > 1;
    return [
      `mutation ($id: String!, $value: ${composite ? '[String]' : 'String'}!) {`,
      `  ${kind}Update(data: { hfid: [$id], ${field}: { hfid: ${
        composite ? '$value' : '[$value]'
      } } }) {`,
      '    ok',
      '  }',
      '}',
    ].join('\n');
  }

  private updateMutation(kind: string, field: string, type: string): string {
    return [
      `mutation ($id: String!, $value: ${
        JSON_TO_GRAPHQL[type] ?? 'String'
      }!) {`,
      `  ${kind}Update(data: { hfid: [$id], ${field}: { value: $value } }) {`,
      '    ok',
      '  }',
      '}',
    ].join('\n');
  }

  /** service_identifier -> Service Identifier */
  private fieldTitle(name: string): string {
    return name
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  }

  /**
   * A picker yields an entity ref, so the Infrahub identifier has to be pulled
   * back out of it. An hfid typed by hand is already the identifier.
   */
  private relationshipValue(relationship: ResolvedRelationship): string {
    return relationship.picker
      ? `\${{ parameters.${relationship.name} | parseEntityRef | pick('name') }}`
      : `\${{ parameters.${relationship.name} }}`;
  }

  /** ServiceDedicatedInternet -> dedicated-internet */

  /**
   * One API entity per ingested kind, its definition the kind's GraphQL slice,
   * so every kind has a "what can I query about this" page. Deliberately
   * unlinked: an Infrahub service does not expose or consume this API, Infrahub
   * does, and inventing providesApis/consumesApis edges would be fiction.
   */
  private async apiEntities(mappings: KindMapping[]): Promise<Entity[]> {
    const built = await mapLimit<KindMapping, Entity | undefined>(
      mappings,
      CONCURRENCY,
      async mapping => {
        const kind = mapping.kind;
        let schema: KindSchema;
        try {
          schema = await infrahubGet(this.infrahub, `/api/schema/${kind}`);
        } catch (error) {
          this.logger.warn(`Could not read the schema for ${kind}: ${error}`);
          return undefined;
        }

        return {
          apiVersion: 'backstage.io/v1alpha1',
          kind: 'API',
          metadata: {
            name: kind.toLowerCase(),
            title: kind,
            description:
              schema.description ??
              `The ${kind} slice of Infrahub's GraphQL API`,
            tags: ['infrahub-schema'],
            ...this.base(`${this.infrahub.externalAddress}/schema`),
          },
          spec: {
            type: 'graphql',
            lifecycle: 'production',
            owner: this.catalog.owner,
            definition: this.graphqlSlice(kind, schema),
          },
        };
      },
    );

    return built.filter((entity): entity is Entity => entity !== undefined);
  }

  private graphqlSlice(kind: string, schema: KindSchema): string {
    const field = (
      name: string,
      type: string,
      optional: boolean | undefined,
      note?: string,
    ) => `  ${name}: ${type}${optional === false ? '!' : ''}${note ?? ''}`;

    const attributes = (schema.attributes ?? []).map(attribute =>
      field(
        attribute.name,
        GRAPHQL_SCALARS[attribute.kind] ?? 'String',
        attribute.optional,
        attribute.choices?.length
          ? `  # one of: ${attribute.choices.map(c => c.name).join(', ')}`
          : undefined,
      ),
    );

    const relationships = (schema.relationships ?? []).map(relationship =>
      field(
        relationship.name,
        relationship.cardinality === 'many'
          ? `[${relationship.peer}]`
          : relationship.peer,
        relationship.optional,
      ),
    );

    return [
      schema.description ? `"""${schema.description}"""` : undefined,
      `type ${kind} {`,
      ...attributes,
      ...(relationships.length ? ['', '  # relationships'] : []),
      ...relationships,
      '}',
    ]
      .filter(line => line !== undefined)
      .join('\n');
  }
}

export const infrahubCatalogModule = createBackendModule({
  pluginId: 'catalog',
  moduleId: 'infrahub-catalog',
  register(env) {
    env.registerInit({
      deps: {
        catalog: catalogProcessingExtensionPoint,
        config: coreServices.rootConfig,
        logger: coreServices.logger,
        scheduler: coreServices.scheduler,
      },
      async init({ catalog, config, logger, scheduler }) {
        catalog.addEntityProvider(
          new InfrahubEntityProvider(
            readInfrahubConfig(config),
            readCatalogConfig(config),
            config.getString('app.baseUrl').replace(/\/$/, ''),
            logger,
            scheduler,
          ),
        );
      },
    });
  },
});
