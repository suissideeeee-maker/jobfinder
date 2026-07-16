"""
Strategy signal logic, ported from the validated Pine Script:

  - EMA(21) / EMA(55) crossover
  - RSI(14): long filter > 55, short filter < 45
  - ADX(14) > 20 trend-strength filter
  - Entry requires crossover + RSI + ADX to all align on the same bar

Thresholds live in bot/config.py and are not re-tuned here.
"""
from dataclasses import dataclass
from typing import Optional

import pandas as pd

from . import config, indicators


@dataclass
class SignalResult:
    timestamp: pd.Timestamp
    close: float
    ema_fast: float
    ema_slow: float
    rsi: float
    adx: float
    signal: Optional[str]   # "LONG", "SHORT", or None
    reason: str             # human-readable explanation, always populated


def compute_indicators(bars: pd.DataFrame) -> pd.DataFrame:
    """Attach EMA/RSI/ADX/crossover columns to an OHLCV DataFrame."""
    df = bars.copy()
    df["ema_fast"] = indicators.ema(df["close"], config.EMA_FAST_PERIOD)
    df["ema_slow"] = indicators.ema(df["close"], config.EMA_SLOW_PERIOD)
    df["rsi"] = indicators.rsi(df["close"], config.RSI_PERIOD)
    df["adx"] = indicators.adx(df["high"], df["low"], df["close"], config.ADX_PERIOD)
    df["cross_up"] = indicators.crossed_above(df["ema_fast"], df["ema_slow"])
    df["cross_down"] = indicators.crossed_below(df["ema_fast"], df["ema_slow"])
    return df


def _signal_from_row(df: pd.DataFrame, idx) -> SignalResult:
    row = df.loc[idx]

    signal = None
    reasons = []

    long_ok_rsi = row["rsi"] > config.RSI_LONG_MIN
    short_ok_rsi = row["rsi"] < config.RSI_SHORT_MAX
    adx_ok = row["adx"] > config.ADX_MIN

    if row["cross_up"] and long_ok_rsi and adx_ok:
        signal = "LONG"
        reasons.append("bullish EMA crossover + RSI>55 + ADX>20")
    elif row["cross_down"] and short_ok_rsi and adx_ok:
        signal = "SHORT"
        reasons.append("bearish EMA crossover + RSI<45 + ADX>20")
    else:
        if row["cross_up"]:
            reasons.append(f"bullish crossover but filtered out (RSI={row['rsi']:.1f}, ADX={row['adx']:.1f})")
        elif row["cross_down"]:
            reasons.append(f"bearish crossover but filtered out (RSI={row['rsi']:.1f}, ADX={row['adx']:.1f})")
        else:
            reasons.append("no crossover")

    return SignalResult(
        timestamp=idx,
        close=float(row["close"]),
        ema_fast=float(row["ema_fast"]),
        ema_slow=float(row["ema_slow"]),
        rsi=float(row["rsi"]),
        adx=float(row["adx"]),
        signal=signal,
        reason="; ".join(reasons),
    )


def _check_min_bars(bars: pd.DataFrame):
    min_bars = max(config.EMA_SLOW_PERIOD, config.RSI_PERIOD, config.ADX_PERIOD) + 2
    if len(bars) < min_bars:
        raise ValueError(f"Need at least {min_bars} bars to evaluate the strategy, got {len(bars)}")


def evaluate_latest_signal(bars: pd.DataFrame) -> SignalResult:
    """
    Evaluate the strategy on the most recently *closed* bar.

    `bars` must contain at least enough history to warm up EMA(55)/RSI(14)/
    ADX(14) — the caller is expected to have dropped any still-forming bar
    before calling this (Alpha Vantage intraday data only returns closed
    bars, so no extra trimming is needed there).
    """
    _check_min_bars(bars)
    df = compute_indicators(bars)
    return _signal_from_row(df, df.index[-1])


def evaluate_new_bars(bars: pd.DataFrame, since: pd.Timestamp = None):
    """
    Evaluate every bar strictly after `since` (chronological order), so a
    cron invocation that missed one or more intervals still checks each
    intermediate bar's stop/target instead of skipping straight to the
    latest close. If `since` is None, evaluates only the single most recent
    bar (used on first run, to start "live" rather than replay history).
    """
    _check_min_bars(bars)
    df = compute_indicators(bars)

    if since is None:
        indices = [df.index[-1]]
    else:
        indices = [idx for idx in df.index if idx > since]

    return [_signal_from_row(df, idx) for idx in indices]
