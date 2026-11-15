"""Strategi scalping berbasis materi @eliz883.

Semua input adalah candle yang SUDAH CLOSE (index = DatetimeIndex UTC).
Setup A  range_deviation : sapuan high/low range H1 lalu close kembali ke dalam range.
Setup B  fib_retest      : retest area Fibonacci 0.70-0.786 pada impuls, candle reaksi 15m.
Filter   : bias trend 4h, anti mid-range, BTC shock, R:R bersih setelah biaya.
Skor     : volume spike, OBV, order book (hanya konfirmasi, tidak pernah berdiri sendiri).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import pandas as pd

from .indicators import atr, htf_bias, obv, volume_ratio


@dataclass
class Setup:
    symbol: str
    side: str  # "long" | "short"
    kind: str  # "range_deviation" | "fib_retest"
    ts: str  # timestamp candle trigger (close time dari candle terakhir)
    entry: float
    sl: float
    tp1: float
    tp2: float
    level: float
    score: int = 50
    reasons: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    @property
    def stop_pct(self) -> float:
        return abs(self.entry - self.sl) / self.entry * 100

    def rr(self, tp: float) -> float:
        return abs(tp - self.entry) / abs(self.entry - self.sl)

    def key(self) -> str:
        return f"{self.symbol}|{self.kind}|{self.side}|{self.ts}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["stop_pct"] = round(self.stop_pct, 3)
        d["rr_tp1"] = round(self.rr(self.tp1), 2)
        d["rr_tp2"] = round(self.rr(self.tp2), 2)
        return d


# --------------------------------------------------------------------------- helpers
def _bullish(c: pd.Series) -> bool:
    return c["close"] > c["open"]


def _bearish(c: pd.Series) -> bool:
    return c["close"] < c["open"]


def _net_rr(s: Setup, p: dict) -> float:
    cost = (p["fee_bps_roundtrip"] + 2 * p["slippage_bps"]) / 100.0  # dalam %
    reward = abs(s.tp2 - s.entry) / s.entry * 100 - cost
    risk = s.stop_pct + cost
    return reward / risk if risk > 0 else 0.0


# --------------------------------------------------------------------------- setup A
def range_deviation(symbol: str, df15: pd.DataFrame, df1h: pd.DataFrame, p: dict) -> list[Setup]:
    n, skip = p["range_lookback_1h"], p["range_skip_1h"]
    if len(df1h) < n + skip or len(df15) < p["dev_window_15m"] + 20:
        return []
    rng = df1h.iloc[-(n + skip) : -skip]
    hi, lo = float(rng["high"].max()), float(rng["low"].min())
    width = hi - lo
    mid = (hi + lo) / 2
    width_pct = width / mid * 100
    if not (p["min_range_pct"] <= width_pct <= p["max_range_pct"]):
        return []

    recent = df15.iloc[-p["dev_window_15m"] :]
    last = df15.iloc[-1]
    a15 = float(atr(df15).iloc[-1])
    buf = p["sl_buffer_atr"] * a15
    out: list[Setup] = []

    # ---- LONG: sapu low range lalu reclaim
    swept = recent[recent["low"] < lo * (1 - p["dev_min_pct"] / 100)]
    if not swept.empty:
        sweep_ts = swept.index[-1]
        depth = (lo - float(swept["low"].min())) / lo * 100
        after = recent.loc[sweep_ts:]
        reclaim = after[after["close"] > lo]
        if (
            depth <= p["dev_max_pct"]
            and not reclaim.empty
            and reclaim.index[0] == last.name  # reclaim PERTAMA = candle yang baru close
            and _bullish(last)
            and last["close"] <= lo + p["extreme_zone"] * width
        ):
            entry = float(last["close"])
            sl = float(swept["low"].min()) - buf
            out.append(
                Setup(symbol, "long", "range_deviation", str(last.name), entry, sl, mid,
                      lo + 0.85 * width, lo,
                      reasons=[f"sapuan low range {lo:.6g} (depth {depth:.2f}%) lalu reclaim close",
                               f"range {width_pct:.1f}% | entry di zona bawah range (bukan mid-range)"])
            )

    # ---- SHORT: sapu high range lalu reclaim
    swept = recent[recent["high"] > hi * (1 + p["dev_min_pct"] / 100)]
    if not swept.empty:
        sweep_ts = swept.index[-1]
        depth = (float(swept["high"].max()) - hi) / hi * 100
        after = recent.loc[sweep_ts:]
        reclaim = after[after["close"] < hi]
        if (
            depth <= p["dev_max_pct"]
            and not reclaim.empty
            and reclaim.index[0] == last.name
            and _bearish(last)
            and last["close"] >= hi - p["extreme_zone"] * width
        ):
            entry = float(last["close"])
            sl = float(swept["high"].max()) + buf
            out.append(
                Setup(symbol, "short", "range_deviation", str(last.name), entry, sl, mid,
                      hi - 0.85 * width, hi,
                      reasons=[f"sapuan high range {hi:.6g} (depth {depth:.2f}%) lalu reclaim close",
                               f"range {width_pct:.1f}% | entry di zona atas range (bukan mid-range)"])
            )
    return out


# --------------------------------------------------------------------------- setup B
def fib_retest(symbol: str, df15: pd.DataFrame, df1h: pd.DataFrame, p: dict) -> list[Setup]:
    if not p.get("fib_enabled", True) or len(df1h) < p["fib_lookback_1h"] or len(df15) < 40:
        return []
    w = df1h.iloc[-p["fib_lookback_1h"] :]
    hi, lo = float(w["high"].max()), float(w["low"].min())
    size = hi - lo
    if size < p["fib_min_impulse_atr"] * float(atr(df1h).iloc[-1]):
        return []
    hi_pos, lo_pos = int(w["high"].values.argmax()), int(w["low"].values.argmin())
    up = lo_pos < hi_pos  # impuls naik lalu retrace turun
    z1, z2 = p["fib_zone"]  # 0.70 dan 0.786
    last = df15.iloc[-1]
    recent = df15.iloc[-3:]
    a15 = float(atr(df15).iloc[-1])
    buf = p["sl_buffer_atr"] * a15

    if up:
        at = lambda r: hi - r * size  # noqa: E731
        zone_hi, zone_lo = at(z1), at(z2)
        if (
            float(recent["low"].min()) <= zone_hi
            and last["close"] > zone_lo
            and _bullish(last)
            and last["close"] < at(0.55)
            and hi_pos < len(w) - 3
        ):
            return [Setup(symbol, "long", "fib_retest", str(last.name), float(last["close"]),
                          zone_lo - buf, at(0.5), at(0.25), at(0.75),
                          reasons=[f"retest area Fib 0.70-0.786 ({zone_lo:.6g}-{zone_hi:.6g}) pada impuls naik",
                                   "candle reaksi bullish 15m; SL tepat di bawah 0.786"])]
    else:
        at = lambda r: lo + r * size  # noqa: E731
        zone_lo, zone_hi = at(z1), at(z2)
        if (
            float(recent["high"].max()) >= zone_lo
            and last["close"] < zone_hi
            and _bearish(last)
            and last["close"] > at(0.55)
            and lo_pos < len(w) - 3
        ):
            return [Setup(symbol, "short", "fib_retest", str(last.name), float(last["close"]),
                          zone_hi + buf, at(0.5), at(0.25), at(0.75),
                          reasons=[f"retest area Fib 0.70-0.786 ({zone_lo:.6g}-{zone_hi:.6g}) pada impuls turun",
                                   "candle reaksi bearish 15m; SL tepat di atas 0.786"])]
    return []


# --------------------------------------------------------------------------- scoring + filter
def _score(s: Setup, df15: pd.DataFrame, bias: str, ob: dict | None, p: dict) -> Setup | None:
    want = "long" if s.side == "long" else "short"
    if bias not in ("neutral", want):
        return None  # melawan trend 4h -> tolak (supremasi trend)

    score = 50
    if bias == want:
        score += 10
        s.reasons.append("searah bias trend 4h (EMA20/50)")
    vr = volume_ratio(df15)
    if vr >= p["volume_spike"]:
        score += 15
        s.reasons.append(f"volume candle trigger {vr:.1f}x rata-rata")
    o = obv(df15)
    if (s.side == "long" and o.iloc[-1] > o.iloc[-5]) or (s.side == "short" and o.iloc[-1] < o.iloc[-5]):
        score += 10
        s.reasons.append("OBV mendukung arah")
    if ob:
        imb = ob.get("bid_ask_ratio", 1.0)
        ok = imb >= p["orderbook_imbalance"] if s.side == "long" else imb <= 1 / p["orderbook_imbalance"]
        if ok:
            score += 10
            s.reasons.append(f"order book mendukung (bid/ask={imb:.2f}) - hanya konfirmasi")
    s.score = score
    s.context = {"bias_4h": bias, "volume_ratio": round(vr, 2), "orderbook": ob or {}}
    return s


def find_setups(symbol: str, df15: pd.DataFrame, df1h: pd.DataFrame, df4h: pd.DataFrame,
                cfg: dict, ob: dict | None = None, btc_1h: pd.DataFrame | None = None) -> list[Setup]:
    """Kembalikan setup valid (sudah lolos filter aturan, belum lolos risk/Claude)."""
    p = cfg["strategy"]
    if min(len(df15), len(df1h), len(df4h)) < 60:
        return []
    bias = htf_bias(df4h, er_min=p.get("trend_er_min", 0.25))
    cands = range_deviation(symbol, df15, df1h, p) + fib_retest(symbol, df15, df1h, p)

    # konfluens: dua setup searah -> ambil yang R:R terbaik + bonus
    result: list[Setup] = []
    for s in cands:
        s = _score(s, df15, bias, ob, p)
        if s is None:
            continue
        if not (p["min_stop_pct"] <= s.stop_pct <= p["max_stop_pct"]):
            continue
        if (s.side == "long" and not s.tp1 > s.entry) or (s.side == "short" and not s.tp1 < s.entry):
            continue
        if _net_rr(s, p) < p["min_rr"]:
            continue
        # BTC shock untuk altcoin (materi: selalu lihat Bitcoin)
        if btc_1h is not None and not symbol.startswith("BTC") and len(btc_1h) > 4:
            chg = (btc_1h["close"].iloc[-1] / btc_1h["close"].iloc[-4] - 1) * 100
            if (s.side == "long" and chg < -p["btc_shock_pct"]) or (s.side == "short" and chg > p["btc_shock_pct"]):
                continue
            s.context["btc_3h_change_pct"] = round(float(chg), 2)
        result.append(s)

    sides = {}
    for s in result:
        sides.setdefault(s.side, []).append(s)
    final: list[Setup] = []
    for lst in sides.values():
        best = max(lst, key=lambda x: (x.score, x.rr(x.tp2)))
        if len(lst) > 1:
            best.score += 10
            best.reasons.append("konfluens dua setup searah")
        if best.score >= p["min_score"]:
            final.append(best)
    return final
