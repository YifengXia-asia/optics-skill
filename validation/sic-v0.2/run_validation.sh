#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="${SKILL_DIR:?Set SKILL_DIR to the skill directory}"
CONFIG="${1:?Usage: SKILL_DIR=/path/to/skill $0 /path/to/config.yaml}"
PYTHON="${PYTHON:-python3}"

"$PYTHON" "$SKILL_DIR/scripts/config_loader.py" --config "$CONFIG" --check
"$PYTHON" "$SKILL_DIR/scripts/prepare.py" --config "$CONFIG"
"$PYTHON" "$SKILL_DIR/scripts/run.py" --config "$CONFIG"
"$PYTHON" "$SKILL_DIR/scripts/extract.py" --config "$CONFIG"
"$PYTHON" "$SKILL_DIR/scripts/plot.py" --config "$CONFIG"
"$PYTHON" "$SKILL_DIR/scripts/validate.py" --config "$CONFIG"
