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
    alamat_email_bewerbung: str = ""
    link_bewerbung: str = ""
    kontak_penanggung_jawab: str = ""
    dokumen_yang_harus_dipenuhi: str = ""
    ba_job_url: str = ""
    scraped_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in cls.__dataclass_fields__.values()]
