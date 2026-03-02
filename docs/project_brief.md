# Project Brief

## Problem

Manually checking reference lists in academic papers is tedious and error-prone. Common issues include:

- Incorrect or missing DOIs, years, or author names
- References to non-existent papers (hallucinated or garbled citations)
- Inconsistent formatting across the reference list (mixed "et al." usage, inconsistent year formats)
- Preprints cited without noting their publication status

## Solution

**checkrefs-batch** automates reference verification for academic PDFs. It:

1. Extracts the references section from PDF papers using PyMuPDF
2. Parses each reference into structured fields (authors, title, year, DOI, arXiv ID)
3. Verifies each reference against CrossRef, arXiv, and optionally Google Scholar
4. Checks formatting consistency across the reference list
5. Generates a markdown report (for human review) and CSV (for programmatic use)

## Target Users

- Researchers preparing submissions who want to catch reference errors before review
- Reviewers who want to spot-check reference accuracy
- Research groups maintaining shared citation quality standards

## Scope

- Input: PDF files with standard academic reference sections
- Parsing: Handles numbered (`[1]`) with IEEE-style quoted titles, and author-year reference styles
- Verification: CrossRef (primary), arXiv (fallback), Google Scholar (optional)
- Output: Per-PDF markdown and CSV reports
- Not in scope: Citation style conversion, bibliography management, or reference insertion
