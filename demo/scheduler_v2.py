"""
scheduler_v2.py
---------------
APScheduler entry point that orchestrates the full daily pipeline:
  1. Check if today is a NYSE trading day (skip weekends/holidays)
  2. Run TradingAgents analysis for all tickers
  3. Run backtest against realized prices
  4. Generate self-improvement reflection

Usage:
    python demo/scheduler_v2.py              # Start scheduler (blocking)
    python demo/scheduler_v2.py --run-now    # Trigger immediately + keep running
    python demo/scheduler_v2.py --once       # Run once and exit (for cron)
"""

import sys
import signal
import logging
import argparse
from datetime import datetime, date
from pathlib import Path

import yaml
import pytz
from dotenv import load_dotenv
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
import pandas_market_calendars as mcal

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
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
            LOG_DIR / f"scheduler_{date.today().isoformat()}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger("scheduler")


def is_trading_day(check_date: date = None) -> bool:
    """Return True if check_date is a NYSE trading day."""
    if check_date is None:
        check_date = date.today()

    cal_name = CFG["schedule"].get("calendar", "NYSE")
    cal = mcal.get_calendar(cal_name)
    schedule = cal.schedule(
        start_date=check_date.isoformat(),
        end_date=check_date.isoformat(),
    )
    return not schedule.empty


def step_analysis() -> bool:
    from demo.run_analysis_v2 import run as run_analysis
    try:
        out = run_analysis()
        logger.info(f"Analysis complete -> {out}")
        return True
    except Exception as exc:
        logger.error(f"Analysis step FAILED: {exc}", exc_info=True)
        return False


def step_backtest() -> bool:
    from demo.backtest_v2 import run as run_backtest
    try:
        results = run_backtest()
        if results:
            m = results.get("metrics", {})
            logger.info(
                f"Backtest complete - "
                f"Sharpe={m.get('sharpe_ratio', 0):.3f}  "
                f"HitRate={m.get('hit_rate', 0)*100:.1f}%  "
                f"Alpha={m.get('alpha_vs_benchmark', 0):.4f}"
            )
        return True
    except Exception as exc:
        logger.error(f"Backtest step FAILED: {exc}", exc_info=True)
        return False


def step_self_improve() -> bool:
    from demo.self_improve_v2 import run as run_self_improve
    try:
        run_self_improve()
        return True
    except Exception as exc:
        logger.error(f"Self-improve step FAILED: {exc}", exc_info=True)
        return False


def daily_pipeline_job():
    """Full daily pipeline - skips non-trading days automatically."""
    today = date.today()
    logger.info("=" * 50)
    logger.info("  TradingAgents Daily Pipeline")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)

    if not is_trading_day(today):
        logger.info(f"  {today} is not a trading day - skipping.")
        return

    logger.info("  -- Step 1/3: Analysis --")
    analysis_ok = step_analysis()

    logger.info("  -- Step 2/3: Backtest --")
    backtest_ok = step_backtest()

    logger.info("  -- Step 3/3: Self-Improve --")
    improve_ok = step_self_improve()

    status = "SUCCESS" if (analysis_ok and backtest_ok and improve_ok) else "PARTIAL"
    logger.info(
        f"\n  Pipeline {status}  "
        f"(analysis={analysis_ok}, backtest={backtest_ok}, improve={improve_ok})\n"
    )


def on_job_executed(event):
    logger.info(f"Job '{event.job_id}' executed successfully.")


def on_job_error(event):
    logger.error(f"Job '{event.job_id}' raised an exception: {event.exception}")


def build_scheduler() -> BlockingScheduler:
    tz_str = CFG["schedule"]["timezone"]
    run_time = CFG["schedule"]["run_time"]
    hour, minute = map(int, run_time.split(":"))

    scheduler = BlockingScheduler(timezone=pytz.timezone(tz_str))
    scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
    scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)

    scheduler.add_job(
        daily_pipeline_job,
        trigger="cron",
        hour=hour,
        minute=minute,
        id="daily_pipeline",
        name="TradingAgents Daily Pipeline",
        max_instances=1,
        misfire_grace_time=3600,
        coalesce=True,
    )

    logger.info(
        f"Scheduler configured: daily at {run_time} {tz_str} "
        f"(NYSE trading days only)"
    )
    return scheduler


def handle_shutdown(signum, frame):
    logger.info("Received shutdown signal - stopping scheduler ...")
    sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TradingAgents Daily Scheduler")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Trigger the pipeline immediately, then keep scheduler running",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run pipeline once and exit (useful for cron/CI)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)

    if args.once:
        logger.info("Running pipeline once (--once mode) ...")
        daily_pipeline_job()
        sys.exit(0)

    if args.run_now:
        logger.info("--run-now: triggering pipeline immediately ...")
        daily_pipeline_job()

    scheduler = build_scheduler()
    logger.info("Scheduler started. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
