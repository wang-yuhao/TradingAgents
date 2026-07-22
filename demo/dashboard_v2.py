"""
dashboard.py
────────────
Streamlit dashboard for TradingAgents demo.
Reads decision_log/ JSON files and renders:
  - Equity curve with benchmark
  - Daily decision log table
  - Win/loss statistics
  - Per-ticker performance breakdown
  - Self-improvement history timeline

Usage:
    streamlit run demo/dashboard.py
    streamlit run demo/dashboard.py --server.port 8502
"""

import sys
import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
load_dotenv(REPO_ROOT / ".env")

CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)

DECISION_LOG_DIR = REPO_ROOT / CFG["dashboard"]["decision_log_dir"]
MEMORY_FILE = REPO_ROOT / CFG["self_improve"]["memory_file"]
REFRESH_SECONDS = CFG["dashboard"]["refresh_seconds"]
DEFAULT_LOOKBACK = CFG["dashboard"]["default_lookback_days"]
BENCHMARK = CFG["benchmark"]

logging.basicConfig(level=logging.WARNING)

# ─────────────────────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TradingAgents Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Dark-themed CSS overrides
st.markdown(
    """
    <style>
    .metric-card {
        background: #1e2130;
        border-radius: 8px;
        padding: 16px 20px;
        margin: 4px 0;
    }
    .metric-positive { color: #00c07a; font-weight: 700; }
    .metric-negative { color: #ff4b6e; font-weight: 700; }
    .metric-neutral  { color: #adb5bd; font-weight: 700; }
    .stDataFrame { font-size: 13px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders (cached)
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=REFRESH_SECONDS)
def load_all_decisions(lookback_days: int = DEFAULT_LOOKBACK) -> pd.DataFrame:
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
            records.append(dec)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date", ascending=False).reset_index(drop=True)


@st.cache_data(ttl=REFRESH_SECONDS)
def load_latest_backtest() -> dict:
    candidates = sorted(DECISION_LOG_DIR.glob("backtest_*.json"), reverse=True)
    if not candidates:
        return {}
    with open(candidates[0]) as f:
        return json.load(f)


@st.cache_data(ttl=REFRESH_SECONDS)
def load_trading_memory() -> str:
    if MEMORY_FILE.exists():
        return MEMORY_FILE.read_text(encoding="utf-8")
    return "*No trading memory yet. Run the full pipeline to generate reflections.*"


# ─────────────────────────────────────────────────────────────────────────────
# Color helpers
# ─────────────────────────────────────────────────────────────────────────────

ACTION_COLORS = {
    "BUY": "#00c07a",
    "SELL": "#ff4b6e",
    "HOLD": "#adb5bd",
}

PLOTLY_THEME = dict(
    plot_bgcolor="#0e1117",
    paper_bgcolor="#0e1117",
    font=dict(color="#e0e0e0", family="Inter, sans-serif", size=12),
    xaxis=dict(gridcolor="#2a2d3e", showgrid=True),
    yaxis=dict(gridcolor="#2a2d3e", showgrid=True),
)


def color_action(action: str) -> str:
    return ACTION_COLORS.get(action.upper(), "#adb5bd")


# ─────────────────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    lookback = st.slider(
        "Lookback (days)", min_value=7, max_value=180, value=DEFAULT_LOOKBACK, step=7
    )
    selected_tickers = st.multiselect(
        "Filter tickers",
        options=CFG["tickers"],
        default=CFG["tickers"],
    )
    st.markdown("---")
    st.markdown("### ℹ️ About")
    st.markdown(
        "TradingAgents Demo Dashboard\n\n"
        "Auto-refreshes every **5 minutes**.\n\n"
        f"[View decision_log/]({DECISION_LOG_DIR})"
    )
    if st.button("🔄 Refresh Now"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown(f"*Last loaded: {datetime.now().strftime('%H:%M:%S')}*")


# ─────────────────────────────────────────────────────────────────────────────
# Main content
# ─────────────────────────────────────────────────────────────────────────────

st.title("📈 TradingAgents — Live Dashboard")
st.caption(f"Multi-agent LLM trading system · {date.today().strftime('%A, %B %d, %Y')}")

decisions = load_all_decisions(lookback_days=lookback)
backtest = load_latest_backtest()

# Filter by selected tickers
if not decisions.empty and selected_tickers:
    decisions = decisions[decisions["ticker"].isin(selected_tickers)]

# ── KPI Row ───────────────────────────────────────────────────────────────────
st.markdown("---")

if backtest and backtest.get("metrics"):
    m = backtest["metrics"]
    c1, c2, c3, c4, c5 = st.columns(5)

    def kpi(col, label, value, delta=None, fmt="{}"):
        col.metric(label=label, value=fmt.format(value), delta=delta)

    hit_rate = m.get("hit_rate", 0) * 100
    sharpe = m.get("sharpe_ratio", 0)
    alpha = m.get("alpha_vs_benchmark", 0) * 100
    total_pnl = m.get("total_pnl_pct", 0) * 100
    closed = m.get("closed_trades", 0)

    c1.metric("Hit Rate", f"{hit_rate:.1f}%", delta=f"{hit_rate - 50:.1f}% vs 50%")
    c2.metric("Sharpe Ratio", f"{sharpe:.3f}")
    c3.metric("Alpha vs SPY", f"{alpha:+.2f}%")
    c4.metric("Total PnL", f"{total_pnl:+.2f}%")
    c5.metric("Closed Trades", f"{closed}")
else:
    st.info(
        "No backtest results yet. Run `python demo/backtest.py` to generate metrics."
    )

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📊 Equity Curve", "📋 Decision Log", "🏆 Per-Ticker", "🤔 Win/Loss", "🧠 Memory"]
)


# ──────────────────────────────────────────────────────────
# TAB 1: Equity Curve
# ──────────────────────────────────────────────────────────
with tab1:
    st.subheader("Equity Curve")

    if backtest and backtest.get("equity_curve") and backtest.get("equity_curve_dates"):
        ec = backtest["equity_curve"]
        dates = backtest["equity_curve_dates"]

        if len(ec) == len(dates):
            df_ec = pd.DataFrame({"date": pd.to_datetime(dates), "equity": ec})

            # Try to overlay benchmark
            bench_data = None
            try:
                import yfinance as yf
                if dates:
                    start = pd.to_datetime(dates[0]) - timedelta(days=5)
                    end = pd.to_datetime(dates[-1]) + timedelta(days=5)
                    bench_raw = yf.download(
                        BENCHMARK,
                        start=start.strftime("%Y-%m-%d"),
                        end=end.strftime("%Y-%m-%d"),
                        auto_adjust=True,
                        progress=False,
                    )
                    if not bench_raw.empty:
                        bench_close = bench_raw["Close"]
                        bench_close = bench_close.reindex(
                            pd.to_datetime(dates), method="nearest"
                        )
                        bench_norm = 100 * bench_close / bench_close.iloc[0]
                        bench_data = bench_norm.values
            except Exception:
                pass

            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df_ec["date"],
                    y=df_ec["equity"],
                    mode="lines+markers",
                    name="Strategy",
                    line=dict(color="#00c07a", width=2),
                    marker=dict(size=4),
                )
            )
            if bench_data is not None:
                fig.add_trace(
                    go.Scatter(
                        x=df_ec["date"],
                        y=bench_data,
                        mode="lines",
                        name=f"{BENCHMARK} (benchmark)",
                        line=dict(color="#5b8dee", width=1.5, dash="dash"),
                    )
                )
            fig.add_hline(y=100, line_dash="dot", line_color="#555", annotation_text="Base")
            fig.update_layout(
                **PLOTLY_THEME,
                title="Portfolio Equity Curve (Base = 100)",
                xaxis_title="Date",
                yaxis_title="Portfolio Value",
                legend=dict(orientation="h", y=1.08),
                height=420,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("Equity curve length mismatch.")
    else:
        st.info("Run `python demo/backtest.py` to generate an equity curve.")


# ──────────────────────────────────────────────────────────
# TAB 2: Decision Log
# ──────────────────────────────────────────────────────────
with tab2:
    st.subheader("Daily Decision Log")

    if decisions.empty:
        st.info(
            "No decisions found. Run `python demo/run_analysis.py` to generate data.\n\n"
            "Or run `python demo/run_analysis.py --date 2026-07-22` to back-fill a date."
        )
    else:
        # Action filter
        action_filter = st.multiselect(
            "Filter actions",
            options=["BUY", "SELL", "HOLD"],
            default=["BUY", "SELL", "HOLD"],
            horizontal=True,
        )
        filtered = decisions[decisions["action"].isin(action_filter)] if action_filter else decisions

        # Display table
        display_cols = ["date", "ticker", "action", "confidence", "rationale_summary"]
        display_cols = [c for c in display_cols if c in filtered.columns]

        def style_action(val):
            colors = {"BUY": "#004d2a", "SELL": "#4d0011", "HOLD": "#2a2d3e"}
            return f"background-color: {colors.get(str(val).upper(), '#2a2d3e')}; color: white;"

        styled = (
            filtered[display_cols]
            .rename(columns={
                "date": "Date",
                "ticker": "Ticker",
                "action": "Action",
                "confidence": "Confidence",
                "rationale_summary": "Rationale",
            })
        )
        styled["Date"] = pd.to_datetime(styled["Date"]).dt.strftime("%Y-%m-%d")
        styled["Confidence"] = styled["Confidence"].apply(lambda x: f"{float(x):.0%}")

        st.dataframe(
            styled.style.applymap(style_action, subset=["Action"]),
            use_container_width=True,
            height=450,
        )

        # Action breakdown bar chart
        if not filtered.empty:
            action_counts = filtered["action"].value_counts().reset_index()
            action_counts.columns = ["action", "count"]
            fig_bar = px.bar(
                action_counts,
                x="action",
                y="count",
                color="action",
                color_discrete_map=ACTION_COLORS,
                title="Action Distribution",
            )
            fig_bar.update_layout(**PLOTLY_THEME, height=280)
            st.plotly_chart(fig_bar, use_container_width=True)


# ──────────────────────────────────────────────────────────
# TAB 3: Per-Ticker Performance
# ──────────────────────────────────────────────────────────
with tab3:
    st.subheader("Per-Ticker Performance Breakdown")

    if backtest and backtest.get("ticker_stats"):
        ts = backtest["ticker_stats"]
        rows = []
        for ticker, stats in ts.items():
            if ticker not in selected_tickers:
                continue
            rows.append({
                "Ticker": ticker,
                "Decisions": stats["decisions"],
                "Hit Rate": f"{stats['hit_rate']*100:.0f}%",
                "Avg Return": f"{stats['avg_return']*100:+.2f}%",
                "Total Return": f"{stats['total_return']*100:+.2f}%",
                "Sharpe": f"{stats['sharpe']:.3f}",
                "BUY": stats["buy_count"],
                "SELL": stats["sell_count"],
                "HOLD": stats["hold_count"],
            })

        if rows:
            df_ts = pd.DataFrame(rows).sort_values("Total Return", ascending=False)
            st.dataframe(df_ts, use_container_width=True, height=400)

            # Scatter: avg return vs hit rate
            scatter_data = []
            for ticker, stats in ts.items():
                if ticker not in selected_tickers:
                    continue
                scatter_data.append({
                    "ticker": ticker,
                    "hit_rate": stats["hit_rate"] * 100,
                    "avg_return": stats["avg_return"] * 100,
                    "decisions": stats["decisions"],
                })

            df_scatter = pd.DataFrame(scatter_data)
            if not df_scatter.empty:
                fig_s = px.scatter(
                    df_scatter,
                    x="hit_rate",
                    y="avg_return",
                    text="ticker",
                    size="decisions",
                    title="Hit Rate vs Avg Return (bubble = # decisions)",
                    labels={"hit_rate": "Hit Rate (%)", "avg_return": "Avg Return (%)"},
                    color="avg_return",
                    color_continuous_scale="RdYlGn",
                )
                fig_s.add_vline(x=50, line_dash="dash", line_color="#555")
                fig_s.add_hline(y=0, line_dash="dash", line_color="#555")
                fig_s.update_traces(textposition="top center")
                fig_s.update_layout(**PLOTLY_THEME, height=420)
                st.plotly_chart(fig_s, use_container_width=True)
    else:
        st.info("Run `python demo/backtest.py` to generate per-ticker stats.")


# ──────────────────────────────────────────────────────────
# TAB 4: Win/Loss Stats
# ──────────────────────────────────────────────────────────
with tab4:
    st.subheader("Win / Loss Analysis")

    if backtest and backtest.get("trades"):
        trades_df = pd.DataFrame(backtest["trades"])
        trades_df["date"] = pd.to_datetime(trades_df["date"])
        closed_df = trades_df[
            trades_df["is_closed"] & trades_df["trade_return"].notna()
        ].copy()

        if not closed_df.empty:
            col_a, col_b = st.columns(2)

            # Win/Loss Donut
            wins = int((closed_df["trade_return"] > 0).sum())
            losses = int((closed_df["trade_return"] <= 0).sum())
            fig_donut = go.Figure(
                go.Pie(
                    labels=["Wins", "Losses"],
                    values=[wins, losses],
                    hole=0.6,
                    marker=dict(colors=["#00c07a", "#ff4b6e"]),
                    textfont=dict(size=14),
                )
            )
            fig_donut.update_layout(
                **PLOTLY_THEME,
                title=f"Win/Loss Split ({wins}W / {losses}L)",
                height=300,
            )
            col_a.plotly_chart(fig_donut, use_container_width=True)

            # Return distribution histogram
            fig_hist = go.Figure(
                go.Histogram(
                    x=closed_df["trade_return"] * 100,
                    nbinsx=20,
                    marker=dict(
                        color=closed_df["trade_return"].apply(
                            lambda r: "#00c07a" if r > 0 else "#ff4b6e"
                        )
                    ),
                    name="Trade Returns",
                )
            )
            fig_hist.add_vline(
                x=float(closed_df["trade_return"].mean() * 100),
                line_dash="dash",
                line_color="#5b8dee",
                annotation_text=f"Mean: {closed_df['trade_return'].mean()*100:+.2f}%",
            )
            fig_hist.update_layout(
                **PLOTLY_THEME,
                title="Return Distribution (%)",
                xaxis_title="Return (%)",
                yaxis_title="Count",
                height=300,
            )
            col_b.plotly_chart(fig_hist, use_container_width=True)

            # Rolling hit rate over time
            closed_sorted = closed_df.sort_values("date")
            closed_sorted["rolling_hit"] = (
                (closed_sorted["trade_return"] > 0).rolling(window=5, min_periods=1).mean() * 100
            )
            fig_rolling = go.Figure(
                go.Scatter(
                    x=closed_sorted["date"],
                    y=closed_sorted["rolling_hit"],
                    mode="lines",
                    fill="tozeroy",
                    line=dict(color="#5b8dee", width=2),
                    fillcolor="rgba(91,141,238,0.15)",
                    name="5-trade rolling hit rate",
                )
            )
            fig_rolling.add_hline(y=50, line_dash="dot", line_color="#555")
            fig_rolling.update_layout(
                **PLOTLY_THEME,
                title="Rolling Hit Rate (5-trade window)",
                yaxis_title="Hit Rate (%)",
                height=280,
            )
            st.plotly_chart(fig_rolling, use_container_width=True)
        else:
            st.info("No closed trades yet. Prices may not have settled for holding period.")
    else:
        st.info("Run `python demo/backtest.py` to generate trade data.")


# ──────────────────────────────────────────────────────────
# TAB 5: Trading Memory / Self-Improvement Log
# ──────────────────────────────────────────────────────────
with tab5:
    st.subheader("🧠 Trading Memory — Self-Improvement Log")
    st.caption(
        "This file is auto-updated by `self_improve.py` after each backtest cycle "
        "and injected into the Portfolio Manager's context."
    )

    memory_content = load_trading_memory()

    st.markdown(
        f"**File path:** `{MEMORY_FILE}`  \n"
        f"**Last modified:** "
        + (
            datetime.fromtimestamp(MEMORY_FILE.stat().st_mtime).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            if MEMORY_FILE.exists()
            else "N/A"
        )
    )
    st.markdown("---")

    # Render as markdown
    st.markdown(memory_content)


# ─────────────────────────────────────────────────────────────────────────────
# Auto-refresh footer
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"Dashboard auto-refreshes every {REFRESH_SECONDS // 60} minutes · "
    f"Built with Streamlit + Plotly · "
    f"TradingAgents Demo"
)

# Streamlit auto-rerun
st_autorefresh_script = f"""
<script>
setTimeout(function() {{
    window.location.reload();
}}, {REFRESH_SECONDS * 1000});
</script>
"""
st.markdown(st_autorefresh_script, unsafe_allow_html=True)
