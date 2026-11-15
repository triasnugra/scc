import numpy as np
import pandas as pd

from helpers import CFG, fib_up_path, ranging, with_sweep_long
from scalper import backtest, main as app
from scalper.indicators import resample_closed
from scalper.state import State
from scalper.strategy import fib_retest, find_setups


def test_fib_retest_long():
    df = fib_up_path()
    s = fib_retest("X", df, resample_closed(df, "1h"), CFG["strategy"])
    assert s and s[0].side == "long" and s[0].sl < s[0].entry < s[0].tp1 < s[0].tp2
    full = find_setups("X", df, resample_closed(df, "1h"), resample_closed(df, "4h"), CFG)
    assert full and full[0].kind == "fib_retest"


def test_backtest_runs_and_is_deterministic():
    rng = np.random.default_rng(7)
    base = ranging(n=2600, period=200)
    noise = rng.normal(0, 0.25, len(base))
    d = base.copy()
    for c in ("open", "high", "low", "close"):
        d[c] = d[c] + noise
    d["high"] = d[["open", "close", "high"]].max(axis=1) + 0.1
    d["low"] = d[["open", "close", "low"]].min(axis=1) - 0.1
    r1 = backtest.run(d, "X", CFG)
    r2 = backtest.run(d, "X", CFG)
    assert r1["trades"] == r2["trades"]


class FakeMarket:
    def __init__(self, df15):
        self.d15 = df15

    def closed(self, sym, tf, limit):
        return {"15m": self.d15, "1h": resample_closed(self.d15, "1h"), "4h": resample_closed(self.d15, "4h")}[tf].iloc[-limit:]

    def price(self, sym):
        return float(self.d15["close"].iloc[-1])

    def orderbook_stats(self, sym, price):
        return {"bid_ask_ratio": 1.4}

    def df(self, *a, **k):
        return pd.DataFrame()


def test_full_cycle_paper_opens_position_and_writes_dashboard(tmp_path, monkeypatch):
    import copy
    from scalper.exchange import PaperBroker
    cfg = copy.deepcopy(CFG)
    cfg.update(mode="paper", symbols=["ETH/USDT:USDT"])
    cfg["claude"]["enabled"] = False
    cfg["max_signal_age_min"] = 10**9  # data sintetis berumur lama
    cfg["risk"]["kill_switch_file"] = str(tmp_path / "KILL")
    monkeypatch.setenv("SITE_DIR", str(tmp_path / "site"))
    st = State(str(tmp_path / "state.json"))
    mk = FakeMarket(with_sweep_long(ranging()))
    br = PaperBroker(cfg, mk, st)
    app.run_cycle(cfg, st, mk, br)
    assert len(st.d["open"]) == 1 and st.d["open"][0]["side"] == "long"
    assert (tmp_path / "site" / "index.html").exists()
    n = len(st.d["open"])
    app.run_cycle(cfg, st, mk, br)  # candle sama -> tidak boleh dobel
    assert len(st.d["open"]) == n
    st2 = State(str(tmp_path / "state.json"))  # state tersimpan & terbaca ulang
    assert len(st2.d["open"]) == 1
