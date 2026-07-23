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

# Cron expression: 09:31 Mon-Fri (US Eastern — adjust TZ if needed)
# Note: crontab variables cannot use quotes; we use a wrapper approach instead.
CRON_MARKER="# TradingAgents daily run"
CRON_LINE="31 9 * * 1-5 cd $DEMO_DIR && $PYTHON $RUN_SCRIPT >> $LOG_FILE 2>&1 $CRON_MARKER"

# Add to crontab (avoid duplicates by removing any existing TradingAgents line first)
(
  crontab -l 2>/dev/null | grep -v "TradingAgents daily run"
  echo "$CRON_LINE"
) | crontab -

echo "\u2705 Cron job installed:"
echo "   $CRON_LINE"
echo ""
echo "Verify with: crontab -l"
echo "Logs will go to: $LOG_FILE"
