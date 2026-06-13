"""Example applicant profile — copy to user_profile.local.py and fill in your details."""

from __future__ import annotations

from typing import Any

USER_PROFILE: dict[str, Any] = {
    "vorname": "Max",
    "nachname": "Mustermann",
    "voller_name": "Max Mustermann",
    "geburtsdatum": "01.01.2000",
    "wohnort": "Berlin",
    "bundesland": "Berlin",
    "land": "Deutschland",
    "email": "max.mustermann@example.com",
    "telefon": "+49 30 12345678",
    "nationalitaet": "Deutsch",
    "schulabschluss_de": "Abitur",
    "schulabschluss_id": "Lulusan SMA",
    "deutsch_niveau": "C1 (Muttersprache)",
    "englisch_niveau": "B2",
    "aktuelle_ausbildung": "",
    "wechsel_motivation_de": (
        "Ich möchte eine Ausbildung zum Fachinformatiker Anwendungsentwicklung beginnen, "
        "weil mich Softwareentwicklung schon länger fasziniert."
    ),
    "wechsel_motivation_id": (
        "Saya ingin memulai Ausbildung Fachinformatiker Anwendungsentwicklung "
        "karena saya tertarik pada pengembangan perangkat lunak."
    ),
    "portfolio_hinweis_de": "Ich habe kleine Programmierprojekte in Python und JavaScript umgesetzt.",
    "portfolio_hinweis_id": "Saya memiliki proyek kecil Python dan JavaScript.",
    "signature_de": "Mit freundlichen Grüßen\nMax Mustermann\nBerlin",
    "signature_id": "Hormat saya,\nMax Mustermann\nBerlin",
}
