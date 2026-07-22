# TradingAgents Demo — Self-Running Pipeline

A production-quality daily trading pipeline built on top of the
[TradingAgents](https://github.com/wang-yuhao/TradingAgents) multi-agent LLM framework.

## What it does

Every trading day (NYSE calendar):
1. **Analyzes** a configurable watchlist using `TradingAgentsGraph.propagate()`
2. **Logs** decisions to `decision_log/<YYYY-MM-DD>.json`
3. **Backtests** past decisions against realized prices (yfinance)
4. **Self-improves** by appending a structured reflection to `trading_memory.md`
5. **Visualizes** everything in a Streamlit dashboard

---

## 1. Environment Setup

### Prerequisites
- Python 3.12
- `conda` or `venv`

### Clone & enter repo
```bash
git clone https://github.com/wang-yuhao/TradingAgents.git
cd TradingAgents
```

### Create environment (conda recommended)
```bash
conda create -n tradingagents python=3.12 -y
conda activate tradingagents
```

### Install base framework
```bash
pip install -e .
```

### Install demo dependencies
```bash
pip install -r demo/requirements.txt
```

---

## 2. Configure API Keys

```bash
cp demo/.env.example .env
```

Edit `.env` and fill in at minimum:
