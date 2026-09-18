#!/bin/sh
# Sign in to the portal as alice and print a Backstage token. Run on the desktop.
J=$(mktemp)
start=$(curl -s -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 10 \
    "https://10.90.0.11:32001/api/auth/oidc/start?env=development")
curl -s -L -b "$J" -c "$J" -o /tmp/l.html --max-time 15 "$start"
form=$(grep -oE 'action="[^"]*"' /tmp/l.html | head -1 | cut -d'"' -f2 | sed 's/&amp;/\&/g')
cb=$(curl -s -b "$J" -c "$J" -o /dev/null -w "%{redirect_url}" --max-time 15 \
    -d "login=alice@otternet.lab" -d "password=password" "http://10.90.0.11:32556${form}")
curl -s -b "$J" -c "$J" --max-time 20 "$cb" > /tmp/frame.html
python3 -c '
import re, urllib.parse
s = urllib.parse.unquote(open("/tmp/frame.html").read())
m = re.search(r"\"token\":\"([A-Za-z0-9._-]+)\"", s)
print(m.group(1) if m else "")
'
