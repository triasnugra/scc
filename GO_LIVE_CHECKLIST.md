# Checklist sebelum uang sungguhan

Urutan wajib. Jangan lompat tahap.

1. **Backtest** (`python -m scalper.backtest --days 90`) pada semua simbol. Perhatikan jumlah trade, profit factor setelah fee, max drawdown. Jika jumlah trade < 30 per simbol, hasilnya belum bermakna statistik.
2. **Mode signal** minimal 1-2 minggu (GitHub Actions). Bandingkan sinyal bot dengan chart secara manual: apakah masuk akal menurut metode @eliz883?
3. **Mode paper** minimal 2 minggu dengan harga nyata. Catat selisih dengan hasil backtest.
4. **Testnet** (`testnet: true`, `mode: live`, API key testnet). Verifikasi satu per satu di bursa:
   - entry terisi, leverage & isolated margin terpasang,
   - SL reduce-only terpasang SEBELUM Anda menutup layar,
   - TP1 & TP2 muncul sebagai order reduce-only,
   - setelah TP1 terisi, SL benar-benar pindah ke break-even,
   - kill switch (`state/KILL`) menghentikan entri baru.
   Parameter order stop/TP berbeda antar exchange (Binance / Bybit / Hyperliquid). Kode sudah memakai parameter unified ccxt, tetapi BELUM diuji terhadap bursa asli oleh pembuatnya. Anggap bagian ini belum terbukti sampai Anda lihat sendiri di testnet.
5. **Mainnet nominal kecil** (misal 50-100 USD, `risk_per_trade_pct: 0.25`) selama minimal 2 minggu. Naikkan bertahap hanya bila perilaku sesuai.

## Keamanan akun
- API key: izin **trade saja**, TANPA withdraw. Aktifkan **IP whitelist** ke IP VPS.
- Hyperliquid: pakai **API wallet (agent)**, bukan private key wallet utama.
- Jangan pernah memasukkan key bursa live ke GitHub Secrets untuk workflow terjadwal. Key live hanya di `.env` di VPS.
- Pakai akun/sub-akun khusus dengan modal yang siap hilang.
- Aktifkan 2FA, dan pasang notifikasi Telegram.

## Pengaman bawaan
| Pengaman | Default |
|---|---|
| Risiko per trade | 0.5% ekuitas |
| Leverage maksimum | 5x (isolated) |
| Batas rugi harian | 2% -> berhenti sampai 00:00 UTC |
| Maks trade / hari, / jam | 3 / 1 |
| Loss beruntun | 3 -> berhenti sampai hari baru |
| Konfirmasi live | env `LIVE_CONFIRM=SAYA_PAHAM_RISIKONYA` |
| Kill switch | buat file `state/KILL` atau env `KILL_SWITCH=1` |
| Claude gagal/timeout | SKIP (fail-closed) |
| SL gagal dipasang | posisi ditutup darurat |

## Keterbatasan yang harus Anda tahu
- Metode asli bersifat diskresioner (membaca chart, heatmap, order book). Kode ini menerjemahkannya ke aturan mekanis; itu **interpretasi**, bukan replika sempurna, dan tidak ada jaminan profit.
- Heatmap likuidasi (Coinglass dsb.) tidak tersedia gratis; bot hanya memakai ketidakseimbangan order book sebagai konfirmasi kecil.
- Backtest tidak mencakup order book, slippage saat volatilitas ekstrem, funding, dan latensi.
- Setup C (breakout+retest) dan D (pullback pasca-momentum) dari materi belum diimplementasikan.
- Jika bursa/koneksi mati saat posisi terbuka, SL yang sudah terpasang di bursa tetap melindungi; bot tidak.
