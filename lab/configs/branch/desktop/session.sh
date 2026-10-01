#!/bin/bash
# The desktop session itself, as the branch user.
#
# Xtigervnc is the X server and nothing more -- it does not read ~/.vnc/xstartup
# and rejects -xstartup outright (that option belongs to the tigervncserver perl
# wrapper, which wants to daemonise and is the wrong shape for a container).
# So the server goes to the background here and the session runs in front of it,
# with the container's lifetime tied to the session.
set -eu

GEOMETRY="${VNC_GEOMETRY:-1440x900}"
log() { echo "[branch-desktop] $*"; }

log "starting Xvnc on :1 ($GEOMETRY)"
# -localhost=0 because guacd connects across the branch LAN, not from inside
# this container. That is not an exposure: the branch LAN sits behind
# branch-rtr and the firewall like any other branch subnet.
Xtigervnc :1 \
    -desktop "branch-desktop" \
    -geometry "$GEOMETRY" \
    -depth 24 \
    -rfbport 5901 \
    -rfbauth "$HOME/.vnc/passwd" \
    -SecurityTypes VncAuth \
    -localhost=0 \
    -AlwaysShared &
XVNC_PID=$!

# When the session ends, the container should end with it rather than sit there
# with an X server and no desktop on it.
trap 'kill "$XVNC_PID" 2>/dev/null || true' EXIT

waited=0
while [ ! -e /tmp/.X11-unix/X1 ]; do
    waited=$((waited + 1))
    [ "$waited" -gt 60 ] && { log "FATAL: Xvnc never created :1"; exit 1; }
    sleep 0.5
done
log "X display :1 is up, starting XFCE"

export DISPLAY=:1
xsetroot -solid "#1c2733" || true

# dbus-launch is required, not decorative: with no session bus xfce4-session
# starts, cannot reach xfconfd, and exits after a few seconds -- which presents
# as Guacamole connecting and then dropping.
exec dbus-launch --exit-with-session xfce4-session
