# Zugangsleitfaden — Projekt öffnen & prüfen

Jeder kann **AusbildungHunter Intelligence** klonen, ausführen und prüfen — ohne Zugriff auf private Bewerbungsdaten des Autors.

| Sprache | Dokument |
|---------|----------|
| English | [ACCESS.md](ACCESS.md) |

## Öffentlich vs. privat — Link-Tabelle

### Öffentlich (GitHub Pages — sicher teilbar)

| Link | Inhalt |
|------|--------|
| https://acimdamero.github.io/ausbildung-scraper/ | Startseite mit Links |
| https://acimdamero.github.io/ausbildung-scraper/viewer/ | Stellendatenbank (6.850+ Einträge, keine PII) |
| https://acimdamero.github.io/ausbildung-scraper/bewerbung-demo/ | Bewerbungs-UI-Demo (Max Mustermann, keine echten Daten) |
| https://github.com/Acimdamero/ausbildung-scraper | Quellcode & Dokumentation |

Im Browser öffnen:

```bash
./scripts/open_public.sh
```

### Privat (nur lokal — Ihr Rechner)

| Link / Befehl | Inhalt |
|---------------|--------|
| `./scripts/open_private.sh` | Lokales Portal mit Links zu Viewer + persönlicher Bewerbung |
| `file://…/data/viewer/index.html` | Stellenviewer (gleiche öffentliche Daten, offline) |
| `file://…/data/bewerbung/index.html` | Persönliche Bewerbung mit echtem Profil & Briefen |
| `src/bewerbung/user_profile.local.py` | Echter Name, Adresse, E-Mail (gitignored) |

Persönliche Bewerbungs-UI erzeugen:

```bash
cp src/bewerbung/user_profile.example.py src/bewerbung/user_profile.local.py
python scripts/generate_bewerbung_exports.py
python scripts/run_bewerbung_pilot.py --limit 10
python scripts/generate_bewerbung_ui.py
./scripts/open_private.sh
```

---

## Schnelllinks

| Ressource | URL / Pfad |
|-----------|------------|
| Repository | https://github.com/Acimdamero/ausbildung-scraper |
| Live-Demo (Startseite) | https://acimdamero.github.io/ausbildung-scraper/ |
| Stellenviewer (Pages) | https://acimdamero.github.io/ausbildung-scraper/viewer/ |
| Bewerbungs-Demo (Pages) | https://acimdamero.github.io/ausbildung-scraper/bewerbung-demo/ |
| Architektur | [ARCHITECTURE.de.md](ARCHITECTURE.de.md) |
| Datenschutz | [PRIVACY.md](PRIVACY.md) |

---

## Für Reviewer (ohne Setup)

1. **Live-Demo öffnen:** [Startseite](https://acimdamero.github.io/ausbildung-scraper/)
2. **Viewer öffnen** — nach Unternehmen, Stadt oder Stichwort suchen; nach Quellportal filtern
3. **Demo öffnen** für Bewerbungs-UI-Struktur (nur Beispieldaten, keine PII)

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
./scripts/open_private.sh
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
| Stellendatenbank zeigen | GitHub-Pages-URLs (Startseite oder `/viewer/`) |
| Briefstruktur prüfen | `/bewerbung-demo/` oder lokal geschwärzte PDFs |
| Echte Briefe prüfen | Dateien direkt senden (E-Mail/USB) — nicht über öffentliches Repo |

---

## HTTP-Server (optional)

```bash
# Stellenviewer
python -m http.server 8765 --directory data/viewer

# Öffentliche Demo (lokaler Build)
python scripts/build_pages_site.py
python -m http.server 8766 --directory data/public
```

Dann `http://localhost:8765` oder `http://localhost:8766` im Browser öffnen.

---

## Fehlerbehebung

| Problem | Lösung |
|---------|--------|
| Viewer leer | `python scripts/dedup_data.py` dann `python scripts/generate_viewer.py` ausführen |
| Bewerbungs-Pilot schlägt fehl: kein Profil | `user_profile.local.py` aus dem Beispiel erstellen |
| Playwright-Scraper schlägt fehl | `playwright install chromium` |
| GitHub Pages 404 | Repository muss **öffentlich** sein (Free-Plan). Pages aktivieren: Settings → Pages → GitHub Actions. Workflow erneut ausführen. |

Siehe auch [github-pages-setup.md](github-pages-setup.md).
