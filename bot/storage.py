"""
SQLite persistence for trades, the equity curve, and per-bar signal checks.
"""
import os
import sqlite3
from contextlib import contextmanager
from typing import Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    direction TEXT NOT NULL,
    entry_time TEXT NOT NULL,
    entry_price REAL NOT NULL,
    exit_time TEXT,
    exit_price REAL,
    size INTEGER NOT NULL,
    stop_price REAL NOT NULL,
    target_price REAL NOT NULL,
    exit_reason TEXT,
    pnl REAL,
    duration_seconds REAL,
    status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE IF NOT EXISTS equity_curve (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    equity REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS signal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    close REAL NOT NULL,
    ema_fast REAL,
    ema_slow REAL,
    rsi REAL,
    adx REAL,
    signal TEXT,
    reason TEXT
);
"""


def _ensure_dirs():
    os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)


@contextmanager
def get_connection(db_path: str = None):
    _ensure_dirs()
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db(db_path: str = None):
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)


def log_signal_check(result, db_path: str = None):
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO signal_log (timestamp, close, ema_fast, ema_slow, rsi, adx, signal, reason) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.timestamp.isoformat(),
                result.close,
                result.ema_fast,
                result.ema_slow,
                result.rsi,
                result.adx,
                result.signal,
                result.reason,
            ),
        )


def open_trade(direction, entry_time, entry_price, size, stop_price, target_price, db_path: str = None) -> int:
    with get_connection(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO trades (direction, entry_time, entry_price, size, stop_price, target_price, status) "
            "VALUES (?, ?, ?, ?, ?, ?, 'OPEN')",
            (direction, entry_time.isoformat(), entry_price, size, stop_price, target_price),
        )
        return cur.lastrowid


def close_trade(trade_id, exit_time, exit_price, exit_reason, pnl, duration_seconds, db_path: str = None):
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE trades SET exit_time=?, exit_price=?, exit_reason=?, pnl=?, duration_seconds=?, status='CLOSED' "
            "WHERE id=?",
            (exit_time.isoformat(), exit_price, exit_reason, pnl, duration_seconds, trade_id),
        )


def get_open_trade(db_path: str = None) -> Optional[sqlite3.Row]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY id DESC LIMIT 1")
        return cur.fetchone()


def record_equity(timestamp, equity, db_path: str = None):
    with get_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO equity_curve (timestamp, equity) VALUES (?, ?)",
            (timestamp.isoformat(), equity),
        )


def get_last_signal_timestamp(db_path: str = None):
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT timestamp FROM signal_log ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row["timestamp"] if row else None


def get_all_trades(db_path: str = None):
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM trades ORDER BY id")
        return cur.fetchall()


def get_closed_trades(db_path: str = None):
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM trades WHERE status='CLOSED' ORDER BY id")
        return cur.fetchall()


def get_equity_curve(db_path: str = None):
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT * FROM equity_curve ORDER BY id")
        return cur.fetchall()


def get_latest_equity(db_path: str = None) -> Optional[float]:
    with get_connection(db_path) as conn:
        cur = conn.execute("SELECT equity FROM equity_curve ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        return row["equity"] if row else None
