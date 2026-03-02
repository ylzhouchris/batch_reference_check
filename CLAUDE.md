# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Batch reference checker for academic PDFs. Extracts references from PDF papers, verifies them against CrossRef and arXiv APIs, checks citation formatting consistency, and generates markdown + CSV reports.

## Commands

```bash
# Install
pip install -e .

# Run on all PDFs in data/
python -m src.cli data/ -o output/ -e your@email.edu

# Run on a single PDF
python -m src.cli --single data/example_manuscript.pdf -o output/ -v

# Run tests
pytest tests/ -v
```

## Structure

- `src/` — Python package (CLI, pipeline, parsers, API clients, report generation)
- `data/` — Input PDF files
- `output/` — Generated reports (gitignored)
- `docs/` — Project documentation
- `tests/` — pytest tests

## Architecture

Pipeline: `pdf_extractor` → `ref_parser` → `crossref_client` → `arxiv_client` → `format_checker` → `report`

Key modules:
- `pdf_extractor.py` — PyMuPDF text extraction, running header filtering, embedded table stripping
- `ref_parser.py` — IEEE-style quoted-title parsing, dual-strategy period-split fallback, dehyphenation, orphan fragment merging
- `crossref_client.py` — DOI lookup + bibliographic search with `difflib.SequenceMatcher` title similarity
- `arxiv_client.py` — ID verification + title-based search fallback
- `models.py` — `VerificationResult.status` property upgrades NOT_FOUND → VERIFIED when arXiv confirms

See `docs/architecture.md` for full details.
