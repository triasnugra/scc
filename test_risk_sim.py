import os
from copy import deepcopy

from helpers import CFG
from scalper import sim
from scalper.claude_judge import judge, parse_decision
from scalper.risk import gate, position_size, register_close
from scalper.state import State
from scalper.strategy import Setup

R = CFG["risk"]


def mk(entry=100.0, sl=99.0, side="long"):
    return Setup("BTC/USDT:USDT", side, "range_deviation", "t", entry, sl, 101.0, 102.0, 99.5)


def test_position_size_risks_fixed_fraction():
    qty, lev = position_size(1000, mk(), R)
    assert abs(qty * 1.0 - 1000 * R["risk_per_trade_pct"] / 100) < 1e-9
    assert lev <= R["max_leverage"]


def test_leverage_cap_reduces_size():
    qty, lev = position_size(1000, mk(100, 99.95), R)  # stop super ketat
    assert abs(qty * 100 / 1000 - R["max_leverage"]) < 1e-9 and lev == R["max_leverage"]


def test_gate_kill_switch_and_daily_loss(tmp_path):
    cfg = deepcopy(R)
    cfg["kill_switch_file"] = str(tmp_path / "KILL")
    st = State(str(tmp_path / "s.json"))
    st.roll_day(1000)
    assert gate(st, mk(), 1000, cfg)[0]
    assert not gate(st, mk(), 970, cfg)[0]  # -3% > limit 2%
    st2 = State(str(tmp_path / "s2.json")); st2.roll_day(1000)
    (tmp_path / "KILL").write_text("x")
    assert gate(st2, mk(), 1000, cfg) == (False, "kill switch aktif")


def test_consecutive_losses_block(tmp_path):
    cfg = deepcopy(R); cfg["kill_switch_file"] = str(tmp_path / "KILL"); cfg["cooldown_after_loss_min"] = 0
    st = State(str(tmp_path / "s.json")); st.roll_day(1000)
    for _ in range(cfg["max_consecutive_losses"]):
        register_close(st, -1.0)
    assert not gate(st, mk(), 1000, cfg)[0]


def test_sim_long_tp1_then_breakeven():
    pos = {"side": "long", "entry": 100.0, "sl": 99.0, "tp1": 101.0, "tp2": 103.0, "qty": 1.0, "qty_open": 1.0, "tp1_hit": False}
    f = sim.advance(pos, 101.5, 99.5, 0.5)
    assert [k for k, *_ in f] == ["tp1"] and pos["sl"] == 100.0 and abs(pos["qty_open"] - 0.5) < 1e-9
    f = sim.advance(pos, 100.5, 99.9, 0.5)  # kembali menyentuh BE
    assert [k for k, *_ in f] == ["be"] and pos["qty_open"] == 0


def test_sim_sl_checked_before_tp_same_candle():
    pos = {"side": "short", "entry": 100.0, "sl": 101.0, "tp1": 99.0, "tp2": 97.0, "qty": 1.0, "qty_open": 1.0, "tp1_hit": False}
    f = sim.advance(pos, 101.2, 98.8, 0.5)  # candle menyentuh SL dan TP1
    assert [k for k, *_ in f] == ["sl"]


def test_fee_reduces_pnl():
    pos = {"side": "long", "entry": 100.0}
    assert sim.fill_pnl(pos, 101.0, 1.0, 0.0005) < 1.0


def test_parse_decision_and_fail_closed():
    assert parse_decision('x {"decision":"take","confidence":80,"reason":"ok"} y')["decision"] == "TAKE"
    os.environ.pop("ANTHROPIC_API_KEY", None)
    v = judge({"a": 1}, {"enabled": True, "model": "m", "min_confidence": 70})
    assert v["decision"] == "SKIP"  # tanpa API key -> fail-closed
