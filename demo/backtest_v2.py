"""
backtest_v2.py
--------------
Reads decision_log/ JSON files, fetches realized prices via yfinance,
and computes: PnL per trade, portfolio equity curve, Sharpe ratio,
hit rate, and alpha vs. SPY benchmark.

Usage:
    python demo/backtest_v2.py
    python demo/backtest_v2.py --lookback 30
    python demo/backtest_v2.py --output my_results.json
"""

import sys
import json
import logging
import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import yaml
import yfinance as yf
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

CONFIG_PATH = Path(__file__).parent / "config_v2.yaml"
with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)

logging.basicConfig(
    level=getattr(logging, CFG["logging"]["level"]),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("backtest")

DECISION_LOG_DIR = REPO_ROOT / CFG["dashboard"]["decision_log_dir"]
HOLDING_PERIOD = CFG["backtest"]["holding_period_days"]
MIN_CONFIDENCE = CFG["backtest"]["min_confidence_threshold"]
RISK_FREE_RATE = CFG["backtest"]["risk_free_rate"]
BENCHMARK = CFG["benchmark"]


def load_decisions(lookback_days: int = 90) -> pd.DataFrame:
    cutoff = date.today() - timedelta(days=lookback_days)
    records = []

    for fp in sorted(DECISION_LOG_DIR.glob("*.json")):
        if "backtest" in fp.name:
            continue
        try:
            file_date = date.fromisoformat(fp.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            continue

        with open(fp) as f:
            data = json.load(f)

        for dec in data.get("decisions", []):
            records.append({
                "date": dec["date"],
                "ticker": dec["ticker"],
                "action": dec["action"],
                "confidence": float(dec.get("confidence", 0.6)),
                "rationale_summary": dec.get("rationale_summary", ""),
            })

    if not records:
        logger.warning("No decision records found in decision_log/")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    logger.info(f"Loaded {len(df)} decision records")
    return df


def fetch_prices(tickers: list, start: date, end: date) -> pd.DataFrame:
    end_buffered = end + timedelta(days=HOLDING_PERIOD * 3)
    logger.info(f"Fetching prices for {tickers} ...")

    raw = yf.download(
        tickers,
        start=start.isoformat(),
        end=end_buffered.isoformat(),
        auto_adjust=True,
        progress=False,
    )

    if raw.empty:
        logger.error("yfinance returned no data.")
        return pd.DataFrame()

    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw["Close"]
    else:
        prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

    prices = prices.dropna(how="all")
    logger.info(f"Downloaded {len(prices)} price rows, {prices.shape[1]} tickers")
    return prices


def get_forward_return(
    prices: pd.DataFrame,
    ticker: str,
    decision_date: pd.Timestamp,
    holding_days: int,
) -> Optional[float]:
    if ticker not in prices.columns:
        return None

    col = prices[ticker].dropna()
    future = col[col.index > decision_date]

    if len(future) < holding_days:
        return None

    entry_price = future.iloc[0]
    exit_price = future.iloc[holding_days - 1]

    if entry_price == 0:
        return None

    return round((exit_price - entry_price) / entry_price, 6)


def direction_to_sign(action: str) -> int:
    return {"BUY": 1, "SELL": -1, "HOLD": 0}.get(action.upper(), 0)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float = RISK_FREE_RATE) -> float:
    if returns.empty or returns.std() == 0:
        return 0.0
    periods_per_year = 252 / HOLDING_PERIOD
    excess = returns - (risk_free_rate / periods_per_year)
    return round(float(excess.mean() / excess.std() * np.sqrt(periods_per_year)), 4)


def hit_rate(pnl_series: pd.Series) -> float:
    actionable = pnl_series.dropna()
    if actionable.empty:
        return 0.0
    return round(float((actionable > 0).mean()), 4)


def compute_alpha(strategy_returns: pd.Series, benchmark_returns: pd.Series) -> float:
    df = pd.DataFrame({"s": strategy_returns, "b": benchmark_returns}).dropna()
    if len(df) < 3:
        return 0.0
    beta = np.cov(df["s"], df["b"])[0, 1] / np.var(df["b"])
    periods_per_year = 252 / HOLDING_PERIOD
    alpha = (df["s"].mean() - beta * df["b"].mean()) * periods_per_year
    return round(float(alpha), 6)


def equity_curve(pnl_series: pd.Series, initial_capital: float = 100.0) -> pd.Series:
    returns = pnl_series.fillna(0)
    return (initial_capital * (1 + returns).cumprod()).round(4)


def run(lookback_days: int = None, output_path: Optional[str] = None) -> dict:
    if lookback_days is None:
        lookback_days = CFG["backtest"]["lookback_days"]

    decisions = load_decisions(lookback_days=lookback_days)
    if decisions.empty:
        logger.warning("No decisions to backtest.")
        return {}

    all_tickers = list(decisions["ticker"].unique())
    if BENCHMARK not in all_tickers:
        all_tickers.append(BENCHMARK)

    start_date = decisions["date"].min().date()
    end_date = decisions["date"].max().date()

    prices = fetch_prices(all_tickers, start_date, end_date)
    if prices.empty:
        return {}

    rows = []
    for _, row in decisions.iterrows():
        fwd = get_forward_return(prices, row["ticker"], row["date"], HOLDING_PERIOD)
        sign = direction_to_sign(row["action"])
        trade_return = round(sign * fwd, 6) if fwd is not None and sign != 0 else None
        bench_fwd = get_forward_return(prices, BENCHMARK, row["date"], HOLDING_PERIOD)

        rows.append({
            **row.to_dict(),
            "forward_return": fwd,
            "trade_return": trade_return,
            "benchmark_return": bench_fwd,
            "is_closed": fwd is not None,
            "is_win": trade_return is not None and trade_return > 0,
        })

    trades = pd.DataFrame(rows)
    closed = trades[trades["is_closed"] & (trades["trade_return"].notna())]

    strategy_returns = closed["trade_return"]
    benchmark_returns = closed["benchmark_return"].dropna()

    metrics = {
        "total_decisions": int(len(trades)),
        "closed_trades": int(len(closed)),
        "open_trades": int(len(trades) - len(closed)),
        "hit_rate": hit_rate(strategy_returns),
        "sharpe_ratio": sharpe_ratio(strategy_returns),
        "alpha_vs_benchmark": compute_alpha(strategy_returns, benchmark_returns),
        "total_pnl_pct": round(float(strategy_returns.sum()), 4),
        "avg_trade_return_pct": round(float(strategy_returns.mean()), 4) if not strategy_returns.empty else 0.0,
        "best_trade": {
            "return": float(closed["trade_return"].max()) if not closed.empty else None,
            "ticker": closed.loc[closed["trade_return"].idxmax(), "ticker"] if not closed.empty else None,
        },
        "worst_trade": {
            "return": float(closed["trade_return"].min()) if not closed.empty else None,
            "ticker": closed.loc[closed["trade_return"].idxmin(), "ticker"] if not closed.empty else None,
        },
    }

    ec = equity_curve(strategy_returns.reset_index(drop=True))

    ticker_stats = {}
    for ticker, grp in closed.groupby("ticker"):
        tr = grp["trade_return"]
        ticker_stats[ticker] = {
            "decisions": int(len(grp)),
            "hit_rate": hit_rate(tr),
            "avg_return": round(float(tr.mean()), 4),
            "total_return": round(float(tr.sum()), 4),
            "sharpe": sharpe_ratio(tr),
            "buy_count": int((grp["action"] == "BUY").sum()),
            "sell_count": int((grp["action"] == "SELL").sum()),
            "hold_count": int((grp["action"] == "HOLD").sum()),
        }

    output = {
        "run_date": date.today().isoformat(),
        "lookback_days": lookback_days,
        "holding_period_days": HOLDING_PERIOD,
        "benchmark": BENCHMARK,
        "metrics": metrics,
        "equity_curve": ec.tolist(),
        "equity_curve_dates": [
            str(closed.iloc[i]["date"].date()) for i in range(len(closed))
        ] if not closed.empty else [],
        "ticker_stats": ticker_stats,
        "trades": trades.to_dict(orient="records"),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }

    if output_path is None:
        DECISION_LOG_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DECISION_LOG_DIR / f"backtest_{date.today().isoformat()}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info(f"Backtest saved -> {output_path}")
    logger.info(
        f"Sharpe={metrics['sharpe_ratio']:.3f}  "
        f"Hit%={metrics['hit_rate']*100:.1f}%  "
        f"Alpha={metrics['alpha_vs_benchmark']:.4f}  "
        f"TotalPnL={metrics['total_pnl_pct']*100:.2f}%"
    )

    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backtest TradingAgents decisions")
    parser.add_argument("--lookback", type=int, default=None)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()
    run(lookback_days=args.lookback, output_path=args.output)
