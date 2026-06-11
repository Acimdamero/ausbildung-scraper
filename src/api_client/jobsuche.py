"""Client for the Arbeitsagentur Jobsuche REST API (jobsuche.api.bund.dev)."""

from __future__ import annotations

import base64
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Iterator

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, Timeout

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class RateLimiter:
    """Thread-safe minimum interval between API requests."""

    def __init__(self, delay: float) -> None:
        self.delay = max(0.0, delay)
        self._lock = threading.Lock()
        self._last_request = 0.0

    def wait(self) -> None:
        if self.delay <= 0:
            return
        with self._lock:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self._last_request = time.monotonic()


class JobsucheClient:
    """Thin wrapper around the Bundesagentur Jobsuche API."""

    def __init__(
        self,
        base_url: str = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service",
        api_key: str = "jobboerse-jobsuche",
        request_delay: float = 0.3,
        timeout: int = 30,
        max_retries: int = 3,
        retry_backoff: float = 2.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.request_delay = request_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._rate_limiter = RateLimiter(request_delay)
        self._session = requests.Session()
        self._session.headers.update({"X-API-Key": self.api_key})
        self._thread_local = threading.local()

    def _session_for_thread(self) -> requests.Session:
        session = getattr(self._thread_local, "session", None)
        if session is None:
            session = requests.Session()
            session.headers.update({"X-API-Key": self.api_key})
            self._thread_local.session = session
        return session

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        session = self._session_for_thread()
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            self._rate_limiter.wait()
            try:
                response = session.get(url, params=params, timeout=self.timeout)
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise HTTPError(
                        f"HTTP {response.status_code}",
                        response=response,
                    )
                response.raise_for_status()
                return response.json()
            except (RequestsConnectionError, Timeout, HTTPError) as exc:
                last_exc = exc
                status = getattr(getattr(exc, "response", None), "status_code", None)
                retryable = isinstance(exc, (RequestsConnectionError, Timeout)) or (
                    status in RETRYABLE_STATUS_CODES
                )
                if attempt < self.max_retries and retryable:
                    wait = self.retry_backoff ** attempt
                    logger.warning(
                        "Request failed (%s), retry %d/%d in %.1fs: %s",
                        path,
                        attempt + 1,
                        self.max_retries,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    continue
                raise

        raise last_exc or RuntimeError("Request failed without exception")

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

    def fetch_details_parallel(
        self,
        referenznummern: list[str],
        *,
        max_workers: int = 1,
        on_progress: Callable[[str, dict[str, Any] | None, Exception | None], None]
        | None = None,
    ) -> list[tuple[str, dict[str, Any] | None, Exception | None]]:
        """Fetch job details concurrently; returns (refnr, detail, error) tuples."""
        if not referenznummern:
            return []

        workers = max(1, max_workers)
        if workers == 1:
            results: list[tuple[str, dict[str, Any] | None, Exception | None]] = []
            for refnr in referenznummern:
                try:
                    detail = self.get_job_details(refnr)
                    results.append((refnr, detail, None))
                    if on_progress:
                        on_progress(refnr, detail, None)
                except Exception as exc:
                    results.append((refnr, None, exc))
                    if on_progress:
                        on_progress(refnr, None, exc)
            return results

        results_map: dict[str, tuple[str, dict[str, Any] | None, Exception | None]] = {}

        def _fetch(refnr: str) -> tuple[str, dict[str, Any] | None, Exception | None]:
            try:
                detail = self.get_job_details(refnr)
                return refnr, detail, None
            except Exception as exc:
                return refnr, None, exc

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(_fetch, refnr): refnr for refnr in referenznummern}
            for future in as_completed(futures):
                refnr, detail, exc = future.result()
                results_map[refnr] = (refnr, detail, exc)
                if on_progress:
                    on_progress(refnr, detail, exc)

        return [results_map[refnr] for refnr in referenznummern if refnr in results_map]

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
            result["page"] = page
            yield result

            total = result.get("maxErgebnisse", 0)
            fetched = page * page_size
            if fetched >= total:
                break
            if max_pages is not None and page >= max_pages:
                break
            page += 1
