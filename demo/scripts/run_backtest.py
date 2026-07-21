#!/usr/bin/env python3
"""
run_backtest.py — Replay the last N trading days and generate performance metrics.

Usage:
  python run_backtest.py --symbol AAPL --days 30
  python run_backtest.py --all-symbols --days 60
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

DEMO_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DEMO_DIR.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(DEMO_DIR / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def is_weekday(d: date) -> bool:
    return d.weekday() < 5


def get_trading_days(n_days: int) -> list[str]:
    days = []
    current = date.today() - timedelta(days=1)  # start from yesterday
    while len(days) < n_days:
        if is_weekday(current):
            days.append(current.isoformat())
        current -= timedelta(days=1)
    return list(reversed(days))


def load_config() -> dict:
    with open(DEMO_DIR / "config" / "demo_config.yaml") as f:
        return yaml.safe_load(f)


def load_weights() -> dict:
    weights_path = DEMO_DIR / "data" / "parameters" / "weights.json"
    defaults = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}
    if weights_path.exists():
        with open(weights_path) as f:
            return json.load(f)
    return defaults


def compute_metrics(results: list[dict]) -> pd.DataFrame:
    """Build a daily performance DataFrame from a list of result dicts."""
    rows = []
    cumulative_pnl = 0.0
    capital = 100000.0

    for r in results:
        decision = r.get("decision", {})
        if isinstance(decision, dict):
            action = decision.get("action", "HOLD")
            confidence = decision.get("confidence", 0.5)
            pnl_pct = decision.get("pnl_pct", 0.0)
        else:
            action, confidence, pnl_pct = str(decision), 0.5, 0.0

        trade_pnl = capital * 0.1 * pnl_pct if action in ("BUY", "SELL") else 0.0
        cumulative_pnl += trade_pnl
        capital += trade_pnl

        rows.append({
            "date": r["date"],
            "symbol": r["symbol"],
            "action": action,
            "confidence": confidence,
            "daily_pnl": round(trade_pnl, 2),
            "cumulative_pnl": round(cumulative_pnl, 2),
            "portfolio_value": round(capital, 2),
            "pnl_pct": pnl_pct,
        })

    return pd.DataFrame(rows)


def save_metrics(df: pd.DataFrame, config: dict):
    perf_dir = DEMO_DIR / config["logging"]["performance_dir"]
    perf_dir.mkdir(parents=True, exist_ok=True)
    path = perf_dir / "metrics.csv"
    df.to_csv(path, index=False)
    log.info("Metrics saved → %s", path)
    return path


def main():
    parser = argparse.ArgumentParser(description="TradingAgents Backtest Runner")
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--all-symbols", action="store_true")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    config = load_config()
    weights = load_weights()

    if args.symbol:
        symbols = [args.symbol.upper()]
    else:
        symbols = config["strategy"]["symbols"]

    trading_days = get_trading_days(args.days)
    log.info("Backtesting %s over %d days (%s → %s)",
             symbols, args.days, trading_days[0], trading_days[-1])

    # Import run function from run_daily
    sys.path.insert(0, str(DEMO_DIR / "scripts"))
    from run_daily import run_trading_agent, save_result

    all_results = []
    for symbol in symbols:
        for day in tqdm(trading_days, desc=f"Backtesting {symbol}"):
            result_path = DEMO_DIR / config["logging"]["results_dir"] / f"{day}_{symbol}.json"
            if result_path.exists():
                with open(result_path) as f:
                    result = json.load(f)
                log.debug("  Cache hit: %s %s", day, symbol)
            else:
                result = run_trading_agent(symbol, day, config, weights, dry_run=True)
                save_result(result, config)
            all_results.append(result)

    df = compute_metrics(all_results)
    save_metrics(df, config)

    # Print summary
    print("\n" + "═" * 50)
    print(f"  BACKTEST SUMMARY ({args.days} days)")
    print("═" * 50)
    for sym in symbols:
        sym_df = df[df["symbol"] == sym]
        if not sym_df.empty:
            total_pnl = sym_df["cumulative_pnl"].iloc[-1]
            n_trades = len(sym_df[sym_df["action"].isin(["BUY", "SELL"])])
            win_rate = len(sym_df[sym_df["daily_pnl"] > 0]) / max(len(sym_df), 1) * 100
            print(f"  {sym}: PnL=${total_pnl:,.0f}  Trades={n_trades}  Win%={win_rate:.1f}%")
    print("═" * 50)

    # Generate dashboard
    try:
        sys.path.insert(0, str(DEMO_DIR / "scripts"))
        from visualize import generate_dashboard
        generate_dashboard(config)
        print(f"\n  Dashboard: {DEMO_DIR / 'dashboards' / 'index.html'}")
    except Exception as e:
        log.warning("Dashboard generation failed: %s", e)


if __name__ == "__main__":
    main()
