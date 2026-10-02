# The branch office workstation.
#
# A container, not a QEMU VM, and the distinction matters less than it looks:
# what the demo needs is a real X session with a real browser at a branch LAN
# address, and this gives that for ~1.5 GB of RAM and a 30-second start instead
# of a disk image, a vrnetlab wrapper and a two-minute boot. Nothing in the
# access-request path can tell the difference -- Guacamole speaks VNC to it and
# the firewall sees packets from 10.70.0.20 either way.
#
# XFCE because it starts in a second and has no compositor to fight with, and
# TigerVNC rather than xrdp because Guacamole speaks VNC natively and xrdp
# wants a session manager this container deliberately does not have.
#
# noble-20260911 is Ubuntu 24.04.5, the dated build the running image was made
# from; the bare 24.04 tag moves with every point release.
FROM ubuntu:noble-20260911

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8

# One layer, and --no-install-recommends throughout: the recommends of xfce4
# alone drag in a display manager, a screensaver and a power manager, none of
# which can work without systemd and all of which log failures forever.
#
# tigervnc-tools is not optional despite the name: on Ubuntu 24.04 vncpasswd
# lives there, not in tigervnc-common, and without it the session dies at
# startup with 'runuser: failed to execute vncpasswd'.
#
# librsvg2-common is not optional either: it is gdk-pixbuf's SVG loader, and
# without it every SVG icon -- all of Humanity and Adwaita's scalable set --
# renders as a blank or a generic document, which is most of the menu.
RUN apt-get update && apt-get install -y --no-install-recommends \
        xfce4-session xfwm4 xfdesktop4 xfce4-panel xfce4-terminal \
        xfce4-settings thunar xfconf \
        tigervnc-standalone-server tigervnc-common tigervnc-tools \
        dbus-x11 x11-xserver-utils xdg-utils \
        fonts-dejavu-core hicolor-icon-theme adwaita-icon-theme librsvg2-common \
        iproute2 iputils-ping curl ca-certificates netcat-openbsd \
        dnsutils less nano \
    && rm -rf /var/lib/apt/lists/*

# Firefox from Mozilla's own apt repository, not from Ubuntu.
#
# Ubuntu 24.04's `firefox` package is a transitional stub that installs a snap,
# and snapd cannot run in this container -- the install "succeeds" and there is
# no browser. The Mozilla repo ships a real .deb, and the pin is what stops apt
# preferring the Ubuntu stub on a later update.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg \
         -o /etc/apt/keyrings/packages.mozilla.org.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
         > /etc/apt/sources.list.d/mozilla.list \
    && printf 'Package: *\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n' \
         > /etc/apt/preferences.d/mozilla \
    && apt-get update && apt-get install -y --no-install-recommends firefox \
    && rm -rf /var/lib/apt/lists/*

# The branch employee. Guacamole logs in as this user over VNC; nothing in the
# demo ever needs root on the desktop.
ARG DESKTOP_USER=branchuser
ARG DESKTOP_UID=1001
RUN useradd -m -u ${DESKTOP_UID} -s /bin/bash ${DESKTOP_USER}

COPY firefox-policies.json /etc/firefox/policies/policies.json
COPY start-here.html /opt/branch/start-here.html
COPY start-desktop.sh /opt/start-desktop.sh
COPY session.sh /opt/session.sh

# The XFCE channels this image sets. Each is partial: what it does not name
# keeps the packaged default, so the files say only what was decided.
ARG XFCONF=/home/${DESKTOP_USER}/.config/xfce4/xfconf/xfce-perchannel-xml
COPY xfce-desktop.xml ${XFCONF}/xfce4-desktop.xml
COPY xfce4-panel.xml ${XFCONF}/xfce4-panel.xml
COPY xfwm4.xml ${XFCONF}/xfwm4.xml
COPY xsettings.xml ${XFCONF}/xsettings.xml

# Two launchers, each in two places: on the desktop, and in the panel, which
# reads its launcher items from a directory per plugin id (xfce4-panel.xml).
COPY service-portal.desktop start-here.desktop /home/${DESKTOP_USER}/Desktop/
COPY service-portal.desktop /home/${DESKTOP_USER}/.config/xfce4/panel/launcher-3/
COPY start-here.desktop /home/${DESKTOP_USER}/.config/xfce4/panel/launcher-4/

# Menu entries hidden by a same-named file higher in XDG_DATA_DIRS. Log Out
# because the session is the container's main process, so it stops the node;
# Mail Reader because no mail client is installed and it opens an error dialog;
# Python because it is a REPL in a terminal and means nothing to a branch user.
# The terminal stays in the menu, deliberately: it is how a presenter shows a
# curl from the branch, and it is not on the desktop or the panel.
RUN install -d /home/${DESKTOP_USER}/.local/share/applications \
    && for entry in xfce4-session-logout xfce4-mail-reader python3.12; do \
         printf '[Desktop Entry]\nType=Application\nName=%s\nHidden=true\n' "$entry" \
           > /home/${DESKTOP_USER}/.local/share/applications/$entry.desktop; \
       done \
    && chmod +x /opt/start-desktop.sh /opt/session.sh /home/${DESKTOP_USER}/Desktop/*.desktop \
    && chown -R ${DESKTOP_USER}:${DESKTOP_USER} /home/${DESKTOP_USER}

ENV DESKTOP_USER=${DESKTOP_USER}
# Matches the password in configs/branch/guacamole/user-mapping.xml. A lab
# credential, written down in both places on purpose so the pair is obvious.
ENV VNC_PASSWORD=branchvnc
ENV VNC_GEOMETRY=1440x900

EXPOSE 5901
CMD ["/opt/start-desktop.sh"]
