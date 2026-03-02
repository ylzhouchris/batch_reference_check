# checkrefs-batch

Batch reference checker for academic PDFs. Extracts references from PDF papers, verifies them against CrossRef and arXiv APIs, checks citation formatting consistency, and generates markdown + CSV reports.

## Installation

Requires Python 3.10+.

```bash
pip install -e .
```

Optional dependencies:

```bash
pip install -e ".[scholar]"   # Google Scholar fallback
pip install -e ".[dev]"       # pytest for tests
```

## Usage

```bash
# Process all PDFs in data/
python -m src.cli data/ -o output/ -e your@email.edu

# Single PDF
python -m src.cli --single data/example_manuscript.pdf -o output/ -v

# With Google Scholar fallback (slower, may hit CAPTCHAs)
python -m src.cli data/ --scholar -e your@email.edu

# Faster rate limit for small batches
python -m src.cli data/ --rate-limit 0.2 -e your@email.edu
```

Or via the installed entry point:

```bash
checkrefs data/ -o output/ -e your@email.edu
```

### CLI Options

| Option | Default | Description |
|--------|---------|-------------|
| `INPUT_PATH` | `data` | Directory of PDFs, or single PDF with `--single` |
| `-o, --output` | `output` | Output directory for reports |
| `-e, --email` | | Email for CrossRef polite pool (recommended) |
| `--scholar / --no-scholar` | off | Enable Google Scholar fallback |
| `--rate-limit` | 1.0 | Seconds between CrossRef API requests |
| `--single` | off | Treat INPUT_PATH as a single PDF file |
| `-v, --verbose` | off | Verbose logging |

## Output

For each PDF, two report files are generated in the output directory:

- **`<name>_report.md`** — Human-readable markdown report grouped by verification status (Not Found, Likely Match, Verified, Errors), with a summary table and format issues section.
- **`<name>_report.csv`** — Machine-readable CSV with one row per reference, including match scores and DOIs.

### Verification Statuses

| Status | Meaning |
|--------|---------|
| **verified** | High-confidence match: CrossRef score >80, title similarity >0.85, DOI exact match, or arXiv ID confirmed |
| **likely_match** | Moderate confidence: CrossRef score 40–80 or title similarity 0.60–0.85 |
| **not_found** | No match found in CrossRef or arXiv — may be a preprint, dataset, website, or citation error |
| **error** | API error during verification |

## Architecture

See [docs/architecture.md](docs/architecture.md) for detailed module descriptions and data flow.

```
PDF files
  → pdf_extractor (PyMuPDF text extraction, header/table filtering)
  → ref_parser (IEEE quoted-title + period-split parsing)
  → crossref_client (DOI lookup + bibliographic search with title similarity)
  → arxiv_client (arXiv ID verification + title-based search fallback)
  → scholar_client (optional Google Scholar fallback)
  → format_checker (consistency checks)
  → report (markdown + CSV generation)
```

## Testing

```bash
pytest tests/ -v
```

## Dependencies

| Library | Purpose |
|---------|---------|
| [PyMuPDF](https://pymupdf.readthedocs.io/) | PDF text extraction |
| [requests](https://docs.python-requests.org/) | HTTP client for CrossRef and arXiv APIs |
| [click](https://click.palletsprojects.com/) | CLI framework |
| [scholarly](https://scholarly.readthedocs.io/) | Google Scholar lookups (optional) |
