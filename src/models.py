from __future__ import annotations

import enum
from dataclasses import dataclass, field


class Status(enum.Enum):
    VERIFIED = "verified"
    LIKELY_MATCH = "likely_match"
    NOT_FOUND = "not_found"
    ERROR = "error"


@dataclass
class Reference:
    raw: str
    index: int
    authors: str = ""
    title: str = ""
    year: str = ""
    venue: str = ""
    doi: str = ""
    arxiv_id: str = ""
    url: str = ""


@dataclass
class CrossRefResult:
    status: Status
    score: float = 0.0
    matched_title: str = ""
    matched_doi: str = ""
    message: str = ""


@dataclass
class ScholarResult:
    found: bool = False
    title: str = ""
    url: str = ""
    message: str = ""


@dataclass
class FormatIssue:
    ref_index: int
    field: str
    issue: str


@dataclass
class ArxivResult:
    found: bool = False
    arxiv_id: str = ""
    title: str = ""
    url: str = ""
    message: str = ""


@dataclass
class VerificationResult:
    reference: Reference
    crossref: CrossRefResult | None = None
    scholar: ScholarResult | None = None
    arxiv: ArxivResult | None = None

    @property
    def status(self) -> Status:
        # arXiv confirmation upgrades NOT_FOUND to VERIFIED
        if self.arxiv and self.arxiv.found:
            if self.crossref and self.crossref.status in (Status.VERIFIED, Status.LIKELY_MATCH):
                return self.crossref.status
            return Status.VERIFIED
        if self.crossref:
            return self.crossref.status
        return Status.NOT_FOUND


@dataclass
class PaperReport:
    filename: str
    total_refs: int = 0
    results: list[VerificationResult] = field(default_factory=list)
    format_issues: list[FormatIssue] = field(default_factory=list)

    @property
    def verified_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.VERIFIED)

    @property
    def likely_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.LIKELY_MATCH)

    @property
    def not_found_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.NOT_FOUND)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.results if r.status == Status.ERROR)
