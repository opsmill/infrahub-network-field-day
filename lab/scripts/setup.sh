#!/usr/bin/env bash
# Build the AVD toolchain in a self-contained virtualenv.
#
# This host runs Python 3.14 and ansible-core 2.21, both outside AVD 6.x's
# supported window (ansible-core 2.16-2.20), so the lab pins its own interpreter
# via uv rather than touching the system install.
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$LAB_DIR"

say() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

command -v uv >/dev/null 2>&1 || {
    echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
}

say "Provisioning Python 3.12 and the virtualenv"
uv python install 3.12
uv venv --python 3.12 .venv

say "Installing ansible-core and pyavd"
uv pip install --python .venv/bin/python "ansible-core<2.21" "pyavd[ansible]"

say "Installing Ansible collections into the lab directory"
ANSIBLE_COLLECTIONS_PATH="$LAB_DIR/.ansible/collections" \
    .venv/bin/ansible-galaxy collection install -r avd/requirements.yml

say "Versions"
.venv/bin/ansible --version | head -2
.venv/bin/python -c 'import pyavd; print("pyavd", pyavd.__version__)'
ANSIBLE_COLLECTIONS_PATH="$LAB_DIR/.ansible/collections" \
    .venv/bin/ansible-galaxy collection list arista.avd 2>/dev/null | tail -3

cat <<'EOF'

Toolchain ready. Next:
  make avd-build      # render the fabric offline -- needs no images, no lab
  make preflight      # check this host can run the lab
  make deploy         # bring the lab up

EOF
