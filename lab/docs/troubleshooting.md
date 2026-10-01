# Troubleshooting runbook

Ordered roughly by how often each thing bites.

## The lab will not deploy

**`ceOS image ceos:4.36.0.1F missing`** — expected on a fresh host. Download
`cEOS64-lab` from arista.com and `docker import` it. See the README.

**`Failed to verify bind path`** — a file referenced by a node's `binds` does
not exist. containerlab validates binds before anything starts. Check the paths
are relative to the topology file, not your shell's cwd.

**Deploy dies partway with OOM, or the host starts swapping** — the full profile
wants ~20 GB. Check what else is holding memory:

```bash
docker ps --format '{{.Names}}\t{{.Image}}' | grep -v '^clab-'
free -g
```

Then either stop the other workload or use `make deploy-lite`.

**ceOS nodes boot and immediately exit** — almost always cgroups. ceOS before
4.32.0F needs cgroups v1; `stat -fc %T /sys/fs/cgroup` returning `cgroup2fs`
means you need 4.32.0F or newer.

## The fabric is up but BGP is not

```bash
make fabric-bgp                     # every switch at once
make ssh-spine1
  show ip bgp summary
  show ip bgp neighbors <peer> | grep -A5 'Last state'
```

**Sessions stuck in Active/Connect** — check the underlying link first:
`show interfaces status`. containerlab wires `eth1..ethN`; if a leaf's uplink
interface numbering disagrees with `uplink_switch_interfaces` in
`OTTERNET_L3LEAFS.yml`, the cable is not where AVD thinks it is.

**Sessions flap or never authenticate** — BGP password mismatch. This is the
`cleartext_password` vs `password` trap: confirm the rendered ciphertext differs
per peer, which is correct behaviour, and that both ends came from the same
`make avd-build`.

```bash
grep -n 'password 7' avd/intended/configs/k8s-leaf1.cfg
```

**EVPN up but no VTEPs** — `show vxlan vtep`, then `show bgp evpn route-type
imet` to confirm type-3 routes are being exchanged.

## MLAG will not form

```bash
make ssh-k8s-leaf1
  show mlag
  show mlag detail
```

Both peer-link members (`Ethernet3`, `Ethernet4`) must be up. Note the topology
deliberately uses two members; a single-member peer-link works but hides
failure modes worth showing.

`inconsistent` state usually means the two switches got config from different
builds — rerun `make avd-deploy`.

## A k8s node has no eth1, or is missing entirely

The switches look fine, the other nodes are fine, and one or two k8s nodes have
no fabric interface at all. This is almost always a crashed k3s several restarts
ago, not a wiring problem — check the restart count first:

```bash
for n in k8s-node1 k8s-node2 k8s-node3; do
    printf '%-11s restarts=%s eth1=%s\n' "$n" \
      "$(docker inspect clab-otternet-$n --format '{{.RestartCount}}')" \
      "$(docker exec clab-otternet-$n ip -br addr show eth1 2>/dev/null | awk '{print $3}')"
done
```

Any non-zero restart count explains a missing `eth1`. containerlab pushes the
veth into the node's namespace from the outside once, at deploy time; a docker
restart builds a new network sandbox without it, and containerlab is not coming
back. These nodes run `--restart=always`, so anything that kills PID 1 costs the
node its fabric link permanently.

The real error is therefore several restarts back in the log, not at the end:

```bash
docker logs clab-otternet-k8s-node2 2>&1 | grep -iE 'FATA|Incorrect Usage' | head
```

`flag provided but not defined: -disable-kube-proxy` means a server-only flag
reached `k3s agent` — kube-proxy is disabled from the server only.

Recovery is a redeploy (`make deploy`), because the link has to be recreated.
If you would rather not rebuild the fabric, the veth pair can be rebuilt by
hand — the entrypoint waits 600s for the link, which is the window to do it in:

```bash
lpid=$(docker inspect -f '{{.State.Pid}}' clab-otternet-k8s-leaf2)
npid=$(docker inspect -f '{{.State.Pid}}' clab-otternet-k8s-node2)
sudo ip link add clabtmpL type veth peer name clabtmpN
sudo ip link set clabtmpL netns "$lpid"
sudo ip link set clabtmpN netns "$npid"
sudo nsenter -t "$lpid" -n ip link set clabtmpL name eth10
sudo nsenter -t "$lpid" -n ip link set eth10 mtu 9214 up
sudo nsenter -t "$npid" -n ip link set clabtmpN name eth1
sudo nsenter -t "$npid" -n ip link set eth1 mtu 9214 up
```

The entrypoint then picks the link up and carries on. Note this races a restart
loop: if k3s is still crashing, the next restart destroys the veth again, so fix
the crash first.

## kubelet dies on "cannot enter cgroupv2 ... invalid state"

```
Failed to start ContainerManager
cannot enter cgroupv2 "/sys/fs/cgroup/kubepods" with domain controllers -- it is in an invalid state
```

k3s did not run as PID 1, so its cgroup v2 nesting workaround never happened.
cgroup v2 forbids a cgroup holding both processes and domain controllers, and
k3s works around that by moving the existing processes into a child cgroup and
enabling the controllers in the subtree — but only when it finds itself as
PID 1.

```bash
docker exec clab-otternet-k8s-node1 cat /proc/1/cgroup
# 0::/init   -> the workaround ran
# 0::/       -> it did not; k3s is not pid 1
```

Check that `k8s/bootstrap/k3s-entrypoint.sh` still ends in
`exec /bin/k3s "$ROLE" "$@"`. Anything that turns that into a supervised child
process — a `while` loop, a `&` plus `wait`, a shell wrapper — reproduces this,
and it looks like a host cgroup problem rather than something the entrypoint
did.

## Kubernetes nodes stay NotReady

This is **expected** until Cilium is installed — k3s has flannel disabled, so
there is no CNI until `make k8s` runs.

If they are still NotReady afterwards:

```bash
docker logs clab-otternet-k8s-node1 | tail -40
kubectl --kubeconfig k8s/.kubeconfig/kubeconfig.yaml get nodes -o wide
```

**Node IP is `172.20.41.x` instead of `10.110.0.x`** — k3s started before its
fabric link was wired. The entrypoint should prevent this; check its output:

```bash
docker logs clab-otternet-k8s-node1 | grep k3s-entrypoint
```

**Agents cannot reach the server** — the agents dial `https://10.110.0.11:6443`,
which requires the k8s leaves and the stretched VLAN 110 to be working. Test the
underlay first:

```bash
docker exec clab-otternet-k8s-node2 ping -c2 10.110.0.11
```

If that fails, the problem is the fabric, not Kubernetes.

## Cilium BGP is not peering

```bash
make k8s-bgp
kubectl -n kube-system exec ds/cilium -- cilium-dbg bgp peers
```

**No BGP instance at all** — nodes are missing the selector label:

```bash
kubectl label nodes --all otternet.lab/bgp=true --overwrite
```

**Peering to the wrong address** — the cluster config must use the leaves'
unique SVI addresses (`10.110.0.2`, `10.110.0.3`), never the VARP gateway
`10.110.0.1`.

**Session down with auth failure** — the secret must match the AVD
`cleartext_password`:

```bash
kubectl -n kube-system get secret otternet-bgp-auth -o jsonpath='{.data.password}' | base64 -d
# expect: Otternet-Cilium
```

## Routes are advertised but not installed

This is usually the security policy working as intended, not a fault.

```bash
make ssh-k8s-leaf1
  show ip bgp neighbors 10.110.0.11 received-routes   # what Cilium offered
  show ip route vrf K8S_PROD bgp                      # what the fabric accepted
  show route-map RM-CILIUM-IN
```

`RM-CILIUM-IN` permits only `10.111.0.0/16 le 26` and `10.112.0.0/16`. A pod
CIDR mask longer than /26, or a LoadBalancer VIP outside the service CIDR, is
denied by design. Widen `PL-CILIUM-PERMITTED` in
`avd/group_vars/OTTERNET_FABRIC/20-security.yml` if that is genuinely what you
want, and rebuild.

## Traffic is blocked between tenants

Work outward from the source. There are three enforcement points and they fail
in distinguishable ways.

**1. Leaf ACL** — drops show as ACL counters:

```bash
make ssh-k8s-leaf1
  show ip access-lists ACL-K8S-NODES-IN
```

Non-zero on the final `deny` entry means anti-spoofing rejected the source. Pod
traffic must originate from `10.111.0.0/16` for this to pass.

**2. Firewall zone policy** — sessions are logged:

```bash
make fw-log
docker exec -it clab-otternet-fw1 cli
  show security policies
  show security flow session
```

`app-prod → k8s-prod` permits only HTTP/HTTPS to the service CIDR plus ICMP.
Anything else hits `deny-and-log`.

**3. Cilium policy** — Hubble shows the verdict, including the L7 reason:

```bash
make hubble    # http://localhost:12000
kubectl -n kube-system exec ds/cilium -- cilium-dbg monitor --type drop
```

The demo namespace is default-deny. `allow-frontend-ingress` permits `GET /` and
`GET /healthz` from `10.210.0.0/24` only — a `POST`, or any other path, is
dropped at L7 even though L3/L4 allowed it.

## Config pushed but the device disagrees

```bash
cd avd && ../.venv/bin/ansible-playbook playbooks/deploy.yml --check --diff
```

To see what AVD *intends* versus what is running:

```bash
docker exec clab-otternet-k8s-leaf1 Cli -c 'show running-config' > /tmp/running.cfg
diff <(grep -v '^!' /tmp/running.cfg) <(grep -v '^!' avd/intended/configs/k8s-leaf1.cfg)
```

Expect differences in certificates, timestamps and dynamic state; anything
structural means the deploy did not land.

## Crossplane and anything else that runs inside the cluster

Crossplane is the first thing in this lab that needs the cluster to work from
the **inside**: it resolves package names over cluster DNS, pulls OCI artefacts
from the internet, and talks to the API server through its ClusterIP. All three
were broken here for a long time without anyone noticing, because a purely
north-south demo never touches any of them.

`k8s/bootstrap/install-crossplane.sh` checks all three before it installs
anything. To check them by hand:

```bash
kubectl run otternet-net-check --image=busybox:1.36 --restart=Never --rm -i \
    --command -- sh -c '
      nc -z -w 5 10.112.0.1 443   && echo "API ClusterIP OK"
      nslookup xpkg.crossplane.io. >/dev/null && echo "external DNS OK"
      nc -z -w 8 1.1.1.1 443      && echo "pod egress OK"'
```

Note the trailing dot on the domain. Without it, busybox `nslookup` walks the
pod's five-entry search list first and a working resolver can still look like a
failure -- which wasted a round of diagnosis here.

### "dial tcp 10.112.0.1:443: i/o timeout" from a pod

No ClusterIP works, anywhere in the cluster. In-cluster DNS is dead too, for the
same reason -- `10.112.0.10` is a ClusterIP.

Cilium's socket-LB translates ClusterIPs at `connect()` time using BPF programs
attached to a cgroup. Check that the cgroup it attached them to is the one the
pods actually live in:

```bash
kubectl -n kube-system exec ds/cilium -c cilium-agent -- \
    sh -c 'cilium-dbg config -a | grep -i cgrouproot; ls $(cilium-dbg config -a \
        | awk "/CGroupRoot/ {print \$3}") | grep -c kubepods'
# expect: /sys/fs/cgroup   and a count of 1
```

If the count is 0, the programs are attached to a cgroup containing only
`cilium-agent` itself and no other pod's `connect()` passes through them. With
`cgroup.autoMount.enabled` left on, the agent mounts a fresh cgroup2 whose root
is -- in this nested containerlab/k3s/pod arrangement -- its own leaf cgroup.
`k8s/helm/cilium-values.yaml` sets:

```yaml
cgroup:
  autoMount:
    enabled: false
  hostRoot: /sys/fs/cgroup
```

which is what k3d and kind set up for you and a plain containerlab node does not.
Same class of bug as the `/sys/fs/bpf` shared-mount problem.

**Changing that value is not enough on its own.** The socket-LB programs are
attached as *pinned bpf_links*, and `bpf_link_update` swaps the program but
never the cgroup a link is bound to -- so the stale links keep the old,
wrong attachment and the agent logs `Updated link for program` as if all is
well. Clear them and restart:

```bash
for n in k8s-node1 k8s-node2 k8s-node3; do
    docker exec clab-otternet-$n rm -rf /sys/fs/bpf/cilium/socketlb/links/cgroup/
done
kubectl -n kube-system rollout restart ds/cilium
kubectl -n kube-system exec ds/cilium -- cilium-dbg status | grep -i routing
```

### A Cilium value was changed and nothing happened

`helm upgrade` writes the `cilium-config` ConfigMap, but a value that only lands
in the ConfigMap does not change the DaemonSet's pod spec, so the pods are not
rolled and the running agents keep the old setting indefinitely. Cilium notices
and says so, quietly:

```bash
kubectl -n kube-system logs ds/cilium -c cilium-agent | grep -i 'config-drift'
# Mismatch found ... key=enable-host-legacy-routing actual=false expectedValue=true
```

`kubectl -n kube-system rollout restart ds/cilium` after any values change, and
confirm the agent actually took it with `cilium-dbg config -a`, not by reading
the ConfigMap back.

### Packages stuck at INSTALLED=False

```bash
kubectl get providers,functions
kubectl describe provider provider-helm | tail -20
```

`cannot resolve ... to digest: ... lookup xpkg.crossplane.io ... server
misbehaving` is the DNS problem above, not a registry outage. CoreDNS forwards
to whatever resolv.conf it inherited; k3s substitutes `8.8.8.8` whenever the
host's resolv.conf has a loopback nameserver, and Docker gives this container
`nameserver 127.0.0.11` -- an address that exists only in the *node's* netns,
not in CoreDNS's pod. `k3s-entrypoint.sh` rewrites resolv.conf before k3s starts
so k3s derives a usable one. On an already-running lab:

```bash
docker exec clab-otternet-k8s-node1 cat /var/lib/rancher/k3s/agent/etc/resolv.conf
kubectl -n kube-system rollout restart deployment/coredns
```

### A claim says SYNCED=True but a resource it should have made is missing

Almost always schema pruning, and it is silent. If an XRD and a claim that uses
a newly-added field are applied in the same `kubectl apply`, the API server may
still be serving the *old* generated CRD schema when the claim lands, and the
unknown field is dropped without warning. The claim is valid, Crossplane
reconciles it successfully, and the field is simply not there:

```bash
kubectl get fabricapp otternet-observability -o jsonpath='{.spec.policy}' | python3 -m json.tool
# the field you set reads back as its default
```

Re-apply the claim on its own. `make xp-apply` applies definitions before
claims for this reason.

### A Helm release is stuck in "failed"

```bash
kubectl get releases.helm.crossplane.io -o wide
```

If the description mentions a pre-install hook and a `Job ... status: NotFound`,
something deleted the chart's hook Job out from under Helm -- deleting a failed
cert-generation job by hand to "make it retry" does exactly this, and the
release cannot recover because the hook it is waiting on no longer exists. Let
`provider-helm` do it instead:

```bash
kubectl delete release <name>     # Crossplane recreates it from the composition
```

### Something Crossplane manages keeps reverting

Working as designed: the `Object` reconciles on a 20s poll and reapplies its
manifest. Edit the XR in `crossplane/`, or delete the `Object` if you genuinely
want to experiment on the CRD by hand.

```bash
make xp                # what is composed, and from what
make xp-drift          # watch it happen on purpose
```

## Grafana never becomes ready, and the VIP demo fails with it

Check for OOM before believing the logs:

```bash
kubectl -n otternet-observability get pods -l app.kubernetes.io/name=grafana
# 2/3  OOMKilled  3 (35s ago)
```

Grafana registers every bundled datasource plugin before it opens port 3000,
and that startup peak is far above its steady-state footprint. Under a tight
memory limit it is killed part-way through and starts over, so the log shows
plugin registration slowing to about one plugin a minute (GC thrash) and then a
restart — which reads as a slow host, not a limit.

The knock-on points away from the cause: while Grafana churns there is no ready
backend on any node, so `externalTrafficPolicy: Local` withdraws the VIP from
BGP and `make verify` reports the *fabric* path failing.

```bash
kubectl get ciliumloadbalancerippool               # the pool still exists
docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c 'show ip route vrf K8S_PROD bgp' | grep 240
kubectl -n otternet-observability get endpoints | grep grafana   # empty = withdrawn
```

`crossplane/apps/20-observability.yaml` sets the limit to 768Mi and widens
Grafana's probes (`failureThreshold: 30`) so a slow start is a slow start rather
than a kill. If you tighten either, expect this back.

## Internet-bound traffic goes nowhere, but the policy looks right

The tenant has a default route, the prefix lists are correct, BGP is up, and a
`curl` to the internet still times out. Check where the packet actually goes
before touching any policy:

```bash
docker exec clab-otternet-isp-pe2 vtysh -c "show ip route 0.0.0.0/0"
# via 172.20.41.1, eth0   <-- the MANAGEMENT default, not the BGP one
```

containerlab gives every node a default route via `eth0` to the management
bridge, and a kernel default beats a BGP-learned one. Internet traffic then
leaves through the management interface, which looks exactly like a routing
policy failure and is not one — the policy is fine, the route is simply never
used.

The rendered `init.sh` for every WAN router removes it at boot for this reason.
If a router still has one, it did not run its init:

```bash
docker exec clab-otternet-isp-pe1 ip route show default
docker logs clab-otternet-isp-pe1 | tail
make wan-build && make wan-deploy     # re-render, then reload
```

Hosts keep their management default deliberately, except hosts behind a tenant
that bought internet access — those get a real default via their CE instead,
or the demo would prove nothing.

## A policy change did not take effect

`make wan-deploy` runs FRR's `frr-reload.py`, which applies configuration but
does not re-evaluate routes already in the table against a changed inbound
route-map. The config is right, `show running-config` proves it, and the route
is still missing or still present:

```bash
docker exec clab-otternet-isp-pe2 vtysh -c "show running-config" | grep PL-INTERNET-IN
# the new prefix list is there...
docker exec clab-otternet-isp-pe2 vtysh -c "show bgp ipv4 unicast" | grep 198.51
# ...but the prefix is not
```

Force a route refresh:

```bash
docker exec clab-otternet-isp-pe2 vtysh -c "clear bgp ipv4 unicast * soft"
```

Check the far end too. An inbound policy cannot accept what the neighbour never
sent: if a prefix is missing after a soft clear, look at the *sender's*
outbound route-map before widening the receiver's inbound one.

## A tenant cannot reach its own cloud, or reaches another tenant's

Three gates, and it is worth knowing which one you are looking at.

```bash
# 1. the fabric -- separate VRFs, and the SVI must be IN the tenant's VRF
docker exec clab-otternet-app-leaf1 Cli -p 15 -c "show ip route vrf TENANT_ACME 10.220.10.0/24"
# "directly connected, Vlan310" -- if this is empty, the SVI was generated
# into the wrong VRF or not at all (see the APP_LEAFS tag filter below)

# 2. the PE -- does this tenant's VRF even learn the prefix?
docker exec clab-otternet-isp-pe1 vtysh -c "show ip route vrf CUST_ACME" | grep 10.220
# acme should see 10.220.10.0/24 and NOT 10.220.20.0/24

# 3. the firewall
make fw-console
  show configuration security policies from-zone wan to-zone acme-cloud | display set
  show security flow session destination-prefix 10.220.10.0/24
```

### The SVI was silently not generated

AVD instantiates a tenant's SVIs on a leaf only if the leaf's `filter.tags`
include the SVI's tag. The cloud SVIs are tagged `cloud`, so `APP_LEAFS` in
`avd/group_vars/OTTERNET_L3LEAFS.yml` must list it:

```yaml
filter:
  tags: [app, cloud]
```

Without it the tenant VRFs exist only on the border leaf, `make avd-build`
succeeds, and the symptom is a cloud host with no gateway.

## The WAN: ISP, customers, branch

### A WAN router has no config at all

The topology bind-mounts `wan/rendered/<node>/frr.conf` straight into the
container. If nothing has been rendered, containerlab creates a *directory*
where the file should be and FRR starts with no config — which looks like a
broken image rather than a missing build step.

```bash
ls wan/rendered/                       # empty or missing?
make wan-build
make wan-deploy
```

`make preflight` fails on this rather than warning, for the same reason.

### A customer's BGP session will not come up

Work outwards from the wire:

```bash
docker exec clab-otternet-cust-acme-ce ip -br addr show          # is eth1 addressed?
docker exec clab-otternet-cust-acme-ce ping -c2 10.51.10.1       # can it see the PE?
docker exec clab-otternet-isp-pe1 vtysh -c 'show bgp vrf CUST_ACME ipv4 unicast summary'
```

Two failure modes specific to this design:

**The PE interface is not in the customer's VRF.** The VRF device has to exist
*before* FRR reads its config — zebra configures interfaces but does not create
VRFs — which is why the rendered `init.sh` is the container's entrypoint rather
than a post-boot exec. If it did not run, the `vrf` stanzas were silently
dropped and the session has nowhere to live:

```bash
docker exec clab-otternet-isp-pe1 ip -br link show type vrf      # CUST_* present?
docker exec clab-otternet-isp-pe1 ip -br link show master CUST_ACME   # eth2 enslaved?
docker logs clab-otternet-isp-pe1 | grep wan-init
```

**bgpd is not running.** The FRR image ships `bgpd=no`, and the failure is
quiet: `vtysh` accepts `router bgp` and keeps no sessions.

```bash
docker exec clab-otternet-isp-pe1 vtysh -c 'show daemons'
```

### A customer can see another customer

The import route-map is missing or not matching. Both customers' prefixes are
legitimately in the provider's default table, so this route-map is the only
thing separating them:

```bash
docker exec clab-otternet-isp-pe1 vtysh -c 'show running-config' \
  | grep -A4 'vrf CUST_ACME'
# expect BOTH:
#   import vrf default
#   import vrf route-map RM-DC-SERVICES-ONLY
```

If only `import vrf default` is present, every customer has the whole provider
table. Re-render and re-deploy; `make verify` asserts the negative directly.

### A customer cannot reach a DC service

Three independent things must all agree, and they fail in different places.
Check them in this order — it is cheapest first, and each answer narrows the
next:

```bash
# 1. Does the customer even have a route?
docker exec clab-otternet-cust-acme-ce vtysh -c 'show ip route 10.112.240.0/24'
#    no route -> RM-DC-SERVICES-ONLY on isp-pe1, or RM-DC-TO-EXTERNAL on the
#    border leaf, or the static route in VRF WAN that originates it

# 2. Did the DC accept the customer's prefix back?
docker exec clab-otternet-border-leaf1 Cli -p 15 -c 'show ip route vrf WAN bgp'
#    missing -> RM-WAN-IN, or the customer announced something PL-WAN-PERMITTED
#    refuses

# 3. Did the firewall permit the session?
docker exec clab-otternet-fw1 nft -a list chain inet zones forward | grep wan
#    counters at zero -> traffic never arrived; look at 1 and 2 again
#    counters rising on a DROP rule -> policy, and the rule name says which
```

If all three look right and it still times out, it is the fourth gate: the
application's own CiliumNetworkPolicy.

```bash
kubectl -n otternet-observability get cnp allow-ingress -o jsonpath='{.spec.ingress[0].fromCIDR}'
```

An external network has to be named in the `FabricApp` claim's
`policy.allowFrom` — the route existing and the firewall permitting the session
is not enough, deliberately. This is the most likely cause of "the network
works but the app times out", and it caught this lab during development: the
fabric and the firewall were already passing traffic while Cilium was still
dropping it.

### Do not ping a LoadBalancer VIP

```
From 10.110.0.12 icmp_seq=1 Time to live exceeded
```

ICMP to a VIP does not work in this datapath and never did. Cilium programs the
service's TCP port only, so an echo request lands on a node with no route for
it, is forwarded back out on its default route, and loops until the TTL
expires. It says nothing about policy. Test a VIP with `curl`, and test
reachability with a ping to a node address.

## The branch desktop and Guacamole

### Port 8080 returns 404

You are hitting Tomcat's default context. The Guacamole war deploys at
`/guacamole/` unless told otherwise, so the obvious URL 404s while
`http://host:8080/guacamole/` works.

The `branch-guac` node sets `WEBAPP_CONTEXT: ROOT` for exactly this reason,
which makes it serve at `/`. If you are seeing a 404 at the bare path, that
variable is not reaching the container:

```bash
docker exec clab-otternet-branch-guac env | grep WEBAPP_CONTEXT   # want ROOT
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8080/
```

`make verify` asserts the root path specifically, so this shows up as a failed
check rather than as a puzzle.

Note also which address you are using. The port is published on every address
the host has, so any of them work — `make guac` lists them all, including the
Tailscale name, which is usually not the first address `hostname -I` prints.

### Guacamole loads but rejects branch / branch

Almost always the user mapping failed to parse, and Guacamole reports that as a
credential failure to the browser while saying what really happened only in the
log:

```bash
docker logs clab-otternet-branch-guac 2>&1 | grep -i user-mapping
# "User mapping file ... is not valid: The string "--" is not permitted within comments."
```

A double hyphen anywhere inside an XML comment is illegal, and the whole mapping
is discarded when one appears. `configs/branch/guacamole/user-mapping.xml`
carries a note about it because the rest of this repo uses double hyphens in
prose comments freely. Fix the file and restart the node:

```bash
docker restart clab-otternet-branch-guac
```

### The connection appears in the list but will not open

That is guacd, not the web front end. guacd sits on the branch LAN and has to
reach the desktop's VNC port:

```bash
docker logs clab-otternet-branch-guacd            # guacd's own view
docker exec clab-otternet-branch-guacd sh -c 'echo > /dev/tcp/10.70.0.20/5901' \
    && echo reachable
docker exec clab-otternet-branch-desktop ss -ltn  # is Xvnc listening at all?
```

If the port is closed, look at the desktop's session rather than the network:

```bash
docker logs clab-otternet-branch-desktop
docker exec clab-otternet-branch-desktop ps -eo comm | grep xfce4-session
```

An X server with no session on it usually means dbus: `xfce4-session` starts,
cannot reach `xfconfd`, and exits after a few seconds, which looks exactly like
VNC dropping the connection.

### The desktop has no LAN address

`branch-desktop` gets its address from the rendered init script the topology
bind-mounts, the same as every other WAN host:

```bash
docker exec clab-otternet-branch-desktop ip -4 -o addr show eth1   # want 10.70.0.20
make wan-build && make wan-deploy
```

If `branch-guacd` is the one missing an address, check `user: "0"` is still on
that node in `otternet.clab.yml`. The stock guacd image runs as uid 1000,
containerlab's post-boot exec inherits that user, and `ip addr replace` then
fails with a permission error that scrolls past during deploy.

## A LoadBalancer VIP is never advertised

The shape of this one: the app is Running, the Service has its VIP, Cilium's BGP
looks fine from one agent, the firewall permits the session and even builds it --
and nothing ever comes back.

```bash
# the firewall's own view: packets in, none out
make fw-console
  show security flow session destination-prefix 10.112.240.0/24   # Junos
  # In:  10.210.0.11 --> 10.112.240.33;tcp  Pkts: 5
  # Out: 10.112.240.33 --> 10.210.0.11;tcp  Pkts: 0     <-- nothing returning
```

Work back from there. The border leaf will have the /32 via the k8s leaf's VTEP
while the k8s leaf itself does not have it at all, which is a loop:

```bash
docker exec clab-otternet-border-leaf1 Cli -p 15 -c "show ip route vrf K8S_PROD 10.112.240.33/32"
docker exec clab-otternet-k8s-leaf1   Cli -p 15 -c "show ip route vrf K8S_PROD 10.112.240.33/32"
```

Then look at which node should be announcing it. Exposed Services use
`externalTrafficPolicy: Local`, so **only the node running the pod advertises
the VIP**. If that node's BGP session is down, that one VIP disappears while
every other app keeps working:

```bash
docker exec clab-otternet-k8s-leaf1 Cli -p 15 -c "show bgp ipv4 unicast summary vrf K8S_PROD"
# a peer in Connect/Idle while the others are Estab is the answer
```

### ...because the node ran out of memory

The usual cause, and it does not look like memory. The node stays `Ready`, there
is no OOM kill in `dmesg`, and what actually happens is the Cilium agent losing
its Kubernetes watches ("watch ended with error"), its BGP sessions dropping to
idle, and `kubectl exec` against that node hanging.

```bash
docker stats --no-stream --format '{{.Name}}	{{.MemUsage}}	{{.MemPerc}}' \
    clab-otternet-k8s-node1 clab-otternet-k8s-node2 clab-otternet-k8s-node3
# anything at 99% is the problem
```

A k3s node container's cgroup limit is invisible to the kubelet, which reports
the *host's* memory as node capacity — so pods schedule happily and then fight
over a limit Kubernetes does not know exists. The control-plane node is the one
that runs out first, because it carries the API server plus whatever landed on
it. Raise `memory:` for that node in `otternet.clab.yml` and redeploy; the file
carries the current figures and why.

## The firewall

### "Cpu virtualization support is required for node fw1"

The firewall is a VM, so this is a hard stop rather than a warning. containerlab
checks `/proc/cpuinfo` for `vmx` or `svm` during topology validation and refuses
before deploying anything. Note the capitalisation if you are grepping for it.

```bash
make preflight          # says so before the lab is torn down
grep -cE 'vmx|svm' /proc/cpuinfo
ls -l /dev/kvm
```

A cloud instance almost never exposes this — on AWS, only `.metal`. There is no
container-firewall fallback in this lab, so a host without it cannot run the lab
at all. Building the image (`make fw-image`) needs none of this and works
anywhere.

### "Login incorrect" on a box that just committed cleanly

The classic one. vrnetlab's `init.conf` sets the admin password as
`plain-text-password-value`, and when that file is the boot configuration Junos
stores the leaf verbatim rather than hashing it, so the account has no usable
credential:

```bash
# get in over the console -- root has no password there
docker exec -it clab-otternet-fw1 telnet localhost 5000
  root
  cli
  show configuration system login | display set
# plain-text-password-value  -> broken
# encrypted-password         -> correct
```

`configs/fw/vsrx/junos.conf` sets an `encrypted-password` explicitly to avoid
this. If you have edited that file and lost the stanza, put it back rather than
setting a password by hand, or the next deploy locks you out again.

### The config did not load

Junos reports config errors during boot and then carries on with whatever it
could parse, so the box comes up looking healthy with half a policy set:

```bash
docker logs clab-otternet-fw1 2>&1 | grep -iE "juniper.conf|check-out|commit"
# want: "mgd: commit complete"
# bad:  "configuration check-out failed"
```

The most likely cause is a value out of range. `mtu 9228` is the one that bit
during development: vSRX allows 256..9192 and the fabric wants 9214, which is
why the config uses 9192 plus a TCP MSS clamp.

Remember the file is *appended* to vrnetlab's `init.conf`. Restating `system`,
`interfaces` or `routing-instances` stanzas that init.conf already defines is
how you get a conflict; the one deliberate exception is the password above.

### A node restart loses the data interfaces

Do not `docker restart clab-otternet-fw1` to reload config. A restart rebuilds the
container's network sandbox without the veths containerlab wired in from
outside, and the firewall comes back with `fxp0` and nothing else. Redeploy
instead:

```bash
make deploy
```

### Which firewall am I running?

```bash
docker inspect clab-otternet-fw1 --format '{{ index .Config.Labels "clab-node-kind" }}'
# juniper_vsrx
make fw-console      # dispatches on that automatically
make fw-log
```

## Self-service access requests

### A request was approved and nothing happened

Walk it down the chain; each object says whether the next one exists.

```bash
kubectl get appaccess                  # is spec.approved true, what is the phase?
kubectl describe appaccess access-<app>
kubectl get firewallaccess             # did the composition emit the grant?
kubectl -n otternet-access logs deploy/fw-controller --tail=40
```

The most common answer is the last one: the controller cannot log in to the
firewall, and nothing else in the cluster goes red when that happens.

### The policy is on the firewall and traffic is still denied

Check the rule is actually where you think it is, and in the right zone pair:

```bash
make access-status
make fw-console
  show configuration security policies from-zone branch to-zone k8s-prod | display set
```

Order is rarely the problem on Junos — the default policy is consulted only
after every policy in the pair has been tried, so an appended grant is reached
normally. What does bite is a grant written into the wrong zone pair, which is
`spec.sourceZone`/`destinationZone` on the `FirewallAccess`. If a rule looks
wrong, delete the `AppAccess` and let it be recreated rather than editing it by
hand — the controller will put its own version back within a reconcile.

Remember there are three gates, not one. The firewall is only the second:

```bash
# 1. does the branch have a route to the VIP at all?
docker exec clab-otternet-branch-rtr vtysh -c "show ip route 10.112.240.0/24"
# 2. the firewall (above)
# 3. Cilium, at the pod
kubectl -n <app namespace> get cnp
```

An app provisioned through the catalog gets its `allowFrom` written from the
request's source CIDR, so gate 3 is usually only a problem for grant-only
entries whose `FabricApp` predates the branch.

### A generated policy came back after I deleted it

Working as intended. The controller re-asserts desired state every twenty
seconds, the same way Crossplane does for the Cilium config. To remove a grant,
delete the object it came from:

```bash
kubectl delete appaccess access-<app>
```

### There are aa-* policies on the box with no request behind them

The controller prunes those itself on its next pass. If they persist, it is not
running or cannot log in:

```bash
kubectl -n otternet-access get pods
kubectl -n otternet-access logs deploy/fw-controller --tail=20
```

### ErrImageNeverPull on the portal or the controller

Their images are built on the lab host and imported into each k3s node; there is
no registry. A node that joined later, or a node whose image store was reset,
has not got them:

```bash
make access-images
kubectl -n otternet-access rollout restart deploy/access-portal deploy/fw-controller
```

## Tools that are not where you expect

Several containers in this lab lack the diagnostic tools you would reach for
first, and they fail in ways that look like evidence:

| Container | Missing | Consequence |
|---|---|---|
| `k8s-node*` (`rancher/k3s`) | `tcpdump` | `docker exec ... tcpdump -w file` fails silently and leaves an empty capture, which reads as "no traffic arrived" |
| demo pods (`traefik/whoami`) | shell, `wget`, `curl`, `timeout` | `kubectl exec` returns an OCI runtime error, not a network result |
| `k8s-node*` | `curl` with TLS | busybox `wget` reports "not an http or ftp url" for `https://`, which is not a connectivity failure |

Use `hubble observe` and `cilium-dbg monitor` for anything inside the cluster,
and `tcpdump` on the WAN routers for the fabric
edge. containerlab links are veth pairs between two container namespaces, so
there is no host-side interface to capture on for a node-to-leaf link.

For an in-cluster shell, run a throwaway pod:

```bash
kubectl run otternet-debug --image=nicolaka/netshoot:latest --restart=Never \
    --command -- sleep 900
kubectl exec otternet-debug -- curl -sS http://<target>/
kubectl delete pod otternet-debug --force --grace-period=0
```

Remember it lands in the `default` namespace, so the demo namespace's policies
will deny it -- that is correct behaviour, not a fault.

## Starting over

```bash
make clean        # destroy the lab and remove generated artefacts
make deploy
```

`make clean` leaves `.venv` and the collections alone. To rebuild those too,
`rm -rf .venv .ansible && make setup`.
