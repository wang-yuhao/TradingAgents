"""
run_analysis_v2.py
-------------------
Calls TradingAgentsGraph.propagate() for each ticker in the watchlist,
parses the result, and saves a structured decision record to decision_log/.

Usage:
    python demo/run_analysis_v2.py
    python demo/run_analysis_v2.py --date 2026-07-15
    python demo/run_analysis_v2.py --tickers AAPL MSFT
"""

import os
import sys
import json
import argparse
import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

load_dotenv(REPO_ROOT / ".env")
CONFIG_PATH = Path(__file__).parent / "config_v2.yaml"

with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)

LOG_DIR = REPO_ROOT / CFG["logging"]["log_dir"]
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, CFG["logging"]["level"]),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            LOG_DIR / f"analysis_{date.today().isoformat()}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("run_analysis")

DECISION_LOG_DIR = REPO_ROOT / CFG["dashboard"]["decision_log_dir"]
DECISION_LOG_DIR.mkdir(parents=True, exist_ok=True)


def build_ta_config() -> dict:
    cfg = DEFAULT_CONFIG.copy()
    llm_cfg = CFG["llm"]
    cfg["llm_provider"] = llm_cfg["provider"]
    cfg["deep_think_llm"] = llm_cfg["model"]
    cfg["quick_think_llm"] = llm_cfg["model"]
    cfg["debate_rounds"] = CFG["trading_agents"]["debate_rounds"]
    cfg["max_risk_discuss_rounds"] = CFG["trading_agents"]["max_risk_discuss_rounds"]
    cfg["online_tools"] = CFG["trading_agents"]["online_tools"]

    provider = llm_cfg["provider"].lower()
    if provider == "openai":
        cfg["openai_api_key"] = os.getenv("OPENAI_API_KEY", "")
    elif provider == "anthropic":
        cfg["anthropic_api_key"] = os.getenv("ANTHROPIC_API_KEY", "")
    elif provider in ("google", "gemini"):
        cfg["google_api_key"] = os.getenv("GOOGLE_API_KEY", "")

    return cfg


def parse_decision(state: dict, ticker: str, analysis_date: str) -> dict:
    raw_decision = (
        state.get("final_trade_decision")
        or state.get("trade_decision")
        or ""
    )

    action = "HOLD"
    # FIX: was truncated as `raw_upper = str(raw_decisio` — corrected below
    raw_upper = str(raw_decision).upper()
    if "BUY" in raw_upper:
        action = "BUY"
    elif "SELL" in raw_upper:
        action = "SELL"

    confidence = _extract_confidence(str(raw_decision))
    rationale = _extract_rationale(str(raw_decision))

    return {
        "date": analysis_date,
        "ticker": ticker,
        "action": action,
        "confidence": confidence,
        "rationale_summary": rationale,
        "raw_decision": str(raw_decision)[:500],
    }


def _extract_confidence(text: str) -> float:
    """Extract a 0-1 confidence score from free-form LLM text."""
    patterns = [
        r"confidence[:\s]+([0-9]+\.?[0-9]*)\s*%",
        r"confidence[:\s]+([0-1]?\.[0-9]+)",
        r"([0-9]{2,3})%\s*confidence",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            return round(val / 100 if val > 1 else val, 4)
    return 0.6


def _extract_rationale(text: str, max_len: int = 200) -> str:
    """Return first max_len chars of the decision text as a summary."""
    cleaned = " ".join(text.split())
    return cleaned[:max_len] + ("..." if len(cleaned) > max_len else "")


@retry(
    stop=stop_after_attempt(CFG["llm"]["max_retries"]),
    wait=wait_exponential(
        multiplier=CFG["llm"]["retry_backoff_base"],
        min=4,
        max=60,
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def analyze_ticker(ta: TradingAgentsGraph, ticker: str, analysis_date: str) -> dict:
    logger.info(f"Analyzing {ticker} for {analysis_date}")
    state, _ = ta.propagate(ticker, analysis_date)
    decision = parse_decision(state, ticker, analysis_date)
    logger.info(
        f"{ticker}: {decision['action']} (confidence={decision['confidence']:.2f})"
    )
    return decision


def run(
    analysis_date: Optional[str] = None,
    tickers: Optional[list] = None,
) -> Path:
    if analysis_date is None:
        analysis_date = date.today().isoformat()

    if tickers is None:
        tickers = CFG["tickers"]

    logger.info("=== TradingAgents Analysis Run ===")
    logger.info(f"Date    : {analysis_date}")
    logger.info(f"Tickers : {', '.join(tickers)}")
    logger.info(f"Model   : {CFG['llm']['provider']}/{CFG['llm']['model']}")

    ta_config = build_ta_config()
    ta = TradingAgentsGraph(debug=False, config=ta_config)

    decisions = []
    failed = []

    for ticker in tickers:
        try:
            decision = analyze_ticker(ta, ticker, analysis_date)
            decisions.append(decision)
            time.sleep(2)
        except Exception as exc:
            logger.error(f"{ticker} FAILED after retries: {exc}")
            failed.append({"ticker": ticker, "error": str(exc)})

    out_path = DECISION_LOG_DIR / f"{analysis_date}.json"
    payload = {
        "run_date": analysis_date,
        "decisions": decisions,
        "failed": failed,
        "meta": {
            "model": CFG["llm"]["model"],
            "provider": CFG["llm"]["provider"],
            "tickers_requested": tickers,
            "tickers_succeeded": len(decisions),
            "tickers_failed": len(failed),
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    logger.info(f"Saved {len(decisions)} decisions -> {out_path}")
    if failed:
        logger.warning(f"{len(failed)} tickers failed: {[f['ticker'] for f in failed]}")

    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run TradingAgents daily analysis")
    parser.add_argument("--date", type=str, default=None, help="Date (YYYY-MM-DD)")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Override watchlist tickers",
    )
    args = parser.parse_args()
    run(analysis_date=args.date, tickers=args.tickers)
