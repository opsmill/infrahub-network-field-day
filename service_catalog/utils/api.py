"""Infrahub API client for the Service Catalog."""

from typing import Any

from infrahub_sdk import Config, InfrahubClientSync


class InfrahubAPIError(Exception):
    """Base exception for Infrahub API errors."""


class InfrahubConnectionError(InfrahubAPIError):
    """Exception raised when connection to Infrahub fails."""


class InfrahubHTTPError(InfrahubAPIError):
    """Exception raised for HTTP errors from Infrahub."""

    def __init__(self, message: str, status_code: int, response_text: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class InfrahubGraphQLError(InfrahubAPIError):
    """Exception raised for GraphQL errors from Infrahub."""

    def __init__(self, message: str, errors: list[dict[str, Any]]):
        super().__init__(message)
        self.errors = errors


class InfrahubClient:
    """Client for interacting with the Infrahub API using the official SDK."""

    def __init__(
        self,
        base_url: str,
        api_token: str | None = None,
        timeout: int = 60,
        ui_url: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.ui_url = (ui_url or base_url).rstrip("/")
        self.api_token = api_token
        self.timeout = timeout

        config = Config(timeout=timeout, api_token=api_token or None)
        self._client = InfrahubClientSync(address=base_url, config=config)

    def get_branches(self) -> list[dict[str, Any]]:
        """Fetch all branches from Infrahub."""
        try:
            branches_dict = self._client.branch.all()
            branches = []
            for branch_name, branch_data in branches_dict.items():
                branches.append(
                    {
                        "name": branch_name,
                        "id": branch_data.id,
                        "is_default": branch_data.is_default,
                        "sync_with_git": branch_data.sync_with_git,
                    }
                )
            return branches
        except Exception as e:
            raise InfrahubConnectionError(f"Failed to fetch branches: {e!s}")

    def execute_graphql(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        branch: str = "main",
    ) -> dict[str, Any]:
        """Execute a GraphQL query or mutation."""
        try:
            result = self._client.execute_graphql(query=query, variables=variables, branch_name=branch)
            return result
        except Exception as e:
            raise InfrahubGraphQLError(f"GraphQL error: {e!s}", [])

    def get_fabrics(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch NetworkFabric objects."""
        try:
            query = """
            query GetFabrics {
                NetworkFabric {
                    edges {
                        node {
                            id
                            display_label
                            name { value }
                        }
                    }
                }
            }
            """
            result = self.execute_graphql(query, branch=branch)
            fabrics = []
            for edge in result.get("NetworkFabric", {}).get("edges", []):
                node = edge["node"]
                fabrics.append(
                    {
                        "id": node.get("id"),
                        "name": {"value": node.get("name", {}).get("value")},
                        "display_label": node.get("display_label"),
                    }
                )
            return fabrics
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch fabrics: {e!s}")

    def get_organizations(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch OrganizationGeneric objects."""
        try:
            query = """
            query GetOrganizations {
                OrganizationGeneric {
                    edges {
                        node {
                            id
                            display_label
                            __typename
                        }
                    }
                }
            }
            """
            result = self.execute_graphql(query, branch=branch)
            organizations = []
            for edge in result.get("OrganizationGeneric", {}).get("edges", []):
                node = edge["node"]
                organizations.append(
                    {
                        "id": node.get("id"),
                        "display_label": node.get("display_label"),
                        "type": node.get("__typename"),
                    }
                )
            return organizations
        except Exception as e:
            raise InfrahubAPIError(f"Failed to fetch organizations: {e!s}")

    def create_branch(self, branch_name: str, sync_with_git: bool = False) -> dict[str, Any]:
        """Create a new branch in Infrahub, or return it if it already exists."""
        try:
            branch = self._client.branch.create(branch_name=branch_name, sync_with_git=sync_with_git)
            return {
                "name": branch.name,
                "id": branch.id,
                "is_default": branch.is_default,
            }
        except Exception as e:
            if "already exists" in str(e):
                branches = self._client.branch.all()
                if branch_name in branches:
                    branch = branches[branch_name]
                    return {
                        "name": branch.name,
                        "id": branch.id,
                        "is_default": branch.is_default,
                    }
            raise InfrahubAPIError(f"Failed to create branch: {e!s}")

    def create_proposed_change(
        self, branch: str, name: str, description: str, destination_branch: str = "main"
    ) -> dict[str, Any]:
        """Create a proposed change for a branch."""
        try:
            pc = self._client.create(
                kind="CoreProposedChange",
                branch=branch,
                name=name,
                description=description,
                source_branch=branch,
                destination_branch=destination_branch,
            )
            pc.save(allow_upsert=True)
            return {"id": pc.id, "name": name}
        except Exception as e:
            raise InfrahubAPIError(f"Failed to create proposed change: {e!s}")

    def get_proposed_change_url(self, pc_id: str) -> str:
        """Get the URL for a proposed change."""
        return f"{self.ui_url}/proposed-changes/{pc_id}"

    def get_tenants(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch EvpnTenant objects."""
        query = """
        query { EvpnTenant { edges { node {
            id display_label name { value } mac_vrf_vni_base { value }
            fabrics { edges { node { id name { value } } } }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("EvpnTenant", {}).get("edges", [])]

    def get_vrfs(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch IpamVRF objects."""
        query = """
        query { IpamVRF { edges { node {
            id display_label name { value } vrf_vni { value }
            tenant { node { id name { value } } }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("IpamVRF", {}).get("edges", [])]

    def get_vlans(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch IpamVLAN objects."""
        query = """
        query { IpamVLAN { edges { node {
            id display_label name { value } vlan_id { value }
            l2domain { node { id name { value } } }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("IpamVLAN", {}).get("edges", [])]

    def get_racks(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch LocationRack objects, with the leaves in each.

        The leaves matter to the form: `generate-server-cabling` cables a
        machine to the switches in ITS rack, so choosing a rack is choosing what
        the machine is wired to.
        """
        query = """
        query { LocationRack { edges { node {
            id display_label name { value }
            devices { edges { node { id name { value } } } }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("LocationRack", {}).get("edges", [])]

    def get_object_templates(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch CoreObjectTemplate objects.

        A template is what gives a machine its interfaces, and cabling cables
        interfaces -- so a placement without one produces a host connected to
        nothing while every step reports success.
        """
        query = """
        query { CoreObjectTemplate { edges { node {
            id __typename template_name { value }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("CoreObjectTemplate", {}).get("edges", [])]

    def create_service(
        self,
        *,
        kind: str,
        branch: str,
        group: str,
        fields: dict[str, Any],
        relationships: dict[str, str | list[str]],
    ) -> str:
        """Create any service kind on a branch, in its generator's target group.

        One helper rather than one per kind, because every service request has
        the same shape: some attribute values, some relationships, a status of
        `provisioning`, and membership of the group the generator targets.
        Membership is the part that is easy to leave out and impossible to
        notice -- a service outside its group is created and then silently never
        built.
        """
        group_id = self._group_id(group, branch=branch)

        declarations = ["$group: String!"]
        assignments = ['status: { value: "provisioning" }', "member_of_groups: [{ id: $group }]"]
        variables: dict[str, Any] = {"group": group_id}

        for name, value in fields.items():
            gql_type = "BigInt" if isinstance(value, int) and not isinstance(value, bool) else "String"
            declarations.append(f"${name}: {gql_type}")
            assignments.append(f"{name}: {{ value: ${name} }}")
            variables[name] = value

        for name, value in relationships.items():
            if isinstance(value, list):
                declarations.append(f"${name}: [RelatedNodeInput]")
                assignments.append(f"{name}: ${name}")
                variables[name] = [{"id": item} for item in value]
            else:
                declarations.append(f"${name}: String!")
                assignments.append(f"{name}: {{ id: ${name} }}")
                variables[name] = value

        mutation = (
            f"mutation({', '.join(declarations)}) {{\n"
            f"  {kind}Create(data: {{ {' '.join(assignments)} }}) {{ ok object {{ id }} }}\n"
            "}"
        )
        result = self.execute_graphql(mutation, variables, branch=branch)
        return str(result[f"{kind}Create"]["object"]["id"])

    def get_organization_tenants(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch OrganizationTenant objects.

        NOT the same thing as `get_tenants`, which returns `EvpnTenant`. The two
        are different kinds serving different layers -- an EvpnTenant is a
        fabric-level construct carrying VNI bases, while an OrganizationTenant is
        who the service is for. `ServiceNetworkSegment.tenant` peers this one, so
        passing an EvpnTenant id is rejected by the mutation.
        """
        query = """
        query { OrganizationTenant { edges { node {
            id display_label name { value }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("OrganizationTenant", {}).get("edges", [])]

    def get_avd_tags(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch AvdTag objects, with the racks each one selects.

        These decide where a segment lands. AVD renders an SVI onto a device only
        where the SVI's tags intersect that device's node-group filter, and in
        this fabric those filters are the racks' own AvdTags -- so a segment with
        no tag renders on no switch at all, silently. The rack names come back
        with them so the form can say which leaves a tag means.
        """
        query = """
        query { AvdTag { edges { node {
            id name { value } description { value }
            racks { edges { node { id name { value } } } }
        } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("AvdTag", {}).get("edges", [])]

    def create_network_segment(
        self,
        *,
        branch: str,
        name: str,
        description: str,
        owner_id: str,
        tenant_id: str,
        vrf_id: str,
        fabric_id: str,
        avd_tag_ids: list[str],
        prefix_length: int,
        vlan_id: int | None = None,
    ) -> str:
        """Request a network segment, and nothing else.

        ONE object. The subnet, the VLAN and the SVI are the generator's job --
        `generate-network-segment` builds all three when the branch merges. The
        portal used to create them itself, which meant a requester had to know
        which VLAN ids were free and which subnet to use, and produced a segment
        with no record of who asked for it and nothing to withdraw.

        `vlan_id` is OMITTED rather than defaulted when the requester states
        none. Empty means "allocate one"; sending a number would turn the
        request back into the work order this replaces.

        Membership of `service_network_segments` is what makes the generator run
        at all -- a generator targets a group, so a segment outside it is created
        and then silently never built.
        """
        group_id = self._group_id("service_network_segments", branch=branch)

        fields = [
            "name: { value: $name }",
            "description: { value: $description }",
            'status: { value: "provisioning" }',
            "owner: { id: $owner }",
            "tenant: { id: $tenant }",
            "vrf: { id: $vrf }",
            "fabric: { id: $fabric }",
            "avd_tags: $avd_tags",
            "prefix_length: { value: $prefix_length }",
            "member_of_groups: [{ id: $group }]",
        ]
        declarations = [
            "$name: String!",
            "$description: String!",
            "$owner: String!",
            "$tenant: String!",
            "$vrf: String!",
            "$fabric: String!",
            "$avd_tags: [RelatedNodeInput]",
            "$prefix_length: BigInt!",
            "$group: String!",
        ]
        variables: dict[str, Any] = {
            "name": name,
            "description": description,
            "owner": owner_id,
            "tenant": tenant_id,
            "vrf": vrf_id,
            "fabric": fabric_id,
            "avd_tags": [{"id": tag_id} for tag_id in avd_tag_ids],
            "prefix_length": prefix_length,
            "group": group_id,
        }
        if vlan_id is not None:
            declarations.append("$vlan_id: BigInt")
            fields.append("vlan_id: { value: $vlan_id }")
            variables["vlan_id"] = vlan_id

        mutation = (
            f"mutation({', '.join(declarations)}) {{\n"
            f"  ServiceNetworkSegmentCreate(data: {{ {' '.join(fields)} }}) {{ ok object {{ id }} }}\n"
            "}"
        )
        result = self.execute_graphql(mutation, variables, branch=branch)
        return str(result["ServiceNetworkSegmentCreate"]["object"]["id"])

    def _group_id(self, group_name: str, branch: str = "main") -> str:
        """Resolve a CoreStandardGroup's id, refusing to guess.

        Passing the name straight into `member_of_groups` happens to work in
        some Infrahub versions through HFID resolution and not in others, and the
        failure is a segment that exists, belongs to no group, and is therefore
        never built by the generator -- with no error anywhere. Resolving it
        explicitly turns that into a message naming the missing group.
        """
        query = """
        query($name: String!) {
            CoreStandardGroup(name__value: $name) { edges { node { id } } }
        }
        """
        result = self.execute_graphql(query, {"name": group_name}, branch=branch)
        edges = result.get("CoreStandardGroup", {}).get("edges", [])
        if not edges:
            raise InfrahubAPIError(
                f"group {group_name!r} does not exist, so a segment created now would never be built "
                "by generate-network-segment; load objects/00_groups.yml"
            )
        return str(edges[0]["node"]["id"])

    def get_l2domains(self, branch: str = "main") -> list[dict[str, Any]]:
        """Fetch IpamL2Domain objects."""
        query = """
        query { IpamL2Domain { edges { node { id display_label name { value } } } } }
        """
        result = self.execute_graphql(query, branch=branch)
        return [e["node"] for e in result.get("IpamL2Domain", {}).get("edges", [])]

    def _resolve_target_id(self, name: str, branch: str = "main") -> str | None:
        """Resolve a node name to its ID by searching common types."""
        for kind in ["NetworkFabric", "NetworkPod", "LocationRack", "DcimFabricSwitch", "DcimDevice"]:
            try:
                query = f'{{ {kind}(name__value: "{name}") {{ edges {{ node {{ id }} }} }} }}'
                result = self.execute_graphql(query, branch=branch)
                edges = result.get(kind, {}).get("edges", [])
                if edges:
                    return edges[0]["node"]["id"]
            except Exception:  # noqa: BLE001
                continue
        return None

    def _run_generator(
        self, generator_name: str, branch: str = "main", timeout: int = 600, target: str | None = None
    ) -> str | bool:
        """Trigger a generator run.

        Args:
            generator_name: Name of the generator definition
            branch: Branch to run on
            timeout: Max seconds to wait for the HTTP call
            target: Optional target object name (e.g. fabric name) to run for a specific member

        Returns task ID string if submitted, True if ok without task ID, False on failure.
        """
        import httpx as _httpx

        # Find the generator definition ID
        query = """
        query($name: String!) {
            CoreGeneratorDefinition(name__value: $name) {
                edges { node { id } }
            }
        }
        """
        result = self.execute_graphql(query, {"name": generator_name}, branch=branch)
        edges = result.get("CoreGeneratorDefinition", {}).get("edges", [])
        if not edges:
            raise InfrahubAPIError(f"Generator '{generator_name}' not found")

        gen_id = edges[0]["node"]["id"]

        mutation = """
        mutation CoreGeneratorDefinitionRun(
            $generatorId: String!,
            $waitUntilCompletion: Boolean,
            $targetNodeIds: [String!]
        ) {
            CoreGeneratorDefinitionRun(
                wait_until_completion: $waitUntilCompletion
                data: { id: $generatorId, nodes: $targetNodeIds }
            ) {
                task { id }
            }
        }
        """

        variables: dict[str, Any] = {
            "generatorId": gen_id,
            "waitUntilCompletion": False,
        }

        if target:
            target_id = self._resolve_target_id(target, branch)
            if target_id:
                variables["targetNodeIds"] = [target_id]

        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["X-INFRAHUB-KEY"] = self.api_token

        try:
            resp = _httpx.post(
                f"{self.base_url}/graphql/{branch}",
                json={"query": mutation, "variables": variables},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                task = data.get("data", {}).get("CoreGeneratorDefinitionRun", {}).get("task", {})
                return task.get("id") if task else True
            return False
        except _httpx.TimeoutException:
            return False

    def run_avd_pipeline(self, branch: str = "main") -> dict[str, bool]:
        """Run the full AVD pipeline: hostvars then structured config.

        Blocks until each generator completes. Returns status for each step.
        """
        results: dict[str, bool] = {}

        results["hostvars"] = self._run_generator("generate-avd-device-hostvar", branch=branch, timeout=600)

        results["structured_config"] = self._run_generator(
            "generate-avd-device-structured-config", branch=branch, timeout=600
        )

        return results
