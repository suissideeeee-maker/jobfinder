"""
Central configuration for the paper trading bot.

Strategy thresholds are ported 1:1 from the validated Pine Script / TradingView
backtest. Do not re-tune these without an explicit request.
"""
import os

# --------------------------------------------------------------------------
# Data source
# --------------------------------------------------------------------------
# Yahoo Finance publishes real CME continuous futures data directly (no ETF
# proxy needed): "MES=F" for Micro E-mini S&P 500, "ES=F" for full-size
# E-mini S&P 500. Both trade on CME Globex. Continuous-contract data can show
# small gaps around quarterly contract rolls, but that's rare within the
# short lookback windows this bot uses.
PROXY_SYMBOL = os.environ.get("PROXY_SYMBOL", "MES=F")

# "yfinance" (default) needs no API key and has no practical daily request
# cap for this kind of polling. "alphavantage" is kept as an alternative for
# anyone with a paid Alpha Vantage plan — its free tier caps out around 25
# requests/day, which a 5-min polling loop burns through in under two hours.
DATA_PROVIDER = os.environ.get("DATA_PROVIDER", "yfinance")

ALPHAVANTAGE_API_KEY = os.environ.get("ALPHAVANTAGE_API_KEY", "")
ALPHAVANTAGE_BASE_URL = "https://www.alphavantage.co/query"

# Must match the timeframe the strategy was validated on: "5min" or "30min".
BAR_INTERVAL = os.environ.get("BAR_INTERVAL", "5min")
VALID_INTERVALS = {"1min", "5min", "15min", "30min", "60min"}

# yfinance interval names and how many days of history to request for each,
# generous enough to comfortably warm up EMA(55)/RSI(14)/ADX(14) regardless
# of weekends/holidays in the window. yfinance limits 1-minute bars to the
# trailing 7 days no matter what.
YFINANCE_INTERVAL_MAP = {"1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m", "60min": "60m"}
YFINANCE_LOOKBACK_DAYS = {"1min": 7, "5min": 10, "15min": 15, "30min": 20, "60min": 30}

# How often the long-running loop polls for a new bar. Defaults to the bar
# interval itself so it wakes up roughly once per new candle.
_interval_seconds = {"1min": 60, "5min": 300, "15min": 900, "30min": 1800, "60min": 3600}
POLL_INTERVAL_SECONDS = _interval_seconds.get(BAR_INTERVAL, 300)

# --------------------------------------------------------------------------
# Strategy parameters (ported from Pine Script — do not re-tune)
# --------------------------------------------------------------------------
EMA_FAST_PERIOD = 21
EMA_SLOW_PERIOD = 55

RSI_PERIOD = 14
RSI_LONG_MIN = 55     # long filter: RSI must be above this
RSI_SHORT_MAX = 45    # short filter: RSI must be below this

ADX_PERIOD = 14
ADX_MIN = 20          # trend-strength filter

# --------------------------------------------------------------------------
# Instrument / tick economics (MES by default; switch to ES if desired)
# --------------------------------------------------------------------------
# ES/MES tick size is 0.25 index points per tick.
INSTRUMENT_TICK_SIZE = 0.25
# Dollar value per full point per contract: MES = $5, ES = $50.
INSTRUMENT_POINT_VALUE = float(os.environ.get("INSTRUMENT_POINT_VALUE", "5.0"))
NUM_CONTRACTS = int(os.environ.get("NUM_CONTRACTS", "1"))

# Ratio of proxy-symbol points to instrument points. 1.0 because PROXY_SYMBOL
# is now a real CME futures ticker (points already match 1:1). Only change
# this if you fall back to an ETF proxy like SPY (~10 SPY points per ES/MES
# point) instead of a real futures ticker.
PROXY_TO_INSTRUMENT_RATIO = float(os.environ.get("PROXY_TO_INSTRUMENT_RATIO", "1.0"))

STOP_LOSS_TICKS = 80
TAKE_PROFIT_TICKS = 120

STOP_LOSS_INSTRUMENT_POINTS = STOP_LOSS_TICKS * INSTRUMENT_TICK_SIZE
TAKE_PROFIT_INSTRUMENT_POINTS = TAKE_PROFIT_TICKS * INSTRUMENT_TICK_SIZE

STOP_LOSS_PROXY_PRICE = STOP_LOSS_INSTRUMENT_POINTS / PROXY_TO_INSTRUMENT_RATIO
TAKE_PROFIT_PROXY_PRICE = TAKE_PROFIT_INSTRUMENT_POINTS / PROXY_TO_INSTRUMENT_RATIO

# --------------------------------------------------------------------------
# Simulated account
# --------------------------------------------------------------------------
STARTING_BALANCE = float(os.environ.get("STARTING_BALANCE", "50000"))

# --------------------------------------------------------------------------
# Persistence / logging
# --------------------------------------------------------------------------
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
DB_PATH = os.path.join(DATA_DIR, "paper_trading.db")
LOG_DIR = os.environ.get("LOG_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs"))
LOG_FILE = os.path.join(LOG_DIR, "bot.log")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
