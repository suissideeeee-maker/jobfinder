# Paper Trading Bot

A persistent, script-driven version of the manual TradingView backtest: pulls
market data, applies the validated EMA/RSI/ADX strategy, simulates trades
against a virtual account, and logs everything to SQLite. **It never places
real orders or touches a real brokerage — pure simulation.**

## Strategy (ported from Pine Script, not re-tuned)

- EMA(21) / EMA(55) crossover
- RSI(14): long filter > 55, short filter < 45
- ADX(14) > 20 trend-strength filter
- Entry: crossover + RSI + ADX all align on the same closed bar
- Exit: 80-tick stop-loss / 120-tick take-profit, converted to price terms
  for the instrument (see `bot/config.py`)

All thresholds live in `bot/config.py`. Don't change them without being asked.

## Data source

The bot trades real CME futures data directly via Yahoo Finance's continuous
contract tickers: `MES=F` (Micro E-mini S&P 500, $5/point) by default, or
`ES=F` (full-size E-mini S&P 500, $50/point). Both trade on CME Globex, so
tick size and point value in `bot/config.py` match the real contract exactly
— no ETF-proxy scaling needed. (Continuous-contract data can show small gaps
around quarterly contract rolls; rare within the lookback windows used here.)

If you ever fall back to an ETF proxy like `SPY` instead, set
`PROXY_TO_INSTRUMENT_RATIO` back to `~10.0` to convert its price scale into
ES/MES points.

Two data providers are supported via `DATA_PROVIDER`:

- **`yfinance`** (default) — no API key required, no practical daily request
  cap. This is what makes a 5-minute polling loop workable for free.
- **`alphavantage`** — needs `ALPHAVANTAGE_API_KEY`. Its free tier caps out
  around **25 requests/day**, which a 5-minute polling loop burns through in
  under two hours (`run-once` makes exactly one API call per invocation, so
  the limit comes from how often it's scheduled, not from the bot being
  inefficient). Only use this if you have a paid Alpha Vantage plan, or are
  running the bot infrequently (e.g. a few checks per day).

> Note: this bot runs as its own standalone process, so it calls the data
> provider's REST API directly. It does not use any MCP connection, since
> MCP tools only exist inside a chat session and aren't reachable from a
> script running on its own schedule.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

The default provider (`yfinance`) needs no further setup — you can run the
bot right away. If you want to use Alpha Vantage instead, edit `.env` and
set `DATA_PROVIDER=alphavantage` and `ALPHAVANTAGE_API_KEY=...`.

Key settings (env vars, all optional):

| Variable | Default | Meaning |
|---|---|---|
| `DATA_PROVIDER` | `yfinance` | `yfinance` or `alphavantage` |
| `ALPHAVANTAGE_API_KEY` | — | required only if `DATA_PROVIDER=alphavantage` |
| `PROXY_SYMBOL` | `MES=F` | ticker to poll (`MES=F`, `ES=F`, or an ETF proxy) |
| `BAR_INTERVAL` | `5min` | `1min/5min/15min/30min/60min`, must match your validated timeframe |
| `STARTING_BALANCE` | `50000` | virtual account starting balance |
| `NUM_CONTRACTS` | `1` | simulated contract size |
| `INSTRUMENT_POINT_VALUE` | `5.0` | $/point/contract (MES=5, ES=50) |
| `PROXY_TO_INSTRUMENT_RATIO` | `1.0` | proxy points per instrument point (1.0 for real futures tickers, ~10.0 for an ETF proxy like SPY) |
| `LOG_LEVEL` | `INFO` | console verbosity |

## Running it

```bash
# One check-and-trade cycle (for cron / Task Scheduler)
python main.py run-once

# Long-running process instead of cron
python main.py loop

# Suppress routine INFO logs, keep warnings/errors
python main.py run-once --quiet

# Print performance stats
python main.py report

# Stats + save an equity curve PNG
python main.py report --plot
```

`run-once` picks up wherever it left off: it remembers the last bar it
evaluated (in SQLite) and walks forward through any bars it missed, so a
cron job that's occasionally late or skips a run won't lose stop/target
checks on intermediate bars. On the very first run it starts "live" from
the most recent closed bar rather than replaying all of history.

## Scheduling

**Cron (Mac/Linux)** — run every 5 minutes to match a 5-min bar strategy:

```cron
*/5 * * * * cd /path/to/jobfinder && /path/to/venv/bin/python main.py run-once --quiet >> logs/cron.log 2>&1
```

For a 30-min strategy, use `*/30 * * * *` and set `BAR_INTERVAL=30min` in `.env`.

**Windows Task Scheduler** — create a Basic Task that runs on a repeating
5 (or 30) minute trigger, with:
- Program: `C:\path\to\venv\Scripts\python.exe`
- Arguments: `main.py run-once --quiet`
- Start in: `C:\path\to\jobfinder`

**Or run it as a standing process** instead of cron:

```bash
nohup python main.py loop > logs/loop.log 2>&1 &
```

## Persistence & logs

- `data/paper_trading.db` — SQLite: `trades`, `equity_curve`, `signal_log`
  (every signal check is recorded here, even non-trades, for debugging)
- `logs/bot.log` — full log history (always DEBUG level on disk, regardless
  of `--quiet`)

## Reporting

`python main.py report` prints starting/current balance, total PnL, trade
count, win rate, profit factor, and max drawdown — the same metrics tracked
in the TradingView backtests. `--plot` additionally saves the equity curve
to a PNG so you can eyeball it anytime.

## Assumptions worth knowing about

- Stop/target checks use each bar's high/low (not just its close). If a bar's
  range touches both the stop and the target, the stop is assumed to hit
  first (conservative).
- Only one position is open at a time.
- Both data providers' intraday endpoints only return fully closed bars, so
  no extra trimming of an in-progress candle is needed.
