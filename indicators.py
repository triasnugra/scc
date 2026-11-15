"""Indikator murni (pandas). Semua fungsi hanya memakai data candle yang sudah close."""
from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev = df["close"].shift()
    tr = pd.concat(
        [df["high"] - df["low"], (df["high"] - prev).abs(), (df["low"] - prev).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def obv(df: pd.DataFrame) -> pd.Series:
    sign = np.sign(df["close"].diff().fillna(0.0))
    return (sign * df["volume"]).cumsum()


def volume_ratio(df: pd.DataFrame, n: int = 20) -> float:
    base = df["volume"].iloc[-n - 1 : -1].mean()
    return float(df["volume"].iloc[-1] / base) if base and base > 0 else 0.0


def efficiency_ratio(s: pd.Series, n: int = 30) -> float:
    """Kaufman ER: 1 = trend lurus, ~0 = sideways/choppy."""
    if len(s) <= n:
        return 0.0
    path = s.diff().abs().iloc[-n:].sum()
    return float(abs(s.iloc[-1] - s.iloc[-1 - n]) / path) if path else 0.0


def htf_bias(df4h: pd.DataFrame, neutral_band: float = 0.003, er_min: float = 0.25) -> str:
    """'long' | 'short' | 'neutral'. EMA20/50 + posisi harga (materi: supremasi trend).
    Pasar sideways (ER rendah) = neutral, sehingga kedua ujung range boleh di-scalp."""
    c = df4h["close"]
    e20, e50, px = ema(c, 20).iloc[-1], ema(c, 50).iloc[-1], c.iloc[-1]
    if efficiency_ratio(c) < er_min or abs(e20 - e50) / px < neutral_band:
        return "neutral"
    if e20 > e50 and px > e50:
        return "long"
    if e20 < e50 and px < e50:
        return "short"
    return "neutral"


def resample_closed(df15: pd.DataFrame, rule: str) -> pd.DataFrame:
    """Resample 15m -> TF lebih besar, buang bucket terakhir bila belum lengkap."""
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
    out = df15.resample(rule, label="left", closed="left").agg(agg).dropna()
    step = pd.Timedelta(rule)
    last_end = df15.index[-1] + pd.Timedelta(minutes=15)
    return out[out.index + step <= last_end]
