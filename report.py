"""Dashboard statis (GitHub Pages) dari state.json. Tanpa dependensi eksternal."""
from __future__ import annotations

import html
from pathlib import Path

CSS = """:root{--bg:#fff;--fg:#1a1a1a;--mut:#666;--card:#f5f5f4;--ok:#0f7b3f;--bad:#b42318;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#161616;--fg:#eee;--mut:#9a9a9a;--card:#222;--ok:#4ade80;--bad:#f87171}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0;padding:1rem;max-width:960px;margin-inline:auto}
h1{font-size:1.3rem}h2{font-size:1.05rem;margin-top:1.6rem}.k{display:flex;gap:.6rem;flex-wrap:wrap}
.c{background:var(--card);border-radius:8px;padding:.6rem .9rem}.c b{display:block;font-size:1.2rem}
.w{overflow-x:auto}table{border-collapse:collapse;width:100%}td,th{padding:.35rem .5rem;text-align:left;border-bottom:1px solid #8884;white-space:nowrap}
.ok{color:var(--ok)}.bad{color:var(--bad)}small{color:var(--mut)}"""


def _rows(items, cols):
    out = []
    for it in items:
        out.append("<tr>" + "".join(f"<td>{html.escape(str(it.get(c, '')))}</td>" for c in cols) + "</tr>")
    return "".join(out) or "<tr><td colspan=9><small>kosong</small></td></tr>"


def write_dashboard(d: dict, out_dir: str, mode: str) -> None:
    closed = d.get("closed", [])
    rs = [float(c.get("r", 0)) for c in closed]
    wins = sum(1 for r in rs if r > 0.05)
    eq, st = d.get("equity"), d.get("day_start_equity")
    pnl_day = f"{(eq - st) / st * 100:+.2f}%" if eq and st else "-"
    sig = [{"waktu": s.get("ts", ""), "simbol": s.get("symbol"), "arah": s.get("side"), "setup": s.get("kind"),
            "entry": s.get("entry"), "SL": s.get("sl"), "TP1": s.get("tp1"), "skor": s.get("score"),
            "claude": s.get("claude", {}).get("decision", "-"), "alasan": s.get("claude", {}).get("reason", s.get("note", ""))[:90]}
           for s in reversed(d.get("signals", [])[-25:])]
    opn = [{k: (round(v, 6) if isinstance(v, float) else v) for k, v in p.items()
            if k in ("symbol", "side", "entry", "sl", "tp1", "tp2", "leverage", "tp1_hit")} for p in d.get("open", [])]
    cls = [{"simbol": c["symbol"], "arah": c["side"], "R": c.get("r"), "pnl": round(c.get("pnl", 0), 2)} for c in reversed(closed[-25:])]
    page = f"""<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Eliz Scalper</title><style>{CSS}</style></head><body>
<h1>Eliz Scalper <small>mode: {html.escape(mode)}</small></h1>
<div class="k"><div class="c"><small>Ekuitas</small><b>{eq if eq is not None else '-'}</b></div>
<div class="c"><small>PnL hari ini</small><b>{pnl_day}</b></div>
<div class="c"><small>Trade ditutup</small><b>{len(rs)}</b></div>
<div class="c"><small>Win rate</small><b>{(wins / len(rs) * 100 if rs else 0):.0f}%</b></div>
<div class="c"><small>Total R</small><b class="{'ok' if sum(rs) >= 0 else 'bad'}">{sum(rs):+.2f}</b></div></div>
<small>Halt: {html.escape(d.get('halted_reason') or '-')}</small>
<h2>Posisi terbuka</h2><div class="w"><table><tr><th>simbol<th>arah<th>entry<th>SL<th>TP1<th>TP2<th>lev<th>TP1 hit</tr>{_rows(opn, ['symbol','side','entry','sl','tp1','tp2','leverage','tp1_hit'])}</table></div>
<h2>Sinyal terbaru</h2><div class="w"><table><tr><th>waktu<th>simbol<th>arah<th>setup<th>entry<th>SL<th>TP1<th>skor<th>claude<th>alasan</tr>{_rows(sig, ['waktu','simbol','arah','setup','entry','SL','TP1','skor','claude','alasan'])}</table></div>
<h2>Trade ditutup</h2><div class="w"><table><tr><th>simbol<th>arah<th>R<th>pnl</tr>{_rows(cls, ['simbol','arah','R','pnl'])}</table></div>
<p><small>Bukan nasihat keuangan. Hasil masa lalu tidak menjamin hasil di masa depan.</small></p></body></html>"""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir, "index.html").write_text(page, encoding="utf-8")
