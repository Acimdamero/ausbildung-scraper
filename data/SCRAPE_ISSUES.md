# Scrape Issues Log

Problems encountered during scraping runs. Updated automatically or by agents.

## meine-ausbildung-in-deutschland.de

### meine_ausbildung_dpa — 2026-06-11

**Last run:** 2026-06-11T11:42:19Z

| Metric | Value |
|--------|-------|
| Pages scraped | 11/11 (search total 208 hits) |
| Raw / filtered stubs | 208 / 190 (18 non-DPA filtered) |
| Scraped / failed | 190 / 0 |
| Cross-dupes vs master | 84 |
| New unique added | 106 |
| Master after merge | 1398 |

**Known limitations:**

- Search iframe lives at `ihk-azubi-stellenmarkt.indexinternet.de`, not on main page DOM.
- Query `daten` is broad; title filter keeps Fachinformatiker Daten-/Prozessanalyse only.
- Many `klick_zaehler.cfm` links redirect to **employer career pages**, not `arbeitsagentur.de/jobdetail` — BA API unavailable; stub + redirect URL used.
- BA API 404 for some refnrs (e.g. `15986-2027_1006-1-S`, `10000-1203639674-S`) — fallback to stub fields.
- Field completeness lower than BA-native listings: gaji 5.3%, email 10%, persyaratan 32.6%.

**Monitor commands:**

```bash
tail -f logs/meine_ausbildung_dpa.log
cat data/progress_meine_ausbildung_dpa.json | python3 -m json.tool | head -30
pgrep -fl meine_ausbildung
```

## meine_ausbildung_ae — 2026-06-11 12:06 UTC

- Discovered: 1439 (expected 1478)
- Scraped: 1439, failed: 0
- Cross-dup vs master: 647, unique new: 770

Known limitations:
- Many click-through links redirect to employer career pages, not Arbeitsagentur jobdetail.
- Listings without BA redirect use stub fields (title, company, city) + final redirect URL.
- Query `daten` may include non-DPA roles (e.g. dual study); filter by title if needed.

## suche.ausbildung.nrw — 2026-06-12 09:41 UTC

### Investigation

- **API available:** True
- **Method:** playwright_discovery_api_intercept + playwright_detail_pages
- **Apprenticeship IDs:** AE=322, DPA=430 (user URL `527,322` maps to dual study + AE, not DPA)

### Results

| Category | Discovered | Scraped | Failed | Cross-dup | Unique new |
|----------|------------|---------|--------|-----------|------------|
| ausbildung_nrw_ae | 57 | 56 | 1 | 40 | 16 |

**Master after merge:** 2158

**Field completeness (%):**

- nama_perusahaan: 100.0%
- titik_data_di_peta: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- kontak_penanggung_jawab: 100.0%
- deskripsi_perusahaan: 85.7%
- alamat_email_bewerbung: 85.7%
- link_bewerbung: 85.7%
- link_website_perusahaan: 83.9%
- apa_yang_ditawarkan: 41.1%
- dokumen_yang_harus_dipenuhi: 28.6%
- gaji: 0.0%
- persyaratan: 0.0%

**Known limitations:**
- Discovery uses `api.ausbildung.nrw/api/user/companies?ids=` batches intercepted during virtual-scroll on search page.
- Detail pages are company profiles; apprenticeship-specific apply links may point to generic `/karriere/` pages.
- Salary (`gaji`) rarely published on NRW portal.
- User filter URL `apprenticeships=527,322` includes dual study (527), not DPA — scraper uses 322 (AE) and 430 (DPA).

**Monitor commands:**

```bash
tail -f logs/ausbildung_nrw_scrape.log
cat data/progress_ausbildung_nrw.json | python3 -m json.tool | head -40
pgrep -fl run_ausbildung_nrw
```

## azubiyo.de — 2026-06-12 09:57 UTC

### Investigation

- **API available:** False
- **Method:** playwright_pagination + playwright_detail_pages (JSON-LD JobPosting)
- **Pagination:** URL path /ausbildung/{beruf}/{page}/ with query filters; ~15 jobs/page
- **start=20262:** start=20262 filters Ausbildungsbeginn 2026 (site shows 532 total, ~98 match with subject+radius filters)

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| azubiyo_de_ae | 98 | 83 | 0 | 15 | 11 | 71 |
| azubiyo_de_dpa | 22 | 22 | 0 | 0 | 1 | 20 |

**Master after merge:** 2249

**Field completeness (%):**

- nama_perusahaan: 100.0%
- detail_deskripsi: 100.0%
- deskripsi_perusahaan: 100.0%
- link_bewerbung: 100.0%
- posisi_kota: 85.4%
- alamat_detail: 85.4%
- jenis_ausbildung: 85.4%
- gaji: 59.2%
- persyaratan: 52.4%
- apa_yang_ditawarkan: 52.4%
- kontak_penanggung_jawab: 36.9%
- dokumen_yang_harus_dipenuhi: 29.1%
- alamat_email_bewerbung: 16.5%
- titik_data_di_peta: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- No public search JSON API; listings loaded via Angular on search pages.
- Pagination uses `/ausbildung/{beruf}/{page}/` URL segments (~15 listings/page).
- DPA search may surface AE listings; parser skips non-matching Beruf keywords.
- Apply link often points to azubiyo.de `/bewerben/` funnel, not employer site.

**Monitor commands:**

```bash
tail -f logs/azubiyo_de_scrape.log
cat data/progress_azubiyo_de.json | python3 -m json.tool | head -40
pgrep -fl run_azubiyo_de
```

## suche.ausbildung.nrw — 2026-06-12 10:01 UTC

### Investigation

- **API available:** True
- **Method:** playwright_discovery_api_intercept + playwright_detail_pages
- **Apprenticeship IDs:** AE=322, DPA=430 (user URL `527,322` maps to dual study + AE, not DPA)

### Results

| Category | Discovered | Scraped | Failed | Cross-dup | Unique new |
|----------|------------|---------|--------|-----------|------------|
| ausbildung_nrw_ae | 181 | 181 | 0 | 143 | 36 |
| ausbildung_nrw_dpa | 34 | 34 | 0 | 22 | 12 |

**Master after merge:** 2316

**Field completeness (%):**

- nama_perusahaan: 100.0%
- titik_data_di_peta: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- kontak_penanggung_jawab: 100.0%
- deskripsi_perusahaan: 85.9%
- alamat_email_bewerbung: 85.9%
- link_bewerbung: 85.9%
- link_website_perusahaan: 84.5%
- apa_yang_ditawarkan: 47.9%
- dokumen_yang_harus_dipenuhi: 35.7%
- persyaratan: 2.3%
- gaji: 0.0%

**Known limitations:**
- Discovery uses `api.ausbildung.nrw/api/user/companies?ids=` batches intercepted during virtual-scroll on search page.
- Detail pages are company profiles; apprenticeship-specific apply links may point to generic `/karriere/` pages.
- Salary (`gaji`) rarely published on NRW portal.
- User filter URL `apprenticeships=527,322` includes dual study (527), not DPA — scraper uses 322 (AE) and 430 (DPA).

**Monitor commands:**

```bash
tail -f logs/ausbildung_nrw_scrape.log
cat data/progress_ausbildung_nrw.json | python3 -m json.tool | head -40
pgrep -fl run_ausbildung_nrw
```

## stepstone.de — 2026-06-12 21:10 UTC

### Investigation

- **API available:** False
- **Method:** playwright_pagination + playwright_detail_pages (JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~25 jobs/page, ~34 pages for AE); click fallback
- **rsearch=2:** rsearch=2 is search-origin/radius param, NOT page number
- **Detail URL:** /stellenangebote--{title}--{id}-inline.html

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| stepstone_de_ae | 848 | 488 | 0 | 360 | 51 | 435 |

**Master after merge:** 2316

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- apa_yang_ditawarkan: 79.8%
- persyaratan: 61.3%
- kontak_penanggung_jawab: 59.1%
- dokumen_yang_harus_dipenuhi: 28.6%
- titik_data_di_peta: 16.7%
- gaji: 12.8%
- alamat_email_bewerbung: 4.9%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- No public listing search JSON API; React SPA with server-rendered search pages.
- Pagination via `?page=N&rsearch=2` (~25 jobs/page); click fallback when goto fails.
- Detail pages must use `-inline.html` URLs (canonical `.html` may return Access denied).
- Apply buttons often absent on inline detail; `directApply` uses StepStone job URL.

**Monitor commands:**

```bash
tail -f logs/stepstone_de_scrape.log
cat data/progress_stepstone_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_stepstone_de
```

## stepstone.de — 2026-06-12 21:56 UTC

### Investigation

- **API available:** False
- **Method:** playwright_pagination + playwright_detail_pages (JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~25 jobs/page, ~34 pages for AE); click fallback
- **rsearch=2:** rsearch=2 is search-origin/radius param, NOT page number
- **Detail URL:** /stellenangebote--{title}--{id}-inline.html

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| stepstone_de_dpa | 550 | 98 | 5 | 447 | 18 | 78 |

**Master after merge:** 2316

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- apa_yang_ditawarkan: 72.9%
- kontak_penanggung_jawab: 62.5%
- persyaratan: 57.3%
- dokumen_yang_harus_dipenuhi: 34.4%
- titik_data_di_peta: 27.1%
- gaji: 15.6%
- alamat_email_bewerbung: 5.2%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- No public listing search JSON API; React SPA with server-rendered search pages.
- Pagination via `?page=N&rsearch=2` (~25 jobs/page); click fallback when goto fails.
- Detail pages must use `-inline.html` URLs (canonical `.html` may return Access denied).
- Apply buttons often absent on inline detail; `directApply` uses StepStone job URL.

**Monitor commands:**

```bash
tail -f logs/stepstone_de_scrape.log
cat data/progress_stepstone_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_stepstone_de
```

## stepstone.de — 2026-06-12 22:02 UTC

### Investigation

- **API available:** False
- **Method:** playwright_pagination + playwright_detail_pages (JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~25 jobs/page); click fallback
- **rsearch=2:** rsearch=2 is search-origin/radius param, NOT page number
- **Detail URL:** /stellenangebote--{title}--{id}-inline.html

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| stepstone_de_ae | 848 | 488 | 0 | 360 | 50 | 433 |
| stepstone_de_dpa | 550 | 98 | 5 | 447 | 19 | 77 |

**Master after merge:** 2826

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- apa_yang_ditawarkan: 78.9%
- persyaratan: 60.8%
- kontak_penanggung_jawab: 59.8%
- dokumen_yang_harus_dipenuhi: 29.7%
- titik_data_di_peta: 18.3%
- gaji: 13.3%
- alamat_email_bewerbung: 5.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- No public listing search JSON API; React SPA with server-rendered search pages.
- Pagination via `?page=N&rsearch=2` (~25 jobs/page); click fallback when goto fails.
- Detail pages must use `-inline.html` URLs (canonical `.html` may return Access denied).
- Apply buttons often absent on inline detail; `directApply` uses StepStone job URL.

**Monitor commands:**

```bash
tail -f logs/stepstone_de_scrape.log
cat data/progress_stepstone_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_stepstone_de
```

## stepstone.de DPA retry — 2026-06-13 08:53 UTC

### Konteks

Scrape DPA awal: 550 discovered, 98 scraped, **5 failed**, 447 skipped (non-DPA).
`failed_urls` tidak tersimpan di `progress_stepstone_de.json` (ter-overwrite summary).
URL gagal diekstrak dari `logs/stepstone_de_dpa_scrape.log`.

### 5 URL gagal (semua sudah `-inline.html`)

| # | StepStone ID | Judul (ringkas) | Can extract? | Root cause |
|---|--------------|-----------------|--------------|------------|
| 1 | 14017595 | Ausbildung Fachinformatiker Systemintegration — Rosenxt Group | NO | Listing expired |
| 2 | 14016906 | Engineering Trainee — OneSubsea GmbH | NO | Listing expired |
| 3 | 14014679 | IT-Administrator — dosmatix GmbH | NO | Listing expired |
| 4 | 11927888 | Praktikum Softwareentwicklung — CAS Software AG | NO | Listing expired |
| 5 | 13409271 | Praktikum Softwareentwicklung — Senacor Technologies AG | NO | Listing expired |

**Catatan:** Bukan Access denied — URL sudah benar (`-inline.html`). Halaman memuat teks *"Diese Stellenanzeige ist nicht mehr verfügbar"* tanpa `application/ld+json`. Scrape awal melaporkan timeout JSON-LD (30s); retry dengan 90s timeout mengonfirmasi penyebab sebenarnya: **lowongan sudah tidak aktif**.

### Hasil retry

| Metrik | Nilai |
|--------|-------|
| Total di-retry | 5 |
| Recovered | 0 |
| Still failed | 5 |
| Master di-update? | **Tidak** (tidak ada data baru) |

### Rekomendasi

1. **Master tidak perlu di-update** — 96 listing DPA valid sudah di master; 5 gagal tidak dapat dipulihkan.
2. **Deteksi expired di scraper utama** — cek teks `nicht mehr verfügbar` sebelum menunggu JSON-LD; hitung sebagai `skipped_expired`, bukan `failed`.
3. **Simpan `failed_urls`** di progress/report agar retry tidak perlu parsing log.
4. **4 dari 5 gagal adalah Praktikum/Trainee/IT-Admin**, bukan DPA — kemungkinan besar akan di-skip `wrong_beruf` meski berhasil di-scrape.
5. Script retry: `python3 scripts/retry_stepstone_failed.py --log logs/stepstone_de_dpa_scrape.log`

**Laporan detail:** `data/samples/stepstone_de_retry_report.json`

## meinestadt.de — 2026-06-13 10:13 UTC

### Investigation

- **API available:** False
- **Method:** playwright (context.request pagination + page detail scrape, JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~20 jobs/page); Seite X von Y until exhausted
- **Radius r=100:** Deutschland-wide via /deutschland/lehrstellen/jkl/{path_ids}
- **Detail URL:** /deutschland/lehrstellen/standard?id={jobId}

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| meinestadt_ae | 195 | 2 | 0 | 193 | 1 | 1 |

**Master after merge:** 2901

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- kontak_penanggung_jawab: 100.0%
- alamat_email_bewerbung: 50.0%
- titik_data_di_peta: 0.0%
- gaji: 0.0%
- persyaratan: 0.0%
- deskripsi_perusahaan: 0.0%
- apa_yang_ditawarkan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

**Known limitations:**
- No public search JSON API; Playwright `context.request.get` for paginated search HTML.
- Pagination via `?page=N` (~20 jobs/page); stop when `Seite X von Y` exhausted.
- Detail URL: `/deutschland/lehrstellen/standard?id={jobId}`; referenznummer `MSD-{id}`.
- DPA/DV use all-FI path `97268-16360-17489-18734` with card-title pre-filter.
- Cookie banner: OneTrust `#onetrust-accept-btn-handler` / `Alle akzeptieren`.
- HTTP/2 disabled (`--disable-http2`) to avoid ERR_HTTP2_PROTOCOL_ERROR.

**Monitor commands:**

```bash
tail -f logs/meinestadt_de_scrape.log
cat data/progress_meinestadt_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_meinestadt_de
```

## meinestadt.de — 2026-06-13 10:26 UTC

### Investigation

- **API available:** False
- **Method:** playwright (context.request pagination + page detail scrape, JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~20 jobs/page); Seite X von Y until exhausted
- **Radius r=100:** Deutschland-wide via /deutschland/lehrstellen/jkl/{path_ids}
- **Detail URL:** /deutschland/lehrstellen/standard?id={jobId}

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| meinestadt_ae | 195 | 2 | 0 | 193 | 1 | 1 |

**Master after merge:** 2902

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- kontak_penanggung_jawab: 100.0%
- alamat_email_bewerbung: 50.0%
- titik_data_di_peta: 0.0%
- gaji: 0.0%
- persyaratan: 0.0%
- deskripsi_perusahaan: 0.0%
- apa_yang_ditawarkan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

**Known limitations:**
- No public search JSON API; Playwright `context.request.get` for paginated search HTML.
- Pagination via `?page=N` (~20 jobs/page); stop when `Seite X von Y` exhausted.
- Detail URL: `/deutschland/lehrstellen/standard?id={jobId}`; referenznummer `MSD-{id}`.
- DPA/DV use all-FI path `97268-16360-17489-18734` with card-title pre-filter.
- Cookie banner: OneTrust `#onetrust-accept-btn-handler` / `Alle akzeptieren`.
- HTTP/2 disabled (`--disable-http2`) to avoid ERR_HTTP2_PROTOCOL_ERROR.

**Monitor commands:**

```bash
tail -f logs/meinestadt_de_scrape.log
cat data/progress_meinestadt_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_meinestadt_de
```

## azubi.de — 2026-06-13 10:41 UTC

### Investigation

- **API available:** False
- **Method:** requests + JSON-LD ItemList (search) + JobPosting (detail)
- **Pagination:** ?page=N query param; 20 listings/page; ~664 total FI listings
- **Total listings (site):** 664

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| azubi_de_fi | 664 | 659 | 0 | 5 | 174 | 471 |

**Master after merge:** 3373

**beruf_typ breakdown:**

- si (Systemintegration): 322
- ae (Anwendungsentwicklung): 214
- dpa (Daten- und Prozessanalyse): 48
- non_fi (Bukan Fachinformatiker): 20
- dual (Duales Studium): 19
- fi_other (Fachinformatiker lainnya): 15
- dv (Digitale Vernetzung): 7

**Field completeness (%):**

- nama_perusahaan: 100.0%
- detail_deskripsi: 100.0%
- link_bewerbung: 100.0%
- persyaratan: 98.8%
- jenis_ausbildung: 91.6%
- posisi_kota: 91.5%
- alamat_detail: 91.5%
- apa_yang_ditawarkan: 62.9%
- gaji: 36.3%
- kontak_penanggung_jawab: 34.7%
- alamat_email_bewerbung: 33.6%
- dokumen_yang_harus_dipenuhi: 31.2%
- titik_data_di_peta: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- Combined Fachinformatiker search page (all FI specializations); beruf_typ from title parsing.
- Static HTML with JSON-LD ItemList (search) + JobPosting (detail); no Playwright needed.
- Apply/contact often via azubi.de portal; external employer email rarely exposed.
- hiringOrganization.url points to azubi.de company profile, not employer website.

**Monitor commands:**

```bash
tail -f logs/azubi_de_scrape.log
cat data/progress_azubi_de.json | python3 -m json.tool | head -40
pgrep -fl run_azubi_de
```

## wir-sind-bund.de — 2026-06-13 14:42 UTC

### Investigation

- **Api Available:** False
- **Method:** Playwright search (pageNo=N) + Playwright detail (HTML text parse)
- **Pagination:** pageNo=0,1,... until no new Stellenangebot links (~20 unique for fachinformatiker)
- **Cookie Note:** Bund.de cookie banner — click 'Auswahl bestätigen' (necessary cookies only)
- **Detail Url Pattern:** ExternalContent/.../Stellenangebote/.../{uuid}.html
- **Notes:** Bundesverwaltung portal; relative hrefs need base URL prefix.

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| wir_sind_bund_fi | 20 | 8 | 12 | 0 | 1 | 6 |

**Master after merge:** 3910

**Field completeness (%):**

- nama_perusahaan: 100.0%
- detail_deskripsi: 100.0%
- kontak_penanggung_jawab: 100.0%
- jenis_ausbildung: 71.4%
- alamat_email_bewerbung: 71.4%
- posisi_kota: 42.9%
- alamat_detail: 42.9%
- apa_yang_ditawarkan: 42.9%
- link_bewerbung: 42.9%
- titik_data_di_peta: 0.0%
- gaji: 0.0%
- persyaratan: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

## karriere-suedwestfalen.de — 2026-06-13 14:45 UTC

### Investigation

- **API available:** False
- **Method:** HTTP pagination (/jobboerse/{page}) + Playwright detail (JSON-LD JobPosting)
- **Pagination:** /jobboerse/{page}?s=query — stop on empty page or 2 stagnant pages
- **Detail JSON-LD:** JobPosting schema on /ausbildung/* detail pages
- **Expected listings:** ~84 unique for fachinformatiker+anwendungsentwicklung

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| karriere_sw_ae | 84 | 84 | 0 | 0 | 16 | 68 |

**Master after merge:** 3978

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- alamat_email_bewerbung: 76.2%
- link_bewerbung: 73.8%
- kontak_penanggung_jawab: 38.1%
- persyaratan: 27.4%
- apa_yang_ditawarkan: 27.4%
- titik_data_di_peta: 0.0%
- gaji: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

**Known limitations:**
- Regional portal (Südwestfalen); search is HTML server-rendered, no public JSON API.
- Pagination: `/jobboerse/{page}?s=...` — pages may repeat/overlap; scraper dedupes URLs.
- Many listings also appear on Arbeitsagentur (partner_portal); cross-dedup via URL/company match.
- referenznummer: `KSW-{listing_id}` from URL slug suffix.

**Monitor commands:**

```bash
tail -f logs/karriere_suedwestfalen_de_scrape.log
cat data/progress_karriere_suedwestfalen_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_karriere_suedwestfalen_de
```

## karriere-suedwestfalen.de — 2026-06-13 14:45 UTC

### Investigation

- **API available:** False
- **Method:** HTTP pagination (/jobboerse/{page}) + Playwright detail (JSON-LD JobPosting)
- **Pagination:** /jobboerse/{page}?s=query — stop on empty page or 2 stagnant pages
- **Detail JSON-LD:** JobPosting schema on /ausbildung/* detail pages
- **Expected listings:** ~84 unique for fachinformatiker+anwendungsentwicklung

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| karriere_sw_ae | 84 | 34 | 0 | 0 | 16 | 68 |

**Master after merge:** 3978

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- alamat_email_bewerbung: 76.2%
- link_bewerbung: 73.8%
- kontak_penanggung_jawab: 38.1%
- persyaratan: 27.4%
- apa_yang_ditawarkan: 27.4%
- titik_data_di_peta: 0.0%
- gaji: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

**Known limitations:**
- Regional portal (Südwestfalen); search is HTML server-rendered, no public JSON API.
- Pagination: `/jobboerse/{page}?s=...` — pages may repeat/overlap; scraper dedupes URLs.
- Many listings also appear on Arbeitsagentur (partner_portal); cross-dedup via URL/company match.
- referenznummer: `KSW-{listing_id}` from URL slug suffix.

**Monitor commands:**

```bash
tail -f logs/karriere_suedwestfalen_de_scrape.log
cat data/progress_karriere_suedwestfalen_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_karriere_suedwestfalen_de
```

## wir-sind-bund.de — 2026-06-13 14:46 UTC

### Investigation

- **Api Available:** False
- **Method:** Playwright search (pageNo=N) + Playwright detail (HTML text parse)
- **Pagination:** Initial ~20 results; click 'Weitere Ergebnisse anzeigen' until exhausted (~25 for fachinformatiker)
- **Cookie Note:** Bund.de cookie banner — click 'Auswahl bestätigen' (necessary cookies only)
- **Detail Url Pattern:** ExternalContent/.../Stellenangebote/.../{uuid}.html
- **Notes:** Bundesverwaltung portal; relative hrefs need base URL prefix.

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| wir_sind_bund_fi | 25 | 25 | 0 | 0 | 7 | 17 |

**Master after merge:** 3995

**Field completeness (%):**

- nama_perusahaan: 100.0%
- detail_deskripsi: 100.0%
- kontak_penanggung_jawab: 95.8%
- jenis_ausbildung: 79.2%
- apa_yang_ditawarkan: 66.7%
- gaji: 58.3%
- alamat_email_bewerbung: 58.3%
- link_bewerbung: 50.0%
- posisi_kota: 33.3%
- alamat_detail: 33.3%
- persyaratan: 20.8%
- titik_data_di_peta: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

## aubi-plus.de — 2026-06-13 14:57 UTC

### Investigation

- **Api Available:** False
- **Method:** Playwright pagination (seite=N, anzahl=10) + detail HTML/JSON-LD
- **Pagination:** Canonical ?seite=N from pagination widget; ~10 /ausbildung/ links/page
- **Search Note:** 807 Plätze total includes dual studium; only /ausbildung/ URLs scraped
- **Expected Ausbildung Urls:** ~190-400
- **Detail Url Pattern:** /ausbildung/{company-slug}-{id}/
- **Notes:** Cookie banner dismissed via .cookie-manager-accept. Detail pages often lack JSON-LD; parser falls back to HTML title/body.

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| aubi_plus_fi | 245 | 245 | 0 | 0 | 50 | 185 |

**Master after merge:** 4180

**Field completeness (%):**

- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- link_bewerbung: 100.0%
- kontak_penanggung_jawab: 97.9%
- jenis_ausbildung: 94.9%
- nama_perusahaan: 82.6%
- apa_yang_ditawarkan: 77.4%
- gaji: 44.7%
- persyaratan: 43.4%
- alamat_email_bewerbung: 42.6%
- link_website_perusahaan: 2.6%
- titik_data_di_peta: 0.0%
- deskripsi_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

## ausbildungsstellen.de — 2026-06-13 15:03 UTC

### Investigation

- **API available:** False
- **Method:** playwright_pagination (?p=N) + playwright_detail (JSON-LD JobPosting)
- **Pagination:** ?p=N query param (~20 jobs/page, AE ~142 pages); Weiter » until exhausted
- **Radius r=100:** r=100 is search radius in km (Bundesweit when l= empty)
- **Detail URL:** /ausbildung-{slug}-{id}.html OR /job.php?c={chiffre} (redirect)

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| ausbildungsstellen_ae | 2833 | 2746 | 1 | 86 | 1 | 137 |
| ausbildungsstellen_dpa | 130 | 122 | 0 | 8 | 0 | 37 |
| ausbildungsstellen_dv | 60 | 56 | 0 | 4 | 0 | 17 |
| ausbildungsstellen_si | 2833 | 2765 | 1 | 67 | 178 | 2281 |

**Master after merge:** 6652

**Field completeness (%):**

- detail_deskripsi: 71.4%
- jenis_ausbildung: 71.4%
- link_bewerbung: 70.3%
- nama_perusahaan: 68.1%
- kontak_penanggung_jawab: 62.1%
- alamat_email_bewerbung: 54.8%
- persyaratan: 37.3%
- apa_yang_ditawarkan: 35.6%
- dokumen_yang_harus_dipenuhi: 24.0%
- link_website_perusahaan: 16.7%
- posisi_kota: 16.0%
- alamat_detail: 16.0%
- gaji: 15.2%
- deskripsi_perusahaan: 13.0%
- titik_data_di_peta: 0.0%

**Known limitations:**
- No public search JSON API; server-rendered HTML with `span.jobTitle > a` links.
- Pagination via `?p=N` (~20 jobs/page); stop when no `Weiter »` in `ul.pagination`.
- Many listings use `/job.php?c={chiffre}` redirecting to partner sites (ausbildung.de).
- Cookie banner: Matomo `cookieconsent.min.js` — dismiss optional for scraping.

**Monitor commands:**

```bash
tail -f logs/ausbildungsstellen_de_scrape.log
cat data/progress_ausbildungsstellen_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_ausbildungsstellen_de
```

## indeed.de — 2026-06-13 16:15 UTC

### Investigation

- **API available:** False
- **Method:** playwright viewjob-first (/viewjob?jk=) + SERP split-view fallback; #jobDescriptionText + JSON-LD
- **Pagination:** Location-sharded search (l=City/Bundesland); start=10+ blocked by Cloudflare
- **Anti-bot:** SERP reload blocked after first job; viewjob direct is primary. Use --headful if headless blocked.
- **Detail URL:** /viewjob?jk={16-char-hex}

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| indeed_de_ae | 402 | 0 | 5 | 0 | 383 | 0 |
| indeed_de_dpa | 240 | 105 | 5 | 130 | 105 | 0 |

**Master after merge:** 6848

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- link_bewerbung: 100.0%
- gaji: 96.5%
- apa_yang_ditawarkan: 74.0%
- persyaratan: 64.5%
- kontak_penanggung_jawab: 35.9%
- dokumen_yang_harus_dipenuhi: 35.2%
- alamat_email_bewerbung: 34.0%
- titik_data_di_peta: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%

**Known limitations:**
- No public listing search JSON API; server-rendered SERP with embedded jobkey.
- Pagination via `?start=N` (10 jobs/page); delays + retries for Cloudflare.
- Detail via SERP split-view panel click; canonical URL stored as /viewjob?jk=...
- Indeed apply links often redirect via pagead/clk; external URLs extracted when present.

**Monitor commands:**

```bash
tail -f logs/indeed_de_scrape.log
cat data/progress_indeed_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_indeed_de
```

## meinestadt.de — 2026-06-13 16:19 UTC

### Investigation

- **API available:** False
- **Method:** playwright (context.request pagination + page detail scrape, JSON-LD JobPosting)
- **Pagination:** ?page=N query param (~20 jobs/page); Seite X von Y until exhausted
- **Radius r=100:** Deutschland-wide via /deutschland/lehrstellen/jkl/{path_ids}
- **Detail URL:** /deutschland/lehrstellen/standard?id={jobId}

### Results

| Category | Discovered | Scraped | Failed | Skipped | Cross-dup | Unique new |
|----------|------------|---------|--------|---------|-----------|------------|
| meinestadt_ae | 176 | 2 | 0 | 174 | 2 | 0 |
| meinestadt_dpa | 540 | 0 | 0 | 540 | 0 | 0 |
| meinestadt_dv | 580 | 0 | 0 | 580 | 0 | 0 |
| meinestadt_si | 295 | 3 | 0 | 292 | 1 | 2 |

**Master after merge:** 6850

**Field completeness (%):**

- nama_perusahaan: 100.0%
- posisi_kota: 100.0%
- alamat_detail: 100.0%
- detail_deskripsi: 100.0%
- jenis_ausbildung: 100.0%
- kontak_penanggung_jawab: 100.0%
- gaji: 60.0%
- link_bewerbung: 40.0%
- apa_yang_ditawarkan: 20.0%
- alamat_email_bewerbung: 20.0%
- titik_data_di_peta: 0.0%
- persyaratan: 0.0%
- deskripsi_perusahaan: 0.0%
- link_website_perusahaan: 0.0%
- dokumen_yang_harus_dipenuhi: 0.0%

**Known limitations:**
- No public search JSON API; Playwright `context.request.get` for paginated search HTML.
- Pagination via `?page=N` (~20 jobs/page); stop when `Seite X von Y` exhausted.
- Detail URL: `/deutschland/lehrstellen/standard?id={jobId}`; referenznummer `MSD-{id}`.
- DPA/DV use all-FI path `97268-16360-17489-18734` with card-title pre-filter.
- Cookie banner: OneTrust `#onetrust-accept-btn-handler` / `Alle akzeptieren`.
- HTTP/2 disabled (`--disable-http2`) to avoid ERR_HTTP2_PROTOCOL_ERROR.

**Monitor commands:**

```bash
tail -f logs/meinestadt_de_scrape.log
cat data/progress_meinestadt_de.json | python3 -m json.tool | head -40
./scripts/watch_progress.sh
pgrep -fl run_meinestadt_de
```
