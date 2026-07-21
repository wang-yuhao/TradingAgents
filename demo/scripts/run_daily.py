#!/usr/bin/env python3
"""
run_daily.py — Daily entry point for the TradingAgents demo.

Usage:
  python run_daily.py                            # Run for today
  python run_daily.py --date 2026-07-21          # Specific date
  python run_daily.py --symbol AAPL --dry-run    # Single symbol, dry-run
  python run_daily.py --all-symbols              # All configured symbols
"""

import argparse
import json
import logging
import os
import sys
from datetime import date, datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ── Path setup ───────────────────────────────────────────────────────────────
DEMO_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = DEMO_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

# Load environment variables from demo/.env
load_dotenv(DEMO_DIR / ".env")

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config() -> dict:
    config_path = DEMO_DIR / "config" / "demo_config.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_weights() -> dict:
    """Load self-improved analyst weights, or return defaults."""
    weights_path = DEMO_DIR / "data" / "parameters" / "weights.json"
    defaults = {
        "bull_analyst": 0.33,
        "bear_analyst": 0.33,
        "news_analyst": 0.34,
    }
    if weights_path.exists():
        with open(weights_path) as f:
            loaded = json.load(f)
        log.info("Loaded self-improved weights: %s", loaded)
        return loaded
    return defaults


def run_trading_agent(symbol: str, trade_date: str, config: dict, weights: dict, dry_run: bool) -> dict:
    """
    Invoke the TradingAgents framework for one symbol on one date.
    Returns a result dict with decision, confidence, and pnl.
    """
    log.info("[%s] Running TradingAgents for %s", trade_date, symbol)

    try:
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        agent_config = dict(DEFAULT_CONFIG)
        agent_config["llm_provider"] = config["agents"]["llm_provider"]
        agent_config["deep_think_llm"] = config["agents"]["model"]
        agent_config["quick_think_llm"] = config["agents"]["model"]
        agent_config["max_debate_rounds"] = config["agents"]["analyst_rounds"]
        agent_config["online_tools"] = not dry_run

        ta = TradingAgentsGraph(debug=False, config=agent_config)

        state, decision = ta.propagate(symbol, trade_date)

        result = {
            "date": trade_date,
            "symbol": symbol,
            "decision": decision,
            "dry_run": dry_run,
            "weights_used": weights,
            "timestamp": datetime.now().isoformat(),
        }

    except ImportError as e:
        log.error("TradingAgents import failed: %s. Running in SIMULATION mode.", e)
        import random
        result = _simulate_trade(symbol, trade_date, weights, dry_run)

    return result


def _simulate_trade(symbol: str, trade_date: str, weights: dict, dry_run: bool) -> dict:
    """Fallback simulation when TradingAgents is not fully configured."""
    import random
    import hashlib

    # Deterministic pseudo-random based on date+symbol for reproducibility
    seed = int(hashlib.md5(f"{trade_date}{symbol}".encode()).hexdigest(), 16) % 10000
    rng = random.Random(seed)

    actions = ["BUY", "SELL", "HOLD"]
    action = rng.choices(actions, weights=[0.4, 0.3, 0.3])[0]
    confidence = round(rng.uniform(0.5, 0.95), 3)
    pnl_pct = round(rng.uniform(-0.03, 0.05), 4)

    log.info("  [SIMULATION] %s → %s (confidence=%.2f, pnl=%.2f%%)",
             symbol, action, confidence, pnl_pct * 100)

    return {
        "date": trade_date,
        "symbol": symbol,
        "decision": {
            "action": action,
            "confidence": confidence,
            "reasoning": f"[Simulated] {action} signal for {symbol} on {trade_date}",
            "pnl_pct": pnl_pct,
        },
        "dry_run": dry_run,
        "weights_used": weights,
        "simulated": True,
        "timestamp": datetime.now().isoformat(),
    }


def save_result(result: dict, config: dict) -> Path:
    results_dir = DEMO_DIR / config["logging"]["results_dir"]
    results_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{result['date']}_{result['symbol']}.json"
    path = results_dir / filename
    with open(path, "w") as f:
        json.dump(result, f, indent=2)
    log.info("Saved result → %s", path)
    return path


def maybe_run_postprocessing(config: dict):
    """After saving results, optionally run self-improvement and visualization."""
    schedule_config_path = DEMO_DIR / "config" / "schedule_config.yaml"
    with open(schedule_config_path) as f:
        sched = yaml.safe_load(f)

    if sched["schedule"].get("run_self_improve_after", True):
        log.info("Running self-improvement analysis...")
        try:
            from scripts.self_improve import run_self_improvement
            run_self_improvement(config)
        except Exception as e:
            log.warning("Self-improvement failed (non-fatal): %s", e)

    if sched["schedule"].get("run_visualize_after", True):
        log.info("Regenerating dashboard...")
        try:
            from scripts.visualize import generate_dashboard
            generate_dashboard(config)
        except Exception as e:
            log.warning("Dashboard generation failed (non-fatal): %s", e)


def main():
    parser = argparse.ArgumentParser(description="TradingAgents Daily Runner")
    parser.add_argument("--date", default="today", help="Date YYYY-MM-DD or 'today'")
    parser.add_argument("--symbol", default=None, help="Single ticker symbol")
    parser.add_argument("--all-symbols", action="store_true", help="Run all configured symbols")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Paper trading mode")
    parser.add_argument("--no-postprocess", action="store_true", help="Skip self-improve + dashboard")
    args = parser.parse_args()

    config = load_config()
    weights = load_weights()

    trade_date = date.today().isoformat() if args.date == "today" else args.date

    if args.symbol:
        symbols = [args.symbol.upper()]
    elif args.all_symbols:
        symbols = config["strategy"]["symbols"]
    else:
        symbols = config["strategy"]["symbols"]

    log.info("═" * 60)
    log.info("TradingAgents Daily Run | Date: %s | Symbols: %s", trade_date, symbols)
    log.info("═" * 60)

    all_results = []
    for symbol in symbols:
        result = run_trading_agent(symbol, trade_date, config, weights, dry_run=args.dry_run)
        save_result(result, config)
        all_results.append(result)

    log.info("All %d symbol(s) processed.", len(all_results))

    if not args.no_postprocess:
        maybe_run_postprocessing(config)

    log.info("Done. Dashboard: %s", DEMO_DIR / "dashboards" / "index.html")


if __name__ == "__main__":
    main()
