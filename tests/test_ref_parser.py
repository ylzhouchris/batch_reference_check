"""Tests for reference parsing."""

from src.ref_parser import parse_reference, parse_references, split_references


class TestSplitReferences:
    def test_numbered_refs(self):
        text = (
            "[1] Smith, J. Title one. Venue, 2020.\n"
            "[2] Doe, A. Title two. Venue, 2021.\n"
            "[3] Lee, B. Title three. Venue, 2022.\n"
        )
        refs = split_references(text)
        assert len(refs) == 3
        assert refs[0].startswith("[1]")
        assert refs[2].startswith("[3]")

    def test_numbered_multiline(self):
        text = (
            "[1] Smith, J. A very long title that\n"
            "spans multiple lines. Venue, 2020.\n"
            "[2] Doe, A. Another title. Venue, 2021.\n"
        )
        refs = split_references(text)
        assert len(refs) == 2
        assert "spans multiple lines" in refs[0]

    def test_empty_text(self):
        assert split_references("") == []

    def test_blank_lines_ignored(self):
        text = "[1] Smith, J. Title. 2020.\n\n\n[2] Doe, A. Title. 2021.\n"
        refs = split_references(text)
        assert len(refs) == 2


class TestParseReference:
    def test_basic_numbered(self):
        raw = "[1] Smith, J. and Doe, A. Deep learning for geospatial data. NeurIPS, 2023."
        ref = parse_reference(raw, 1)
        assert ref.index == 1
        assert "Smith" in ref.authors
        assert "Deep learning" in ref.title
        assert ref.year == "2023"

    def test_doi_extraction(self):
        raw = "[5] Author, A. Some title. Journal, 2022. 10.1234/test.5678"
        ref = parse_reference(raw, 5)
        assert ref.doi == "10.1234/test.5678"

    def test_arxiv_extraction(self):
        raw = "[3] Author, A. Title. arXiv:2301.12345, 2023."
        ref = parse_reference(raw, 3)
        assert ref.arxiv_id == "2301.12345"

    def test_url_extraction(self):
        raw = "[2] Author, A. Title. https://example.com/paper, 2022."
        ref = parse_reference(raw, 2)
        assert "example.com" in ref.url

    def test_year_in_parens(self):
        raw = "[1] Author (2024). Title. Venue."
        ref = parse_reference(raw, 1)
        assert ref.year == "2024"

    def test_missing_year(self):
        raw = "[1] Author. Title without a year. Venue."
        ref = parse_reference(raw, 1)
        assert ref.year == ""


class TestParseReferences:
    def test_full_pipeline(self):
        text = (
            "[1] Smith, J. Title one. Venue, 2020.\n"
            "[2] Doe, A. Title two. Venue, 2021.\n"
        )
        refs = parse_references(text)
        assert len(refs) == 2
        assert refs[0].index == 1
        assert refs[1].index == 2
