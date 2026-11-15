"""Backtest strategi (tanpa Claude) pada data 15m.

  python -m scalper.backtest --symbol BTC/USDT:USDT --days 90
  python -m scalper.backtest --csv data/btc15m.csv      # kolom: ts(ms atau ISO),open,high,low,close,volume
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import sim
from .indicators import resample_closed
from .risk import position_size
from .strategy import Setup, find_setups

WINDOW = 1100  # candle 15m (~11 hari) agar EMA50 4h matang


def load_csv(path: str) -> pd.DataFrame:
    d = pd.read_csv(path)
    ts = d.iloc[:, 0]
    d.index = pd.to_datetime(ts, unit="ms", utc=True) if np.issubdtype(ts.dtype, np.number) else pd.to_datetime(ts, utc=True)
    return d[["open", "high", "low", "close", "volume"]].astype(float)


def fetch_history(cfg: dict, symbol: str, days: int) -> pd.DataFrame:
    from .exchange import Market

    m = Market(cfg)
    since = int((time.time() - days * 86400) * 1000)
    parts = []
    while True:
        d = m.df(symbol, "15m", 1000, since=since)
        if d.empty:
            break
        parts.append(d)
        nxt = int(d.index[-1].timestamp() * 1000) + 1
        if nxt <= since or len(d) < 2:
            break
        since = nxt
        if d.index[-1] > pd.Timestamp.utcnow() - pd.Timedelta(minutes=30):
            break
    return pd.concat(parts)[~pd.concat(parts).index.duplicated()].iloc[:-1]


def run(df15: pd.DataFrame, symbol: str, cfg: dict, start_equity: float = 1000.0, btc15: pd.DataFrame | None = None) -> dict:
    p, rk = cfg["strategy"], cfg["risk"]
    fee, slip = p["fee_bps_roundtrip"] / 2 / 1e4, p["slippage_bps"] / 1e4
    eq, peak, maxdd = start_equity, start_equity, 0.0
    trades, pos, last_open, cons_loss, last_loss = [], None, None, 0, None
    per_day: dict[str, int] = {}
    day_start: dict[str, float] = {}

    for i in range(WINDOW, len(df15) - 1):
        nxt = df15.iloc[i + 1]
        ts_next = df15.index[i + 1]
        day = ts_next.strftime("%Y-%m-%d")
        day_start.setdefault(day, eq)

        if pos is not None:  # kelola posisi di candle i+1 (candle masuk juga dievaluasi)
            for kind, price, q in sim.advance(pos, nxt["high"], nxt["low"], p["tp1_fraction"], slip):
                pos["pnl"] += (pnl := sim.fill_pnl(pos, price, q, fee))
                eq += pnl
            if pos["qty_open"] <= 0:
                r = pos["pnl"] / pos["risk_usd"]
                trades.append({"symbol": symbol, "side": pos["side"], "kind": pos["kind"], "open": pos["t"],
                               "close": ts_next, "r": r, "pnl": pos["pnl"]})
                if r < -0.05:
                    cons_loss, last_loss = cons_loss + 1, ts_next
                elif r > 0.05:
                    cons_loss = 0
                pos = None
            peak = max(peak, eq)
            maxdd = max(maxdd, (peak - eq) / peak * 100)
            continue

        # gating harian (replika risk.gate)
        if per_day.get(day, 0) >= rk["max_trades_per_day"] or cons_loss >= rk["max_consecutive_losses"]:
            continue
        if (day_start[day] - eq) / day_start[day] * 100 >= rk["daily_loss_limit_pct"]:
            continue
        if last_open is not None and (ts_next - last_open).total_seconds() < 3600 / max(1, rk["max_trades_per_hour"]):
            continue
        if last_loss is not None and (ts_next - last_loss).total_seconds() < rk["cooldown_after_loss_min"] * 60:
            continue

        w = df15.iloc[i + 1 - WINDOW : i + 1]
        setups = find_setups(symbol, w, resample_closed(w, "1h"), resample_closed(w, "4h"), cfg, None,
                             resample_closed(btc15.loc[w.index[0] : w.index[-1]], "1h") if btc15 is not None else None)
        if not setups:
            continue
        s: Setup = setups[0]
        d = sim.direction(s.side)
        entry = float(nxt["open"]) * (1 + d * slip)
        if abs(entry - s.entry) / abs(s.entry - s.sl) > p["max_chase_r"] and (entry - s.entry) * d > 0:
            continue
        s.entry = entry
        if not p["min_stop_pct"] <= s.stop_pct <= p["max_stop_pct"]:
            continue
        qty, _ = position_size(eq, s, rk)
        if qty <= 0:
            continue
        pos = {"side": s.side, "kind": s.kind, "entry": entry, "sl": s.sl, "sl_init": s.sl, "tp1": s.tp1, "tp2": s.tp2,
               "qty": qty, "qty_open": qty, "tp1_hit": False, "pnl": 0.0, "risk_usd": abs(entry - s.sl) * qty, "t": ts_next}
        last_open = ts_next
        per_day[day] = per_day.get(day, 0) + 1
        # candle masuk dievaluasi pada iterasi berikutnya? tidak: evaluasi sekarang agar konservatif
        for kind, price, q in sim.advance(pos, nxt["high"], nxt["low"], p["tp1_fraction"], slip):
            pos["pnl"] += (pnl := sim.fill_pnl(pos, price, q, fee))
            eq += pnl
        if pos["qty_open"] <= 0:
            r = pos["pnl"] / pos["risk_usd"]
            trades.append({"symbol": symbol, "side": pos["side"], "kind": pos["kind"], "open": ts_next, "close": ts_next, "r": r, "pnl": pos["pnl"]})
            if r < -0.05:
                cons_loss, last_loss = cons_loss + 1, ts_next
            elif r > 0.05:
                cons_loss = 0
            pos = None

    t = pd.DataFrame(trades)
    if t.empty:
        return {"trades": 0, "note": "tidak ada trade", "df": t}
    gp, gl = t.loc[t.r > 0, "pnl"].sum(), -t.loc[t.r <= 0, "pnl"].sum()
    return {"trades": len(t), "win_rate_%": round((t.r > 0.05).mean() * 100, 1), "avg_R": round(t.r.mean(), 3),
            "profit_factor": round(gp / gl, 2) if gl > 0 else float("inf"), "return_%": round((eq / start_equity - 1) * 100, 2),
            "max_drawdown_%": round(maxdd, 2), "df": t}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--symbol")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--csv")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    syms = [a.symbol] if a.symbol else cfg["symbols"]
    out = Path("backtest_out")
    out.mkdir(exist_ok=True)
    for sym in syms:
        df = load_csv(a.csv) if a.csv else fetch_history(cfg, sym, a.days)
        res = run(df, sym, cfg)
        trades = res.pop("df")
        print(sym, res)
        if len(trades):
            trades.to_csv(out / f"{sym.replace('/', '_').replace(':', '_')}.csv", index=False)


if __name__ == "__main__":
    main()
