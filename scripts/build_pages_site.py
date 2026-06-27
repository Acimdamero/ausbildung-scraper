#!/usr/bin/env python3
"""Assemble public-safe GitHub Pages site under data/public/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "data" / "public"
VIEWER_SRC = ROOT / "data" / "viewer" / "index.html"
VIEWER_DST = PUBLIC / "viewer" / "index.html"
DEMO_SRC = ROOT / "data" / "public" / "bewerbung-demo" / "index.html"

LANDING_HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AusbildungHunter Intelligence — Public Demo</title>
  <style>
    :root { --bg:#0f1419; --card:#1a2332; --text:#e7ecf3; --muted:#8b9cb3; --accent:#3d8bfd; --border:#2a3544; --ok:#7ddea2; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }
    header { padding:2rem 1.5rem 1.5rem; border-bottom:1px solid var(--border); background:var(--card); text-align:center; }
    h1 { margin:0 0 .5rem; font-size:1.75rem; }
    .tagline { color:var(--muted); max-width:640px; margin:0 auto; }
    .banner { display:inline-block; margin-top:1rem; padding:.45rem .85rem; border-radius:999px; border:1px solid #2d6b47; color:var(--ok); font-size:.85rem; }
    main { max-width:760px; margin:0 auto; padding:1.5rem; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:14px; padding:1.25rem 1.35rem; margin-bottom:1rem; }
    .card h2 { margin:0 0 .35rem; font-size:1.15rem; }
    .card p { margin:.35rem 0 .85rem; color:var(--muted); font-size:.95rem; }
    a.btn { display:inline-block; text-decoration:none; background:rgba(61,139,253,.18); border:1px solid var(--accent); color:var(--accent); border-radius:10px; padding:.55rem 1rem; font-weight:600; }
    a.btn:hover { background:rgba(61,139,253,.3); }
    a.btn.secondary { background:transparent; border-color:var(--border); color:var(--text); margin-left:.5rem; }
    footer { text-align:center; color:var(--muted); font-size:.85rem; padding:1rem 1.5rem 2rem; border-top:1px solid var(--border); }
    footer a { color:var(--accent); }
    table { width:100%; border-collapse:collapse; font-size:.92rem; margin-top:.75rem; }
    th, td { text-align:left; padding:.55rem .4rem; border-bottom:1px solid var(--border); vertical-align:top; }
    th { color:var(--muted); font-weight:600; font-size:.78rem; text-transform:uppercase; letter-spacing:.03em; }
    code { background:var(--bg); padding:.12rem .35rem; border-radius:4px; font-size:.88em; }
  </style>
</head>
<body>
  <header>
    <h1>AusbildungHunter Intelligence</h1>
    <p class="tagline">Multi-portal FI apprenticeship discovery — public demo with job listings and sample Bewerbung UI. No personal applicant data.</p>
    <span class="banner">PUBLIC · Safe to share</span>
  </header>
  <main>
    <div class="card">
      <h2>Job database viewer</h2>
      <p>Search 8,500+ deduplicated apprenticeship listings from 15 German portals. Public job data only — no applicant PII.</p>
      <a class="btn" href="viewer/">Open viewer</a>
    </div>
    <div class="card">
      <h2>Bewerbung UI demo</h2>
      <p>Sample application documents (Max Mustermann, example.com). Shows UI structure — not real personal data.</p>
      <a class="btn" href="bewerbung-demo/">Open demo</a>
    </div>
    <div class="card">
      <h2>Public vs private</h2>
      <table>
        <thead><tr><th>Public (this site)</th><th>Private (local only)</th></tr></thead>
        <tbody>
          <tr><td>Job listings viewer</td><td>Personal Bewerbung with real profile</td></tr>
          <tr><td>Sample Bewerbung demo</td><td><code>user_profile.local.py</code></td></tr>
          <tr><td>Scraper code on GitHub</td><td><code>data/bewerbung/</code>, enriched JSON</td></tr>
        </tbody>
      </table>
      <p style="margin-top:1rem">Clone the repo and run <code>scripts/open_private.sh</code> for your personal version.</p>
      <a class="btn secondary" href="https://github.com/Acimdamero/ausbildung-scraper">View repository</a>
    </div>
  </main>
  <footer>
    <a href="https://github.com/Acimdamero/ausbildung-scraper/blob/main/docs/PRIVACY.md">Privacy policy</a>
    · MIT License · AusbildungHunter Intelligence
  </footer>
</body>
</html>
"""


def build() -> None:
    viewer_script = ROOT / "scripts" / "generate_viewer.py"
    if not viewer_script.is_file():
        print(f"ERROR: missing viewer generator: {viewer_script}", file=sys.stderr)
        sys.exit(1)
    if not DEMO_SRC.is_file():
        print(f"ERROR: missing demo source: {DEMO_SRC}", file=sys.stderr)
        sys.exit(1)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    VIEWER_DST.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(viewer_script),
            "--public",
            "--source",
            "processed",
            "--output",
            str(VIEWER_DST),
        ],
        cwd=ROOT,
        check=True,
    )
    if not VIEWER_DST.is_file():
        print(f"ERROR: missing public viewer after build: {VIEWER_DST}", file=sys.stderr)
        sys.exit(1)

    PUBLIC.mkdir(parents=True, exist_ok=True)
    VIEWER_DST.parent.mkdir(parents=True, exist_ok=True)
    viewer_html = VIEWER_DST.read_text(encoding="utf-8")
    public_banner = (
        '<div class="public-banner">'
        "PUBLIC · Job listings only · No applicant PII · "
        '<a href="../">Back to demo home</a></div>'
    )
    viewer_html = viewer_html.replace("<h1>Ausbildung Listings Viewer</h1>", 
        "<h1>Ausbildung Listings Viewer</h1>\n    " + public_banner, 1)
    VIEWER_DST.write_text(viewer_html, encoding="utf-8")
    (PUBLIC / "index.html").write_text(LANDING_HTML, encoding="utf-8")
    print(f"Built public site at {PUBLIC.relative_to(ROOT)}/")
    print(f"  - index.html (landing)")
    print(f"  - viewer/index.html")
    print(f"  - bewerbung-demo/index.html")


if __name__ == "__main__":
    build()
