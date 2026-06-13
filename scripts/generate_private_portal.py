#!/usr/bin/env python3
"""Generate local-only portal landing page with links to private tools."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / "data" / "private"
VIEWER = ROOT / "data" / "viewer" / "index.html"
BEWERBUNG = ROOT / "data" / "bewerbung" / "index.html"

HTML = """<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AusbildungHunter — Private Portal</title>
  <style>
    :root { --bg:#0f1419; --card:#1a2332; --text:#e7ecf3; --muted:#8b9cb3; --accent:#3d8bfd; --border:#2a3544; --warn:#f0c674; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; background:var(--bg); color:var(--text); line-height:1.55; }
    header { padding:1.5rem; border-bottom:1px solid var(--border); background:var(--card); }
    h1 { margin:0 0 .35rem; font-size:1.4rem; }
    .banner { background:rgba(240,198,116,.12); border:1px solid #6b5a2a; color:var(--warn); padding:.65rem 1rem; border-radius:8px; margin-top:.75rem; font-size:.9rem; }
    main { max-width:720px; margin:0 auto; padding:1.5rem; }
    .card { background:var(--card); border:1px solid var(--border); border-radius:12px; padding:1.1rem 1.25rem; margin-bottom:1rem; }
    .card h2 { margin:0 0 .35rem; font-size:1.05rem; }
    .card p { margin:.25rem 0 .75rem; color:var(--muted); font-size:.92rem; }
    a.btn { display:inline-block; text-decoration:none; background:rgba(61,139,253,.18); border:1px solid var(--accent); color:var(--accent); border-radius:8px; padding:.5rem .9rem; }
    .missing { color:#e88a7d; font-size:.88rem; }
    footer { text-align:center; color:var(--muted); font-size:.82rem; padding:1rem 1.5rem 2rem; }
  </style>
</head>
<body>
  <header>
    <h1>Private Portal — Local only</h1>
    <p style="color:var(--muted); margin:0">Personal Bewerbung data · never uploaded to GitHub</p>
    <div class="banner">⚠ PRIVATE — Contains real applicant profile and generated letters. Do not share this folder or commit to git.</div>
  </header>
  <main>
    <div class="card">
      <h2>Job database viewer</h2>
      <p>Same public listing data — open locally for offline use or future personal notes.</p>
      __VIEWER_LINK__
    </div>
    <div class="card">
      <h2>Personal Bewerbung Intelligence</h2>
      <p>Real Anschreiben, Motivationsschreiben, and email drafts from your profile.</p>
      __BEWERBUNG_LINK__
    </div>
    <div class="card">
      <h2>Setup Bewerbung (if missing)</h2>
      <p style="font-family:ui-monospace,monospace; font-size:.82rem; white-space:pre-wrap">cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
python scripts/generate_bewerbung_exports.py
python scripts/run_bewerbung_pilot.py --limit 10
python scripts/generate_bewerbung_ui.py</p>
    </div>
  </main>
  <footer>Generated locally · gitignored · data/private/</footer>
</body>
</html>
"""


def _link(path: Path, label: str) -> str:
    if path.is_file():
        href = path.as_uri()
        return f'<a class="btn" href="{href}">{label}</a>'
    return f'<p class="missing">Not found: {path.relative_to(ROOT)} — run the setup steps below.</p>'


def main() -> None:
    PRIVATE_DIR.mkdir(parents=True, exist_ok=True)
    html = HTML.replace("__VIEWER_LINK__", _link(VIEWER, "Open viewer"))
    html = html.replace("__BEWERBUNG_LINK__", _link(BEWERBUNG, "Open Bewerbung UI"))
    out = PRIVATE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
