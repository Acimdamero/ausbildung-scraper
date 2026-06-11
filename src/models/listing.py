from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class AusbildungListing:
    """Normalized apprenticeship listing for export."""

    referenznummer: str
    category_id: str
    nama_perusahaan: str = ""
    titik_data_di_peta: str = ""
    posisi_kota: str = ""
    alamat_detail: str = ""
    detail_deskripsi: str = ""
    gaji: str = ""
    persyaratan: str = ""
    jenis_ausbildung: str = ""
    deskripsi_perusahaan: str = ""
    apa_yang_ditawarkan: str = ""
    link_website_perusahaan: str = ""
    link_website_perusahaan_resmi: str = ""
    website_type: str = ""
    alamat_email_bewerbung: str = ""
    link_bewerbung: str = ""
    link_bewerbung_externe: str = ""
    link_bewerbung_efektif: str = ""
    bewerbung_sumber: str = ""
    kontak_penanggung_jawab: str = ""
    dokumen_yang_harus_dipenuhi: str = ""
    ba_job_url: str = ""
    sumber_data: str = ""
    ausbildung_de_url: str = ""
    is_duplicate_of_arbeitsagentur: bool = False
    duplicate_of_refnr: str = ""
    kelengkapan_score: int = 0
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in cls.__dataclass_fields__.values()]
