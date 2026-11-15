"""Entry point.  python -m scalper.main --once | --loop  [--mode signal|paper|live]"""
from __future__ import annotations

import argparse
import os
import sys
import time
import traceback

import pandas as pd
import yaml

from . import claude_judge, notify, report, risk
from .exchange import LiveBroker, Market, PaperBroker
from .state import State, utcnow
from .strategy import find_setups

LIVE_PHRASE = "SAYA_PAHAM_RISIKONYA"


def load_cfg(path: str, mode: str | None) -> dict:
    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    if mode:
        cfg["mode"] = mode
    return cfg


def make_broker(cfg: dict, market: Market, state: State):
    mode = cfg["mode"]
    if mode == "live":
        if os.getenv("LIVE_CONFIRM") != LIVE_PHRASE:
            sys.exit(f"LIVE ditolak: set env LIVE_CONFIRM={LIVE_PHRASE} setelah membaca docs/GO_LIVE_CHECKLIST.md")
        if not cfg.get("testnet", True):
            notify.send("⚠️ MODE LIVE MAINNET aktif - uang sungguhan.")
        return LiveBroker(cfg)
    return PaperBroker(cfg, market, state)  # signal & paper memakai ekuitas virtual


def handle_events(events: list[dict], state: State) -> None:
    for ev in events:
        p = ev["pos"]
        if ev["type"] == "closed":
            risk.register_close(state, ev["r"])
            notify.send(f"✅ Ditutup {p['symbol']} {p['side']} | R={ev['r']:+.2f}")
        elif ev["type"] == "tp1":
            notify.send(f"🎯 TP1 {p['symbol']} → SL digeser ke break-even")


def scan_symbol(sym: str, cfg: dict, market: Market, broker, state: State, btc_1h: pd.DataFrame) -> None:
    tf = cfg["timeframes"]
    df15, df1h, df4h = (market.closed(sym, tf["trigger"], 300), market.closed(sym, tf["range"], 200),
                        market.closed(sym, tf["trend"], 120))
    age_min = (utcnow() - (df15.index[-1] + pd.Timedelta(minutes=15))).total_seconds() / 60
    if age_min > cfg.get("max_signal_age_min", 10):
        return  # candle terakhir sudah basi -> jangan buat sinyal
    price = float(df15["close"].iloc[-1])
    setups = find_setups(sym, df15, df1h, df4h, cfg, market.orderbook_stats(sym, price), btc_1h)
    for s in setups:
        if s.key() in state.d["seen"]:
            continue
        state.d["seen"].append(s.key())
        rec = s.to_dict()
        now_px = market.price(sym)
        dist = abs(s.entry - s.sl)
        moved = (now_px - s.entry) * (1 if s.side == "long" else -1) / dist
        if moved > cfg["strategy"]["max_chase_r"] or moved < -0.5:
            rec["note"] = f"dilewati: harga sudah bergerak {moved:.2f}R dari entry (no chasing)"
            state.d["signals"].append(rec)
            continue
        equity = broker.equity()
        ok, why = risk.gate(state, s, equity, cfg["risk"])
        if not ok:
            rec["note"] = f"ditolak risk: {why}"
            state.d["signals"].append(rec)
            continue
        verdict = claude_judge.judge(rec, cfg["claude"], {"equity": equity, "mode": cfg["mode"]})
        rec["claude"] = verdict
        state.d["signals"].append(rec)
        head = f"{'🟢' if s.side == 'long' else '🔴'} {s.symbol} {s.side.upper()} [{s.kind}] skor {s.score}\n" \
               f"entry {s.entry:.6g} | SL {s.sl:.6g} ({s.stop_pct:.2f}%) | TP1 {s.tp1:.6g} | TP2 {s.tp2:.6g}\n" \
               f"Claude: {verdict['decision']} ({verdict['confidence']}) {verdict['reason']}"
        if verdict["decision"] != "TAKE":
            notify.send("⏭️ SKIP\n" + head)
            continue
        qty, lev = risk.position_size(equity, s, cfg["risk"])
        if qty <= 0:
            continue
        if cfg["mode"] == "signal":
            notify.send("📣 SINYAL (mode signal, tanpa order)\n" + head + f"\nqty≈{qty:.6g} lev≈{lev:.1f}x")
            continue
        pos = broker.open(s, qty, lev)
        state.d["open"].append(pos)
        state.d["trades_today"].append(time.time())
        notify.send(f"🚀 ORDER {cfg['mode'].upper()}\n" + head + f"\nqty {qty:.6g} lev {lev:.1f}x")


def run_cycle(cfg: dict, state: State, market: Market, broker) -> None:
    state.roll_day(broker.equity())
    handle_events(broker.manage(state), state)
    state.roll_day(broker.equity())
    btc_1h = None
    try:
        btc_1h = market.closed(next((s for s in cfg["symbols"] if s.startswith("BTC")), cfg["symbols"][0]), "1h", 10)
    except Exception:
        pass
    for sym in cfg["symbols"]:
        try:
            scan_symbol(sym, cfg, market, broker, state, btc_1h)
        except Exception as e:
            print(f"[{sym}] error: {e}")
            traceback.print_exc()
    state.save()
    report.write_dashboard(state.d, os.getenv("SITE_DIR", "site"), cfg["mode"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--mode", choices=["signal", "paper", "live"])
    ap.add_argument("--state", default=os.getenv("STATE_PATH", "state/state.json"))
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--once", action="store_true")
    g.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    cfg = load_cfg(a.config, a.mode)
    state, market = State(a.state), Market(cfg)
    broker = make_broker(cfg, market, state)
    notify.send(f"Eliz Scalper start | mode={cfg['mode']} exchange={cfg['exchange']} testnet={cfg.get('testnet')}")
    if a.loop:
        while True:
            try:
                run_cycle(cfg, state, market, broker)
            except Exception as e:
                print("cycle error:", e)
                traceback.print_exc()
            time.sleep(cfg.get("loop_seconds", 60))
    else:
        run_cycle(cfg, state, market, broker)


if __name__ == "__main__":
    main()
