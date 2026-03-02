"""Tests for CrossRef client (uses mocked responses)."""

from unittest.mock import MagicMock, patch

from src.crossref_client import CrossRefClient, _build_query, _title_similarity
from src.models import Reference, Status


class TestBuildQuery:
    def test_full_fields(self):
        ref = Reference(raw="", index=1, authors="Smith, J.", title="Deep learning", year="2023")
        q = _build_query(ref)
        assert "Smith" in q
        assert "Deep learning" in q
        assert "2023" in q

    def test_title_only(self):
        ref = Reference(raw="", index=1, title="Just a title")
        q = _build_query(ref)
        assert q == "Just a title"

    def test_empty(self):
        ref = Reference(raw="", index=1)
        assert _build_query(ref) == ""


class TestTitleSimilarity:
    def test_identical(self):
        assert _title_similarity("Deep Learning", "Deep Learning") > 0.99

    def test_case_insensitive(self):
        assert _title_similarity("Deep Learning", "deep learning") > 0.99

    def test_punctuation_ignored(self):
        assert _title_similarity("Self-supervised learning", "Selfsupervised learning") > 0.9

    def test_different(self):
        assert _title_similarity("Deep learning for NLP", "Quantum computing basics") < 0.3

    def test_empty(self):
        assert _title_similarity("", "anything") == 0.0

    def test_close_match(self):
        # Realistic case: CrossRef may return slightly different title
        a = "Functional map of the world"
        b = "Functional Map of the World"
        assert _title_similarity(a, b) > 0.95


class TestCrossRefClient:
    def _mock_response(self, score, title="Matched Title", doi="10.1234/test"):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "message": {
                "items": [
                    {"score": score, "title": [title], "DOI": doi}
                ]
            }
        }
        resp.raise_for_status = MagicMock()
        return resp

    @patch("src.crossref_client.requests.Session")
    def test_verified_by_score(self, mock_session_cls):
        session = MagicMock()
        session.get.return_value = self._mock_response(95)
        mock_session_cls.return_value = session

        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1, title="Test", authors="Smith", year="2023")
        result = client.verify(ref)
        assert result.status == Status.VERIFIED
        assert result.score == 95

    @patch("src.crossref_client.requests.Session")
    def test_verified_by_title_similarity(self, mock_session_cls):
        """Low CrossRef score but high title similarity → VERIFIED."""
        session = MagicMock()
        session.get.return_value = self._mock_response(
            30, title="Functional Map of the World"
        )
        mock_session_cls.return_value = session

        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1, title="Functional map of the world", authors="Christie")
        result = client.verify(ref)
        assert result.status == Status.VERIFIED

    @patch("src.crossref_client.requests.Session")
    def test_likely_match(self, mock_session_cls):
        session = MagicMock()
        session.get.return_value = self._mock_response(55)
        mock_session_cls.return_value = session

        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1, title="Test")
        result = client.verify(ref)
        assert result.status == Status.LIKELY_MATCH

    @patch("src.crossref_client.requests.Session")
    def test_not_found(self, mock_session_cls):
        session = MagicMock()
        session.get.return_value = self._mock_response(10, title="Totally unrelated paper")
        mock_session_cls.return_value = session

        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1, title="Test")
        result = client.verify(ref)
        assert result.status == Status.NOT_FOUND

    @patch("src.crossref_client.requests.Session")
    def test_doi_direct_lookup(self, mock_session_cls):
        """When ref has a DOI, verify by direct lookup first."""
        session = MagicMock()
        doi_resp = MagicMock()
        doi_resp.status_code = 200
        doi_resp.json.return_value = {
            "message": {"title": ["The Paper"], "DOI": "10.1234/known"}
        }
        doi_resp.raise_for_status = MagicMock()
        session.get.return_value = doi_resp
        mock_session_cls.return_value = session

        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1, title="The Paper", doi="10.1234/known")
        result = client.verify(ref)
        assert result.status == Status.VERIFIED
        assert result.matched_doi == "10.1234/known"

    def test_no_query_returns_error(self):
        client = CrossRefClient(rate_limit=0)
        ref = Reference(raw="", index=1)
        result = client.verify(ref)
        assert result.status == Status.ERROR
