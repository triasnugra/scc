"""Akses exchange via ccxt: Binance USDT-M, Bybit (swap), Hyperliquid.

- Market data SELALU dari mainnet publik (testnet datanya tipis & tidak representatif).
- Order memakai klien terpisah (testnet bila cfg.testnet = true).
PERINGATAN: parameter order (stop/TP reduceOnly) berbeda antar exchange. Wajib diuji di
testnet/dengan nominal kecil sebelum modal besar. Lihat docs/GO_LIVE_CHECKLIST.md.
"""
from __future__ import annotations

import math
import os
import time
import uuid

import pandas as pd

from . import sim
from .state import State, utcnow
from .strategy import Setup


def build_client(cfg: dict, with_keys: bool = False):
    import ccxt

    name = cfg["exchange"]
    cls = {"binance": ccxt.binanceusdm, "bybit": ccxt.bybit, "hyperliquid": ccxt.hyperliquid}[name]
    params: dict = {"enableRateLimit": True}
    if name == "bybit":
        params["options"] = {"defaultType": "swap"}
    if with_keys:
        if name == "hyperliquid":
            params["walletAddress"] = os.environ["HL_WALLET_ADDRESS"]
            params["privateKey"] = os.environ["HL_PRIVATE_KEY"]
        else:
            params["apiKey"] = os.environ["EXCHANGE_API_KEY"]
            params["secret"] = os.environ["EXCHANGE_API_SECRET"]
    ex = cls(params)
    if with_keys and cfg.get("testnet", True):
        ex.set_sandbox_mode(True)
    return ex


def quote_asset(cfg: dict) -> str:
    return "USDC" if cfg["exchange"] == "hyperliquid" else "USDT"


class Market:
    """Data publik (tanpa API key)."""

    def __init__(self, cfg: dict):
        self.ex = build_client(cfg, with_keys=False)

    def df(self, symbol: str, tf: str, limit: int = 300, since: int | None = None) -> pd.DataFrame:
        raw = self.ex.fetch_ohlcv(symbol, tf, since=since, limit=limit)
        d = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        d.index = pd.to_datetime(d.pop("ts"), unit="ms", utc=True)
        return d

    def closed(self, symbol: str, tf: str, limit: int) -> pd.DataFrame:
        return self.df(symbol, tf, limit).iloc[:-1]  # buang candle yang masih berjalan

    def price(self, symbol: str) -> float:
        return float(self.ex.fetch_ticker(symbol)["last"])

    def orderbook_stats(self, symbol: str, price: float, band: float = 0.005) -> dict | None:
        try:
            ob = self.ex.fetch_order_book(symbol, limit=50)
            bid = sum(p * q for p, q in ob["bids"] if p >= price * (1 - band))
            ask = sum(p * q for p, q in ob["asks"] if p <= price * (1 + band))
            return {"bid_ask_ratio": round(bid / ask, 3) if ask else 1.0}
        except Exception:
            return None


# ----------------------------------------------------------------------------- paper
class PaperBroker:
    """Simulasi dengan harga nyata. Ekuitas virtual disimpan di state."""

    mode = "paper"

    def __init__(self, cfg: dict, market: Market, state: State):
        self.cfg, self.market, self.state = cfg, market, state
        self.fee = cfg["strategy"]["fee_bps_roundtrip"] / 2 / 1e4
        self.slip = cfg["strategy"]["slippage_bps"] / 1e4
        state.d.setdefault("paper_balance", float(cfg.get("paper_equity", 1000)))

    def equity(self) -> float:
        return float(self.state.d["paper_balance"])

    def open(self, s: Setup, qty: float, lev: float) -> dict:
        d = sim.direction(s.side)
        entry = s.entry * (1 + d * self.slip)
        risk_usd = abs(entry - s.sl) * qty
        return {
            "id": uuid.uuid4().hex[:8], "symbol": s.symbol, "side": s.side, "kind": s.kind,
            "entry": entry, "sl": s.sl, "sl_init": s.sl, "tp1": s.tp1, "tp2": s.tp2,
            "qty": qty, "qty_open": qty, "tp1_hit": False, "leverage": round(lev, 2),
            "risk_usd": risk_usd, "pnl": 0.0, "opened_ts": time.time(), "mode": "paper",
        }

    def manage(self, state: State) -> list[dict]:
        events = []
        tp1_frac = self.cfg["strategy"]["tp1_fraction"]
        for pos in list(state.d["open"]):
            since = int(pos.get("last_ts", pos["opened_ts"]) * 1000)
            try:
                candles = self.market.df(pos["symbol"], "5m", 300, since=since)
            except Exception:
                continue
            for ts, c in candles.iterrows():
                if ts.timestamp() < pos.get("last_ts", pos["opened_ts"]):
                    continue
                for kind, price, q in sim.advance(pos, c["high"], c["low"], tp1_frac, self.slip):
                    pnl = sim.fill_pnl(pos, price, q, self.fee)
                    pos["pnl"] += pnl
                    state.d["paper_balance"] += pnl
                    events.append({"type": kind, "pos": pos, "pnl": pnl})
                pos["last_ts"] = ts.timestamp() + 300
                if pos["qty_open"] <= 0:
                    break
            if pos["qty_open"] <= 0:
                state.d["open"].remove(pos)
                state.d["closed"].append({**pos, "closed_ts": time.time(),
                                          "r": round(pos["pnl"] / pos["risk_usd"], 2) if pos["risk_usd"] else 0})
                events.append({"type": "closed", "pos": pos, "r": pos["pnl"] / pos["risk_usd"] if pos["risk_usd"] else 0})
        return events


# ----------------------------------------------------------------------------- live
class LiveBroker:
    """Order sungguhan. Entry market + SL reduce-only + TP1/TP2 reduce-only; SL -> BE setelah TP1."""

    mode = "live"

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.ex = build_client(cfg, with_keys=True)
        self.ex.load_markets()
        self.quote = quote_asset(cfg)

    # -- util
    def equity(self) -> float:
        bal = self.ex.fetch_balance()
        return float(bal[self.quote]["total"])

    def _amt(self, sym: str, qty: float) -> float:
        return float(self.ex.amount_to_precision(sym, qty))

    def _min_amt(self, sym: str) -> float:
        return float(self.ex.market(sym)["limits"]["amount"]["min"] or 0)

    def _size(self, sym: str) -> float:
        try:
            for p in self.ex.fetch_positions([sym]):
                if p.get("symbol") == sym:
                    return abs(float(p.get("contracts") or 0))
        except Exception:
            pass
        return 0.0

    # -- open
    def open(self, s: Setup, qty: float, lev: float) -> dict:
        ex, sym = self.ex, s.symbol
        long = s.side == "long"
        side, close = ("buy", "sell") if long else ("sell", "buy")
        for fn, args in ((ex.set_margin_mode, ("isolated", sym)), (ex.set_leverage, (int(math.ceil(lev)), sym))):
            try:
                fn(*args)
            except Exception:
                pass  # sudah di-set / tidak didukung -> lanjut, leverage dibatasi sizing
        qty = self._amt(sym, qty)
        mn = self._min_amt(sym)
        if qty < max(mn, 1e-12):
            raise RuntimeError(f"qty {qty} < minimum {mn}")
        o = ex.create_order(sym, "market", side, qty, s.entry)  # Hyperliquid butuh price
        entry = float(o.get("average") or o.get("price") or s.entry)
        try:
            sl = ex.create_order(sym, "market", close, qty, s.sl, {"stopLossPrice": s.sl, "reduceOnly": True})
        except Exception:
            ex.create_order(sym, "market", close, qty, entry, {"reduceOnly": True})  # darurat: tutup
            raise RuntimeError("SL gagal dipasang -> posisi ditutup darurat")
        frac = self.cfg["strategy"]["tp1_fraction"]
        q1, q2 = self._amt(sym, qty * frac), self._amt(sym, qty - self._amt(sym, qty * frac))
        ids = {"sl": sl["id"], "tp1": None, "tp2": None}
        if q1 < mn or q2 < mn:  # terlalu kecil untuk dibagi -> satu TP di tp1
            ids["tp1"] = ex.create_order(sym, "limit", close, qty, s.tp1, {"reduceOnly": True})["id"]
            frac = 1.0
        else:
            ids["tp1"] = ex.create_order(sym, "limit", close, q1, s.tp1, {"reduceOnly": True})["id"]
            ids["tp2"] = ex.create_order(sym, "limit", close, q2, s.tp2, {"reduceOnly": True})["id"]
        return {
            "id": o["id"], "symbol": sym, "side": s.side, "kind": s.kind, "entry": entry,
            "sl": s.sl, "sl_init": s.sl, "tp1": s.tp1, "tp2": s.tp2, "qty": qty, "qty_open": qty,
            "tp1_hit": False, "tp1_qty": q1 if frac < 1 else qty, "leverage": round(lev, 2),
            "risk_usd": abs(entry - s.sl) * qty, "pnl": 0.0, "opened_ts": time.time(),
            "ids": ids, "mode": "live",
        }

    # -- manage
    def manage(self, state: State) -> list[dict]:
        events = []
        ex = self.ex
        for pos in list(state.d["open"]):
            sym = pos["symbol"]
            try:
                size = self._size(sym)
                open_ids = {o["id"] for o in ex.fetch_open_orders(sym)}
            except Exception:
                continue
            ids = pos["ids"]
            if size <= self._min_amt(sym) * 0.5:  # posisi sudah tertutup
                try:
                    ex.cancel_all_orders(sym)
                except Exception:
                    pass
                r = self._estimate_r(pos)
                state.d["open"].remove(pos)
                state.d["closed"].append({**pos, "closed_ts": time.time(), "r": round(r, 2)})
                events.append({"type": "closed", "pos": pos, "r": r})
                continue
            tp1_done = ids.get("tp1") and ids["tp1"] not in open_ids and size < pos["qty"] * 0.999
            if tp1_done and not pos["tp1_hit"]:
                pos["tp1_hit"] = True
                try:
                    ex.cancel_order(ids["sl"], sym)
                except Exception:
                    pass
                close = "sell" if pos["side"] == "long" else "buy"
                new_sl = ex.create_order(sym, "market", close, self._amt(sym, size), pos["entry"],
                                         {"stopLossPrice": pos["entry"], "reduceOnly": True})
                ids["sl"], pos["sl"] = new_sl["id"], pos["entry"]
                events.append({"type": "tp1", "pos": pos, "pnl": 0.0})
        return events

    def _estimate_r(self, pos: dict) -> float:
        """Estimasi R dari order exit yang terisi (best-effort; ekuitas bursa tetap sumber kebenaran)."""
        d = sim.direction(pos["side"])
        pnl_r = 0.0
        dist = abs(pos["entry"] - pos["sl_init"]) * pos["qty"]
        try:
            for k in ("tp1", "tp2", "sl"):
                oid = pos["ids"].get(k)
                if not oid:
                    continue
                o = self.ex.fetch_order(oid, pos["symbol"])
                filled = float(o.get("filled") or 0)
                if filled > 0:
                    pnl_r += d * (float(o["average"]) - pos["entry"]) * filled
            return pnl_r / dist if dist else 0.0
        except Exception:
            return 0.0
