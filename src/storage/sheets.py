"""Google Sheets export via gspread service account."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.listing import AusbildungListing

logger = logging.getLogger(__name__)


class GoogleSheetsExporter:
    def __init__(
        self,
        spreadsheet_id: str,
        credentials_path: str | Path,
    ) -> None:
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = Path(credentials_path)
        self._client = None
        self._spreadsheet = None

    def _connect(self):
        if self._spreadsheet is not None:
            return self._spreadsheet

        try:
            import gspread
            from google.oauth2.service_account import Credentials
        except ImportError as exc:
            raise RuntimeError(
                "gspread and google-auth required for Sheets export. "
                "Run: pip install gspread google-auth"
            ) from exc

        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Service account JSON not found: {self.credentials_path}"
            )

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(
            str(self.credentials_path), scopes=scopes
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def export_listings(
        self,
        tab_name: str,
        listings: list[AusbildungListing],
    ) -> None:
        from src.models.listing import AusbildungListing

        spreadsheet = self._connect()
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except Exception:
            worksheet = spreadsheet.add_worksheet(
                title=tab_name, rows=max(100, len(listings) + 10), cols=20
            )

        headers = AusbildungListing.field_names()
        rows = [headers]
        for item in listings:
            row = [item.to_dict().get(h, "") for h in headers]
            rows.append(row)

        worksheet.clear()
        worksheet.update(rows, value_input_option="RAW")
        logger.info("Exported %d rows to sheet tab '%s'", len(listings), tab_name)
