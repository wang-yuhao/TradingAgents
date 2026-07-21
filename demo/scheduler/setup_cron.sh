#!/usr/bin/env bash
# setup_cron.sh — Install a cron job to run the TradingAgents demo daily.
# Usage: bash demo/scheduler/setup_cron.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$(dirname "$SCRIPT_DIR")"
REPO_ROOT="$(dirname "$DEMO_DIR")"

# Detect virtual environment python
if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/.venv/bin/python"
elif [ -f "$REPO_ROOT/venv/bin/python" ]; then
    PYTHON="$REPO_ROOT/venv/bin/python"
else
    PYTHON=$(which python3)
    echo "WARNING: Could not find .venv — using system python3: $PYTHON"
fi

RUN_SCRIPT="$DEMO_DIR/scripts/run_daily.py"
LOG_FILE="$DEMO_DIR/logs/cron_daily.log"

# Ensure log directory exists
mkdir -p "$DEMO_DIR/logs"

# Cron expression: 09:31 Mon-Fri (US Eastern, adjust for your timezone)
CRON_EXPR="31 9 * * 1-5 cd \"$DEMO_DIR\" && $PYTHON $RUN_SCRIPT >> $LOG_FILE 2>&1"

# Add to crontab (avoid duplicates)
( crontab -l 2>/dev/null | grep -v "run_daily.py"; echo "$CRON_EXPR" ) | crontab -

echo "✅ Cron job installed:"
echo "   $CRON_EXPR"
echo ""
echo "Verify with: crontab -l"
echo "Logs will go to: $LOG_FILE"
