# TradingAgents Daily Demo

A fully automated, self-improving quantitative trading agent demo that:
- **Runs daily** on your local laptop via a scheduler
- **Back-tests and paper-trades** using the TradingAgents multi-agent framework
- **Self-improves** by persisting performance metrics and adjusting analyst weights
- **Visualizes results** with interactive HTML dashboards updated every day

> **Two execution modes:** The `demo/` folder contains two sets of scripts.
> - **`scripts/` (v1)** — simple standalone scripts that use `demo/config/demo_config.yaml`
> - **`*_v2.py` files (v2)** — production pipeline with retries, market-calendar awareness, and APScheduler; uses `demo/config_v2.yaml`
>
> **For a quick first run, use the v1 scripts. For automated daily scheduling, use v2.**

---

## Project Structure

```
demo/
├── README.md                    # This file
├── requirements.txt             # Python dependencies (install this!)
├── .env.example                 # API key template
├── config/
│   ├── demo_config.yaml         # v1 strategy/agent config
│   └── schedule_config.yaml     # v1 scheduler settings
├── config_v2.yaml               # v2 all-in-one config
├── scripts/                     # v1 entry points
│   ├── run_daily.py             # Main daily entry point
│   ├── run_backtest.py          # Backtest runner
│   ├── self_improve.py          # Perf analysis & parameter tuning
│   └── visualize.py             # Dashboard generator
├── run_analysis_v2.py           # v2 analysis runner
├── backtest_v2.py               # v2 backtest engine
├── self_improve_v2.py           # v2 self-improvement
├── scheduler_v2.py              # v2 APScheduler entry point
├── dashboard_v2.py              # v2 dashboard server
├── data/
│   ├── results/                 # Daily trade logs (JSON)
│   ├── performance/             # Cumulative metrics (CSV)
│   └── parameters/              # Evolving strategy params (JSON)
├── decision_log/                # v2 decision logs (JSON, auto-created)
├── dashboards/
│   └── index.html               # Auto-generated daily dashboard
├── logs/                        # Runtime log files (auto-created)
├── tests/
│   ├── test_pipeline.py         # Integration tests
│   └── test_self_improve.py     # Self-improvement unit tests
└── scheduler/
    ├── setup_cron.sh            # macOS/Linux cron installer
    └── setup_task_windows.ps1   # Windows Task Scheduler script
```

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | ≥ 3.11 | Use pyenv or conda |
| pip | ≥ 23 | `pip install --upgrade pip` |
| OpenAI API key | — | Required for LLM agents |
| FinnHub API key | — | Free tier works |
| Git | any | To clone repo |

---

## Step-by-Step Setup Guide

### Step 1 — Clone the repository

```bash
git clone https://github.com/wang-yuhao/TradingAgents.git
cd TradingAgents
```

### Step 2 — Create a Python virtual environment

```bash
# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate

# Windows PowerShell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Step 3 — Install all dependencies

```bash
# Install base TradingAgents package from repo root
pip install -e .

# Install demo-specific extras (includes yfinance, APScheduler, tenacity, etc.)
pip install -r demo/requirements.txt
```

### Step 4 — Configure API keys

```bash
# Copy the example env file
cp demo/.env.example demo/.env

# Edit demo/.env and fill in your keys:
#   OPENAI_API_KEY=sk-...
#   FINNHUB_API_KEY=...
#   TAVILY_API_KEY=...  (optional, for news search)
```

> ⚠️ **Never commit `demo/.env` to Git.** It is already listed in `.gitignore`.

---

## Quick Start — v1 Scripts (Recommended for first run)

All commands below are run **from the repo root**.

### Step 5 — Run a manual one-off test

```bash
python demo/scripts/run_daily.py --date today --symbol AAPL --dry-run
```

Expected output:
```
[2026-07-22 09:31:00] INFO TradingAgents Daily Run | Date: 2026-07-22 | Symbols: ['AAPL']
[2026-07-22 09:31:01] INFO [2026-07-22] Running TradingAgents for AAPL
[2026-07-22 09:31:05] INFO   [SIMULATION] AAPL → BUY (confidence=0.73, pnl=2.10%)
[2026-07-22 09:31:05] INFO Saved result → demo/data/results/2026-07-22_AAPL.json
```

### Step 6 — Run the backtest (last 30 days)

```bash
python demo/scripts/run_backtest.py --symbol AAPL --days 30
```

This will:
1. Replay the last 30 trading days using historical/simulated data
2. Save daily results to `demo/data/results/`
3. Compute cumulative metrics in `demo/data/performance/metrics.csv`
4. Generate the dashboard at `demo/dashboards/index.html`

Open `demo/dashboards/index.html` in your browser to see results.

### Step 7 — Run the self-improvement analysis

```bash
python demo/scripts/self_improve.py
```

This reads accumulated performance data and:
- Identifies which analyst agents contributed most to profitable decisions
- Adjusts analyst confidence weights in `demo/data/parameters/weights.json`
- Logs the improvement reasoning to `demo/data/performance/improvement_log.csv`

### Step 8 — Generate / refresh the dashboard

```bash
python demo/scripts/visualize.py --open-browser
```

---

## Production Pipeline — v2 (for automated daily scheduling)

### Run the v2 analysis once

```bash
python demo/run_analysis_v2.py
# or for a specific date:
python demo/run_analysis_v2.py --date 2026-07-22
```

### Run the v2 backtest

```bash
python demo/backtest_v2.py
# or with custom lookback:
python demo/backtest_v2.py --lookback 60
```

### Run the v2 self-improvement

```bash
python demo/self_improve_v2.py
```

### Start the v2 scheduler (runs full pipeline daily)

```bash
# Start blocking scheduler (keeps running, fires at 08:30 ET on trading days)
python demo/scheduler_v2.py

# Or trigger once immediately and keep running:
python demo/scheduler_v2.py --run-now

# Or run once and exit (suitable for OS-level cron):
python demo/scheduler_v2.py --once
```

### Step 9 — Automate daily runs

#### macOS / Linux (cron)

```bash
bash demo/scheduler/setup_cron.sh
```

This installs a cron job that runs at **09:31 AM on weekdays** (after US market open).

Verify it was installed:
```bash
crontab -l
# Should show a line containing: run_daily.py
```

#### Windows (Task Scheduler)

Open PowerShell as Administrator:
```powershell
cd demo\scheduler
.\setup_task_windows.ps1
```

### Step 10 — View the dashboard

```bash
# Open in default browser (macOS)
open demo/dashboards/index.html

# Linux
xdg-open demo/dashboards/index.html

# Or serve locally
python -m http.server 8080 --directory demo/dashboards
# Then open http://localhost:8080
```

---

## Configuration Reference

### v1 — `demo/config/demo_config.yaml`

```yaml
strategy:
  symbols: ["AAPL", "MSFT", "NVDA"]   # Tickers to trade
  initial_capital: 100000
  max_position_pct: 0.2

agents:
  llm_provider: openai
  model: gpt-4o-mini
  analyst_rounds: 2

self_improvement:
  enabled: true
  lookback_days: 14
  min_trades_to_improve: 5
  learning_rate: 0.05
  weight_bounds: [0.05, 0.95]
```

### v2 — `demo/config_v2.yaml`

```yaml
tickers: [AAPL, MSFT, GOOGL, NVDA, TSLA, AMZN, META, SPY]
benchmark: SPY

schedule:
  run_time: "08:30"
  timezone: "America/New_York"
  calendar: "NYSE"

llm:
  provider: openai
  model: gpt-4o-mini
  max_retries: 3

trading_agents:
  debate_rounds: 1
  max_risk_discuss_rounds: 1
  online_tools: true
```

---

## How Self-Improvement Works

```
Daily Run ──► Trade Decision ──► Result Logged
                                      │
                              ┌───────▼────────┐
                              │  Performance   │
                              │  Analyzer      │
                              │  (14-day look- │
                              │   back window) │
                              └───────┬────────┘
                                      │
                              ┌───────▼────────┐
                              │ Weight Updater │
                              │ Bull/Bear/News  │
                              │ analyst weights │
                              └───────┬────────┘
                                      │
                              Next day uses updated weights
```

---

## Running Tests

```bash
# Run from repo root
python -m pytest demo/tests/ -v
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `ModuleNotFoundError: tradingagents` | Run `pip install -e .` from repo root |
| `ModuleNotFoundError: yfinance` | Run `pip install -r demo/requirements.txt` |
| `ModuleNotFoundError: apscheduler` | Run `pip install -r demo/requirements.txt` |
| `ModuleNotFoundError: tenacity` | Run `pip install -r demo/requirements.txt` |
| `OPENAI_API_KEY not set` | Check `demo/.env` is present and loaded |
| `No data for symbol` | FinnHub free tier has limited history; try AAPL/MSFT |
| Dashboard not updating | Check `demo/data/results/` has JSON files from today |
| Cron not running | Run `crontab -l` and check path; ensure venv is activated in script |
| `KeyError` in config | Ensure you're using `config_v2.yaml` for v2 scripts and `config/demo_config.yaml` for v1 |
