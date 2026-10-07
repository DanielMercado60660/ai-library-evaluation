#!/bin/bash
# Simple wrapper to run the Python seed_all script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

python3 scripts/seed_all.py
