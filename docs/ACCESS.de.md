# Zugangsleitfaden — Projekt öffnen & prüfen

Jeder kann **AusbildungHunter Intelligence** klonen, ausführen und prüfen — ohne Zugriff auf private Bewerbungsdaten des Autors.

| Sprache | Dokument |
|---------|----------|
| English | [ACCESS.md](ACCESS.md) |

---

## Schnelllinks

| Ressource | URL / Pfad |
|-----------|------------|
| Repository | https://github.com/Acimdamero/ausbildung-scraper |
| Live-Stellenviewer (GitHub Pages) | https://acimdamero.github.io/ausbildung-scraper/ |
| Bewerbungs-UI-Demo (Beispieldaten) | `data/public/bewerbung-demo/index.html` |
| Architektur | [ARCHITECTURE.de.md](ARCHITECTURE.de.md) |
| Datenschutz | [PRIVACY.md](PRIVACY.md) |

---

## Für Reviewer (ohne Setup)

1. **Live-Demo öffnen:** [Stellenviewer](https://acimdamero.github.io/ausbildung-scraper/)
2. Nach Unternehmen, Stadt oder Stichwort suchen; nach Quellportal filtern
3. **Bewerbungs-UI-Struktur** ansehen (keine echten personenbezogenen Daten): Repository klonen und `data/public/bewerbung-demo/index.html` im Browser öffnen

> Wenn die GitHub-Pages-URL 404 zurückgibt, muss Pages einmalig unter **Settings → Pages → GitHub Actions** aktiviert werden.

---

## Für Entwickler (vollständiges lokales Setup)

```bash
git clone https://github.com/Acimdamero/ausbildung-scraper.git
cd ausbildung-scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # erforderlich für browserbasierte Scraper
cp .env.example .env
```

### Stellendatenbank lokal ansehen

```bash
open data/viewer/index.html
# oder aus verarbeitetem JSON neu generieren:
python scripts/generate_viewer.py && open data/viewer/index.html
```

### Bewerbungs-Pipeline ausführen (privat — nur auf Ihrem Rechner)

```bash
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
# user_profile.local.py bearbeiten

python scripts/generate_bewerbung_exports.py
python scripts/run_bewerbung_pilot.py --limit 10
python scripts/generate_bewerbung_ui.py
open data/bewerbung/index.html
```

Die Ausgabe bleibt in gitignored Pfaden — wird niemals zu GitHub gepusht.

---

## Für Helfer beim Bewerbungstext-Review

Der Autor kann **geschwärzte Exporte** oder Bildschirmaufnahmen aus der lokalen UI teilen. Das öffentliche Repository enthält absichtlich keine echten Anschreiben oder Motivationsschreiben.

**Empfohlene Review-Checkliste:**

- [ ] Deutsche Grammatik und Ton (Sie-Form, formelle Struktur)
- [ ] Unternehmensspezifische Absätze (kein generisches Copy-Paste)
- [ ] Motivation für den FI-AE-Wechsel ist klar formuliert
- [ ] Kontaktblock ist korrekt (nur lokal prüfen)
- [ ] E-Mail-Betreff enthält Ausbildungstitel und Referenznummer falls vorhanden

### Was sicher geteilt werden kann

| Ziel | Sicherer Weg |
|------|--------------|
| Stellendatenbank zeigen | GitHub-Pages-Viewer-URL teilen |
| Briefstruktur prüfen | `data/public/bewerbung-demo/` oder lokal geschwärzte PDFs |
| Echte Briefe prüfen | Dateien direkt senden (E-Mail/USB) — nicht über öffentliches Repo |

---

## HTTP-Server (optional)

```bash
# Stellenviewer
python -m http.server 8765 --directory data/viewer

# Bewerbungs-Demo (öffentlich sicher)
python -m http.server 8766 --directory data/public/bewerbung-demo
```

Dann `http://localhost:8765` oder `http://localhost:8766` im Browser öffnen.

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Viewer leer | `python scripts/dedup_data.py` dann `python scripts/generate_viewer.py` ausführen |
| Bewerbungs-Pilot schlägt fehl: kein Profil | `user_profile.local.py` aus dem Beispiel erstellen |
| Playwright-Scraper schlägt fehl | `playwright install chromium` |
| GitHub Pages 404 | Pages unter Repo Settings → Pages → GitHub Actions aktivieren |

Siehe auch [github-pages-setup.md](github-pages-setup.md).
