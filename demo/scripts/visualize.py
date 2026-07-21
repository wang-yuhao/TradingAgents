#!/usr/bin/env python3
"""
visualize.py — Generate an interactive HTML dashboard from performance data.

Usage:
  python visualize.py
  python visualize.py --open-browser
"""

import argparse
import json
import logging
import os
import sys
import webbrowser
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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


def load_metrics(config: dict) -> pd.DataFrame:
    metrics_path = DEMO_DIR / config["logging"]["performance_dir"] / "metrics.csv"
    if not metrics_path.exists():
        log.warning("No metrics.csv found. Run run_backtest.py first.")
        return pd.DataFrame()
    df = pd.read_csv(metrics_path)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_improvement_log(config: dict) -> pd.DataFrame:
    log_path = DEMO_DIR / config["logging"]["performance_dir"] / "improvement_log.csv"
    if not log_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(log_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def load_current_weights(config: dict) -> dict:
    weights_path = DEMO_DIR / "data" / "parameters" / "weights.json"
    if weights_path.exists():
        with open(weights_path) as f:
            return json.load(f)
    return {"bull_analyst": 0.33, "bear_analyst": 0.33, "news_analyst": 0.34}


def build_dashboard(df: pd.DataFrame, improvement_df: pd.DataFrame,
                    weights: dict, config: dict) -> str:
    """
    Build a multi-panel Plotly dashboard and return the full HTML string.
    """
    symbols = df["symbol"].unique().tolist() if not df.empty else []
    n_symbols = max(len(symbols), 1)

    # Build subplots: row 1 = PnL curves, row 2 = action distribution,
    # row 3 = confidence over time, row 4 = analyst weights evolution
    fig = make_subplots(
        rows=4, cols=n_symbols,
        subplot_titles=(
            [f"{s} — Cumulative PnL ($)" for s in symbols] +
            [f"{s} — Daily Actions" for s in symbols] +
            [f"{s} — Decision Confidence" for s in symbols] +
            ["Analyst Weights Over Time"] + [""] * (n_symbols - 1)
        ),
        vertical_spacing=0.08,
        horizontal_spacing=0.06,
    )

    color_map = {"BUY": "#26A69A", "SELL": "#EF5350", "HOLD": "#78909C"}

    for col_idx, symbol in enumerate(symbols, start=1):
        sym_df = df[df["symbol"] == symbol].sort_values("date")

        # ── Row 1: Cumulative PnL line chart ─────────────────────────────
        fig.add_trace(
            go.Scatter(
                x=sym_df["date"], y=sym_df["cumulative_pnl"],
                mode="lines+markers", name=f"{symbol} PnL",
                line=dict(color="#42A5F5", width=2),
                marker=dict(size=4),
                hovertemplate="%{x|%Y-%m-%d}<br>PnL: $%{y:,.0f}<extra></extra>",
            ),
            row=1, col=col_idx,
        )
        # Zero line
        fig.add_hline(y=0, line_dash="dot", line_color="gray", row=1, col=col_idx)

        # ── Row 2: Action distribution (stacked bar) ──────────────────────
        for action, color in color_map.items():
            action_df = sym_df[sym_df["action"] == action]
            fig.add_trace(
                go.Bar(
                    x=action_df["date"], y=action_df["daily_pnl"],
                    name=action, marker_color=color,
                    hovertemplate="%{x|%Y-%m-%d}<br>%{y:,.0f}<extra></extra>",
                    showlegend=(col_idx == 1),
                ),
                row=2, col=col_idx,
            )

        # ── Row 3: Confidence scatter ─────────────────────────────────────
        colors = sym_df["action"].map(color_map).fillna("#78909C")
        fig.add_trace(
            go.Scatter(
                x=sym_df["date"], y=sym_df["confidence"],
                mode="markers",
                marker=dict(color=colors, size=8, opacity=0.8),
                name=f"{symbol} Confidence",
                hovertemplate="%{x|%Y-%m-%d}<br>Confidence: %{y:.2f}<extra></extra>",
                showlegend=False,
            ),
            row=3, col=col_idx,
        )

    # ── Row 4: Analyst weights evolution ─────────────────────────────────
    if not improvement_df.empty:
        weight_cols = [c for c in improvement_df.columns if c.startswith("new_")]
        analyst_colors = ["#AB47BC", "#FF7043", "#66BB6A"]
        for i, col in enumerate(weight_cols):
            analyst_name = col.replace("new_", "").replace("_", " ").title()
            fig.add_trace(
                go.Scatter(
                    x=improvement_df["timestamp"], y=improvement_df[col],
                    mode="lines+markers", name=analyst_name,
                    line=dict(color=analyst_colors[i % len(analyst_colors)], width=2),
                    hovertemplate="%{x|%Y-%m-%d %H:%M}<br>Weight: %{y:.3f}<extra></extra>",
                ),
                row=4, col=1,
            )
    else:
        # Show current weights as pie chart
        fig.add_trace(
            go.Pie(
                labels=[k.replace("_", " ").title() for k in weights.keys()],
                values=list(weights.values()),
                hole=0.4,
                marker_colors=["#AB47BC", "#FF7043", "#66BB6A"],
                textinfo="label+percent",
            ),
            row=4, col=1,
        )

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        height=1200,
        template="plotly_dark",
        title=dict(
            text=f"TradingAgents Demo Dashboard — Updated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            font=dict(size=18),
        ),
        barmode="relative",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(t=100, b=40, l=60, r=40),
    )
    fig.update_yaxes(tickprefix="$", row=1)
    fig.update_yaxes(title_text="Weight", row=4)

    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def generate_dashboard(config: dict = None, open_browser: bool = False):
    if config is None:
        config = load_config()

    df = load_metrics(config)
    improvement_df = load_improvement_log(config)
    weights = load_current_weights(config)

    if df.empty:
        log.warning("No performance data to visualize. Run run_backtest.py first.")
        html = "<html><body><h2>No data yet. Run <code>python scripts/run_backtest.py</code> first.</h2></body></html>"
    else:
        html = build_dashboard(df, improvement_df, weights, config)

    dashboard_dir = DEMO_DIR / config["logging"]["dashboard_dir"]
    dashboard_dir.mkdir(parents=True, exist_ok=True)
    out_path = dashboard_dir / "index.html"
    out_path.write_text(html, encoding="utf-8")
    log.info("Dashboard saved → %s", out_path)

    if open_browser:
        webbrowser.open(f"file://{out_path.resolve()}")

    return out_path


def main():
    parser = argparse.ArgumentParser(description="TradingAgents Dashboard Generator")
    parser.add_argument("--open-browser", action="store_true", help="Open in default browser")
    args = parser.parse_args()
    config = load_config()
    generate_dashboard(config, open_browser=args.open_browser)


if __name__ == "__main__":
    main()
