#!/bin/bash
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

# Activate venv
source .venv/bin/activate

# Run server
python -m lingbot.runner
