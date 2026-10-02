# OTTERNET lab — EVPN fabric + AVD + security + Kubernetes
#
# Two sizes of the same lab, on one topology file:
#
#   make deploy       full fabric + WAN + branch   ~37 GB RAM
#   make deploy-lite  one pod + WAN + branch       ~30 GB RAM
#
# The firewall is a Junos vSRX in both. It is a VM under vrnetlab, so BOTH
# require CPU virtualization -- there is no container-firewall fallback any
# more. `make preflight` checks before anything is torn down.
#
# Both include the ISP, its customers and the branch office with its desktop and
# Guacamole gateway -- the branch is where the self-service access demo lives.
#
SHELL := $(shell command -v bash)
.DEFAULT_GOAL := help
.ONESHELL:

# Every target here is a command, not a file. This is not boilerplate: the
# `crossplane` target has the same name as the crossplane/ directory, so
# without this make finds the directory, decides the target is already built,
# and prints "make: 'crossplane' is up to date." while doing nothing at all.
.PHONY: access access-images access-status avd-build avd-clean avd-deploy avd-validate clean crossplane deploy deploy-lite desktop-image destroy fabric-bgp fw-console fw-image fw-log grafana grafana-forward graph guac help hubble inspect k8s k8s-bgp k8s-status post-deploy preflight preflight-lite prometheus-forward redeploy setup tooling-bridge verify wan-bgp wan-build wan-customers wan-deploy wan-tenants xp xp-apply xp-drift

LAB      := otternet
TOPO     := otternet.clab.yml
# sudo -E is refused outright on this host ("preserving the entire environment is
# not supported"), which would silently drop every OTTERNET_* override. Name the
# variables explicitly instead.
CLAB_ENV := OTTERNET_CEOS_IMAGE,OTTERNET_CEOS_MEMORY,OTTERNET_VSRX_IMAGE
CLAB     := sudo --preserve-env=$(CLAB_ENV) containerlab
VENV     := .venv/bin
AVD      := cd avd && ANSIBLE_COLLECTIONS_PATH=$(CURDIR)/.ansible/collections $(CURDIR)/$(VENV)/ansible-playbook

# NEVER put $(MAKE) inside a recipe in this file.
#
# This Makefile sets .ONESHELL, so the whole recipe is a single shell
# invocation -- and GNU make executes any recipe line containing $(MAKE) even
# under `make -n`, on the assumption that a recursive make will itself honour
# the dry run. With .ONESHELL that "line" is the ENTIRE recipe, so one $(MAKE)
# at the bottom makes every command above it run for real. Worse, `make -n`
# skips prerequisites, so `preflight` does not gate it.
#
# `make -n deploy` therefore destroyed a running lab once: containerlab deploy
# --reconfigure tears the lab down first, the firewall VM then failed the
# virtualization check, and nothing came back up. From a dry run.
#
# So sub-steps that need to be shared are shell command variables, called
# directly, rather than recursive make targets.
# $(AVD) begins with `cd avd &&`, and .ONESHELL means the whole recipe is one
# shell -- so that cd LEAKS into every command after it in the same recipe.
# `make deploy` failed with "./scripts/wan-deploy.sh: No such file or
# directory" for exactly this reason: by then the shell was sitting in avd/.
# Wrapping it in a subshell contains the cd; the script paths are absolute so
# they do not care either way.
AVD_DEPLOY   := ( $(AVD) playbooks/deploy.yml )
POST_DEPLOY   = printf '\n\033[1;36m==> Waiting for the fabric to finish booting (ceOS takes a few minutes)\033[0m\n'; $(AVD_DEPLOY)
WAN_DEPLOY   := $(CURDIR)/scripts/wan-deploy.sh
KUBECONFIG_PATH := $(CURDIR)/k8s/.kubeconfig/kubeconfig.yaml
KUBECTL  := kubectl --kubeconfig $(KUBECONFIG_PATH)

# The 'lite' profile trims the fabric to one pod plus the border leaf and drops a
# k3s node, so the lab coexists with other workloads on a 30 GB host.
# Every node the ISP or the branch router has a wire to must be in this list,
# even the ones the lite deployment does not really need. Their init scripts
# wait for each interface by name, and a filtered-out peer means the wire is
# never created -- so the router sits in wait_for for five minutes and then
# fails, which reads as a broken image rather than a missing neighbour.
LITE_NODES := spine1,spine2,k8s-leaf1,k8s-leaf2,border-leaf1,fw1,k8s-node1,k8s-node2,host-a,isp-pe1,isp-pe2,cust-acme-ce,cust-acme-host,cust-acme-dr-ce,cust-acme-dr-host,cust-globex-ce,cust-globex-host,internet-rtr,internet-host,branch-rtr,branch-host,branch-desktop,branch-guacd,branch-guac

export OTTERNET_CEOS_IMAGE  ?= ceos:4.36.0.1F
export OTTERNET_CEOS_MEMORY ?= 2048MB

# The firewall. Juniper does not redistribute the image, so it is built locally
# by scripts/build-vsrx.sh from a qcow2 in /images; the version comes straight
# out of that file's name because that is exactly how vrnetlab derives the
# docker tag, so the two cannot disagree.
VSRX_VERSION ?= 22.3R1.11
OTTERNET_VSRX_QCOW2 ?= /images/junos-vsrx3-x86-64-$(VSRX_VERSION).qcow2
export OTTERNET_VSRX_IMAGE ?= vrnetlab/juniper_vsrx:$(VSRX_VERSION)

## ---------------------------------------------------------------- setup ----

help: ## Show this help
	@printf '\n\033[1mOTTERNET lab\033[0m\n\n'
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@printf '\n\033[1mDeployments\033[0m\n'
	@printf '  \033[36mdeploy\033[0m           full fabric + WAN + branch, vSRX firewall  ~37 GB RAM\n'
	@printf '  \033[36mdeploy-lite\033[0m      one pod + WAN + branch, vSRX firewall      ~30 GB RAM\n'
	@printf '\n  Both need CPU virtualization -- the firewall is a VM. Both include the ISP,\n'
	@printf '  its customers, and the branch office with its desktop and Guacamole\n'
	@printf '  gateway, which is where the self-service access demo lives.\n\n'

setup: ## Build the AVD virtualenv and install collections
	./scripts/setup.sh

preflight: ## Check this host can run the lab
	./scripts/preflight.sh full

preflight-lite: ## Check this host can run the reduced-footprint lab
	./scripts/preflight.sh lite

## ------------------------------------------------------------------ avd ----

avd-build: ## Render intended configs offline (no images or lab needed)
	$(AVD) playbooks/build.yml

avd-deploy: ## Push intended configs to the running fabric over eAPI
	$(AVD) playbooks/deploy.yml

avd-validate: ## Validate fabric state with ANTA
	$(AVD) playbooks/validate.yml

avd-clean: ## Remove generated AVD output
	rm -rf avd/intended avd/reports

## --------------------------------------------------------------- deploy ----

# No post-deploy config push. containerlab's startup-config genuinely works for
# the juniper_vsrx kind: vrnetlab appends configs/fw/vsrx/junos.conf to its own
# init.conf and Junos loads the result at boot, so the firewall comes up already
# carrying its zones and policy.
# avd-build as well as wan-build: both render generated config from a data
# model, and both are gitignored, so a fresh clone has neither. Regenerating
# on every deploy also means the intended config always matches the model --
# which is the whole premise, and cheap at ~20s offline.
deploy: fw-image desktop-image avd-build wan-build preflight tooling-bridge ## Deploy the full lab + WAN + branch
	$(CLAB) deploy -t $(TOPO) --reconfigure
	$(POST_DEPLOY)
	$(WAN_DEPLOY)

deploy-lite: fw-image desktop-image avd-build wan-build tooling-bridge ## Deploy the reduced-footprint lab
	./scripts/preflight.sh lite
	OTTERNET_CEOS_MEMORY=1536MB \
		$(CLAB) deploy -t $(TOPO) --reconfigure --node-filter $(LITE_NODES)
	$(POST_DEPLOY)
	$(WAN_DEPLOY)

fw-image: ## Build the vSRX vrnetlab image from a Junos vSRX 3.0 qcow2
	./scripts/build-vsrx.sh $(OTTERNET_VSRX_QCOW2)

# ContainerLab does not create a `kind: bridge` node's bridge; it refuses the
# topology when one is missing. A host bridge does not survive a reboot, so this
# is a precondition of every deploy rather than a one-off setup step.
tooling-bridge: ## Create the tooling bridge and the host's address on it
	./scripts/tooling-bridge.sh

desktop-image: ## Build the branch office desktop image (XFCE + VNC + Firefox)
	docker build -t otternet/branch-desktop:local configs/branch/desktop/

fw-console: ## Open the Junos CLI on the firewall
	@echo "Junos CLI -- login admin / $${OTTERNET_VSRX_PASSWORD:-admin@123}"
	docker exec -it clab-$(LAB)-fw1 ssh -o StrictHostKeyChecking=no \
		-o UserKnownHostsFile=/dev/null admin@127.0.0.1

post-deploy: ## Push AVD config to a freshly deployed fabric
	$(POST_DEPLOY)

destroy: ## Tear the lab down
	$(CLAB) destroy -t $(TOPO) --cleanup

redeploy: destroy deploy ## Tear down and redeploy

## ------------------------------------------------------------------ k8s ----

k8s: ## Install Cilium (the CNI only -- BGP and the apps are Crossplane's)
	./k8s/bootstrap/install-cilium.sh

k8s-bgp: ## Show Cilium BGP peering state
	$(KUBECTL) -n kube-system exec ds/cilium -- cilium-dbg bgp peers
	$(KUBECTL) -n kube-system exec ds/cilium -- cilium-dbg bgp routes advertised ipv4 unicast

k8s-status: ## Show cluster, workload and service state
	$(KUBECTL) get nodes -o wide
	$(KUBECTL) -n otternet-demo get pods,svc -o wide
	$(KUBECTL) -n otternet-demo get cnp

hubble: ## Port-forward the Hubble UI to localhost:12000
	@echo "Hubble UI: http://localhost:12000"
	$(KUBECTL) -n kube-system port-forward svc/hubble-ui 12000:80

## ---------------------------------------------------------- crossplane ----

crossplane: ## Install Crossplane, the platform APIs, the peering and the apps
	./k8s/bootstrap/install-crossplane.sh

xp: ## Show what Crossplane is managing and whether it is healthy
	@printf '\n\033[1m--- packages ---\033[0m\n'
	$(KUBECTL) get providers,functions
	@printf '\n\033[1m--- platform APIs ---\033[0m\n'
	$(KUBECTL) get xrd,composition
	@printf '\n\033[1m--- claims ---\033[0m\n'
	$(KUBECTL) get fabricpeering,fabricapp
	@printf '\n\033[1m--- composed resources ---\033[0m\n'
	$(KUBECTL) get objects.kubernetes.crossplane.io,releases.helm.crossplane.io
	@printf '\n\033[1m--- Cilium config Crossplane owns ---\033[0m\n'
	$(KUBECTL) get ciliumbgpclusterconfig,ciliumbgppeerconfig,ciliumbgpadvertisement,ciliumloadbalancerippool

xp-apply: ## Re-apply every Crossplane definition and claim from crossplane/
	$(KUBECTL) apply -f crossplane/providers/01-runtime.yaml -f crossplane/providers/02-rbac.yaml
	$(KUBECTL) apply -f crossplane/providers/00-packages.yaml
	$(KUBECTL) apply -f crossplane/providers/03-provider-configs.yaml
	$(KUBECTL) apply -f crossplane/platform/ -f crossplane/apps/

## ----------------------------------------------------------- access ----
#
# THE LAB'S OWN ACCESS BROKER, which exists only in a lab-only deployment.
# When Infrahub drives this lab, `invoke cluster`'s handover deletes the
# broker ON PURPOSE: nothing in Infrahub models it, and a workload no service
# object declares is state no proposed change can explain. Access is then
# requested through Infrahub's portal (Backstage, in the tooling cluster) as a
# `ServiceAppAccess`, and the rule lands on fw1 through the Junos artifact --
# so there are no AppAccess or FirewallAccess objects for `access-status` to
# show, and `access` would re-install exactly what the handover removed.
#
# The test is the same one scripts/verify.sh uses: a `vidra-system` namespace
# means Infrahub delivers into this cluster. OTTERNET_ACCESS_BROKER=1 overrides
# it, for someone who really does want both.
define access_broker_gate
	@if [ -z "$${OTTERNET_ACCESS_BROKER:-}" ] && $(KUBECTL) get namespace vidra-system >/dev/null 2>&1; then \
		printf '\n\033[1;33mInfrahub drives this lab, so the lab'"'"'s access broker is gone by design.\033[0m\n\n'; \
		printf '  `invoke cluster` removed it in the handover: nothing in Infrahub models it.\n'; \
		printf '  Request access in the Backstage portal instead (a ServiceAppAccess); the\n'; \
		printf '  rule reaches fw1 through the Junos Configuration artifact.\n\n'; \
		printf '  Grants:   Infrahub, Service Requests -> Application Access\n'; \
		printf '  Override: OTTERNET_ACCESS_BROKER=1 make $@   (or `invoke cluster --no-handover`)\n\n'; \
		exit 1; \
	fi
endef

access-images: ## Lab-only: build the access broker's images (refused when Infrahub drives the lab)
	$(access_broker_gate)
	./scripts/access-images.sh

access: ## Lab-only: (re-)install the access broker (refused when Infrahub drives the lab)
	$(access_broker_gate)
	$(KUBECTL) apply -f crossplane/access/00-crd-firewall-access.yaml
	$(KUBECTL) apply -f crossplane/access/01-xrd-app-access.yaml
	$(KUBECTL) apply -f crossplane/access/02-composition-app-access.yaml
	$(KUBECTL) apply -f crossplane/access/03-rbac.yaml
	$(KUBECTL) apply -f crossplane/access/10-access-portal.yaml
	@printf '\n\033[1;36m==> Waiting for the portal\033[0m\n'
	$(KUBECTL) wait fabricapp/otternet-access --for=condition=Ready --timeout=5m

access-status: ## Lab-only: the access broker's requests, grants and firewall policies
	$(access_broker_gate)
	@printf '\n\033[1m--- requests (the platform API) ---\033[0m\n'
	$(KUBECTL) get appaccess
	@printf '\n\033[1m--- grants (what the controller was told to do) ---\033[0m\n'
	$(KUBECTL) get firewallaccess
	@printf '\n\033[1m--- generated policies on the firewall itself ---\033[0m\n'
	@docker exec clab-$(LAB)-fw1 sshpass -p "$${OTTERNET_VSRX_PASSWORD:-admin@123}" \
		ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		admin@127.0.0.1 "show configuration security policies | display set | match aa-" \
		2>/dev/null | grep -a "aa-" \
		|| printf '  none -- nothing has been granted yet\n'
	@printf '\n\033[1m--- controller ---\033[0m\n'
	$(KUBECTL) -n otternet-access logs deploy/fw-controller --tail=6 2>/dev/null || true

guac: ## How to reach the branch desktop through Guacamole
	@printf '\n\033[1mBranch office desktop, in a browser\033[0m\n\n'
	@printf '  sign in:  branch / branch\n\n'
	@printf '  Guacamole is published on port 8080 of every address this host has,\n'
	@printf '  and it serves at / -- there is no /guacamole/ path to remember:\n\n'
	@for a in $$(hostname -I 2>/dev/null) $$(hostname -f 2>/dev/null); do \
		printf '    http://%s:8080/\n' "$$a"; \
	done
	@printf '\n'
	@printf '  The desktop itself is 10.70.0.20 on the branch LAN; Guacamole reaches\n'
	@printf '  it through guacd at 10.70.0.31, so the VNC session crosses the site\n'
	@printf '  network. Firefox opens on the access portal at http://10.112.240.33/\n\n'
	@printf '  If the page loads but the connection does not:\n'
	@printf '    docker logs clab-$(LAB)-branch-guacd\n'
	@printf '    docker exec clab-$(LAB)-branch-desktop ss -ltn\n\n'

xp-drift: ## Prove the XR is the source of truth: break Cilium by hand, watch it heal
	@printf '\n\033[1;36m==> Current localASN on the CiliumBGPClusterConfig Crossplane owns\033[0m\n'
	$(KUBECTL) get ciliumbgpclusterconfig otternet-fabric \
		-o jsonpath='{.spec.bgpInstances[0].localASN}{"\n"}'
	@printf '\n\033[1;36m==> Hand-editing it to a wrong AS (65999), the way someone would in an incident\033[0m\n'
	$(KUBECTL) patch ciliumbgpclusterconfig otternet-fabric --type=merge \
		-p '{"spec":{"bgpInstances":[{"name":"fabric","localASN":65999,"peers":[{"name":"k8s-leaf1","peerASN":65101,"peerAddress":"10.110.0.2","peerConfigRef":{"name":"otternet-leaf-peer"}},{"name":"k8s-leaf2","peerASN":65101,"peerAddress":"10.110.0.3","peerConfigRef":{"name":"otternet-leaf-peer"}}]}]}}'
	$(KUBECTL) get ciliumbgpclusterconfig otternet-fabric \
		-o jsonpath='{"  now: "}{.spec.bgpInstances[0].localASN}{"\n"}'
	@printf '\n\033[1;36m==> Waiting for Crossplane to notice and revert it\033[0m\n'
	@for i in $$(seq 1 60); do
		asn=$$($(KUBECTL) get ciliumbgpclusterconfig otternet-fabric -o jsonpath='{.spec.bgpInstances[0].localASN}')
		if [ "$$asn" = "65401" ]; then
			printf '  reverted to %s after %ss -- the XR, not the CRD, is the source of truth\n' "$$asn" "$$i"
			exit 0
		fi
		sleep 1
	done
	printf '\033[1;31m  still 65999 after 60s -- is provider-kubernetes healthy? make xp\033[0m\n'; exit 1

grafana: ## How to reach Grafana (otternet-metrics, delivered by Infrahub through Vidra)
	@vip=$$($(KUBECTL) -n otternet-metrics get svc -l app.kubernetes.io/name=grafana \
		-o jsonpath='{.items[0].status.loadBalancer.ingress[0].ip}')
	printf '\nGrafana VIP (advertised into EVPN): \033[1mhttp://%s/\033[0m\n' "$$vip"
	printf '  sign in with Dex (e.g. alice); the branch reaches it only once a grant exists.\n'
	printf '  break-glass admin: GRAFANA_ADMIN_PASSWORD in the repository .env\n\n'
	printf 'From this host (management path, no fabric involved):\n'
	printf '  make grafana-forward   # then http://localhost:13000\n\n'

grafana-forward: ## Port-forward Grafana to localhost:13000
	@echo "Grafana: http://localhost:13000  (admin password: GRAFANA_ADMIN_PASSWORD in the repository .env)"
	$(KUBECTL) -n otternet-metrics port-forward \
		svc/$$($(KUBECTL) -n otternet-metrics get svc -l app.kubernetes.io/name=grafana -o jsonpath='{.items[0].metadata.name}') 13000:80

prometheus-forward: ## Port-forward Prometheus to localhost:19090
	@echo "Prometheus: http://localhost:19090/targets"
	$(KUBECTL) -n otternet-metrics port-forward \
		svc/$$($(KUBECTL) -n otternet-metrics get svc -l app=kube-prometheus-stack-prometheus -o jsonpath='{.items[0].metadata.name}') 19090:9090

## ------------------------------------------------------------------- wan ----

wan-build: ## Render every ISP / customer / branch config offline (no lab needed)
	$(CURDIR)/$(VENV)/python $(CURDIR)/wan/render.py

wan-deploy: ## Push rendered WAN configs onto the SR Linux routers in place
	$(WAN_DEPLOY)

wan-bgp: ## BGP state from every WAN router
	@for n in isp-pe1 isp-pe2 internet-rtr cust-acme-ce cust-globex-ce branch-rtr; do
		if docker ps --format '{{.Names}}' | grep -qx "clab-$(LAB)-$$n"; then
			printf '\n\033[1m--- %s ---\033[0m\n' "$$n"
			docker exec "clab-$(LAB)-$$n" sr_cli -d "show network-instance * protocols bgp neighbor" 2>/dev/null | grep -E '^\| ' || true
		fi
	done

wan-tenants: ## What each tenant can and cannot see, from the ISP edge
	@$(CURDIR)/$(VENV)/python -c "import yaml;d=yaml.safe_load(open('wan/tenants.yml'));\
print('\n'.join('%s %s %s %s' % (t['vrf'], t['name'], t['dc']['subnet'], 'internet' if t['internet'] else 'no-internet') for t in d['tenants']))" \
	| while read vrf name cloud net; do
		printf '\n\033[1m--- %s (%s, cloud %s, %s) ---\033[0m\n' "$$name" "$$vrf" "$$cloud" "$$net"
		docker exec clab-$(LAB)-isp-pe1 sr_cli -d "show network-instance $$vrf ipv4 route" 2>/dev/null | grep -E '^[0-9]'
	done
	@printf '\n\033[1mWhat to look for\033[0m\n'
	@printf '  every tenant: its own sites, and 10.112.240.0/24 (shared DC services)\n'
	@printf '  acme only:    0.0.0.0/0 (it bought internet) and 10.220.10.0/24\n'
	@printf '  globex only:  10.220.20.0/24, and NO default route\n'
	@printf '  neither:      any prefix belonging to the other tenant\n\n'

# Kept as an alias: the concept is a tenant now, but the old name is in muscle
# memory and in the docs history.
wan-customers: wan-tenants ## Alias for wan-tenants

wan-console-%: ## sr_cli on a WAN router, e.g. make wan-console-isp-pe1
	docker exec -it clab-$(LAB)-$* sr_cli

## ---------------------------------------------------------------- checks ----

verify: ## Run end-to-end checks across fabric, security and k8s
	./scripts/verify.sh

graph: ## Render the topology diagram
	$(CLAB) graph -t $(TOPO)

inspect: ## Show lab node state
	$(CLAB) inspect -t $(TOPO)

fabric-bgp: ## Underlay and overlay BGP summary from every switch
	@for n in spine1 spine2 k8s-leaf1 k8s-leaf2 app-leaf1 app-leaf2 border-leaf1; do
		if docker ps --format '{{.Names}}' | grep -qx "clab-$(LAB)-$$n"; then
			printf '\n\033[1m--- %s ---\033[0m\n' "$$n"
			docker exec "clab-$(LAB)-$$n" Cli -c "show ip bgp summary" 2>/dev/null || true
			docker exec "clab-$(LAB)-$$n" Cli -c "show bgp evpn summary" 2>/dev/null || true
		fi
	done

fw-log: ## Tail firewall session logs
	@printf '\n\033[1m--- active sessions ---\033[0m\n'
	@docker exec clab-$(LAB)-fw1 sshpass -p "$${OTTERNET_VSRX_PASSWORD:-admin@123}" \
		ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		admin@127.0.0.1 "show security flow session summary" 2>/dev/null
	@printf '\n\033[1m--- permits and denies (RT_FLOW) ---\033[0m\n'
	@docker exec clab-$(LAB)-fw1 sshpass -p "$${OTTERNET_VSRX_PASSWORD:-admin@123}" \
		ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
		admin@127.0.0.1 "show log messages | match RT_FLOW | last 30" 2>/dev/null \
		|| printf '  no session log yet -- policies log on session-init\n'

ssh-%: ## SSH into a switch, e.g. make ssh-k8s-leaf1
	docker exec -it clab-$(LAB)-$* Cli

clean: destroy avd-clean ## Tear down and remove all generated artefacts
	rm -rf clab-$(LAB) .clab.$(TOPO).bak k8s/.kubeconfig/*
