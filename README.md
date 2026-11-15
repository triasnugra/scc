# Eliz Scalper

Mesin analisis & eksekusi scalping crypto berbasis metode @eliz883 (aturan: `knowledge/eliz_scalping_rules.md`), dengan **Claude sebagai filter veto** sebelum order.

> Bukan nasihat keuangan. Trading futures ber-leverage bisa menghabiskan seluruh modal. Baca `docs/GO_LIVE_CHECKLIST.md` sebelum memakai uang sungguhan.

## Cara kerja
```
OHLCV 15m/1h/4h  ->  Setup A: sapuan range + reclaim (anti mid-range)
                 ->  Setup B: retest Fib 0.70-0.786 + candle reaksi
                 ->  filter bias 4h, BTC shock, R:R bersih (fee+slippage), skor (volume, OBV, order book)
                 ->  gerbang risiko (batas harian, loss beruntun, kill switch)
                 ->  Claude: TAKE / SKIP (hanya boleh veto)
                 ->  order: entry + SL + TP1 (50%) + TP2, SL -> break-even setelah TP1
```

## Mulai cepat (lokal)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest -q
cp .env.example .env            # isi ANTHROPIC_API_KEY (dan lainnya bila perlu)
export PYTHONPATH=src
python -m scalper.backtest --symbol BTC/USDT:USDT --days 90
python -m scalper.main --once --mode signal
```

## Deploy dengan GitHub Actions
1. Buat repo, upload semua file ini, push ke `main`.
2. **Settings > Pages > Source: GitHub Actions**.
3. **Settings > Secrets and variables > Actions**: tambah `ANTHROPIC_API_KEY` (opsional `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`).
4. Workflow:
   - `ci.yml` - tes otomatis tiap push.
   - `scan.yml` - tiap ~5 menit: scan sinyal (mode `signal`/`paper`), simpan state ke branch `data`, publish dashboard ke GitHub Pages. Jalankan manual lewat *Actions > Scan & Dashboard > Run workflow*.
   - `deploy.yml` - **live trading**: build Docker -> GHCR -> SSH ke VPS -> `docker compose up -d`. Tambah secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `VPS_DIR`, dan buat Environment `production` (beri required reviewer).
5. Setup VPS satu kali: salin `docker-compose.yml`, `config.yaml`, dan `.env` (berisi `BOT_IMAGE=ghcr.io/<user-huruf-kecil>/<repo>:latest`, API key bursa, `LIVE_CONFIRM`) ke `VPS_DIR`, lalu `docker login ghcr.io`.

Kenapa live tidak di Actions terjadwal: cron GitHub bisa tertunda 5-20+ menit, tidak cocok untuk scalping, dan menaruh key live di sana memperbesar risiko.

## Konfigurasi
Semua parameter ada di `config.yaml` (mode, exchange, simbol, parameter strategi, risiko, model Claude). Default sengaja konservatif: `mode: signal`, `testnet: true`.

## Struktur
```
src/scalper/  indicators, strategy, risk, claude_judge, exchange (paper+live), sim, backtest, main, report
knowledge/    aturan metode (dipakai juga sebagai system prompt Claude)
tests/        unit + siklus penuh dengan market palsu
PROMPT_BUILDER.md  prompt untuk meminta AI membangun ulang/mengembangkan mesin ini
```

## Kill switch
Buat file `state/KILL` (di VPS, atau commit ke branch `data` untuk Actions) atau set `KILL_SWITCH=1`. Bot berhenti membuka posisi baru; posisi yang ada tetap dilindungi SL di bursa.
