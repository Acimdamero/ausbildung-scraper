"""Client for the Arbeitsagentur Jobsuche REST API (jobsuche.api.bund.dev)."""

from __future__ import annotations

import base64
import logging
import time
from typing import Any, Iterator

import requests

logger = logging.getLogger(__name__)


class JobsucheClient:
    """Thin wrapper around the Bundesagentur Jobsuche API."""

    def __init__(
        self,
        base_url: str = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
        api_key: str = "jobboerse-jobsuche",
        request_delay: float = 0.3,
        timeout: int = 30,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.request_delay = request_delay
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": self.api_key})

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        response = self._session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        if self.request_delay > 0:
            time.sleep(self.request_delay)
        return response.json()

    @staticmethod
    def encode_refnr(referenznummer: str) -> str:
        return base64.b64encode(referenznummer.encode()).decode()

    def search_jobs(
        self,
        was: str,
        angebotsart: int = 4,
        page: int = 1,
        size: int = 25,
    ) -> dict[str, Any]:
        """Search apprenticeship listings (angebotsart=4 = Ausbildung)."""
        return self._get(
            "/pc/v6/jobs",
            params={
                "was": was,
                "angebotsart": angebotsart,
                "page": page,
                "size": size,
            },
        )

    def get_job_details(self, referenznummer: str) -> dict[str, Any]:
        encoded = self.encode_refnr(referenznummer)
        return self._get(f"/pc/v4/jobdetails/{encoded}")

    def iter_search_pages(
        self,
        was: str,
        angebotsart: int = 4,
        page_size: int = 25,
        max_pages: int | None = 1,
    ) -> Iterator[dict[str, Any]]:
        """Yield search result pages; max_pages=None means all pages."""
        page = 1
        while True:
            result = self.search_jobs(was=was, angebotsart=angebotsart, page=page, size=page_size)
            yield result

            total = result.get("maxErgebnisse", 0)
            fetched = page * page_size
            if fetched >= total:
                break
            if max_pages is not None and page >= max_pages:
                break
            page += 1
