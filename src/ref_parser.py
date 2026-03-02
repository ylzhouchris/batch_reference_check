"""Parse a raw references block into structured Reference objects."""

from __future__ import annotations

import re

from .models import Reference

# Numbered reference pattern: [1], [2], etc.
_NUMBERED_REF = re.compile(r"^\[(\d+)\]")

# Author-year style: starts with capitalized surname or org abbreviation (e.g. "NBS.")
_AUTHOR_START = re.compile(r"^(?:[A-Z][a-z]+[\s,]|[A-Z]{2,6}\.)")

# DOI patterns — also handle line-break spaces inside DOIs like "10.1038/ s41467..."
_DOI_PATTERN = re.compile(r"(10\.\d{4,}/[^\s,;]+)")
_DOI_LABEL = re.compile(r"doi:\s*(10\.\d{4,}/\s*\S+)", re.IGNORECASE)

# arXiv pattern
_ARXIV_PATTERN = re.compile(r"arXiv[:\s]*(\d{4}\.\d{4,5}(?:v\d+)?)", re.IGNORECASE)

# Year in parentheses or standalone 4-digit year
_YEAR_PAREN = re.compile(r"\((\d{4}[a-z]?)\)")
_YEAR_BARE = re.compile(r"\b((?:19|20)\d{2}[a-z]?)\b")

# URL pattern
_URL_PATTERN = re.compile(r"https?://[^\s,;)]+")

# Line-break hyphenation: "repre- sentation" → "representation"
_DEHYPHEN = re.compile(r"(\w)- (\w)")


def _dehyphenate(text: str) -> str:
    """Remove line-break hyphens: 'repre- sentation' → 'representation'."""
    return _DEHYPHEN.sub(r"\1\2", text)


def split_references(text: str) -> list[str]:
    """Split a references block into individual reference strings."""
    lines = text.splitlines()
    refs: list[str] = []
    current: list[str] = []

    # Detect style: numbered [N] vs. paragraph-based
    non_blank = [ln.strip() for ln in lines if ln.strip()]
    is_numbered = (
        len(non_blank) >= 1
        and _NUMBERED_REF.match(non_blank[0]) is not None
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        if is_numbered:
            if _NUMBERED_REF.match(stripped):
                if current:
                    refs.append(" ".join(current))
                current = [stripped]
            else:
                current.append(stripped)
        else:
            # Heuristic: new reference starts with author-like pattern after
            # a line that ended a previous reference (year + period)
            if (
                current
                and _AUTHOR_START.match(stripped)
                and _looks_like_ref_end(" ".join(current))
            ):
                refs.append(" ".join(current))
                current = [stripped]
            else:
                current.append(stripped)

    if current:
        refs.append(" ".join(current))

    # Post-process: merge orphan fragments back into adjacent refs.
    # An orphan is a short ref that looks like just a venue, publisher, or
    # title fragment (no author-like comma pattern in the first 60 chars).
    if not is_numbered:
        refs = _merge_orphan_fragments(refs)

    return refs


def _merge_orphan_fragments(refs: list[str]) -> list[str]:
    """Merge fragments that don't look like standalone references."""
    if len(refs) <= 1:
        return refs

    merged: list[str] = []
    for ref in refs:
        if merged and _is_orphan_fragment(ref):
            # Append to previous ref
            merged[-1] = merged[-1] + " " + ref
        else:
            merged.append(ref)
    return merged


def _is_orphan_fragment(text: str) -> bool:
    """Check if text looks like a fragment rather than a complete reference.

    Very conservative: only merges short texts that clearly lack any
    author-title structure (no "Author. Title" pattern).
    """
    # Long texts are standalone refs
    if len(text) > 150:
        return False
    # Has author-title boundary: ". TitleWord" (period-space-uppercase word of 2+ chars)
    if re.search(r"\.\s+[A-Z][a-z]{2,}", text):
        return False
    # Has initials pattern like ", J." or " A."
    if re.search(r"[\s,][A-Z]\.", text[:80]):
        return False
    # Starts with "Firstname Lastname," (standard author list)
    if re.search(r"^[A-Z][a-z]+ [A-Z][a-z]+,", text):
        return False
    # Starts with org abbreviation like "NBS." or "IEEE."
    if re.match(r"[A-Z]{2,6}\.", text):
        return False
    return True


def _looks_like_ref_end(text: str) -> bool:
    """Check if text looks like a complete reference.

    A reference is complete when it contains a year AND ends with a period,
    DOI, or URL.  Requiring a year prevents splitting mid-reference at lines
    like "...street-level images." (title only, no year yet).
    """
    text = text.rstrip()
    if not text:
        return False
    # Must contain a year to be considered complete
    if not _YEAR_BARE.search(text):
        return False
    if text[-1] in ".?":
        return True
    if _DOI_PATTERN.search(text[-60:]):
        return True
    if _URL_PATTERN.search(text[-80:]):
        return True
    return False


def parse_reference(raw: str, index: int) -> Reference:
    """Parse a single raw reference string into a Reference object."""
    ref = Reference(raw=raw, index=index)

    # Strip leading number tag like [1]
    text = _NUMBERED_REF.sub("", raw).strip()

    # Dehyphenate line-break hyphens before any further parsing
    text = _dehyphenate(text)

    # Extract DOI — try labeled "doi: ..." first (handles spaces from line breaks),
    # then fall back to bare pattern
    doi_match = _DOI_LABEL.search(text)
    if doi_match:
        ref.doi = doi_match.group(1).replace(" ", "").rstrip(".")
    else:
        doi_match = _DOI_PATTERN.search(text)
        if doi_match:
            ref.doi = doi_match.group(1).rstrip(".")

    # Extract arXiv ID
    arxiv_match = _ARXIV_PATTERN.search(text)
    if arxiv_match:
        ref.arxiv_id = arxiv_match.group(1)

    # Extract URL
    url_match = _URL_PATTERN.search(text)
    if url_match:
        ref.url = url_match.group(0).rstrip(".")

    # Extract year
    year_match = _YEAR_PAREN.search(text)
    if year_match:
        ref.year = year_match.group(1)
    else:
        year_match = _YEAR_BARE.search(text)
        if year_match:
            ref.year = year_match.group(1)

    # Split authors and title
    _parse_authors_title(text, ref)

    return ref


def _parse_authors_title(text: str, ref: Reference) -> None:
    """Extract authors and title from reference text.

    Tries three strategies in order:
    1. IEEE-style: title is enclosed in "double quotes" (common in IEEE/ACM)
    2. Period-split Strategy A (broad): lookbehind skips initials
    3. Period-split Strategy B (strict): requires [A-Z][a-z] after period
    """
    # --- Strategy 0: IEEE-style quoted title ---
    # Matches: Authors, "Title here," in Venue...
    # Use straight or curly double quotes
    ieee_match = re.search(
        r'[\u201c"]\s*(.+?)\s*[,.]?\s*[\u201d"]',
        text,
        re.DOTALL,
    )
    if ieee_match:
        title_text = ieee_match.group(1).strip().rstrip(",.")
        # Authors = everything before the opening quote
        authors_text = text[: ieee_match.start()].strip().rstrip(",")
        # Venue = everything after the closing quote
        venue_text = text[ieee_match.end() :].strip().lstrip(",. ")

        if title_text and len(title_text) > 5:
            ref.title = title_text
            if authors_text:
                ref.authors = authors_text
            if venue_text:
                # Clean up venue: remove year, DOI, URL, arXiv
                venue_text = _YEAR_PAREN.sub("", venue_text)
                venue_text = _DOI_PATTERN.sub("", venue_text)
                venue_text = _URL_PATTERN.sub("", venue_text)
                venue_text = _ARXIV_PATTERN.sub("", venue_text)
                # Remove trailing "vol. X, no. Y, pp. Z, year." bits
                venue_text = re.sub(
                    r",?\s*vol\..*$", "", venue_text, flags=re.IGNORECASE
                )
                venue_text = re.sub(
                    r",?\s*pp?\..*$", "", venue_text, flags=re.IGNORECASE
                )
                venue_text = re.sub(r"\b\d{4}\b", "", venue_text)
                venue_text = venue_text.strip(" .,;")
                if venue_text and len(venue_text) > 3:
                    ref.venue = venue_text
            return

    # --- Strategy A: broad lookahead, lookbehind skips initials ---
    parts_a = re.split(
        r"(?<=\w{2})\.\s+(?=[A-Z](?:[a-z]|\s|\d|:))",
        text,
        maxsplit=2,
    )
    # --- Strategy B: strict lookahead (original), no lookbehind ---
    parts_b = re.split(r"\.\s+(?=[A-Z][a-z])", text, maxsplit=2)

    # Pick the split with the shorter first part (authors are shorter than titles)
    if len(parts_a) >= 2 and len(parts_b) >= 2:
        parts = parts_a if len(parts_a[0]) <= len(parts_b[0]) else parts_b
    elif len(parts_a) >= 2:
        parts = parts_a
    elif len(parts_b) >= 2:
        parts = parts_b
    else:
        parts = [text]

    if len(parts) >= 2:
        ref.authors = parts[0].strip().rstrip(".")
        # Title is usually the second segment
        title_candidate = parts[1].strip()
        # Remove trailing venue/year info after the next period
        title_end = re.search(r"\.\s", title_candidate)
        if title_end:
            ref.title = title_candidate[: title_end.start()].strip()
        else:
            ref.title = title_candidate.rstrip(".")
        # Remaining text after title is venue
        if len(parts) >= 3:
            venue_text = parts[2].strip()
            # Clean up venue: remove year, DOI, URL
            venue_text = _YEAR_PAREN.sub("", venue_text)
            venue_text = _DOI_PATTERN.sub("", venue_text)
            venue_text = _URL_PATTERN.sub("", venue_text)
            venue_text = _ARXIV_PATTERN.sub("", venue_text)
            venue_text = venue_text.strip(" .,;")
            if venue_text:
                ref.venue = venue_text
    else:
        # Fallback: put everything as title
        ref.title = text.strip().rstrip(".")


def parse_references(text: str) -> list[Reference]:
    """Split and parse all references from a references section text block."""
    raw_refs = split_references(text)
    return [parse_reference(raw, i + 1) for i, raw in enumerate(raw_refs)]
