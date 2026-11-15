import numpy as np
import pandas as pd
import yaml
from pathlib import Path

CFG = yaml.safe_load(open(Path(__file__).resolve().parents[1] / "config.yaml", encoding="utf-8"))


def ranging(n=1200, lo=95.0, hi=105.0, period=160, end_phase="trough", vol=100.0):
    """Pasar sideways sinus 15m. Berakhir di titik terendah/tertinggi."""
    k = np.arange(n)
    mid, amp = (lo + hi) / 2, (hi - lo) / 2
    shift = (n - 1) % period
    phase = 2 * np.pi * (k - shift) / period
    close = mid + (amp * np.cos(phase) if end_phase == "peak" else -amp * np.cos(phase))
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.1,
                         "low": np.minimum(open_, close) - 0.1, "close": close, "volume": vol}, index=idx)


def with_sweep_long(df, lo=95.0):
    d = df.copy()
    i = d.index[-1]
    d.loc[i, ["open", "high", "low", "close", "volume"]] = [lo - 0.4, lo + 0.9, lo - 0.9, lo + 0.6, 320.0]
    return d


def mirror(df, axis=200.0):
    return pd.DataFrame({"open": axis - df["open"], "high": axis - df["low"], "low": axis - df["high"],
                         "close": axis - df["close"], "volume": df["volume"]}, index=df.index)


def fib_up_path(n_flat=1000, last_bull=True):
    """Datar di 100, impuls naik ke 130, retrace ke ~0.75 (107.5), candle reaksi bullish."""
    rng = np.random.default_rng(1)
    flat = 100 + rng.normal(0, 0.15, n_flat)
    up = np.linspace(100, 130, 80)
    down = np.linspace(130, 107.4, 60)
    close = np.r_[flat, up, down, [107.9]]
    idx = pd.date_range("2026-02-01", periods=len(close), freq="15min", tz="UTC")
    open_ = np.r_[close[0], close[:-1]]
    open_[-1] = 107.45
    df = pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + 0.15, "low": np.minimum(open_, close) - 0.15,
                       "close": close, "volume": 100.0}, index=idx)
    df.iloc[-1, df.columns.get_loc("volume")] = 250.0
    return df
