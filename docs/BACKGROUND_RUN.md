# Menjalankan scraper di background (Mac)

Panduan singkat agar scrape **ausbildung.de** tetap berjalan saat Anda menutup Cursor/terminal — dengan catatan penting tentang **sleep** MacBook.

## Mulai dan hentikan (paling praktis)

Dari folder proyek (`~/Projects/ausbildung-scraper`):

- **Mulai:** `./scripts/start_background_pipeline.sh`
- **Hentikan kapan saja:** `./scripts/stop_background_pipeline.sh`

Skrip stop aman dipanggil meski tidak ada yang jalan: menghentikan proses scrape (PID di `logs/ausbildung_de_scrape.pid`), menutup sesi `screen` bernama `ausbildung_pipeline`, dan menulis **STOPPED (by user)** ke `data/BACKGROUND_STATUS.md`.

Cek status: `cat data/BACKGROUND_STATUS.md`


## Peringatan: tutup lid MacBook (jujur)

- **macOS:** menutup lid hampir selalu membuat Mac **tidur (sleep)**. Proses scrape/pipeline **berhenti atau tertunda** sampai Mac dibangunkan lagi.
- **Tethering hotspot saja tidak mencegah sleep** — koneksi internet tidak menjaga Mac tetap bangun.

**Opsi agar tetap jalan:**

| Opsi | Keterangan |
|------|------------|
| **(a) Lid terbuka** | Paling sederhana dan andal. |
| **(b) Clamshell mode** | Lid tertutup **hanya** jika ada monitor eksternal + keyboard + mouse/trackpad **dan** Mac terpasang adaptor daya (sesuai aturan Apple). |
| **(c) `caffeinate -dims`** | Jalankan di terminal terpisah saat adaptor daya; membantu menahan sleep, tetapi **lid tertutup** di banyak Mac tetap bisa memaksa tidur. Skrip start sudah memakai `caffeinate -i` di dalam sesi screen. |
| **(d) System Settings** | Kurangi/matikan sleep saat colok listrik (Battery / Energy / Displays — tergantung versi macOS). |
| **(e) Amphetamine** (atau app sejenis) | Third-party untuk menahan sleep; tetap baca batasan hardware saat lid tertutup. |

Anda **bisa menghentikan pipeline kapan saja** dengan `./scripts/stop_background_pipeline.sh` tanpa harus menunggu selesai.


## Cara paling andal dari Cursor (GNU `screen`)

Jika `nohup` dari dalam agent Cursor mati saat sesi ditutup, jalankan di **Terminal macOS** (atau):

```bash
cd ~/Projects/ausbildung-scraper
./scripts/start_background_pipeline.sh
```

Cek sesi: `screen -ls` → attach: `screen -r ausbildung_pipeline` (Ctrl+A lalu D untuk lepas lagi).

## Mulai pipeline penuh di background

```bash
cd ~/Projects/ausbildung-scraper
source .venv/bin/activate
mkdir -p logs

nohup caffeinate -i ./scripts/run_background_pipeline.sh > logs/pipeline_nohup.out 2>&1 &
echo $! > logs/pipeline.pid
```

Pipeline otomatis:

1. Scrape **ausbildung.de** (kategori AE + DPA)
2. **Dedup** lintas sumber dari export
3. **generate_bewerbung_exports** + **viewer** HTML

## Hanya scrape ausbildung.de (tanpa pipeline penuh)

```bash
cd ~/Projects/ausbildung-scraper
source .venv/bin/activate
mkdir -p logs

nohup caffeinate -i python scripts/run_ausbildung_de.py --delay 0.25 \
  >> logs/ausbildung_de_scrape.log 2>&1 &
echo $! > logs/ausbildung_de_scrape.pid
```

## Cek apakah masih jalan

```bash
cd ~/Projects/ausbildung-scraper

# Pipeline penuh
cat logs/pipeline.pid
ps -p "$(cat logs/pipeline.pid)"

# Hanya scrape
cat logs/ausbildung_de_scrape.pid
ps -p "$(cat logs/ausbildung_de_scrape.pid)"

# Atau cari proses Python scrape
pgrep -fl "run_ausbildung_de.py"
pgrep -fl "run_background_pipeline"
```

## Cek progress setelah kembali

```bash
cd ~/Projects/ausbildung-scraper

# Ringkasan status (diperbarui saat pipeline selesai/gagal)
cat data/BACKGROUND_STATUS.md

# Progress scrape tersimpan
cat data/progress_ausbildung_de.json

# Ikuti log live
tail -f logs/ausbildung_de_scrape.log
# atau log pipeline terbaru:
ls -t logs/pipeline_*.log | head -1 | xargs tail -f
```

## Setelah pipeline selesai

File **`data/BACKGROUND_STATUS.md`** berisi state `COMPLETED` atau `FAILED`.

Secara otomatis Anda mendapat:

- Export scrape di `data/exports/`
- Master dedup di `data/processed/all_listings_deduped.json` (dan CSV)
- CSV Bewerbung: `data/processed/master_bewerbung.csv`, `high_priority.csv`, dll.
- Viewer: `data/viewer/index.html`

