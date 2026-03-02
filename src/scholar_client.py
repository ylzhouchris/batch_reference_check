"""Optional Google Scholar fallback for references not found in CrossRef."""

from __future__ import annotations

import logging

from .models import Reference, ScholarResult

logger = logging.getLogger(__name__)


class ScholarClient:
    def __init__(self):
        self._scholarly = None
        self._consecutive_failures = 0
        self._disabled = False

    def _ensure_scholarly(self) -> bool:
        if self._scholarly is not None:
            return True
        try:
            import scholarly  # type: ignore[import-untyped]

            self._scholarly = scholarly
            return True
        except ImportError:
            logger.warning(
                "scholarly not installed. Install with: pip install scholarly"
            )
            self._disabled = True
            return False

    def lookup(self, ref: Reference) -> ScholarResult:
        """Search Google Scholar for a reference. Auto-disables after 3 failures."""
        if self._disabled:
            return ScholarResult(message="Scholar lookup disabled")

        if not self._ensure_scholarly():
            return ScholarResult(message="scholarly not installed")

        query = ref.title or ref.raw[:120]
        try:
            results = self._scholarly.search_pubs(query)
            pub = next(results, None)
            if pub is None:
                self._consecutive_failures += 1
                self._check_disable()
                return ScholarResult(message="No results found")

            bib = pub.get("bib", {})
            self._consecutive_failures = 0
            return ScholarResult(
                found=True,
                title=bib.get("title", ""),
                url=pub.get("pub_url", ""),
            )
        except Exception as exc:
            self._consecutive_failures += 1
            self._check_disable()
            logger.warning("Scholar lookup failed: %s", exc)
            return ScholarResult(message=f"Error: {exc}")

    def _check_disable(self) -> None:
        if self._consecutive_failures >= 3:
            logger.warning(
                "Scholar: 3 consecutive failures, disabling further lookups"
            )
            self._disabled = True
