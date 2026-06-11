# Architecture

## Overview

Sistem menggunakan **Arbeitsagentur Jobsuche REST API** (bukan browser scraping) untuk mengumpulkan data Ausbildung.

```mermaid
flowchart TB
    subgraph Config
        CAT[categories.yaml]
        FLD[fields_mapping.yaml]
        ENV[.env]
    end

    subgraph Core
        RUN[scripts/run_scraper.py]
        API[JobsucheClient]
        PAR[ListingParser]
    end

    subgraph External
        BA[(Arbeitsagentur API)]
        GS[(Google Sheets)]
    end

    subgraph Storage
        JSON[data/exports/*.json]
        CSV[data/exports/*.csv]
        PRG[data/progress.json]
    end

    CAT --> RUN
    FLD --> PAR
    ENV --> RUN
    RUN --> API
    API -->|GET /pc/v6/jobs| BA
    API -->|GET /pc/v4/jobdetails| BA
    BA --> PAR
    PAR --> JSON
    PAR --> CSV
    PAR --> GS
    RUN --> PRG
```

## Komponen

| Modul | Path | Tanggung jawab |
|-------|------|----------------|
| API Client | `src/api_client/jobsuche.py` | Search + detail fetch, rate limiting |
| Parser | `src/parser/listing_parser.py` | Normalisasi API → `AusbildungListing` |
| Models | `src/models/listing.py` | Dataclass field output |
| Local Storage | `src/storage/local.py` | JSON/CSV export |
| Sheets | `src/storage/sheets.py` | Tab per kategori |
| Progress | `src/storage/progress.py` | Tracking & markdown export |

## Alur Data

1. **Search** — `GET /pc/v6/jobs?was=...&angebotsart=4` → daftar `referenznummer`
2. **Detail** — `GET /pc/v4/jobdetails/{base64(refnr)}` → deskripsi lengkap
3. **Parse** — Map ke 15+ field user + metadata
4. **Store** — JSON, CSV, Sheets, progress

## Keputusan Desain

| Keputusan | Alasan |
|-----------|--------|
| API over Playwright | Stabil, cepat, tidak butuh browser |
| Dataclass model | Type-safe, mudah di-serialize |
| Tab Sheets per kategori | Sesuai 3 profil pencarian user |
| Dedup kategori duplikat | URL #3 dan #4 identik |

## Roadmap Arsitektur

```mermaid
flowchart LR
    MVP[MVP: API Scraper] --> NLP[NLP: ekstrak email dari deskripsi]
    NLP --> BEW[Auto-Bewerbung Generator]
    BEW --> TRACK[Lamaran Tracker]
```
