#!/bin/bash
# Bring up the branch desktop: one VNC-backed X session running XFCE.
#
# Runs as pid 1 as root, prepares the desktop user's VNC credentials, then
# hands the session itself to that user. Nothing here needs systemd, a display
# manager, or a session bus started by anything other than xfce4-session.
set -eu

USER_NAME="${DESKTOP_USER:-branchuser}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
PASSWORD="${VNC_PASSWORD:-branchvnc}"

log() { echo "[branch-desktop] $*"; }

# TigerVNC keeps its password in its own obfuscated format, so it has to be
# written by vncpasswd rather than echoed into a file. vncpasswd lives in
# tigervnc-tools on Ubuntu 24.04, not in tigervnc-common.
install -d -m 700 -o "$USER_NAME" -g "$USER_NAME" "$HOME_DIR/.vnc"
printf '%s\n%s\n\n' "$PASSWORD" "$PASSWORD" \
    | runuser -u "$USER_NAME" -- vncpasswd "$HOME_DIR/.vnc/passwd" >/dev/null
chmod 600 "$HOME_DIR/.vnc/passwd"
chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.vnc"

# A stale lock survives a container restart, because /tmp is baked into the
# image layer. Xvnc then refuses :1 with "A VNC server is already running".
rm -f /tmp/.X1-lock /tmp/.X11-unix/X1

log "handing the session to $USER_NAME"
exec runuser -u "$USER_NAME" -- /opt/session.sh
