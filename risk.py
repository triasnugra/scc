"""Manajemen risiko & pengaman. Bagian ini TIDAK boleh dilewati oleh Claude atau strategi."""
from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from .state import State, utcnow
from .strategy import Setup


def position_size(equity: float, setup: Setup, rcfg: dict) -> tuple[float, float]:
    """Kembalikan (qty, leverage). Risiko tetap = risk_per_trade_pct dari ekuitas pada jarak SL."""
    risk_usd = equity * rcfg["risk_per_trade_pct"] / 100
    dist = abs(setup.entry - setup.sl)
    if dist <= 0:
        return 0.0, 0.0
    qty = risk_usd / dist
    notional = qty * setup.entry
    max_notional = equity * rcfg["max_leverage"]
    if notional > max_notional:
        qty = max_notional / setup.entry
        notional = max_notional
    return qty, max(1.0, notional / equity)


def gate(state: State, setup: Setup, equity: float, rcfg: dict) -> tuple[bool, str]:
    """Pemeriksaan kill-switch & batas harian. Return (boleh, alasan)."""
    if os.getenv("KILL_SWITCH") == "1" or Path(rcfg["kill_switch_file"]).exists():
        return False, "kill switch aktif"
    d = state.d
    if d["halted_reason"]:
        return False, f"halt: {d['halted_reason']}"
    start = d.get("day_start_equity") or equity
    if start > 0 and (start - equity) / start * 100 >= rcfg["daily_loss_limit_pct"]:
        d["halted_reason"] = "batas rugi harian tercapai"
        return False, d["halted_reason"]
    if d["consecutive_losses"] >= rcfg["max_consecutive_losses"]:
        return False, "terlalu banyak loss beruntun (reset manual/hari baru)"
    if len(d["open"]) >= rcfg["max_open_positions"]:
        return False, "posisi terbuka sudah maksimal"
    if any(o["symbol"] == setup.symbol for o in d["open"]):
        return False, "sudah ada posisi di simbol ini"
    now = utcnow()
    tt = list(d["trades_today"])  # epoch detik
    if len(tt) >= rcfg["max_trades_per_day"]:
        return False, "batas trade harian"
    if len([t for t in tt if now.timestamp() - t < 3600]) >= rcfg["max_trades_per_hour"]:
        return False, "batas trade per jam"
    if d["last_loss_ts"] and now - _parse(d["last_loss_ts"]) < timedelta(minutes=rcfg["cooldown_after_loss_min"]):
        return False, "cooldown setelah loss"
    return True, "ok"


def _parse(ts):
    from datetime import datetime, timezone
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts, timezone.utc)
    return datetime.fromisoformat(str(ts))


def register_close(state: State, r_multiple: float) -> None:
    d = state.d
    if r_multiple < -0.05:
        d["consecutive_losses"] += 1
        d["last_loss_ts"] = utcnow().isoformat()
    elif r_multiple > 0.05:
        d["consecutive_losses"] = 0
