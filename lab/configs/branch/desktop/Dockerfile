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
RUN apt-get update && apt-get install -y --no-install-recommends \
        xfce4-session xfwm4 xfdesktop4 xfce4-panel xfce4-terminal \
        xfce4-settings thunar xfconf \
        tigervnc-standalone-server tigervnc-common tigervnc-tools \
        dbus-x11 x11-xserver-utils xdg-utils \
        fonts-dejavu-core hicolor-icon-theme adwaita-icon-theme \
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
COPY xfce-desktop.xml /home/${DESKTOP_USER}/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml
COPY service-portal.desktop /home/${DESKTOP_USER}/Desktop/service-portal.desktop
COPY start-desktop.sh /opt/start-desktop.sh
COPY session.sh /opt/session.sh

RUN chmod +x /opt/start-desktop.sh /opt/session.sh /home/${DESKTOP_USER}/Desktop/service-portal.desktop \
    && chown -R ${DESKTOP_USER}:${DESKTOP_USER} /home/${DESKTOP_USER}

ENV DESKTOP_USER=${DESKTOP_USER}
# Matches the password in configs/branch/guacamole/user-mapping.xml. A lab
# credential, written down in both places on purpose so the pair is obvious.
ENV VNC_PASSWORD=branchvnc
ENV VNC_GEOMETRY=1440x900

EXPOSE 5901
CMD ["/opt/start-desktop.sh"]
