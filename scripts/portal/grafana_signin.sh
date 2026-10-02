#!/bin/sh
# Sign in to Grafana through Dex as alice and print her org role. Run on the desktop.
#
# The same flow as verify_bootstrap.sh's, but through Grafana's VIP rather than a
# port-forward: from the branch desktop, so a "Viewer" here proves the firewall,
# the border leaf's route, Grafana's pod policy and the Dex back channel at once.
# Prints `no-answer` when Grafana does not respond and `no-redirect` when it does
# but does not send the browser to Dex.
G=http://10.112.240.81
J=$(mktemp)
auth=$(curl -s -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 10 "$G/login/generic_oauth") \
    || { echo "no-answer"; exit 0; }
case "$auth" in http://10.90.0.11:32556/dex/auth*client_id=grafana*) ;; *) echo "no-redirect"; exit 0 ;; esac
curl -s -L -b "$J" -c "$J" -o /tmp/grafana-login.html --max-time 15 "$auth"
form=$(grep -oE 'action="[^"]*"' /tmp/grafana-login.html | head -1 | cut -d'"' -f2 | sed 's/&amp;/\&/g')
cb=$(curl -s -b "$J" -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 15 \
    -d "login=alice@otternet.lab" -d "password=password" "http://10.90.0.11:32556${form}")
curl -s -b "$J" -c "$J" -o /dev/null --max-time 20 "$cb"
curl -s -b "$J" --max-time 10 "$G/api/user/orgs" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["role"])' 2>/dev/null || echo "no-session"
