#!/usr/bin/env python3
"""
test_pipeline.py — Integration tests for the daily pipeline.
"""

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

DEMO_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DEMO_DIR / "scripts"))


def test_load_config():
    from run_daily import load_config
    config = load_config()
    assert "strategy" in config
    assert "symbols" in config["strategy"]
    assert len(config["strategy"]["symbols"]) > 0


def test_load_weights_defaults():
    from run_daily import load_weights
    # Temporarily rename weights file if it exists
    weights_path = DEMO_DIR / "data" / "parameters" / "weights.json"
    backup = None
    if weights_path.exists():
        backup = weights_path.read_text()
        weights_path.unlink()

    try:
        weights = load_weights()
        assert "bull_analyst" in weights
        assert abs(sum(weights.values()) - 1.0) < 0.01
    finally:
        if backup:
            weights_path.parent.mkdir(parents=True, exist_ok=True)
            weights_path.write_text(backup)


def test_simulate_trade_is_deterministic():
    from run_daily import _simulate_trade
    r1 = _simulate_trade("AAPL", "2026-07-15", {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}, dry_run=True)
    r2 = _simulate_trade("AAPL", "2026-07-15", {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}, dry_run=True)
    assert r1["decision"]["action"] == r2["decision"]["action"]
    assert r1["decision"]["confidence"] == r2["decision"]["confidence"]


def test_simulate_trade_result_structure():
    from run_daily import _simulate_trade
    result = _simulate_trade("MSFT", "2026-07-20", {"bull_analyst": 0.4, "bear_analyst": 0.3, "news_analyst": 0.3}, dry_run=True)
    assert result["symbol"] == "MSFT"
    assert result["date"] == "2026-07-20"
    assert result["decision"]["action"] in ("BUY", "SELL", "HOLD")
    assert 0.0 <= result["decision"]["confidence"] <= 1.0


def test_save_result_creates_file(tmp_path):
    from run_daily import save_result
    import yaml

    config_path = DEMO_DIR / "config" / "demo_config.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)

    # Override results dir to tmp_path
    config["logging"]["results_dir"] = str(tmp_path)

    result = {
        "date": "2026-07-22",
        "symbol": "AAPL",
        "decision": {"action": "BUY", "confidence": 0.7, "pnl_pct": 0.01},
        "dry_run": True,
        "weights_used": {},
        "timestamp": "2026-07-22T09:31:00",
    }

    path = save_result(result, config)
    assert path.exists()
    loaded = json.loads(path.read_text())
    assert loaded["symbol"] == "AAPL"


def test_backtest_compute_metrics():
    from run_backtest import compute_metrics
    results = [
        {"date": "2026-07-21", "symbol": "AAPL",
         "decision": {"action": "BUY", "confidence": 0.8, "pnl_pct": 0.02}},
        {"date": "2026-07-22", "symbol": "AAPL",
         "decision": {"action": "SELL", "confidence": 0.6, "pnl_pct": -0.01}},
    ]
    df = compute_metrics(results)
    assert len(df) == 2
    assert "cumulative_pnl" in df.columns
    assert "portfolio_value" in df.columns
