"""
Simulated (paper) execution engine.

State lives entirely in SQLite so the bot can be invoked repeatedly by cron
(or run as a long-lived loop) without losing track of an open position or
the running account balance. No real brokerage or money is ever touched.
"""
import logging

import pandas as pd

from . import config, storage

logger = logging.getLogger(__name__)


def _stop_target_prices(direction: str, entry_price: float):
    if direction == "LONG":
        stop = entry_price - config.STOP_LOSS_PROXY_PRICE
        target = entry_price + config.TAKE_PROFIT_PROXY_PRICE
    else:  # SHORT
        stop = entry_price + config.STOP_LOSS_PROXY_PRICE
        target = entry_price - config.TAKE_PROFIT_PROXY_PRICE
    return stop, target


def _compute_pnl(direction: str, entry_price: float, exit_price: float) -> float:
    price_move = (exit_price - entry_price) if direction == "LONG" else (entry_price - exit_price)
    instrument_points = price_move * config.PROXY_TO_INSTRUMENT_RATIO
    return instrument_points * config.INSTRUMENT_POINT_VALUE * config.NUM_CONTRACTS


def get_realized_balance(db_path: str = None) -> float:
    closed = storage.get_closed_trades(db_path)
    return config.STARTING_BALANCE + sum(t["pnl"] for t in closed)


def _unrealized_pnl(open_trade, mark_price: float) -> float:
    return _compute_pnl(open_trade["direction"], open_trade["entry_price"], mark_price)


def _check_exit(open_trade, bar: pd.Series, bar_time: pd.Timestamp, db_path: str = None):
    """Return (closed: bool, pnl or None) after checking this bar's high/low
    against the open trade's stop and target. If both are touched within the
    same bar, the stop is assumed to hit first (conservative assumption)."""
    direction = open_trade["direction"]
    stop_price = open_trade["stop_price"]
    target_price = open_trade["target_price"]

    stop_hit = bar["low"] <= stop_price if direction == "LONG" else bar["high"] >= stop_price
    target_hit = bar["high"] >= target_price if direction == "LONG" else bar["low"] <= target_price

    if not stop_hit and not target_hit:
        return False, None

    if stop_hit:
        exit_price, exit_reason = stop_price, "STOP_LOSS"
    else:
        exit_price, exit_reason = target_price, "TAKE_PROFIT"

    pnl = _compute_pnl(direction, open_trade["entry_price"], exit_price)
    entry_time = pd.Timestamp(open_trade["entry_time"])
    duration = (bar_time - entry_time).total_seconds()

    storage.close_trade(open_trade["id"], bar_time, exit_price, exit_reason, pnl, duration, db_path)
    logger.info(
        "Closed %s trade #%s: entry=%.4f exit=%.4f reason=%s pnl=%.2f",
        direction, open_trade["id"], open_trade["entry_price"], exit_price, exit_reason, pnl,
    )
    return True, pnl


def process_bar(bar_time: pd.Timestamp, bar: pd.Series, signal, db_path: str = None):
    """
    Advance the simulation by one closed bar.

    `signal` is a bot.strategy.SignalResult for this same bar. Always logs
    the signal check, checks/settles any open position against this bar's
    high/low, opens a new position if a signal fires and no position is
    open, and appends a mark-to-market equity point.
    """
    storage.log_signal_check(signal, db_path)

    open_trade = storage.get_open_trade(db_path)
    if open_trade is not None:
        _check_exit(open_trade, bar, bar_time, db_path)
        open_trade = storage.get_open_trade(db_path)  # re-check after possible close

    if open_trade is None and signal.signal in ("LONG", "SHORT"):
        entry_price = bar["close"]
        stop_price, target_price = _stop_target_prices(signal.signal, entry_price)
        trade_id = storage.open_trade(
            signal.signal, bar_time, entry_price, config.NUM_CONTRACTS, stop_price, target_price, db_path
        )
        logger.info(
            "Opened %s trade #%s at %.4f (stop=%.4f target=%.4f)",
            signal.signal, trade_id, entry_price, stop_price, target_price,
        )
        open_trade = storage.get_open_trade(db_path)

    realized = get_realized_balance(db_path)
    equity = realized if open_trade is None else realized + _unrealized_pnl(open_trade, bar["close"])
    storage.record_equity(bar_time, equity, db_path)

    return equity
