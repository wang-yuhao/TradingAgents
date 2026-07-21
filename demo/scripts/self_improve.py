#!/usr/bin/env python3
"""
self_improve.py — Analyze accumulated trade performance and update analyst weights.

Logic:
  1. Load all result JSON files from the last N days
  2. For each trade: determine if it was profitable (pnl_pct > 0)
  3. Check which analyst signals dominated the decision
  4. Increase weights of analysts whose high-confidence signals led to profits
  5. Decrease weights of analysts whose high-confidence signals led to losses
  6. Save updated weights to data/parameters/weights.json

Usage:
  python self_improve.py
  python self_improve.py --lookback 30
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

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


def load_config() -> dict:
    with open(DEMO_DIR / "config" / "demo_config.yaml") as f:
        return yaml.safe_load(f)


def load_recent_results(lookback_days: int, config: dict) -> list[dict]:
    results_dir = DEMO_DIR / config["logging"]["results_dir"]
    if not results_dir.exists():
        return []

    cutoff = (date.today() - timedelta(days=lookback_days)).isoformat()
    results = []
    for f in sorted(results_dir.glob("*.json")):
        date_part = f.stem.split("_")[0]  # e.g. 2026-07-21_AAPL → 2026-07-21
        if date_part >= cutoff:
            with open(f) as fh:
                results.append(json.load(fh))
    return results


def load_current_weights(config: dict) -> dict:
    weights_path = DEMO_DIR / "data" / "parameters" / "weights.json"
    defaults = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}
    if weights_path.exists():
        with open(weights_path) as f:
            return json.load(f)
    return defaults


def compute_new_weights(results: list[dict], current_weights: dict, config: dict) -> dict:
    """
    Simple gradient-style weight update:
    - For profitable trades (pnl_pct > 0): nudge weights toward the dominant analyst
    - For losing trades (pnl_pct <= 0): nudge weights away from the dominant analyst
    """
    si_config = config["self_improvement"]
    lr = si_config["learning_rate"]
    w_min, w_max = si_config["weight_bounds"]

    weights = dict(current_weights)
    analyst_keys = list(weights.keys())

    # Track cumulative score per analyst
    scores = {k: 0.0 for k in analyst_keys}
    count = 0

    for r in results:
        decision = r.get("decision", {})
        if not isinstance(decision, dict):
            continue

        pnl = decision.get("pnl_pct", 0.0)
        action = decision.get("action", "HOLD")
        if action == "HOLD":
            continue

        # Infer dominant analyst from weights_used (stored at decision time)
        weights_used = r.get("weights_used", weights)
        dominant = max(weights_used, key=weights_used.get)

        # Reward or penalize dominant analyst
        signal = 1.0 if pnl > 0 else -1.0
        scores[dominant] += signal
        count += 1

    if count < si_config["min_trades_to_improve"]:
        log.info("Not enough trades (%d < %d) to update weights. Keeping current.",
                 count, si_config["min_trades_to_improve"])
        return weights

    log.info("Analyst performance scores over %d trades: %s", count, scores)

    # Apply gradient update
    new_weights = {}
    for k in analyst_keys:
        delta = lr * (scores[k] / max(count, 1))
        new_weights[k] = min(w_max, max(w_min, weights[k] + delta))

    # Normalize to sum to 1.0
    total = sum(new_weights.values())
    new_weights = {k: round(v / total, 4) for k, v in new_weights.items()}

    log.info("Old weights: %s", {k: round(v, 4) for k, v in weights.items()})
    log.info("New weights: %s", new_weights)
    return new_weights


def save_weights(weights: dict, config: dict):
    params_dir = DEMO_DIR / "data" / "parameters"
    params_dir.mkdir(parents=True, exist_ok=True)
    path = params_dir / "weights.json"
    with open(path, "w") as f:
        json.dump(weights, f, indent=2)
    log.info("Weights saved → %s", path)


def log_improvement(old_weights: dict, new_weights: dict, n_trades: int, config: dict):
    perf_dir = DEMO_DIR / config["logging"]["performance_dir"]
    perf_dir.mkdir(parents=True, exist_ok=True)
    log_path = perf_dir / "improvement_log.csv"

    row = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "n_trades_analyzed": n_trades,
    }
    for k in old_weights:
        row[f"old_{k}"] = old_weights[k]
        row[f"new_{k}"] = new_weights.get(k, old_weights[k])

    df_new = pd.DataFrame([row])
    if log_path.exists():
        df_existing = pd.read_csv(log_path)
        df_all = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df_all = df_new
    df_all.to_csv(log_path, index=False)
    log.info("Improvement log updated → %s", log_path)


def run_self_improvement(config: dict = None, lookback_days: int = None):
    if config is None:
        config = load_config()
    if lookback_days is None:
        lookback_days = config["self_improvement"]["lookback_days"]

    results = load_recent_results(lookback_days, config)
    log.info("Loaded %d results from last %d days.", len(results), lookback_days)

    if not results:
        log.warning("No results found. Run run_backtest.py first.")
        return

    old_weights = load_current_weights(config)
    new_weights = compute_new_weights(results, old_weights, config)
    save_weights(new_weights, config)
    log_improvement(old_weights, new_weights, len(results), config)


def main():
    parser = argparse.ArgumentParser(description="TradingAgents Self-Improvement")
    parser.add_argument("--lookback", type=int, default=None,
                        help="Days of history to analyze (default: from config)")
    args = parser.parse_args()

    config = load_config()
    run_self_improvement(config, lookback_days=args.lookback)


if __name__ == "__main__":
    main()
