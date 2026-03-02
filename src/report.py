"""Generate markdown and CSV reports from verification results."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from .models import PaperReport, Status, VerificationResult


def generate_markdown(report: PaperReport) -> str:
    """Generate a markdown report string."""
    lines: list[str] = []
    lines.append(f"# Reference Check Report: {report.filename}")
    lines.append("")

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total references | {report.total_refs} |")
    lines.append(f"| Verified | {report.verified_count} |")
    lines.append(f"| Likely match | {report.likely_count} |")
    lines.append(f"| **Not found** | **{report.not_found_count}** |")
    lines.append(f"| Errors | {report.error_count} |")
    lines.append(f"| Format issues | {len(report.format_issues)} |")
    lines.append("")

    # Group results by status
    by_status: dict[Status, list[VerificationResult]] = {
        Status.NOT_FOUND: [],
        Status.LIKELY_MATCH: [],
        Status.VERIFIED: [],
        Status.ERROR: [],
    }
    for vr in report.results:
        by_status[vr.status].append(vr)

    # --- NOT FOUND: prominent section, users should review these ---
    not_found = by_status[Status.NOT_FOUND]
    if not_found:
        lines.append("---")
        lines.append("")
        lines.append(f"## !! Not Found ({len(not_found)}) — Please Review")
        lines.append("")
        lines.append(
            "> These references could not be verified via CrossRef or arXiv. "
            "They may be preprints, datasets, websites, or contain errors. "
            "Please check each one manually."
        )
        lines.append("")
        for vr in not_found:
            _render_ref_detail(lines, vr, highlight=True)

    # --- LIKELY MATCH ---
    likely = by_status[Status.LIKELY_MATCH]
    if likely:
        lines.append("---")
        lines.append("")
        lines.append(f"## Likely Match ({len(likely)})")
        lines.append("")
        lines.append(
            "> These references found a probable match in CrossRef but the "
            "confidence is moderate. Spot-check any that look suspicious."
        )
        lines.append("")
        for vr in likely:
            _render_ref_detail(lines, vr)

    # --- VERIFIED ---
    verified = by_status[Status.VERIFIED]
    if verified:
        lines.append("---")
        lines.append("")
        lines.append(f"## Verified ({len(verified)})")
        lines.append("")
        for vr in verified:
            _render_ref_detail(lines, vr)

    # --- ERROR ---
    errors = by_status[Status.ERROR]
    if errors:
        lines.append("---")
        lines.append("")
        lines.append(f"## Errors ({len(errors)})")
        lines.append("")
        for vr in errors:
            _render_ref_detail(lines, vr)

    # Format issues at the end
    if report.format_issues:
        # Build lookup from ref index → VerificationResult
        vr_by_index: dict[int, VerificationResult] = {
            vr.reference.index: vr for vr in report.results
        }

        lines.append("---")
        lines.append("")
        lines.append("## Format Issues")
        lines.append("")
        for issue in report.format_issues:
            lines.append(f"### Ref #{issue.ref_index} — {issue.field}: {issue.issue}")
            lines.append("")
            vr = vr_by_index.get(issue.ref_index)
            if vr:
                ref = vr.reference
                lines.append(f"- **Original citation**: {ref.raw}")
                matched = _get_matched_title(vr)
                if matched:
                    lines.append(f"- **Closest match**: {matched}")
            lines.append("")

    return "\n".join(lines)


def _render_ref_detail(
    lines: list[str], vr: VerificationResult, *, highlight: bool = False
) -> None:
    """Append markdown lines for a single reference."""
    ref = vr.reference
    prefix = "> " if highlight else ""

    lines.append(f"{prefix}### Ref #{ref.index}")
    lines.append(f"{prefix}")
    if ref.authors:
        lines.append(f"{prefix}- **Authors**: {ref.authors}")
    if ref.title:
        lines.append(f"{prefix}- **Title**: {ref.title}")
    if ref.year:
        lines.append(f"{prefix}- **Year**: {ref.year}")
    if ref.doi:
        lines.append(f"{prefix}- **DOI (in paper)**: `{ref.doi}`")
    if ref.arxiv_id:
        lines.append(f"{prefix}- **arXiv**: `{ref.arxiv_id}`")
    lines.append(f"{prefix}- **Status**: {vr.status.value}")

    # Show match details only for actual matches
    if vr.crossref and vr.status in (Status.VERIFIED, Status.LIKELY_MATCH):
        lines.append(f"{prefix}- **CrossRef score**: {vr.crossref.score:.1f}")
        if vr.crossref.matched_doi:
            lines.append(f"{prefix}- **Matched DOI**: `{vr.crossref.matched_doi}`")
        if vr.crossref.message:
            lines.append(f"{prefix}- **Note**: {vr.crossref.message}")

    # arXiv match info
    if vr.arxiv and vr.arxiv.found:
        lines.append(f"{prefix}- **arXiv verified**: {vr.arxiv.url}")

    # Scholar match info
    if vr.scholar and vr.scholar.found:
        lines.append(f"{prefix}- **Google Scholar**: {vr.scholar.url}")

    # For NOT_FOUND, show the raw text so users can investigate
    if highlight:
        lines.append(f"{prefix}- **Raw text**: {ref.raw}")

    lines.append("")


def generate_csv(report: PaperReport) -> str:
    """Generate a CSV report string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ref_index", "authors", "title", "year", "doi", "arxiv_id",
        "status", "crossref_score", "matched_doi", "title_similarity",
        "arxiv_verified", "scholar_found",
    ])
    for vr in report.results:
        ref = vr.reference
        # Extract title similarity from message if present
        title_sim = ""
        if vr.crossref and vr.crossref.message.startswith("title_similarity="):
            title_sim = vr.crossref.message.split("=")[1]

        writer.writerow([
            ref.index,
            ref.authors,
            ref.title,
            ref.year,
            ref.doi,
            ref.arxiv_id,
            vr.status.value,
            f"{vr.crossref.score:.1f}" if vr.crossref else "",
            vr.crossref.matched_doi if vr.crossref and vr.status in (Status.VERIFIED, Status.LIKELY_MATCH) else "",
            title_sim,
            "yes" if vr.arxiv and vr.arxiv.found else "",
            "yes" if vr.scholar and vr.scholar.found else "",
        ])
    return output.getvalue()


def _get_matched_title(vr: VerificationResult) -> str:
    """Return the best matched title from CrossRef or arXiv, if available."""
    parts: list[str] = []
    if vr.crossref and vr.crossref.matched_title:
        doi_str = f" (DOI: `{vr.crossref.matched_doi}`)" if vr.crossref.matched_doi else ""
        parts.append(f"CrossRef: {vr.crossref.matched_title}{doi_str}")
    if vr.arxiv and vr.arxiv.found and vr.arxiv.title:
        url_str = f" ({vr.arxiv.url})" if vr.arxiv.url else ""
        parts.append(f"arXiv: {vr.arxiv.title}{url_str}")
    return " | ".join(parts)


def write_reports(report: PaperReport, output_dir: Path) -> tuple[Path, Path]:
    """Write markdown and CSV reports to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(report.filename).stem

    md_path = output_dir / f"{stem}_report.md"
    csv_path = output_dir / f"{stem}_report.csv"

    md_path.write_text(generate_markdown(report), encoding="utf-8")
    csv_path.write_text(generate_csv(report), encoding="utf-8")

    return md_path, csv_path
