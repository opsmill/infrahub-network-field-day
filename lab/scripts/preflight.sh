#!/usr/bin/env bash
# Check the host can actually run the profile you asked for, before containerlab
# spends ten minutes finding out it cannot.
set -uo pipefail

PROFILE="${1:-full}"
LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rc=0

ok()   { printf '  \033[1;32mok\033[0m    %s\n' "$*"; }
warn() { printf '  \033[1;33mwarn\033[0m  %s\n' "$*"; }
bad()  { printf '  \033[1;31mFAIL\033[0m  %s\n' "$*"; rc=1; }

printf '\n\033[1mOTTERNET preflight (profile: %s)\033[0m\n\n' "$PROFILE"

# ---- required tooling ------------------------------------------------------
printf 'Tooling\n'
for tool in containerlab docker; do
    if command -v "$tool" >/dev/null 2>&1; then ok "$tool present"; else bad "$tool missing"; fi
done
for tool in kubectl helm; do
    if command -v "$tool" >/dev/null 2>&1; then ok "$tool present"; else warn "$tool missing (needed for the k8s layer)"; fi
done
if [[ -x "$LAB_DIR/.venv/bin/ansible-playbook" ]]; then
    ok "AVD virtualenv present ($("$LAB_DIR/.venv/bin/python" -c 'import pyavd;print("pyavd "+pyavd.__version__)' 2>/dev/null))"
else
    bad "AVD virtualenv missing -- run: make setup"
fi

# ---- images ----------------------------------------------------------------
printf '\nImages\n'
CEOS_IMAGE="${OTTERNET_CEOS_IMAGE:-ceos:4.36.0.1F}"
if docker image inspect "$CEOS_IMAGE" >/dev/null 2>&1; then
    ok "ceOS image $CEOS_IMAGE"
else
    bad "ceOS image $CEOS_IMAGE missing -- download cEOS64-lab from arista.com, then:
             docker import cEOS-lab-4.36.0.1F.tar ceos:4.36.0.1F"
fi

# The firewall image is built here, not pulled, so a missing one is a hard fail:
# containerlab would try to pull vrnetlab/juniper_vsrx from a registry that does
# not have it and the lab would come up with no firewall at all.
FW_IMAGE="${OTTERNET_VSRX_IMAGE:-vrnetlab/juniper_vsrx:${VSRX_VERSION:-22.3R1.11}}"
if docker image inspect "$FW_IMAGE" >/dev/null 2>&1; then
    ok "firewall image $FW_IMAGE"
else
    bad "firewall image $FW_IMAGE missing -- run: make fw-image
     It is built from a Junos vSRX 3.0 qcow2 in /images. Juniper does not
     redistribute it; a free account registered for evaluation access can
     download one from https://support.juniper.net/support/downloads/?p=vsrxeval"
fi

SRL_IMAGE="${OTTERNET_SRL_IMAGE:-ghcr.io/nokia/srlinux:26.7.2}"
for img in rancher/k3s:v1.31.3-k3s1 ghcr.io/srl-labs/network-multitool:v0.10.0 "$SRL_IMAGE"; do
    if docker image inspect "$img" >/dev/null 2>&1; then ok "$img"; else warn "$img not pulled yet (deploy will fetch it)"; fi
done

# ---- the branch office -----------------------------------------------------
# The desktop image is built here, not pulled, so a missing one is a hard fail:
# containerlab would try docker.io/otternet/branch-desktop and the branch site
# would come up without the workstation the access demo is driven from.
DESKTOP_IMAGE="${OTTERNET_DESKTOP_IMAGE:-otternet/branch-desktop:local}"
if docker image inspect "$DESKTOP_IMAGE" >/dev/null 2>&1; then
    ok "branch desktop image $DESKTOP_IMAGE"
else
    bad "branch desktop image $DESKTOP_IMAGE missing -- run: make desktop-image"
fi
for img in "${OTTERNET_GUACD_IMAGE:-guacamole/guacd:1.5.5}" \
           "${OTTERNET_GUACAMOLE_IMAGE:-guacamole/guacamole:1.5.5}"; do
    if docker image inspect "$img" >/dev/null 2>&1; then ok "$img"; else warn "$img not pulled yet (deploy will fetch it)"; fi
done

# The access broker runs in Kubernetes, so these are only needed by `make
# crossplane` -- a warning rather than a failure, and `make access-images`
# builds them.
for img in otternet/access-portal:local otternet/fw-controller:local; do
    if docker image inspect "$img" >/dev/null 2>&1; then ok "$img"; else warn "$img not built yet (run: make access-images)"; fi
done

# ---- the WAN layer ---------------------------------------------------------
# The topology bind-mounts these paths directly, so a missing render is not a
# warning: containerlab creates a DIRECTORY where the file should be, the
# router starts with no config, and the failure looks like a broken image.
printf '\nWAN configs\n'
if [[ -d "$LAB_DIR/wan/rendered" ]]; then
    n=$(find "$LAB_DIR/wan/rendered" -name config.cli 2>/dev/null | wc -l)
    if (( n > 0 )); then
        ok "$n SR Linux configs rendered in wan/rendered/"
    else
        bad "wan/rendered/ exists but has no SR Linux configs -- run: make wan-build"
    fi
else
    bad "no WAN configs rendered -- run: make wan-build"
fi

# ---- virtualization, for the VM-based firewall profiles --------------------
# Worth its own check because the failure is otherwise reported by containerlab
# as a bare "CPU virtualization support is required", after the images are
# pulled and some nodes are already up.
# Unconditional now: the firewall is a VM in every deployment, so a host
# without vmx/svm cannot run this lab at all.
if true; then
    printf '\nVirtualization (the firewall is a VM)\n'

    # This is exactly the test containerlab makes: it greps /proc/cpuinfo for
    # vmx or svm and refuses to deploy a VM-based kind if neither is present.
    if grep -qE '(^flags.*\bvmx\b|^flags.*\bsvm\b)' /proc/cpuinfo; then
        ok "CPU virtualization exposed (vmx/svm present)"
    else
        bad "no CPU virtualization: /proc/cpuinfo has neither vmx nor svm.
             containerlab checks for exactly this and will refuse the
             juniper_vsrx node with:
               Cpu virtualization support is required for node \"fw1\" (juniper_vsrx).
             On a cloud VM this normally means nested virtualization is not
             offered by the instance type -- on AWS only .metal instances
             expose it. There is no container-firewall fallback in this lab any
             more, so this host cannot run it.
             The image build (make fw-image) does not need any of this and
             works anywhere."
    fi

    if [[ -e /dev/kvm ]]; then
        ok "/dev/kvm present"
    else
        bad "/dev/kvm missing -- QEMU would fall back to TCG software emulation.
             vrnetlab does handle that (it only adds -enable-kvm when /dev/kvm
             exists) but it also asks QEMU for '-cpu host', which TCG cannot
             provide, so the VM would not start unqualified."
    fi

    mem_gb=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
    vm_gb=4    # what the vSRX VM itself asks for
    if (( mem_gb >= vm_gb + 2 )); then
        ok "${mem_gb} GB available (the vSRX VM wants ${vm_gb} GB plus QEMU overhead)"
    else
        warn "only ${mem_gb} GB available; the vSRX VM alone wants ~$((vm_gb + 1)) GB"
    fi
fi

# ---- kernel / host ---------------------------------------------------------
printf '\nHost\n'
cgroup=$(stat -fc %T /sys/fs/cgroup 2>/dev/null)
if [[ "$cgroup" == "cgroup2fs" ]]; then
    ok "cgroups v2 (requires ceOS 4.32.0F or newer -- older builds need cgroups v1)"
else
    warn "cgroups v1 detected"
fi
for mod in vxlan br_netfilter; do
    if lsmod | grep -q "^$mod"; then ok "kernel module $mod loaded"; else warn "kernel module $mod not loaded"; fi
done

# ---- memory ----------------------------------------------------------------
printf '\nMemory\n'
avail_mb=$(( $(awk '/MemAvailable/ {print $2}' /proc/meminfo) / 1024 ))

# Count what THIS lab is already holding as available.
#
# `make deploy` runs containerlab with --reconfigure, which tears the existing
# lab down before building the new one, so its memory is about to come back.
# Without this the check fails every time the lab is already up -- which is
# most of the time you actually run it -- and the advice it prints ("try
# deploy-lite") is wrong, because the full profile would have fit fine.
running_mb=0
for c in $(docker ps --format '{{.Names}}' | grep '^clab-otternet-' || true); do
    lim=$(docker inspect "$c" --format '{{.HostConfig.Memory}}' 2>/dev/null || echo 0)
    running_mb=$(( running_mb + lim / 1048576 ))
done
if (( running_mb > 0 )); then
    printf '  this lab currently holds %s MB, which a redeploy releases first\n' "$running_mb"
    avail_mb=$(( avail_mb + running_mb ))
fi

# The branch office costs ~3.3 GB more than it used to: a 2 GB XFCE desktop, a
# 1 GB Guacamole front end and 256 MB of guacd.
case "$PROFILE" in
    lite) need_mb=30000 ;;
    *)    need_mb=36500 ;;
esac
printf '  effective available: %s MB, profile needs roughly %s MB\n' "$avail_mb" "$need_mb"
if (( avail_mb >= need_mb )); then
    ok "enough memory for the $PROFILE profile"
else
    bad "not enough memory for the $PROFILE profile"
    other=$(docker ps --format '{{.Names}}' | grep -v '^clab-' | head -5 | tr '\n' ' ')
    [[ -n "$other" ]] && printf '        non-lab containers holding memory: %s\n' "$other"
    [[ "$PROFILE" != "lite" ]] && printf '        try: make deploy-lite\n'
fi

cpus=$(nproc)
if (( cpus >= 8 )); then ok "$cpus vCPUs"; else warn "$cpus vCPUs -- the fabric will boot slowly"; fi

printf '\n'
if (( rc == 0 )); then
    printf '\033[1;32mPreflight passed.\033[0m\n\n'
else
    printf '\033[1;31mPreflight failed -- fix the items above first.\033[0m\n\n'
fi
exit $rc
