"""Extract text from PDFs and isolate the references section."""

from __future__ import annotations

import re

import fitz  # PyMuPDF


# Patterns that mark the start of the references section
_REF_HEADER = re.compile(
    r"^\s*(References|Bibliography|Works\s+Cited)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Patterns that mark the end of the references section
_REF_STOP = re.compile(
    r"^\s*(Appendix|Supplementary|Acknowledgement|Acknowledgment)\b",
    re.IGNORECASE | re.MULTILINE,
)

# Common page header/footer noise (page numbers, running headers)
_PAGE_NOISE = re.compile(
    r"^\s*\d+\s*$"  # bare page numbers
)

# Running headers that appear on every page of conference papers
_RUNNING_HEADER = re.compile(
    r"^\s*("
    r"Published as a conference paper at\b"
    r"|Under review as a conference paper at\b"
    r"|Accepted (?:at|to|by)\b"
    r"|Preprint\."
    r")",
    re.IGNORECASE,
)


def extract_full_text(pdf_path: str) -> str:
    """Return the full text of a PDF, with page-break markers removed."""
    doc = fitz.open(pdf_path)
    pages: list[str] = []
    for page in doc:
        text = page.get_text("text")
        # Strip likely page-number-only lines at top/bottom
        lines = text.splitlines()
        cleaned = [
            ln for ln in lines
            if not _PAGE_NOISE.match(ln) and not _RUNNING_HEADER.match(ln)
        ]
        pages.append("\n".join(cleaned))
    doc.close()
    return "\n".join(pages)


def _strip_embedded_tables(text: str) -> str:
    """Remove table content that sometimes leaks into the references section.

    Detects TABLE headers and removes table rows until we hit a reference
    marker [N] or text that looks like reference prose (not table data).
    """
    lines = text.splitlines()
    out: list[str] = []
    in_table = False

    for line in lines:
        stripped = line.strip()

        # Detect table start: "TABLE IV", "TABLE 1", "Table 3:", etc.
        if re.match(r"^TABLE\s+[IVXLCDM\d]+", stripped, re.IGNORECASE):
            in_table = True
            continue

        if in_table:
            if not stripped:
                continue  # skip blank lines in table
            # Reference marker always ends the table
            if re.match(r"^\[\d+\]", stripped):
                in_table = False
                out.append(line)
            elif _is_table_line(stripped):
                continue  # skip table content
            else:
                # Looks like reference prose — table is over
                in_table = False
                out.append(line)
        else:
            out.append(line)

    return "\n".join(out)


def _is_table_line(line: str) -> bool:
    """Check if a line looks like table content (headers, data rows, captions)."""
    # All-caps lines (table captions / headers)
    if line == line.upper() and len(line) > 10:
        return True
    # Lines with multiple % signs (data rows)
    if line.count("%") >= 2:
        return True
    # Short lines that are a single word or column header
    if len(line) < 30 and not re.search(r'[,"\u201c\u201d]', line):
        return True
    # Lines like "N=4  N=8  N=12"
    if re.match(r"^[N=\d\s×xX]+$", line):
        return True
    # Data rows: mostly numbers
    tokens = line.split()
    if len(tokens) >= 3:
        numeric = sum(1 for t in tokens if re.match(r"^[\d.]+%?$", t))
        if numeric >= len(tokens) * 0.5:
            return True
    # Multi-word title-case lines without commas or quotes (table sub-headers)
    if (len(line) < 80
            and not re.search(r'[,"\u201c\u201d]', line)
            and re.match(r"^[A-Z][a-z]", line)):
        return True
    return False


def extract_references_section(full_text: str) -> str:
    """Find and return just the references section from the full text."""
    # Find the *last* occurrence of a references header (in case the word
    # "References" appears earlier in the paper body).
    match = None
    for m in _REF_HEADER.finditer(full_text):
        match = m

    if match is None:
        return ""

    start = match.end()
    rest = full_text[start:]

    # Cut at the first stop marker
    stop = _REF_STOP.search(rest)
    if stop:
        rest = rest[: stop.start()]

    # Remove any embedded tables
    rest = _strip_embedded_tables(rest)

    return rest.strip()


def extract_references_text(pdf_path: str) -> str:
    """Convenience: extract full text then isolate the references section."""
    full_text = extract_full_text(pdf_path)
    return extract_references_section(full_text)
