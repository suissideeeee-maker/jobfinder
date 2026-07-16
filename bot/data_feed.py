"""
Market data retrieval.

This runs as a standalone process (cron job or long-running loop), so it
talks to the data provider's REST API directly rather than through any
chat-session MCP connection.

Two providers are supported (bot.config.DATA_PROVIDER):
  - "yfinance" (default): no API key, no practical daily request cap.
  - "alphavantage": needs ALPHAVANTAGE_API_KEY; free tier caps out around
    25 requests/day, which a 5-min polling loop exhausts in under two hours.
"""
import logging
import time

import pandas as pd
import requests

from . import config

logger = logging.getLogger(__name__)


class DataFeedError(Exception):
    pass


def fetch_intraday(symbol: str = None, interval: str = None) -> pd.DataFrame:
    """
    Fetch intraday OHLCV bars for `symbol` at `interval` from whichever
    provider is configured (bot.config.DATA_PROVIDER).

    Returns a DataFrame sorted ascending by timestamp with columns:
    open, high, low, close, volume. The DataFrame index is a tz-naive
    pandas.Timestamp (exchange local time).
    """
    symbol = symbol or config.PROXY_SYMBOL
    interval = interval or config.BAR_INTERVAL
    if interval not in config.VALID_INTERVALS:
        raise ValueError(f"Unsupported interval: {interval}")

    if config.DATA_PROVIDER == "yfinance":
        return _fetch_intraday_yfinance(symbol, interval)
    elif config.DATA_PROVIDER == "alphavantage":
        return _fetch_intraday_alphavantage(symbol, interval)
    else:
        raise ValueError(f"Unsupported DATA_PROVIDER: {config.DATA_PROVIDER}")


def _fetch_intraday_yfinance(symbol: str, interval: str) -> pd.DataFrame:
    import yfinance as yf

    yf_interval = config.YFINANCE_INTERVAL_MAP[interval]
    lookback_days = config.YFINANCE_LOOKBACK_DAYS[interval]

    df = yf.download(
        symbol, period=f"{lookback_days}d", interval=yf_interval, progress=False, auto_adjust=False
    )
    if df.empty:
        raise DataFeedError(f"yfinance returned no data for {symbol} at {interval}")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df.astype(float).sort_index()


def _fetch_intraday_alphavantage(
    symbol: str,
    interval: str,
    outputsize: str = "compact",
    max_retries: int = 3,
) -> pd.DataFrame:
    if not config.ALPHAVANTAGE_API_KEY:
        raise DataFeedError("ALPHAVANTAGE_API_KEY is not set")

    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": config.ALPHAVANTAGE_API_KEY,
        "datatype": "json",
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(config.ALPHAVANTAGE_BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            payload = resp.json()
        except requests.RequestException as exc:
            last_error = exc
            logger.warning("Alpha Vantage request failed (attempt %d/%d): %s", attempt, max_retries, exc)
            time.sleep(2 ** attempt)
            continue

        if "Error Message" in payload:
            raise DataFeedError(f"Alpha Vantage error: {payload['Error Message']}")
        if "Note" in payload or "Information" in payload:
            # Rate limit / throttling notice. Back off and retry.
            msg = payload.get("Note") or payload.get("Information")
            logger.warning("Alpha Vantage throttled us (attempt %d/%d): %s", attempt, max_retries, msg)
            last_error = DataFeedError(msg)
            time.sleep(15 * attempt)
            continue

        series_key = f"Time Series ({interval})"
        if series_key not in payload:
            raise DataFeedError(f"Unexpected Alpha Vantage response, missing '{series_key}': {payload}")

        return _parse_time_series(payload[series_key])

    raise DataFeedError(f"Failed to fetch intraday data after {max_retries} attempts: {last_error}")


def _parse_time_series(raw: dict) -> pd.DataFrame:
    df = pd.DataFrame.from_dict(raw, orient="index")
    df = df.rename(
        columns={
            "1. open": "open",
            "2. high": "high",
            "3. low": "low",
            "4. close": "close",
            "5. volume": "volume",
        }
    )
    df.index = pd.to_datetime(df.index)
    df = df.astype(float)
    df = df.sort_index()
    return df
