#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FLASHDREAMS_ROOT="$HERE/../.."
cd "$HERE"

source .venv/bin/activate

export PYTHONPATH="$FLASHDREAMS_ROOT:$HERE:$FLASHDREAMS_ROOT/apps:${PYTHONPATH:-}"

python << 'PYEOF'
from lingbot.demo.app import main
main(['webrtc', '--host', '0.0.0.0', '--port', '8089', '--device', 'cuda:0', '--example-data', 'True'])
PYEOF

