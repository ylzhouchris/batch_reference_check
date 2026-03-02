"""Tests for format checker."""

from src.format_checker import check_formatting
from src.models import Reference


def _make_ref(index, **kwargs):
    return Reference(raw="", index=index, **kwargs)


class TestCheckFormatting:
    def test_missing_title(self):
        refs = [_make_ref(1, authors="Smith", year="2023")]
        issues = check_formatting(refs)
        fields = [(i.ref_index, i.field) for i in issues]
        assert (1, "title") in fields

    def test_missing_authors(self):
        refs = [_make_ref(1, title="Test", year="2023")]
        issues = check_formatting(refs)
        fields = [(i.ref_index, i.field) for i in issues]
        assert (1, "authors") in fields

    def test_missing_year(self):
        refs = [_make_ref(1, title="Test", authors="Smith")]
        issues = check_formatting(refs)
        fields = [(i.ref_index, i.field) for i in issues]
        assert (1, "year") in fields

    def test_duplicate_titles(self):
        refs = [
            _make_ref(1, title="Same Title", authors="A", year="2020"),
            _make_ref(2, title="Same Title", authors="B", year="2021"),
        ]
        issues = check_formatting(refs)
        dup_issues = [i for i in issues if "Duplicate" in i.issue]
        assert len(dup_issues) == 1
        assert dup_issues[0].ref_index == 2

    def test_no_issues(self):
        refs = [
            _make_ref(1, title="Title A", authors="Smith and Doe", year="2020"),
            _make_ref(2, title="Title B", authors="Lee and Kim", year="2021"),
        ]
        issues = check_formatting(refs)
        assert len(issues) == 0

    def test_inconsistent_author_format(self):
        refs = [
            _make_ref(1, title="A", authors="Smith et al.", year="2020"),
            _make_ref(2, title="B", authors="Lee and Kim", year="2021"),
            _make_ref(3, title="C", authors="Doe and Fox", year="2022"),
            _make_ref(4, title="D", authors="Park and Lin", year="2023"),
        ]
        issues = check_formatting(refs)
        author_issues = [i for i in issues if i.field == "authors"]
        # "et al." is the minority (1 vs 3), so ref 1 should be flagged
        assert any(i.ref_index == 1 for i in author_issues)

    def test_unusual_year_format(self):
        refs = [_make_ref(1, title="T", authors="A", year="20x3")]
        issues = check_formatting(refs)
        year_issues = [i for i in issues if i.field == "year"]
        assert len(year_issues) == 1
