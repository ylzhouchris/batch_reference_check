"""Orchestrate the full reference-checking pipeline."""

from __future__ import annotations

import logging
from pathlib import Path

from .arxiv_client import ArxivClient
from .crossref_client import CrossRefClient
from .format_checker import check_formatting
from .models import PaperReport, Status, VerificationResult
from .pdf_extractor import extract_references_text
from .ref_parser import parse_references
from .report import write_reports
from .scholar_client import ScholarClient

logger = logging.getLogger(__name__)


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    *,
    email: str = "",
    rate_limit: float = 1.0,
    use_scholar: bool = False,
    verbose: bool = False,
) -> PaperReport:
    """Run the full pipeline on a single PDF and write reports."""
    filename = pdf_path.name
    logger.info("Processing: %s", filename)

    # Step 1: Extract references text
    ref_text = extract_references_text(str(pdf_path))
    if not ref_text:
        logger.warning("No references section found in %s", filename)
        report = PaperReport(filename=filename)
        write_reports(report, output_dir)
        return report

    # Step 2: Parse references
    refs = parse_references(ref_text)
    logger.info("Found %d references in %s", len(refs), filename)

    # Step 3: Verify against CrossRef
    crossref = CrossRefClient(email=email, rate_limit=rate_limit)
    arxiv = ArxivClient(session=crossref.session)
    scholar = ScholarClient() if use_scholar else None
    results: list[VerificationResult] = []

    for ref in refs:
        if verbose:
            logger.info("  [%d/%d] %s", ref.index, len(refs), ref.title[:60] if ref.title else ref.raw[:60])

        cr_result = crossref.verify(ref)
        vr = VerificationResult(reference=ref, crossref=cr_result)

        # Step 3b: arXiv verification for NOT_FOUND refs
        if cr_result.status == Status.NOT_FOUND:
            if ref.arxiv_id:
                # Direct ID lookup
                vr.arxiv = arxiv.verify(ref)
            elif ref.title:
                # Title-based arXiv search as fallback
                vr.arxiv = arxiv.search_by_title(ref)

        # Step 4: Scholar fallback for still-NOT_FOUND
        if scholar and vr.status == Status.NOT_FOUND:
            vr.scholar = scholar.lookup(ref)

        results.append(vr)

    # Step 5: Format checks
    format_issues = check_formatting(refs)

    # Step 6: Build report and write
    report = PaperReport(
        filename=filename,
        total_refs=len(refs),
        results=results,
        format_issues=format_issues,
    )
    md_path, csv_path = write_reports(report, output_dir)
    logger.info("Reports written: %s, %s", md_path, csv_path)

    return report


def process_batch(
    input_dir: Path,
    output_dir: Path,
    **kwargs,
) -> list[PaperReport]:
    """Process all PDFs in a directory."""
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        logger.warning("No PDF files found in %s", input_dir)
        return []

    logger.info("Found %d PDF(s) to process", len(pdfs))
    reports: list[PaperReport] = []
    for pdf_path in pdfs:
        report = process_pdf(pdf_path, output_dir, **kwargs)
        reports.append(report)

    return reports
