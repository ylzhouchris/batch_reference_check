"""Check citation formatting consistency across references."""

from __future__ import annotations

import re
from collections import Counter

from .models import FormatIssue, Reference


def check_formatting(refs: list[Reference]) -> list[FormatIssue]:
    """Run all formatting checks and return a list of issues found."""
    issues: list[FormatIssue] = []
    issues.extend(_check_missing_fields(refs))
    issues.extend(_check_duplicate_titles(refs))
    issues.extend(_check_year_format(refs))
    issues.extend(_check_author_format(refs))
    return issues


def _check_missing_fields(refs: list[Reference]) -> list[FormatIssue]:
    issues: list[FormatIssue] = []
    for ref in refs:
        if not ref.title:
            issues.append(FormatIssue(ref.index, "title", "Missing title"))
        if not ref.authors:
            issues.append(FormatIssue(ref.index, "authors", "Missing authors"))
        if not ref.year:
            issues.append(FormatIssue(ref.index, "year", "Missing year"))
    return issues


def _check_duplicate_titles(refs: list[Reference]) -> list[FormatIssue]:
    issues: list[FormatIssue] = []
    titles: dict[str, int] = {}
    for ref in refs:
        if not ref.title:
            continue
        normalized = ref.title.lower().strip()
        if normalized in titles:
            issues.append(
                FormatIssue(
                    ref.index,
                    "title",
                    f"Duplicate title (same as ref #{titles[normalized]})",
                )
            )
        else:
            titles[normalized] = ref.index
    return issues


def _check_year_format(refs: list[Reference]) -> list[FormatIssue]:
    """Check that years are consistently formatted (4-digit, optional letter)."""
    issues: list[FormatIssue] = []
    valid_year = re.compile(r"^\d{4}[a-z]?$")
    for ref in refs:
        if ref.year and not valid_year.match(ref.year):
            issues.append(
                FormatIssue(ref.index, "year", f"Unusual year format: '{ref.year}'")
            )
    return issues


def _check_author_format(refs: list[Reference]) -> list[FormatIssue]:
    """Detect mixed author formatting styles (e.g., 'et al.' vs full lists)."""
    issues: list[FormatIssue] = []
    styles: Counter[str] = Counter()
    ref_styles: list[tuple[int, str]] = []

    for ref in refs:
        if not ref.authors:
            continue
        if "et al" in ref.authors:
            style = "et_al"
        elif " and " in ref.authors or "&" in ref.authors:
            style = "full_list"
        else:
            style = "single_or_other"
        styles[style] += 1
        ref_styles.append((ref.index, style))

    # If both et_al and full_list are used, flag the minority style
    if styles["et_al"] > 0 and styles["full_list"] > 0:
        minority = "et_al" if styles["et_al"] < styles["full_list"] else "full_list"
        for idx, style in ref_styles:
            if style == minority:
                issues.append(
                    FormatIssue(
                        idx,
                        "authors",
                        f"Inconsistent author format: uses '{style}' "
                        f"style (minority among references)",
                    )
                )

    return issues
