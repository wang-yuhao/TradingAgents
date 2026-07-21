#!/usr/bin/env python3
"""
test_self_improve.py — Unit tests for the self-improvement module.
"""

import sys
from pathlib import Path

import pytest

DEMO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO_DIR / "scripts"))


def load_config():
    import yaml
    with open(DEMO_DIR / "config" / "demo_config.yaml") as f:
        return yaml.safe_load(f)


def test_weights_sum_to_one_after_improvement():
    from self_improve import compute_new_weights
    config = load_config()
    old_weights = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}

    # Simulate 10 winning BUY trades dominated by bull_analyst
    results = []
    for i in range(10):
        results.append({
            "decision": {"action": "BUY", "pnl_pct": 0.02, "confidence": 0.8},
            "weights_used": {"bull_analyst": 0.5, "bear_analyst": 0.25, "news_analyst": 0.25},
        })

    new_weights = compute_new_weights(results, old_weights, config)
    total = sum(new_weights.values())
    assert abs(total - 1.0) < 1e-9, f"Weights don't sum to 1: {total}"


def test_weights_stay_in_bounds():
    from self_improve import compute_new_weights
    config = load_config()
    w_min, w_max = config["self_improvement"]["weight_bounds"]
    old_weights = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}

    results = []
    for i in range(20):
        results.append({
            "decision": {"action": "BUY", "pnl_pct": 0.05, "confidence": 0.9},
            "weights_used": {"bull_analyst": 0.8, "bear_analyst": 0.1, "news_analyst": 0.1},
        })

    new_weights = compute_new_weights(results, old_weights, config)
    for k, v in new_weights.items():
        assert w_min <= v <= w_max, f"{k}={v} out of bounds [{w_min}, {w_max}]"


def test_insufficient_trades_returns_unchanged():
    from self_improve import compute_new_weights
    config = load_config()
    old_weights = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}

    # Only 2 trades, below min_trades_to_improve=5
    results = [
        {"decision": {"action": "BUY", "pnl_pct": 0.01}, "weights_used": old_weights},
        {"decision": {"action": "SELL", "pnl_pct": -0.01}, "weights_used": old_weights},
    ]

    new_weights = compute_new_weights(results, old_weights, config)
    assert new_weights == old_weights


def test_losing_trades_reduce_dominant_analyst():
    from self_improve import compute_new_weights
    config = load_config()
    old_weights = {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}

    # 10 losing trades dominated by bull_analyst
    results = []
    for i in range(10):
        results.append({
            "decision": {"action": "BUY", "pnl_pct": -0.03, "confidence": 0.8},
            "weights_used": {"bull_analyst": 0.8, "bear_analyst": 0.1, "news_analyst": 0.1},
        })

    new_weights = compute_new_weights(results, old_weights, config)
    assert new_weights["bull_analyst"] < old_weights["bull_analyst"], \
        "Bull analyst weight should decrease after repeated losses"
