# TradingAgents Daily Demo

A fully automated, self-improving quantitative trading agent demo that:
- **Runs daily** on your local laptop via a scheduler
- **Back-tests and paper-trades** using the TradingAgents multi-agent framework
- **Self-improves** by persisting performance metrics and adjusting strategy parameters
- **Visualizes results** with interactive HTML dashboards updated every day

---

## Project Structure

```
demo/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.example                 # API key template
├── config/
│   ├── demo_config.yaml         # Main strategy/agent config
│   └── schedule_config.yaml     # Scheduler settings
├── scripts/
│   ├── run_daily.py             # Main daily entry point
│   ├── run_backtest.py          # Backtest runner
│   ├── self_improve.py          # Perf analysis & parameter tuning
│   └── visualize.py             # Dashboard generator
├── data/
│   ├── results/                 # Daily trade logs (JSON)
│   ├── performance/             # Cumulative metrics (CSV)
│   └── parameters/              # Evolving strategy params (JSON)
├── dashboards/
│   └── index.html               # Auto-generated daily dashboard
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
# Install base TradingAgents package
pip install -e .

# Install demo-specific extras
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

### Step 5 — Run a manual one-off test

```bash
cd demo
python scripts/run_daily.py --date today --symbol AAPL --dry-run
```

Expected output:
```
[2026-07-22] Running TradingAgents for AAPL (dry-run mode)
[ANALYST] Fetching market data...
[BULL]    Bullish thesis: ...
[BEAR]    Bearish thesis: ...
[TRADER]  Decision: BUY  | Confidence: 0.73
[RESULT]  Saved to data/results/2026-07-22_AAPL.json
[CHART]   Dashboard updated: dashboards/index.html
```

### Step 6 — Run the backtest (last 30 days)

```bash
python scripts/run_backtest.py --symbol AAPL --days 30
```

This will:
1. Replay the last 30 trading days using historical data
2. Save daily results to `data/results/`
3. Compute cumulative metrics in `data/performance/metrics.csv`
4. Generate the dashboard at `dashboards/index.html`

Open `dashboards/index.html` in your browser to see results.

### Step 7 — Run the self-improvement analysis

```bash
python scripts/self_improve.py
```

This reads accumulated performance data and:
- Identifies which analyst agents contributed most to profitable decisions
- Adjusts analyst confidence weights in `data/parameters/weights.json`
- Logs the improvement reasoning to `data/performance/improvement_log.csv`

### Step 8 — Automate daily runs

#### macOS / Linux (cron)

```bash
bash demo/scheduler/setup_cron.sh
```

This installs a cron job that runs at **09:31 AM on weekdays** (after market open).

Verify it was installed:
```bash
crontab -l
# Should show: 31 9 * * 1-5 /path/to/.venv/bin/python .../run_daily.py
```

#### Windows (Task Scheduler)

Open PowerShell as Administrator:
```powershell
cd demo\scheduler
.\setup_task_windows.ps1
```

### Step 9 — View the dashboard

```bash
# Open in default browser (macOS)
open dashboards/index.html

# Linux
xdg-open dashboards/index.html

# Or serve locally
python -m http.server 8080 --directory dashboards
# Then open http://localhost:8080
```

---

## Configuration Reference

Edit `config/demo_config.yaml` to customize:

```yaml
strategy:
  symbols: ["AAPL", "MSFT", "NVDA"]   # Tickers to trade
  initial_capital: 100000              # Paper trading capital
  max_position_pct: 0.2                # Max 20% per position

agents:
  llm_provider: openai
  model: gpt-4o-mini                   # Use mini for cost efficiency
  analyst_rounds: 2                    # Debate rounds per decision

self_improvement:
  enabled: true
  lookback_days: 14                    # Days of history to analyze
  min_trades_to_improve: 5             # Min trades before adjusting weights
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
cd demo
python -m pytest tests/ -v
```

---

## Troubleshooting

| Error | Fix |
|---|---|
| `ModuleNotFoundError: tradingagents` | Run `pip install -e .` from repo root |
| `OPENAI_API_KEY not set` | Check `demo/.env` is present and loaded |
| `No data for symbol` | FinnHub free tier has limited history; try AAPL/MSFT |
| Dashboard not updating | Check `data/results/` has JSON files from today |
| Cron not running | Run `crontab -l` and check path; ensure venv is activated in script |
