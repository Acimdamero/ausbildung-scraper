#!/usr/bin/env python3
"""Real-time terminal monitor for ausbildung-scraper progress."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"

SCRAPE_PATTERNS = (
    "run_scraper.py",
    "run_ausbildung_de.py",
    "run_meine_ausbildung_de.py",
    "run_ausbildung_nrw.py",
    "run_azubiyo_de.py",
    "run_stepstone_de.py",
    "run_indeed_de.py",
    "run_ausbildungsstellen_de.py",
    "run_meinestadt_de.py",
    "run_backinjob_de.py",
)

SOURCE_LOGS: dict[str, Path] = {
    "arbeitsagentur": LOGS / "arbeitsagentur_scrape.log",
    "ausbildung_de": LOGS / "ausbildung_de_scrape.log",
    "meine_ae": LOGS / "meine_ausbildung_ae.log",
    "meine_dpa": LOGS / "meine_ausbildung_dpa.log",
    "ausbildung_nrw": LOGS / "ausbildung_nrw_scrape.log",
    "azubiyo_de": LOGS / "azubiyo_de_scrape.log",
    "stepstone_de": LOGS / "stepstone_de_scrape.log",
    "indeed_de": LOGS / "indeed_de_scrape.log",
    "ausbildungsstellen_de": LOGS / "ausbildungsstellen_de_scrape.log",
    "meinestadt_de": LOGS / "meinestadt_de_scrape.log",
    "backinjob_de": LOGS / "backinjob_de_scrape.log",
}

SOURCE_PID_FILES: dict[str, Path] = {
    "ausbildung_de": LOGS / "ausbildung_de_scrape.pid",
    "meine_ae": LOGS / "meine_ausbildung_ae.pid",
    "meine_dpa": LOGS / "meine_ausbildung_dpa.pid",
    "stepstone_de": LOGS / "stepstone_de_scrape.pid",
    "indeed_de": LOGS / "indeed_de_scrape.pid",
    "ausbildungsstellen_de": LOGS / "ausbildungsstellen_de_scrape.pid",
    "meinestadt_de": LOGS / "meinestadt_de_scrape.pid",
    "backinjob_de": LOGS / "backinjob_de_scrape.pid",
}

DEDUP_SOURCE_LABELS = {
    "fachinformatiker": "Arbeitsagentur",
    "ausbildung_de": "ausbildung.de",
    "meine_ausbildung": "meine-ausbildung",
    "ausbildung_nrw": "ausbildung.nrw",
    "azubiyo_de": "azubiyo.de",
    "stepstone_de": "stepstone.de",
    "indeed_de": "indeed.de",
    "ausbildungsstellen_de": "ausbildungsstellen.de",
    "meinestadt_de": "meinestadt.de",
    "backinjob_de": "backinjob.de",
}


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def is_pid_running(pid_file: Path) -> bool:
    if not pid_file.is_file():
        return False
    try:
        pid = int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return False
    return subprocess.run(["ps", "-p", str(pid)], capture_output=True).returncode == 0


def pgrep_lines(*patterns: str) -> list[str]:
    lines: list[str] = []
    for pattern in patterns:
        try:
            result = subprocess.run(
                ["pgrep", "-fl", pattern],
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        for line in result.stdout.splitlines():
            line = line.strip()
            if line and line not in lines:
                lines.append(line)
    return lines


def last_log_line(log_path: Path) -> str:
    if not log_path.is_file():
        return "(log tidak ada)"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "(tidak bisa baca log)"
    return lines[-1] if lines else "(log kosong)"


def pct(scraped: int, total: int) -> str:
    if total <= 0:
        return "—"
    return f"{100 * scraped / total:.1f}%"


def eta_from_log(log_path: Path, scraped: int, total: int) -> str:
    if total <= 0 or scraped >= total:
        return "selesai"
    if not log_path.is_file():
        return "?"
    matches = re.findall(
        r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}).*?(\d+)/(\d+) details",
        log_path.read_text(encoding="utf-8", errors="replace"),
    )
    if len(matches) < 2:
        return "?"
    t1, n1, _ = matches[-2]
    t2, n2, _ = matches[-1]
    try:
        n1 = int(n1)
        n2 = int(n2)
        dt1 = datetime.strptime(t1, "%Y-%m-%d %H:%M:%S")
        dt2 = datetime.strptime(t2, "%Y-%m-%d %H:%M:%S")
        elapsed = (dt2 - dt1).total_seconds()
        if elapsed <= 0 or n2 <= n1:
            return "?"
        rate = (n2 - n1) / elapsed
        remaining = total - scraped
        mins = remaining / rate / 60
        if mins < 90:
            return f"~{mins:.0f} menit"
        return f"~{mins / 60:.1f} jam"
    except ValueError:
        return "?"


def normalize_categories(data: dict) -> list[dict]:
    cats = data.get("categories") or []
    if isinstance(cats, dict):
        return [v for v in cats.values() if isinstance(v, dict)]
    if isinstance(cats, list):
        return [c for c in cats if isinstance(c, dict)]
    return []


def dedup_source_key(category_id: str) -> str:
    if category_id.startswith("fachinformatiker"):
        return "fachinformatiker"
    for prefix in (
        "ausbildung_de",
        "meine_ausbildung",
        "ausbildung_nrw",
        "azubiyo_de",
        "stepstone_de",
        "indeed_de",
    ):
        if category_id.startswith(prefix):
            return prefix
    if category_id.startswith("ausbildungsstellen_"):
        return "ausbildungsstellen_de"
    if category_id.startswith("meinestadt_"):
        return "meinestadt_de"
    if category_id.startswith("backinjob_"):
        return "backinjob_de"
    return category_id.split("_")[0]


def is_ae_category(category_id: str) -> bool:
    return category_id.endswith("_ae") or category_id in {
        "fachinformatiker_ae",
        "fachinformatiker_ae_2026",
    }


def is_dpa_category(category_id: str) -> bool:
    return category_id.endswith("_dpa") or category_id == "fachinformatiker_dpa"


def deduped_stats() -> dict:
    data = load_json(DATA / "processed" / "all_listings_deduped.json")
    if not isinstance(data, list):
        return {
            "total": None,
            "ae": None,
            "dpa": None,
            "by_source": {},
            "by_category": {},
        }
    by_category: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    ae = 0
    dpa = 0
    for row in data:
        cat = str(row.get("category_id", "unknown"))
        by_category[cat] += 1
        by_source[dedup_source_key(cat)] += 1
        if is_ae_category(cat):
            ae += 1
        elif is_dpa_category(cat):
            dpa += 1
    return {
        "total": len(data),
        "ae": ae,
        "dpa": dpa,
        "by_source": dict(by_source),
        "by_category": dict(by_category),
    }


def detect_running(proc_blob: str) -> dict[str, bool]:
    return {
        "arbeitsagentur": "run_scraper.py" in proc_blob,
        "ausbildung_de": is_pid_running(SOURCE_PID_FILES["ausbildung_de"])
        or "run_ausbildung_de.py" in proc_blob,
        "meine_ae": is_pid_running(SOURCE_PID_FILES["meine_ae"])
        or "meine_ausbildung_ae" in proc_blob,
        "meine_dpa": is_pid_running(SOURCE_PID_FILES["meine_dpa"])
        or "meine_ausbildung_dpa" in proc_blob,
        "ausbildung_nrw": "run_ausbildung_nrw.py" in proc_blob,
        "azubiyo_de": "run_azubiyo_de.py" in proc_blob,
        "stepstone_de": is_pid_running(SOURCE_PID_FILES["stepstone_de"])
        or "run_stepstone_de.py" in proc_blob,
        "indeed_de": is_pid_running(SOURCE_PID_FILES["indeed_de"])
        or "run_indeed_de.py" in proc_blob,
        "ausbildungsstellen_de": is_pid_running(SOURCE_PID_FILES["ausbildungsstellen_de"])
        or "run_ausbildungsstellen_de.py" in proc_blob,
        "meinestadt_de": is_pid_running(SOURCE_PID_FILES["meinestadt_de"])
        or "run_meinestadt_de.py" in proc_blob,
        "backinjob_de": is_pid_running(SOURCE_PID_FILES["backinjob_de"])
        or "run_backinjob_de.py" in proc_blob,
    }


def multi_category_status(data: dict, running: bool) -> str:
    if running:
        return "RUNNING"
    cats = normalize_categories(data)
    if not cats:
        return "IDLE"
    discovered = sum(int(c.get("discovered_urls", c.get("discovered", 0)) or 0) for c in cats)
    scraped = sum(int(c.get("scraped", 0) or 0) for c in cats)
    if discovered > 0 and scraped >= discovered:
        return "DONE"
    if scraped > 0:
        return "PARTIAL"
    return "IDLE"


def format_arbeitsagentur(data: dict, running: bool) -> list[str]:
    cats = data.get("categories", [])
    discovered = sum(int(c.get("total_available", 0) or 0) for c in cats)
    scraped = int(data.get("total_scraped", 0) or 0)
    if running:
        status = "RUNNING"
    elif discovered > 0 and scraped >= discovered:
        status = "DONE"
    elif scraped > 0:
        status = "PARTIAL"
    else:
        status = "IDLE"
    lines = [
        f"  Arbeitsagentur [{status}]: {scraped} scraped, "
        f"{data.get('total_failed', 0)} failed"
    ]
    for cat in cats:
        name = cat.get("category_name", cat.get("category_id", "?"))
        avail = cat.get("total_available", 0)
        count = cat.get("scraped_count", 0)
        lines.append(f"    • {name}: {count}/{avail} ({pct(count, avail)})")
    return lines


def format_multi_category(
    data: dict,
    label: str,
    log_path: Path,
    running: bool,
    *,
    extra_fields: list[str] | None = None,
) -> list[str]:
    status = multi_category_status(data, running)
    cats = normalize_categories(data)
    scraped = int(data.get("total_scraped", 0) or 0)
    if not scraped and cats:
        scraped = sum(int(c.get("scraped", 0) or 0) for c in cats)
    failed = int(data.get("total_failed", 0) or 0)
    if not failed and cats:
        failed = sum(int(c.get("failed", 0) or 0) for c in cats)
    discovered = sum(int(c.get("discovered_urls", c.get("discovered", 0)) or 0) for c in cats)
    eta = eta_from_log(log_path, scraped, discovered) if status == "RUNNING" else "—"
    lines = [
        f"  {label} [{status}]: {scraped} scraped"
        + (f", {discovered} discovered" if discovered else "")
        + f", failed {failed}, master merge {data.get('merged_master_total', '—')}, ETA {eta}"
    ]
    if extra_fields:
        for field in extra_fields:
            if field in data:
                lines.append(f"    {field}: {data[field]}")
    for cat in cats:
        cid = cat.get("category_id", "?")
        disc = int(cat.get("discovered_urls", cat.get("discovered", 0)) or 0)
        count = int(cat.get("scraped", 0) or 0)
        cat_failed = int(cat.get("failed", 0) or 0)
        extra = ""
        skipped = cat.get("skipped_wrong_beruf")
        if skipped:
            extra = f", skipped {skipped}"
        lines.append(
            f"    • {cid}: {count}/{disc} ({pct(count, disc)}), failed {cat_failed}{extra}"
        )
    updated = data.get("last_run_at")
    if updated:
        lines.append(f"    updated: {str(updated)[:19]}")
    return lines


def format_meine(
    data: dict,
    label: str,
    log_path: Path,
    running: bool,
) -> list[str]:
    scraped = int(data.get("scraped", data.get("total_scraped", 0)) or 0)
    discovered = int(data.get("discovered", data.get("discovered_urls", 0)) or 0)
    failed = int(data.get("failed", data.get("total_failed", 0)) or 0)
    finished = bool(data.get("finished"))
    if finished or (discovered > 0 and scraped >= discovered):
        status = "DONE"
    elif running:
        status = "RUNNING"
    else:
        status = "IDLE"
    eta = eta_from_log(log_path, scraped, discovered) if status == "RUNNING" else "—"
    lines = [
        f"  {label} [{status}]: {scraped}/{discovered} "
        f"({pct(scraped, discovered)}), failed {failed}, ETA {eta}"
    ]
    query = data.get("query")
    if query:
        lines.append(f"    query: {query}")
    updated = data.get("updated_at")
    if updated:
        lines.append(f"    updated: {str(updated)[:19]}")
    return lines


def format_deduped_summary(stats: dict) -> list[str]:
    lines = [
        f"  Total: {stats['total'] or '?'} listing",
        f"  AE: {stats['ae'] or '?'} | DPA: {stats['dpa'] or '?'}",
    ]
    if stats["by_source"]:
        lines.append("  Per source (deduped):")
        for key in (
            "fachinformatiker",
            "ausbildung_de",
            "meine_ausbildung",
            "ausbildung_nrw",
            "azubiyo_de",
            "stepstone_de",
            "indeed_de",
            "ausbildungsstellen_de",
            "meinestadt_de",
            "backinjob_de",
        ):
            count = stats["by_source"].get(key)
            if count:
                label = DEDUP_SOURCE_LABELS.get(key, key)
                ae = sum(
                    n
                    for cat, n in stats["by_category"].items()
                    if dedup_source_key(cat) == key and is_ae_category(cat)
                )
                dpa = sum(
                    n
                    for cat, n in stats["by_category"].items()
                    if dedup_source_key(cat) == key and is_dpa_category(cat)
                )
                lines.append(f"    • {label}: {count} (AE {ae}, DPA {dpa})")
    return lines


def build_display(running: dict[str, bool], interval: int) -> tuple[str, str]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    dedup = deduped_stats()
    lines = [
        "=" * 62,
        "  AUSBILDUNG SCRAPER — LIVE PROGRESS",
        f"  {now}  (refresh {interval}s, Ctrl+C keluar)",
        "=" * 62,
        "",
        f"MASTER TOTAL: {dedup['total'] or '?'} listing (all_listings_deduped.json)",
        "",
        "AE / DPA (deduped):",
        *format_deduped_summary(dedup),
        "",
    ]

    bg = DATA / "BACKGROUND_STATUS.md"
    if bg.is_file():
        lines.append("BACKGROUND STATUS:")
        for row in bg.read_text(encoding="utf-8").splitlines()[2:8]:
            if row.strip():
                lines.append(f"  {row.strip()}")
        lines.append("")

    lines.append("SOURCES:")
    aa = load_json(DATA / "progress.json")
    if isinstance(aa, dict):
        lines.extend(format_arbeitsagentur(aa, running["arbeitsagentur"]))

    ad = load_json(DATA / "progress_ausbildung_de.json")
    if isinstance(ad, dict):
        lines.extend(
            format_multi_category(
                ad,
                "ausbildung.de",
                SOURCE_LOGS["ausbildung_de"],
                running["ausbildung_de"],
            )
        )

    ae = load_json(DATA / "progress_meine_ausbildung_ae.json")
    if isinstance(ae, dict):
        lines.extend(
            format_meine(
                ae,
                "meine-ausbildung AE",
                SOURCE_LOGS["meine_ae"],
                running["meine_ae"],
            )
        )

    dpa = load_json(DATA / "progress_meine_ausbildung_dpa.json")
    if isinstance(dpa, dict):
        lines.extend(
            format_meine(
                dpa,
                "meine-ausbildung DPA",
                SOURCE_LOGS["meine_dpa"],
                running["meine_dpa"],
            )
        )

    nrw = load_json(DATA / "progress_ausbildung_nrw.json")
    if isinstance(nrw, dict):
        lines.extend(
            format_multi_category(
                nrw,
                "ausbildung.nrw",
                SOURCE_LOGS["ausbildung_nrw"],
                running["ausbildung_nrw"],
                extra_fields=["new_unique_vs_master", "cross_duplicates_with_master"],
            )
        )

    azu = load_json(DATA / "progress_azubiyo_de.json")
    if isinstance(azu, dict):
        lines.extend(
            format_multi_category(
                azu,
                "azubiyo.de",
                SOURCE_LOGS["azubiyo_de"],
                running["azubiyo_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    step = load_json(DATA / "progress_stepstone_de.json")
    if isinstance(step, dict):
        lines.extend(
            format_multi_category(
                step,
                "stepstone.de",
                SOURCE_LOGS["stepstone_de"],
                running["stepstone_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    indeed = load_json(DATA / "progress_indeed_de.json")
    if isinstance(indeed, dict):
        lines.extend(
            format_multi_category(
                indeed,
                "indeed.de",
                SOURCE_LOGS["indeed_de"],
                running["indeed_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    ast = load_json(DATA / "progress_ausbildungsstellen_de.json")
    if isinstance(ast, dict):
        lines.extend(
            format_multi_category(
                ast,
                "ausbildungsstellen.de",
                SOURCE_LOGS["ausbildungsstellen_de"],
                running["ausbildungsstellen_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    msd = load_json(DATA / "progress_meinestadt_de.json")
    if isinstance(msd, dict):
        lines.extend(
            format_multi_category(
                msd,
                "meinestadt.de",
                SOURCE_LOGS["meinestadt_de"],
                running["meinestadt_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    bij = load_json(DATA / "progress_backinjob_de.json")
    if isinstance(bij, dict):
        lines.extend(
            format_multi_category(
                bij,
                "backinjob.de",
                SOURCE_LOGS["backinjob_de"],
                running["backinjob_de"],
                extra_fields=[
                    "new_unique_vs_master",
                    "cross_duplicates_with_master",
                    "total_skipped_wrong_beruf",
                ],
            )
        )

    lines.append("")
    lines.append("PROSES AKTIF:")
    try:
        screen = subprocess.run(["screen", "-ls"], capture_output=True, text=True)
        screen_lines = screen.stdout.splitlines() if screen.returncode == 0 else []
    except OSError:
        screen_lines = []
    shown_screen = False
    for row in screen_lines:
        if any(
            token in row.lower()
            for token in (
                "meine",
                "ausbildung",
                "azubiyo",
                "stepstone",
                "indeed",
                "ausbildungsstellen",
                "meinestadt",
                "backinjob",
                "nrw",
                "socket",
                "scraper",
            )
        ):
            lines.append(f"  {row.strip()}")
            shown_screen = True
    if not shown_screen:
        lines.append("  (tidak ada sesi screen terkait)")

    procs = pgrep_lines(*SCRAPE_PATTERNS)
    if procs:
        for proc in procs[:10]:
            lines.append(f"  {proc}")
    else:
        lines.append("  (tidak ada proses scrape Python aktif)")

    lines.append("")
    lines.append("LOG TERAKHIR:")
    active_logs = [
        (name, path)
        for name, path in SOURCE_LOGS.items()
        if running.get(name) and path.is_file()
    ]
    if not active_logs:
        active_logs = [
            (name, path) for name, path in SOURCE_LOGS.items() if path.is_file()
        ]
    if not active_logs:
        lines.append("  (tidak ada log scrape)")
    else:
        for name, log_path in active_logs:
            lines.append(f"  [{name}] {last_log_line(log_path)}")

    lines.append("")
    lines.append("=" * 62)
    text = "\n".join(lines)
    md = (
        "# Live Scrape Status\n\n"
        f"**Updated:** {now}\n\n"
        "Snapshot otomatis dari `scripts/watch_progress.py`.\n\n"
        f"```\n{text}\n```\n"
    )
    return text, md


def main() -> int:
    parser = argparse.ArgumentParser(description="Real-time scrape progress monitor")
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=7,
        help="Refresh interval in seconds (default: 7)",
    )
    parser.add_argument("--once", action="store_true", help="Print once and exit")
    parser.add_argument(
        "--no-live-file",
        action="store_true",
        help="Do not write data/LIVE_STATUS.md",
    )
    args = parser.parse_args()
    interval = max(3, args.interval)

    try:
        while True:
            proc_blob = " ".join(pgrep_lines(*SCRAPE_PATTERNS))
            running = detect_running(proc_blob)
            text, md = build_display(running, interval)
            if not args.no_live_file:
                DATA.mkdir(parents=True, exist_ok=True)
                (DATA / "LIVE_STATUS.md").write_text(md, encoding="utf-8")
            if args.once:
                print(text)
                return 0
            os.system("clear" if os.name != "nt" else "cls")
            print(text)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nMonitor dihentikan.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
