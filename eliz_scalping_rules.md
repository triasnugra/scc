# Aturan Scalping @eliz883 (hasil sintesis dua sumber)

Sumber:
- [X]  = postingan X/Twitter @eliz883 (file "no tanggal postingan")
- [YT] = skrip YouTube ElizCrypto, HANYA bagian scalping / low-timeframe / entry-stop-TP

Materi non-scalping dari YouTube (spot jangka panjang, makro, rotasi dominance, dll.) sengaja TIDAK dipakai.

## 1. Filosofi
- Jangan memprediksi. Bereaksi pada trigger/level yang sudah ditandai sebelumnya. [X][YT]
- Kualitas di atas kuantitas: sekitar 3-4 trade dalam 3-4 hari; maksimal 1-2 per jam. [YT]
- Lebih baik menepi daripada memaksa trade; hari tanpa kerugian sudah sebuah keberhasilan. [X]
- Jangan mengejar harga (no chasing) dan jangan mengantisipasi breakout/breakdown (hampir selalu kena SL). [X][YT]
- Entry harus di titik presisi, karena di situlah R:R terbaik. Scalping pun begitu. [X]
- Drawdown rendah lebih penting daripada profit besar. [X]

## 2. Konteks / bias (filter arah)
- Supremasi trend: ikuti trend besar. Uptrend -> scalp LONG saat pullback kecil. Downtrend -> scalp SHORT saat retracement naik. [YT]
- "Long season -> scalp long; short season -> scalp short." [X]
- Box/zona kunci: di atas box = bias long scalp, di bawah box (close + konfirmasi) = bias short. [X]
- EMA20/EMA50 hanya konfirmasi trend (price action dulu, indikator belakangan). OBV dipantau: tidak boleh ada volume jual besar melawan posisi. [YT]
- Saat trading altcoin selalu lihat Bitcoin dulu. [YT]
- Saat BTC sideways, altcoin lebih menarik untuk scalp, tetapi pilih hanya setup berkualitas tinggi. [X]

## 3. Di mana boleh entry
- Hanya di range high atau range low. JANGAN PERNAH di mid-range (tidak ada edge). [X][YT]
- Kerja di timeframe rendah, terutama H1: fokus pada deviasi (spike keluar lalu kembali) di high/low range. [X]
- Level mingguan seperti Monday low/high dan sapuan likuiditas di bawah/atas level itu adalah zona scalp. [X]
- Level ditandai lebih dulu sebagai trigger, lalu tunggu konfirmasi. [X][YT]

## 4. Trigger entry
A. Deviasi / stop run + reclaim: harga menyapu low (atau high) range lalu candle close kembali ke dalam range. Double deviation (bearish lalu dipulihkan) = kekuatan beli besar. Stop di bawah low sapuan. [X][YT]
B. Fibonacci retracement pada impuls: area 0.75 (dan 0.786) adalah area retest favorit; level penting 0.75 / 0.5 / 0.25. Setelah menyentuh area, tunggu candle reaksi di 15m. Stop tepat di bawah 0.786 (long) atau di atasnya (short). TP bertahap di 0.5 dan 0.25. [YT]
C. Breakout dengan volume lalu retest, stop di bawah spike/zona. [YT][X]  (belum diimplementasikan di bot v1)
D. Setelah rally momentum yang menyerap likuiditas di atas range, pullback ke zona tertentu -> long scalp dengan konfirmasi trend. [X]  (belum diimplementasikan di bot v1)

## 5. Konfirmasi tambahan
- Order book / heatmap / liquidity map HANYA konfirmasi, tidak pernah berdiri sendiri. Blok order dekat level penting (0.75, level daily/3 hari) menambah keyakinan. Tanpa price action = ikut kerumunan. [X][YT]
- Lonjakan volume pada candle trigger menambah kualitas. [YT]
- Heatmap paling berguna saat trend kuat; saat range/manipulasi, price action memimpin. [X]

## 6. Manajemen risiko
- Stop sangat pendek dan invalidasi sederhana. Posisi leverage: stop sekitar 2-4% harga maksimum. [YT]
- R:R harus layak: target 2% dengan stop 1-1.5% di BTC = mengejar ekor sendiri, jangan diambil. [YT]
- Ambil profit cepat di TP1; setelah itu geser stop ke break-even dan biarkan sisanya jalan. [YT]
- Jika stop tersentuh dan kemudian setup valid lagi, boleh masuk ulang; bukan sebelum valid lagi. [YT]
- Jangan over-leverage; waspada flash dump dan likuidasi. [YT][X]

## 7. Kapan TIDAK trade
- Harga di mid-range / "tengah ketidakjelasan". [X]
- Pasar tipis, likuiditas rendah, penuh manipulasi, atau arah tidak jelas. [X]
- Sebelum berita besar atau saat BTC bergerak liar melawan arah posisi altcoin. [YT]
- Jika tidak yakin: menunggu. [X][YT]
