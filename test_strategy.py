from copy import deepcopy

from helpers import CFG, ranging, with_sweep_long, mirror
from scalper.indicators import resample_closed, htf_bias
from scalper.strategy import find_setups, range_deviation


def frames(df15):
    return df15, resample_closed(df15, "1h"), resample_closed(df15, "4h")


def test_resample_drops_incomplete_bucket():
    df = ranging(n=1202)  # berhenti di tengah jam
    h1 = resample_closed(df, "1h")
    assert h1.index[-1] + __import__("pandas").Timedelta("1h") <= df.index[-1] + __import__("pandas").Timedelta("15min")


def test_long_deviation_reclaim_detected():
    df = with_sweep_long(ranging())
    s = find_setups("ETH/USDT:USDT", *frames(df), CFG)
    assert s and s[0].side == "long" and s[0].kind == "range_deviation"
    assert s[0].sl < s[0].entry < s[0].tp1 < s[0].tp2
    assert s[0].score >= CFG["strategy"]["min_score"]


def test_short_deviation_reclaim_detected():
    df = mirror(with_sweep_long(ranging()))
    s = find_setups("ETH/USDT:USDT", *frames(df), CFG)
    assert s and s[0].side == "short" and s[0].sl > s[0].entry > s[0].tp1 > s[0].tp2


def test_mid_range_no_trade():
    df = ranging(end_phase="trough")
    # candle terakhir di tengah range, tanpa sapuan
    i = df.index[-1]
    df.loc[i, ["open", "high", "low", "close"]] = [99.9, 100.2, 99.7, 100.1]
    assert find_setups("ETH/USDT:USDT", *frames(df), CFG) == []


def test_no_signal_when_reclaim_not_fresh():
    df = with_sweep_long(ranging())
    # tambah satu candle lagi setelah reclaim -> reclaim pertama bukan candle terakhir
    nxt = df.iloc[[-1]].copy()
    nxt.index = nxt.index + __import__("pandas").Timedelta("15min")
    nxt[["open", "close", "low", "high"]] = [95.6, 95.9, 95.5, 96.0]
    import pandas as pd
    df2 = pd.concat([df, nxt])
    assert range_deviation("X", df2, resample_closed(df2, "1h"), CFG["strategy"]) == []


def test_breakdown_too_deep_is_not_deviation():
    df = ranging()
    i = df.index[-1]
    df.loc[i, ["open", "high", "low", "close", "volume"]] = [95.0, 95.5, 90.0, 95.4, 320.0]  # depth > 1.5%
    assert range_deviation("X", df, resample_closed(df, "1h"), CFG["strategy"]) == []


def test_counter_trend_rejected():
    import numpy as np, pandas as pd
    cfg = deepcopy(CFG)
    df = with_sweep_long(ranging())
    d15, d1h, d4h = frames(df)
    # paksa 4h downtrend kuat -> long ditolak
    n = len(d4h)
    d4h = d4h.copy()
    d4h["close"] = np.linspace(130, 70, n)
    assert htf_bias(d4h) == "short"
    assert find_setups("ETH/USDT:USDT", d15, d1h, d4h, cfg) == []


def test_btc_shock_blocks_altcoin_long():
    df = with_sweep_long(ranging())
    d15, d1h, d4h = frames(df)
    btc = d1h.copy()
    btc["close"] = [100.0] * (len(btc) - 4) + [100, 100, 99, 97]  # -3% dalam 3 jam
    assert find_setups("ETH/USDT:USDT", d15, d1h, d4h, CFG, None, btc) == []
    assert find_setups("BTC/USDT:USDT", d15, d1h, d4h, CFG, None, btc) != []
