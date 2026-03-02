"""Verify references against the arXiv API."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

import requests

from .models import ArxivResult, Reference

logger = logging.getLogger(__name__)

ARXIV_API = "https://export.arxiv.org/api/query"

# Minimum title similarity to consider an arXiv search result a match
_TITLE_MATCH_THRESHOLD = 0.75


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s)


class ArxivClient:
    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()

    def verify(self, ref: Reference) -> ArxivResult:
        """Check if a reference's arXiv ID exists and optionally verify title."""
        arxiv_id = ref.arxiv_id
        if not arxiv_id:
            return ArxivResult(message="No arXiv ID")

        return self._lookup_by_id(arxiv_id)

    def search_by_title(self, ref: Reference) -> ArxivResult:
        """Search arXiv by title. Used as fallback when CrossRef returns NOT_FOUND."""
        title = ref.title
        if not title or len(title) < 10:
            return ArxivResult(message="Title too short for arXiv search")

        try:
            resp = self.session.get(
                ARXIV_API,
                params={
                    "search_query": f'ti:"{title}"',
                    "max_results": 3,
                },
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("arXiv title search failed: %s", exc)
            return ArxivResult(message=str(exc))

        entries = self._parse_entries(resp.text)
        if not entries:
            return ArxivResult(message="No arXiv results for title search")

        # Find best title match
        ref_norm = _normalize(title)
        best: ArxivResult | None = None
        best_sim = 0.0

        for entry_title, entry_url, entry_id in entries:
            sim = SequenceMatcher(None, ref_norm, _normalize(entry_title)).ratio()
            if sim > best_sim:
                best_sim = sim
                best = ArxivResult(
                    found=True,
                    arxiv_id=entry_id,
                    title=entry_title,
                    url=entry_url,
                )

        if best and best_sim >= _TITLE_MATCH_THRESHOLD:
            logger.info("arXiv title match (sim=%.2f): %s", best_sim, best.title[:60])
            return best

        return ArxivResult(
            message=f"Best arXiv match similarity={best_sim:.2f}, below threshold"
        )

    def _lookup_by_id(self, arxiv_id: str) -> ArxivResult:
        """Look up a specific arXiv ID."""
        try:
            resp = self.session.get(
                ARXIV_API,
                params={"id_list": arxiv_id, "max_results": 1},
                timeout=15,
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("arXiv lookup failed for %s: %s", arxiv_id, exc)
            return ArxivResult(message=str(exc))

        entries = self._parse_entries(resp.text)
        if not entries:
            return ArxivResult(message=f"arXiv ID {arxiv_id} not found")

        title, url, eid = entries[0]
        if not title or "error" in title.lower():
            return ArxivResult(message=f"arXiv ID {arxiv_id} not found")

        return ArxivResult(found=True, arxiv_id=arxiv_id, title=title, url=url)

    def _parse_entries(self, xml_text: str) -> list[tuple[str, str, str]]:
        """Parse arXiv Atom XML and return list of (title, url, id)."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("arXiv XML parse error: %s", exc)
            return []

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        results: list[tuple[str, str, str]] = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            title = title_el.text.strip() if title_el is not None and title_el.text else ""
            id_el = entry.find("atom:id", ns)
            url = id_el.text.strip() if id_el is not None and id_el.text else ""
            # Extract arXiv ID from URL like http://arxiv.org/abs/2310.06743v2
            arxiv_id = url.rsplit("/", 1)[-1] if url else ""
            arxiv_id = re.sub(r"v\d+$", "", arxiv_id)
            results.append((title, url, arxiv_id))
        return results
