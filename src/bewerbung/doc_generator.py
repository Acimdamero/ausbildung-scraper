"""Generate personalized Bewerbung documents (DE + ID)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.bewerbung.contact_extractor import _clean_email
from src.bewerbung.user_profile import get_profile


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _salutation(ansprechpartner: dict[str, str], fallback: str = "Sehr geehrte Damen und Herren") -> str:
    anrede = ansprechpartner.get("anrede", "").strip()
    name = ansprechpartner.get("name", "").strip()
    if anrede and name:
        return f"Sehr geehrte{'r' if anrede == 'Herr' else ''} {anrede} {name}"
    if anrede:
        return f"Sehr geehrte{'r' if anrede == 'Herr' else ''} {anrede}"
    return fallback


def _salutation_id(ansprechpartner: dict[str, str]) -> str:
    anrede = ansprechpartner.get("anrede", "").strip()
    name = ansprechpartner.get("name", "").strip()
    if anrede == "Frau" and name:
        return f"Yth. Ibu {name}"
    if anrede == "Herr" and name:
        return f"Yth. Bapak {name}"
    return "Yth. Tim Rekrutmen"


def _company(listing: dict[str, Any]) -> str:
    return str(listing.get("nama_perusahaan", "") or "Ihr Unternehmen").strip()


def _role(listing: dict[str, Any]) -> str:
    return str(
        listing.get("jenis_ausbildung", "")
        or "Fachinformatiker/in Anwendungsentwicklung"
    ).strip()


def _city(listing: dict[str, Any]) -> str:
    return str(listing.get("posisi_kota", "") or "").strip()


def _start_hint(listing: dict[str, Any]) -> str:
    year = listing.get("tahun_mulai")
    month = listing.get("bulan_mulai")
    if year and month:
        return f"{int(month):02d}.{year}"
    if year:
        return str(year)
    return "wie ausgeschrieben"


def generate_documents(
    listing: dict[str, Any],
    enriched: dict[str, Any],
) -> dict[str, str]:
    profile = get_profile()
    company = _company(listing)
    role = _role(listing)
    city = _city(listing)
    start = _start_hint(listing)
    ap = enriched.get("ansprechpartner") or {}
    recherche = enriched.get("firmen_recherche") or {}
    salutation = _salutation(ap)
    salutation_id = _salutation_id(ap)
    ref = listing.get("referenznummer", "")

    anschreiben_de = f"""{profile['voller_name']}
{profile['wohnort']}
{profile['email']}

{company}
{city}

{salutation},

hiermit bewerbe ich mich um einen Ausbildungsplatz als {role} mit Beginn {start}.

{profile['wechsel_motivation_de']} Ich bringe einen {profile['schulabschluss_de']} mit sowie Deutschkenntnisse auf Niveau {profile['deutsch_niveau']}. {profile['portfolio_hinweis_de']}

Besonders reizt mich an {company}, dass {recherche.get('projekte', 'Sie moderne Softwarelösungen entwickeln')[:200]}. {recherche.get('relevanz_profil', '')[:250]}

Gerne überzeuge ich Sie in einem persönlichen Gespräch von meiner Motivation und Lernbereitschaft.

{profile['signature_de']}
"""

    anschreiben_id = f"""{profile['voller_name']}
{profile['wohnort']}
{profile['email']}

{company}
{city}

{salutation_id},

Dengan hormat saya melamar posisi Ausbildung {role} dengan mulai {start}.

{profile['wechsel_motivation_id']} Saya lulus {profile['schulabschluss_id']} dan memiliki kemampuan bahasa Jerman {profile['deutsch_niveau']}. {profile['portfolio_hinweis_id']}

Yang menarik perhatian saya dari {company}: {recherche.get('projekte', 'pengembangan perangkat lunak modern')[:200]}.

Saya siap membuktikan motivasi saya dalam wawancara.

{profile['signature_id']}
"""

    motivationsschreiben_de = f"""Motivationsschreiben — {role}
{company}, {city}

1. Persönlicher Werdegang
Mein Name ist {profile['voller_name']}. Ich wohne in {profile['wohnort']} ({profile['bundesland']}) und habe meinen Schulabschluss in Indonesien abgeschlossen (beglaubigte deutsche Übersetzung vorhanden). Seit September 2025 absolviere ich eine Ausbildung zum Hotelfachmann. Dabei wurde mir deutlich, dass meine wirkliche Begeisterung der Informationstechnologie und der Softwareentwicklung gilt.

2. Warum Fachinformatiker Anwendungsentwicklung?
Ich möchte strukturiert lernen, wie Anwendungen konzipiert, programmiert und getestet werden. Die Stelle bei {company} in {city} passt zu diesem Ziel, weil {recherche.get('branche', 'IT')} und {recherche.get('kultur', 'eine praxisnahe Ausbildung')[:150]}.

3. Meine Stärken
- Lernbereitschaft und Ausdauer (Deutsch B2 erreicht, Alltag in Deutschland)
- Analytisches Denken und Teamarbeit aus Hotelfach-Ausbildung
- Erste Programmiererfahrung ({profile['portfolio_hinweis_de']})

4. Warum {company}?
{recherche.get('relevanz_profil', f'Ich schätze die Möglichkeit, bei {company} praxisnah Softwareentwicklung zu lernen.')}

Ich freue mich auf Ihre Rückmeldung.

{profile['signature_de']}
"""

    motivationsschreiben_id = f"""Surat Motivasi — {role}
{company}, {city}

1. Latar belakang
Nama saya {profile['voller_name']}, domisili {profile['wohnort']}. Saya lulus SMA di Indonesia (ada terjemahan resmi Jerman). Sejak September 2025 saya menjalani Ausbildung Hotelfachmann dan menyadari passion saya di IT.

2. Mengapa FI Anwendungsentwicklung?
Saya ingin belajar membuat, menguji, dan memelihara aplikasi perangkat lunak. Posisi di {company} ({city}) sejalan dengan tujuan ini.

3. Kelebihan
- Motivasi belajar tinggi, sertifikat Jerman B2
- Pengalaman kerja tim dari hotel
- {profile['portfolio_hinweis_id']}

4. Mengapa {company}?
{recherche.get('relevanz_profil', f'Kesempatan belajar langsung di {company}.')[:300]}

Terima kasih atas pertimbangannya.

{profile['signature_id']}
"""

    bewerbungsschreiben_de = anschreiben_de  # Combined cover letter variant

    bewerbungsschreiben_id = anschreiben_id

    apply_email = _clean_email(str(listing.get("alamat_email_bewerbung", "") or ""))
    subject_de = f"Bewerbung Ausbildung {role} — {profile['nachname']}, Ref. {ref}"
    subject_id = f"Lamaran Ausbildung {role} — {profile['nachname']}"

    portal_note = ""
    if enriched.get("portal_only"):
        portal_note = (
            "\n\n[HINWEIS: Bewerbung vermutlich nur über Unternehmensportal — "
            "E-Mail dient als Anfrage/Erstkontakt, Anhänge separat hochladen.]"
        )

    email_draft_de = f"""An: {apply_email or '(E-Mail aus Stellenanzeige eintragen)'}
Betreff: {subject_de}

{salutation},

anbei sende ich Ihnen meine Bewerbungsunterlagen für die Ausbildung als {role} (Beginn {start}):

- Anschreiben
- Motivationsschreiben
- Lebenslauf
- Zeugnisse (SMA Indonesia, beglaubigte Übersetzung)
- Goethe-Zertifikat B2

Kurz zu mir: Ich wechsle motiviert aus der laufenden Hotelfachmann-Ausbildung in die IT, wohne in {profile['wohnort']} und bringe {profile['deutsch_niveau']} mit.

Bei Rückfragen erreichen Sie mich unter {profile['email']}.

{profile['signature_de']}{portal_note}
"""

    email_draft_id = f"""Kepada: {apply_email or '(isi email dari lowongan)'}
Subjek: {subject_id}

{salutation_id},

Terlampir dokumen lamaran Ausbildung {role} (mulai {start}):
Anschreiben, surat motivasi, CV, ijazah SMA + terjemahan resmi, sertifikat Goethe B2.

Saya pindah motivasi dari Hotelfachmann ke IT, domisili {profile['wohnort']}, bahasa Jerman {profile['deutsch_niveau']}.

Kontak: {profile['email']}

{profile['signature_id']}
"""

    return {
        "motivationsschreiben_de": motivationsschreiben_de.strip(),
        "motivationsschreiben_id": motivationsschreiben_id.strip(),
        "anschreiben_de": anschreiben_de.strip(),
        "anschreiben_id": anschreiben_id.strip(),
        "bewerbungsschreiben_de": bewerbungsschreiben_de.strip(),
        "bewerbungsschreiben_id": bewerbungsschreiben_id.strip(),
        "email_draft_de": email_draft_de.strip(),
        "email_draft_id": email_draft_id.strip(),
        "email_subject_de": subject_de,
        "email_subject_id": subject_id,
        "_generated_at": _now_iso(),
    }


def apply_docs_to_enriched(enriched: dict[str, Any], docs: dict[str, str]) -> dict[str, Any]:
    enriched = dict(enriched)
    public_docs = {k: v for k, v in docs.items() if not k.startswith("_")}
    enriched["bewerbung_docs"] = public_docs
    enriched["docs_generated_at"] = docs.get("_generated_at", _now_iso())
    if enriched.get("bewerbung_status") in ("pending", "researched"):
        enriched["bewerbung_status"] = "draft_ready"
    enriched["updated_at"] = _now_iso()
    return enriched
