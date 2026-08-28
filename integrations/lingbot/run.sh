#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Set PYTHONPATH to include cam2v and other apps
export PYTHONPATH="$(cd "$HERE/../.." && pwd)/apps:${PYTHONPATH:-}"

# Activate venv
source .venv/bin/activate

# Run server
python -m lingbot.runner
