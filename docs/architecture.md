# Architecture

## Module Overview

```
src/
├── cli.py              Click CLI entry point
├── pipeline.py         Orchestrates the full verification pipeline
├── pdf_extractor.py    PDF text extraction and reference section detection
├── ref_parser.py       Splits and parses raw reference text into structured objects
├── crossref_client.py  CrossRef API verification (DOI lookup + bibliographic search)
├── arxiv_client.py     arXiv API verification (ID lookup + title search)
├── scholar_client.py   Optional Google Scholar fallback
├── format_checker.py   Citation formatting consistency checks
├── report.py           Markdown and CSV report generation
└── models.py           Dataclasses and enums
```

## Data Flow

```
PDF file
  │
  ▼
pdf_extractor.extract_references_text()
  │  - Extracts full text page-by-page via PyMuPDF
  │  - Filters running headers ("Published as a conference paper at...")
  │  - Strips embedded tables (TABLE IV, etc.) that leak into reference sections
  │  - Finds the last "References" heading
  │  - Stops at "Appendix" / "Supplementary" if present
  │
  ▼
ref_parser.parse_references()
  │  - split_references(): Detects numbered [N] vs author-year style
  │  - For author-year: splits on author-start patterns after ref-end heuristic
  │  - Post-processing: merges orphan fragments back into adjacent refs
  │  - parse_reference(): Extracts authors, title, year, DOI, arXiv ID, URL
  │  - IEEE-style: detects "quoted titles" to split authors/title/venue
  │  - Period-split fallback: dual-strategy regex for author-year styles
  │  - Dehyphenates line-break hyphens ("repre- sentation" → "representation")
  │
  ▼
crossref_client.verify()
  │  - If ref has DOI: direct lookup via /works/{doi}
  │  - Otherwise: bibliographic search via /works?query.bibliographic=...
  │  - Scores top 5 results by CrossRef score + title similarity
  │  - Title similarity: difflib.SequenceMatcher on normalized titles
  │  - Classification: >80 or sim>0.85 → VERIFIED, >40 or sim>0.60 → LIKELY_MATCH
  │
  ▼
arxiv_client (fallback for NOT_FOUND)
  │  - If ref has arXiv ID: direct Atom API lookup
  │  - If ref has title: search by title with similarity threshold 0.75
  │  - Confirmed arXiv match upgrades NOT_FOUND → VERIFIED
  │
  ▼
scholar_client (optional, for remaining NOT_FOUND)
  │  - Uses `scholarly` library
  │  - Auto-disables after 3 consecutive failures (CAPTCHAs)
  │
  ▼
format_checker.check_formatting()
  │  - Missing fields (title, year, authors)
  │  - Duplicate titles
  │  - Year format inconsistency (parenthesized vs bare)
  │  - Author format inconsistency ("et al." vs full author lists)
  │
  ▼
report.write_reports()
     - Markdown: grouped by status (Not Found → Likely → Verified → Errors)
     - Format issues with original citation + closest match context
     - CSV: one row per reference with all fields
```

## Key Design Decisions

### Reference Parsing Strategy

The parser uses a **three-strategy approach** for splitting author/title fields:

1. **IEEE-style quoted titles** (Strategy 0): Detects titles enclosed in `"double quotes"` or `\u201ccurly quotes\u201d`, common in IEEE/ACM formats. Authors are everything before the opening quote, title is between quotes, venue follows after. This handles formats like `Y. Shapira and N. Agmon, "Path planning for..."` where initials (`Y.`, `N.`) would break period-based splitting.

2. **Strategy A (broad)**: `(?<=\w{2})\.\s+(?=[A-Z](?:[a-z]|\s|\d|:))` — requires 2+ word chars before the period (skips initials like "J."), accepts titles starting with "A ", "H3:", digits, etc.

3. **Strategy B (strict)**: `\.\s+(?=[A-Z][a-z])` — requires uppercase+lowercase after the period.

For strategies A/B, the parser tries both and picks the split with the **shorter first part** (author block), since author lists are typically shorter than titles.

### Embedded Table Handling

Some PDFs render tables (e.g., TABLE IV) within the references page area. The extractor detects `TABLE` headers and strips subsequent table content (all-caps captions, numeric/percentage data rows, short column headers) until reference prose resumes. This prevents table data from being concatenated into reference text.

### Verification Layering

CrossRef alone is insufficient — many valid papers get low scores due to title variations, preprint status, or non-standard formats. The tool uses a layered fallback:

1. **CrossRef DOI lookup** — exact match when DOI is present in the citation
2. **CrossRef bibliographic search** — score + title similarity across top 5 results
3. **arXiv ID verification** — direct lookup for citations with arXiv IDs
4. **arXiv title search** — fuzzy title match for remaining NOT_FOUND refs
5. **Google Scholar** — optional last resort, prone to CAPTCHAs

### Title Similarity

Raw CrossRef scores can be misleading (e.g., score 80 for a completely different paper). Title similarity using `difflib.SequenceMatcher` on lowercased, punctuation-stripped titles provides a more reliable signal. A high similarity (>0.85) can upgrade a low-scoring result to VERIFIED.

### Orphan Fragment Merging

Non-numbered reference lists sometimes split mid-reference at lines like "Nature Communications, 12(1):..." that happen to start with a capital letter. The parser post-processes by merging short fragments that lack author-title structure back into the preceding reference.

## Models

```
Status (enum): VERIFIED | LIKELY_MATCH | NOT_FOUND | ERROR

Reference: raw, index, authors, title, year, venue, doi, arxiv_id, url
CrossRefResult: status, score, matched_title, matched_doi, message
ArxivResult: found, arxiv_id, title, url, message
ScholarResult: found, title, url, message
FormatIssue: ref_index, field, issue

VerificationResult: reference, crossref?, arxiv?, scholar?
  └─ status property: arXiv confirmation upgrades NOT_FOUND → VERIFIED

PaperReport: filename, total_refs, results[], format_issues[]
  └─ verified_count, likely_count, not_found_count, error_count
```

## API Rate Limiting

- **CrossRef**: Configurable delay between requests (default 1s). Exponential backoff on HTTP 429. Uses `mailto` parameter for polite pool access (faster rate limits).
- **arXiv**: 3-second delay between requests per arXiv API terms.
- **Google Scholar**: No official API. The `scholarly` library handles its own rate limiting but may trigger CAPTCHAs. Auto-disables after 3 consecutive failures.
