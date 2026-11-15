"""Simulasi pergerakan posisi per candle (dipakai paper broker DAN backtest => perilaku identik).

Konservatif: dalam satu candle, SL diperiksa lebih dulu daripada TP.
Setelah TP1 kena: SL digeser ke break-even, sisa posisi diproses mulai candle berikutnya.
"""
from __future__ import annotations


def direction(side: str) -> int:
    return 1 if side == "long" else -1


def advance(pos: dict, hi: float, lo: float, tp1_frac: float, slip: float = 0.0) -> list[tuple[str, float, float]]:
    d = direction(pos["side"])
    fills: list[tuple[str, float, float]] = []
    if pos["qty_open"] <= 0:
        return fills
    sl_hit = lo <= pos["sl"] if d == 1 else hi >= pos["sl"]
    if sl_hit:
        kind = "be" if pos["tp1_hit"] else "sl"
        price = pos["sl"] * (1 - d * slip)  # slippage merugikan
        fills.append((kind, price, pos["qty_open"]))
        pos["qty_open"] = 0.0
        return fills
    if not pos["tp1_hit"]:
        if (d == 1 and hi >= pos["tp1"]) or (d == -1 and lo <= pos["tp1"]):
            q = pos["qty"] * tp1_frac
            fills.append(("tp1", pos["tp1"], q))
            pos["qty_open"] -= q
            pos["tp1_hit"] = True
            pos["sl"] = pos["entry"]
            if pos["qty_open"] <= 1e-12:
                pos["qty_open"] = 0.0
        return fills
    if (d == 1 and hi >= pos["tp2"]) or (d == -1 and lo <= pos["tp2"]):
        fills.append(("tp2", pos["tp2"], pos["qty_open"]))
        pos["qty_open"] = 0.0
    return fills


def fill_pnl(pos: dict, price: float, qty: float, fee_rate: float) -> float:
    """PnL realisasi untuk satu fill, sudah termasuk fee entry (proporsional) dan fee exit."""
    d = direction(pos["side"])
    gross = d * (price - pos["entry"]) * qty
    fees = fee_rate * (pos["entry"] * qty + price * qty)
    return gross - fees
