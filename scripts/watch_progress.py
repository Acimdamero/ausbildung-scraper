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
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LOGS = ROOT / "logs"


def load_json(path: Path) -> dict | list | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def master_count() -> int | None:
    data = load_json(DATA / "processed" / "master_bewerbung.json")
    return len(data) if isinstance(data, list) else None


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


def detect_running() -> dict[str, bool]:
    procs = " ".join(pgrep_lines("run_meine_ausbildung_de.py", "run_ausbildung_de.py"))
    return {
        "meine_ae": is_pid_running(LOGS / "meine_ausbildung_ae.pid")
        or "meine_ausbildung_ae" in procs,
        "meine_dpa": is_pid_running(LOGS / "meine_ausbildung_dpa.pid")
        or "meine_ausbildung_dpa" in procs,
        "ausbildung_de": is_pid_running(LOGS / "ausbildung_de_scrape.pid")
        or "run_ausbildung_de.py" in procs,
    }


def format_arbeitsagentur(data: dict) -> list[str]:
    lines = [
        f"  Arbeitsagentur: {data.get('total_scraped', 0)} scraped, "
        f"{data.get('total_failed', 0)} failed"
    ]
    for cat in data.get("categories", []):
        name = cat.get("category_name", cat.get("category_id", "?"))
        avail = cat.get("total_available", 0)
        scraped = cat.get("scraped_count", 0)
        lines.append(f"    • {name}: {scraped}/{avail} ({pct(scraped, avail)})")
    return lines


def format_ausbildung_de(data: dict) -> list[str]:
    lines = [
        f"  ausbildung.de: {data.get('total_scraped', 0)} scraped, "
        f"master merge {data.get('merged_master_total', '—')}"
    ]
    for cat in data.get("categories", []):
        cid = cat.get("category_id", "?")
        disc = cat.get("discovered_urls", 0)
        scraped = cat.get("scraped", 0)
        failed = cat.get("failed", 0)
        lines.append(
            f"    • {cid}: {scraped}/{disc} ({pct(scraped, disc)}), failed {failed}"
        )
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


def build_display(running: dict[str, bool], interval: int) -> tuple[str, str]:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "=" * 62,
        "  AUSBILDUNG SCRAPER — LIVE PROGRESS",
        f"  {now}  (refresh {interval}s, Ctrl+C keluar)",
        "=" * 62,
        "",
        f"MASTER TOTAL: {master_count() or '?'} listing (master_bewerbung.json)",
        "",
    ]

    bg = DATA / "BACKGROUND_STATUS.md"
    if bg.is_file():
        lines.append("BACKGROUND STATUS:")
        for row in bg.read_text(encoding="utf-8").splitlines()[2:6]:
            if row.strip():
                lines.append(f"  {row.strip()}")
        lines.append("")

    lines.append("SOURCES:")
    aa = load_json(DATA / "progress.json")
    if isinstance(aa, dict):
        lines.extend(format_arbeitsagentur(aa))

    ad = load_json(DATA / "progress_ausbildung_de.json")
    if isinstance(ad, dict):
        lines.extend(format_ausbildung_de(ad))

    ae = load_json(DATA / "progress_meine_ausbildung_ae.json")
    if isinstance(ae, dict):
        lines.extend(
            format_meine(
                ae,
                "meine-ausbildung AE",
                LOGS / "meine_ausbildung_ae.log",
                running["meine_ae"],
            )
        )

    dpa = load_json(DATA / "progress_meine_ausbildung_dpa.json")
    if isinstance(dpa, dict):
        lines.extend(
            format_meine(
                dpa,
                "meine-ausbildung DPA",
                LOGS / "meine_ausbildung_dpa.log",
                running["meine_dpa"],
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
        if any(token in row.lower() for token in ("meine", "ausbildung", "socket")):
            lines.append(f"  {row.strip()}")
            shown_screen = True
    if not shown_screen:
        lines.append("  (tidak ada sesi screen terkait)")

    procs = pgrep_lines("run_meine_ausbildung_de.py", "run_ausbildung_de.py")
    if procs:
        for proc in procs[:6]:
            lines.append(f"  {proc}")
    else:
        lines.append("  (tidak ada proses scrape Python aktif)")

    lines.append("")
    lines.append("LOG TERAKHIR:")
    if running["meine_ae"]:
        log_targets = [("meine_ae", LOGS / "meine_ausbildung_ae.log")]
    elif running["meine_dpa"]:
        log_targets = [("meine_dpa", LOGS / "meine_ausbildung_dpa.log")]
    elif running["ausbildung_de"]:
        log_targets = [("ausbildung_de", LOGS / "ausbildung_de_scrape.log")]
    else:
        log_targets = [
            ("meine_ae", LOGS / "meine_ausbildung_ae.log"),
            ("meine_dpa", LOGS / "meine_ausbildung_dpa.log"),
        ]
    for name, log_path in log_targets:
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
            running = detect_running()
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
