"""Verify references against the CrossRef API."""

from __future__ import annotations

import logging
import re
import time
from difflib import SequenceMatcher

import requests

from .models import CrossRefResult, Reference, Status

logger = logging.getLogger(__name__)

CROSSREF_API = "https://api.crossref.org/works"

# Score thresholds for classification
VERIFIED_THRESHOLD = 80
LIKELY_THRESHOLD = 40

# Title similarity thresholds (0-1 scale)
TITLE_VERIFIED_SIM = 0.85
TITLE_LIKELY_SIM = 0.60


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation/whitespace for comparison."""
    title = title.lower().strip()
    title = re.sub(r"[^a-z0-9\s]", "", title)
    title = re.sub(r"\s+", " ", title)
    return title


def _title_similarity(a: str, b: str) -> float:
    """Return 0-1 similarity between two title strings."""
    a_norm = _normalize_title(a)
    b_norm = _normalize_title(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


class CrossRefClient:
    def __init__(self, email: str = "", rate_limit: float = 1.0):
        self.session = requests.Session()
        self.session.headers["User-Agent"] = (
            f"checkrefs-batch/0.1 (mailto:{email})" if email else "checkrefs-batch/0.1"
        )
        self.rate_limit = rate_limit
        self._last_request: float = 0

    def _wait(self) -> None:
        if self.rate_limit > 0:
            elapsed = time.monotonic() - self._last_request
            if elapsed < self.rate_limit:
                time.sleep(self.rate_limit - elapsed)

    def verify(self, ref: Reference) -> CrossRefResult:
        """Verify a reference. Tries DOI lookup first, then bibliographic search."""
        # Strategy 1: Direct DOI lookup (most reliable)
        if ref.doi:
            result = self._verify_by_doi(ref.doi, ref)
            if result.status in (Status.VERIFIED, Status.LIKELY_MATCH):
                return result

        # Strategy 2: Bibliographic search with title similarity boosting
        return self._verify_by_search(ref)

    def _verify_by_doi(self, doi: str, ref: Reference) -> CrossRefResult:
        """Directly look up a DOI in CrossRef."""
        self._wait()
        try:
            resp = self.session.get(
                f"{CROSSREF_API}/{doi}",
                timeout=30,
            )
            self._last_request = time.monotonic()

            if resp.status_code == 404:
                return CrossRefResult(
                    status=Status.NOT_FOUND,
                    message=f"DOI {doi} not found in CrossRef",
                )
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning("Rate limited, sleeping %ds", retry_after)
                time.sleep(retry_after)
                return self._verify_by_doi(doi, ref)

            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("CrossRef DOI lookup failed: %s", exc)
            return CrossRefResult(status=Status.ERROR, message=str(exc))

        item = data.get("message", {})
        matched_title = " ".join(item.get("title", []))
        matched_doi = item.get("DOI", doi)

        return CrossRefResult(
            status=Status.VERIFIED,
            score=100.0,
            matched_title=matched_title,
            matched_doi=matched_doi,
            message="Verified by direct DOI lookup",
        )

    def _verify_by_search(self, ref: Reference) -> CrossRefResult:
        """Search CrossRef bibliographically with title similarity boosting."""
        query = _build_query(ref)
        if not query:
            return CrossRefResult(
                status=Status.ERROR, message="No searchable fields in reference"
            )

        self._wait()
        try:
            resp = self.session.get(
                CROSSREF_API,
                params={"query.bibliographic": query, "rows": 5},
                timeout=30,
            )
            self._last_request = time.monotonic()

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 5))
                logger.warning("Rate limited, sleeping %ds", retry_after)
                time.sleep(retry_after)
                return self._verify_by_search(ref)

            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as exc:
            logger.error("CrossRef request failed: %s", exc)
            return CrossRefResult(status=Status.ERROR, message=str(exc))

        items = data.get("message", {}).get("items", [])
        if not items:
            return CrossRefResult(status=Status.NOT_FOUND, message="No results")

        # Check all returned items, not just the first — pick the best match
        best_result = None
        best_rank = (-1, 0.0)  # (status_rank, similarity)

        for item in items:
            score = item.get("score", 0)
            matched_title = " ".join(item.get("title", []))
            matched_doi = item.get("DOI", "")
            sim = _title_similarity(ref.title, matched_title) if ref.title else 0.0

            # Determine status from both CrossRef score AND title similarity
            if score >= VERIFIED_THRESHOLD or sim >= TITLE_VERIFIED_SIM:
                status = Status.VERIFIED
                rank = (3, sim)
            elif score >= LIKELY_THRESHOLD or sim >= TITLE_LIKELY_SIM:
                status = Status.LIKELY_MATCH
                rank = (2, sim)
            else:
                status = Status.NOT_FOUND
                rank = (1, sim)

            if rank > best_rank:
                best_rank = rank
                best_result = CrossRefResult(
                    status=status,
                    score=score,
                    matched_title=matched_title,
                    matched_doi=matched_doi,
                    message=f"title_similarity={sim:.2f}" if sim > 0 else "",
                )

        return best_result or CrossRefResult(
            status=Status.NOT_FOUND, message="No results"
        )


def _build_query(ref: Reference) -> str:
    """Build a bibliographic query string from a Reference."""
    parts: list[str] = []
    if ref.authors:
        # Take first author surname
        first_author = ref.authors.split(",")[0].split(" and ")[0].strip()
        parts.append(first_author)
    if ref.title:
        parts.append(ref.title)
    if ref.year:
        parts.append(ref.year)
    return " ".join(parts)
