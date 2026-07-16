#!/usr/bin/env python3
"""
Paper trading bot entrypoint.

Usage:
    python main.py run-once [--quiet]     one check-and-trade cycle (for cron)
    python main.py loop [--quiet]         long-running loop, sleeps between bars
    python main.py report [--plot[=PATH]] print performance stats

Never places real orders — this only simulates trades against a virtual
account and logs everything to SQLite.
"""
import argparse
import logging
import time

from dotenv import load_dotenv

load_dotenv()  # must run before bot.config reads env vars at import time

import pandas as pd

from bot import config, data_feed, engine, report, storage, strategy
from bot.logging_setup import setup_logging

logger = logging.getLogger(__name__)


def run_once():
    storage.init_db()
    bars = data_feed.fetch_intraday()

    since_str = storage.get_last_signal_timestamp()
    since = pd.Timestamp(since_str) if since_str else None
    signals = strategy.evaluate_new_bars(bars, since)

    if not signals:
        logger.info("No new closed bars since last check (%s); nothing to do.", since)
        return

    for signal in signals:
        bar = bars.loc[signal.timestamp]
        equity = engine.process_bar(signal.timestamp, bar, signal)
        logger.info(
            "Bar %s close=%.4f rsi=%.1f adx=%.1f signal=%s equity=$%.2f | %s",
            signal.timestamp, signal.close, signal.rsi, signal.adx, signal.signal, equity, signal.reason,
        )


def run_loop():
    storage.init_db()
    logger.info("Starting long-running loop, polling every %d seconds", config.POLL_INTERVAL_SECONDS)
    while True:
        try:
            run_once()
        except Exception:
            logger.exception("Error during check-and-trade cycle; will retry next interval")
        time.sleep(config.POLL_INTERVAL_SECONDS)


def main():
    parser = argparse.ArgumentParser(description="Paper trading bot")
    parser.add_argument("--quiet", action="store_true", help="Suppress routine INFO logs on the console")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("run-once", help="Run a single fetch-check-trade cycle (for cron)")
    sub.add_parser("loop", help="Run continuously, sleeping between bar intervals")

    report_parser = sub.add_parser("report", help="Print performance stats")
    report_parser.add_argument("--plot", metavar="PATH", nargs="?", const="equity_curve.png",
                                help="Also save an equity curve plot to PATH")

    args = parser.parse_args()
    setup_logging(quiet=args.quiet)

    if args.command == "run-once":
        run_once()
    elif args.command == "loop":
        run_loop()
    elif args.command == "report":
        storage.init_db()
        report.print_stats()
        if args.plot:
            report.plot_equity_curve(out_path=args.plot)


if __name__ == "__main__":
    main()
