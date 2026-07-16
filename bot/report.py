"""
Prints the same performance metrics tracked in the TradingView backtests:
win rate, profit factor, max drawdown, and total PnL. Can also plot the
saved equity curve to a PNG.
"""
import argparse

from tabulate import tabulate

from . import config, engine, storage


def compute_stats(db_path: str = None) -> dict:
    closed = storage.get_closed_trades(db_path)
    equity_curve = storage.get_equity_curve(db_path)

    total_trades = len(closed)
    wins = [t for t in closed if t["pnl"] > 0]
    losses = [t for t in closed if t["pnl"] <= 0]

    gross_profit = sum(t["pnl"] for t in wins)
    gross_loss = -sum(t["pnl"] for t in losses)  # positive number

    win_rate = (len(wins) / total_trades * 100) if total_trades else 0.0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float("inf") if gross_profit > 0 else 0.0
    total_pnl = sum(t["pnl"] for t in closed)

    equities = [row["equity"] for row in equity_curve] or [config.STARTING_BALANCE]
    peak = equities[0]
    max_drawdown = 0.0
    max_drawdown_pct = 0.0
    for e in equities:
        peak = max(peak, e)
        dd = peak - e
        dd_pct = (dd / peak * 100) if peak else 0.0
        max_drawdown = max(max_drawdown, dd)
        max_drawdown_pct = max(max_drawdown_pct, dd_pct)

    current_balance = engine.get_realized_balance(db_path)

    return {
        "total_trades": total_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": win_rate,
        "profit_factor": profit_factor,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_pnl": total_pnl,
        "max_drawdown": max_drawdown,
        "max_drawdown_pct": max_drawdown_pct,
        "starting_balance": config.STARTING_BALANCE,
        "current_balance": current_balance,
    }


def print_stats(db_path: str = None):
    stats = compute_stats(db_path)
    rows = [
        ("Starting balance", f"${stats['starting_balance']:,.2f}"),
        ("Current balance", f"${stats['current_balance']:,.2f}"),
        ("Total PnL", f"${stats['total_pnl']:,.2f}"),
        ("Total trades", stats["total_trades"]),
        ("Wins / Losses", f"{stats['wins']} / {stats['losses']}"),
        ("Win rate", f"{stats['win_rate_pct']:.1f}%"),
        ("Profit factor", f"{stats['profit_factor']:.2f}" if stats["profit_factor"] != float("inf") else "inf"),
        ("Max drawdown", f"${stats['max_drawdown']:,.2f} ({stats['max_drawdown_pct']:.1f}%)"),
    ]
    print(tabulate(rows, headers=["Metric", "Value"], tablefmt="simple"))


def plot_equity_curve(db_path: str = None, out_path: str = "equity_curve.png"):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd

    rows = storage.get_equity_curve(db_path)
    if not rows:
        print("No equity curve data yet.")
        return
    df = pd.DataFrame([dict(r) for r in rows])
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    plt.figure(figsize=(10, 5))
    plt.plot(df["timestamp"], df["equity"])
    plt.title("Paper Trading Equity Curve")
    plt.xlabel("Time")
    plt.ylabel("Equity ($)")
    plt.tight_layout()
    plt.savefig(out_path)
    print(f"Saved equity curve to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Print paper trading performance stats")
    parser.add_argument("--plot", metavar="PATH", nargs="?", const="equity_curve.png",
                         help="Also save an equity curve plot to PATH (default: equity_curve.png)")
    args = parser.parse_args()

    storage.init_db()
    print_stats()
    if args.plot:
        plot_equity_curve(out_path=args.plot)


if __name__ == "__main__":
    main()
