"""Unit tests for the statutes/rules citation extractor.

Valid and malformed synthetic citations, mirroring the formats observed in
the 200 benchmark documents and the answer key.
"""

import pytest

from citation_extractor import extract_citations_from_text, normalize_citation


class TestStatutes:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("pursuant to AS 25.24.946", "AS 25.24.946"),
            ("AS 25.20.070 establishes that", "AS 25.20.070"),
            ("The rule in AS 25.24.220(d)(2) is", "AS 25.24.220"),
            ("AS 25.24.160(a)(4) requires", "AS 25.24.160"),
            ("Alaska Statute AS 25.20.060 grants", "AS 25.20.060"),
            ("Alaska Statute 25.24.150(c) sets", "AS 25.24.150"),
            ("Alaska Statute 25.30.300 provides", "AS 25.30.300"),
        ],
    )
    def test_valid_statutes(self, text, expected):
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "statute"] == [expected]

    def test_multiple_statutes_in_one_paragraph(self):
        text = "The court relies on AS 25.24.200 and AS 25.24.220."
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "statute"] == [
            "AS 25.24.200",
            "AS 25.24.220",
        ]

    def test_statute_deduplicated_within_paragraph(self):
        text = "AS 25.24.160(a) and AS 25.24.160(b) both apply."
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "statute"] == ["AS 25.24.160"]

    def test_bare_section_number_is_not_a_citation(self):
        text = "the 25.24.160 amount was not reached"
        cites = extract_citations_from_text(text)
        assert [c for c in cites if c.type == "statute"] == []

    def test_statute_text_is_preserved(self):
        cites = extract_citations_from_text("per AS 25.24.946, the court")
        assert cites[0].text == "AS 25.24.946"
        assert cites[0].type == "statute"


class TestCivilRules:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("child support is governed by Civil Rule 90.3.", "Alaska R. Civ. P. 90.3"),
            ("Civil Rule 90.3(a)(1) is determined", "Alaska R. Civ. P. 90.3"),
            ("Alaska Civil Rule 90.3 applies", "Alaska R. Civ. P. 90.3"),
            ("under Rule 90.3 the formula", "Alaska R. Civ. P. 90.3"),
            ("Civil Rule 16.2(e) is", "Alaska R. Civ. P. 16.2"),
            ("Civil Rule 100(a) governs", "Alaska R. Civ. P. 100"),
        ],
    )
    def test_valid_civil_rules(self, text, expected):
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "rule"] == [expected]

    def test_fabricated_rule_is_extracted(self):
        text = "pursuant to Civil Rule 913(b), the court"
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites] == ["Alaska R. Civ. P. 913"]

    def test_rule_deduplicated_within_paragraph(self):
        text = "Civil Rule 90.3(a) and Civil Rule 90.3(b) both apply."
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "rule"] == ["Alaska R. Civ. P. 90.3"]


class TestEvidenceRules:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Alaska R. Evid. 104(a) allows", "Alaska R. Evid. 104"),
            ("Alaska R. Evid. 201(d)", "Alaska R. Evid. 201"),
            ("Alaska R. Evid. 401", "Alaska R. Evid. 401"),
            ("Alaska R. Evid. 504(d) is", "Alaska R. Evid. 504"),
        ],
    )
    def test_valid_evidence_rules(self, text, expected):
        cites = extract_citations_from_text(text)
        assert [c.normalized for c in cites if c.type == "rule"] == [expected]


class TestNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("AS 25.24.310(a)", "AS 25.24.310"),
            ("Alaska Statute AS 25.20.060", "AS 25.20.060"),
            ("Civil Rule 90.3(a)(3)", "Alaska R. Civ. P. 90.3"),
            ("Rule 90.3", "Alaska R. Civ. P. 90.3"),
            ("Alaska R. Evid. 104(a)", "Alaska R. Evid. 104"),
            ("Alaska R. Civ. P. 90.1", "Alaska R. Civ. P. 90.1"),
        ],
    )
    def test_normalize(self, raw, expected):
        assert normalize_citation(raw) == expected


class TestParagraphPosition:
    def test_paragraph_index_is_reported(self):
        text = "The court applies AS 25.24.220."
        cites = extract_citations_from_text(text, paragraph_index=4)
        assert cites[0].paragraph_index == 4

    def test_doc_id_is_reported(self):
        text = "per AS 25.24.946"
        cites = extract_citations_from_text(text, doc_id="doc-0001")
        assert cites[0].doc_id == "doc-0001"