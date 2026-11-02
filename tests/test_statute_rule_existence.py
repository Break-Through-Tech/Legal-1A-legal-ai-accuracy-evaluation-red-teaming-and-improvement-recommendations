"""Tests for statute and court-rule existence checking (DATA_DICTIONARY §3.1)."""

import json
from pathlib import Path

import pytest

from citation_extractor.statute_rule_existence import (
    FABRICATED,
    OUT_OF_SCOPE,
    REAL,
    check_rule_existence,
    check_statute_existence,
    load_civil_rule_index,
    load_evidence_rule_index,
    load_statute_index,
)


@pytest.fixture
def indexes(tmp_path):
    """Small hermetic corpus mirroring the real files' field layout."""
    statutes = tmp_path / "statutes.jsonl"
    statutes.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"citation": "AS 25.24.150", "status": "active"},
                {"citation": "AS 25.24.900", "status": "active"},
                {"citation": "AS 18.66.100", "status": "active"},
            ]
        )
    )
    civil = tmp_path / "rules.jsonl"
    civil.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"citation": "Alaska R. Civ. P. 90.3", "subrule": "a"},
                {"citation": "Alaska R. Civ. P. 90.3", "subrule": "b"},
                {"citation": "Alaska R. Civ. P. 16.2", "subrule": None},
            ]
        )
    )
    evidence = tmp_path / "rules-evidence.jsonl"
    evidence.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"ruleNumber": "505", "ruleset": "evidence"},
                {"ruleNumber": "104", "ruleset": "evidence"},
            ]
        )
    )
    return (
        load_statute_index(statutes),
        load_civil_rule_index(civil),
        load_evidence_rule_index(evidence),
    )


class TestStatuteExistence:
    def test_real_statute(self, indexes):
        assert check_statute_existence("AS 25.24.150", indexes[0]) == REAL

    def test_pinpoint_stripped(self, indexes):
        assert check_statute_existence("AS 25.24.150(a)(3)", indexes[0]) == REAL

    def test_prose_prefix_normalized(self, indexes):
        assert check_statute_existence("Alaska Statute 25.24.150", indexes[0]) == REAL

    def test_fabricated_statute(self, indexes):
        assert check_statute_existence("AS 25.24.946", indexes[0]) == FABRICATED

    def test_900_range_collision_is_present(self, indexes):
        # AS 25.24.900 is a real corpus section even though the benchmark plants
        # it as a "fabricated" replacement; the checker reports the corpus truth.
        assert check_statute_existence("AS 25.24.900", indexes[0]) == REAL

    def test_title_outside_corpus_is_out_of_scope(self, indexes):
        # The corpus has only Titles 18 and 25; AS 11.56.807 is real law it can't check.
        assert check_statute_existence("AS 11.56.807", indexes[0]) == OUT_OF_SCOPE

    def test_missing_section_in_covered_title_is_fabricated(self, indexes):
        assert check_statute_existence("AS 18.66.946", indexes[0]) == FABRICATED


class TestRuleExistence:
    def test_civil_rule_short_form(self, indexes):
        assert check_rule_existence("Civil Rule 90.3(a)", indexes[1], indexes[2]) == REAL

    def test_bare_rule_form(self, indexes):
        assert check_rule_existence("Rule 90.3", indexes[1], indexes[2]) == REAL

    def test_formal_civil_rule(self, indexes):
        assert check_rule_existence("Alaska R. Civ. P. 16.2", indexes[1], indexes[2]) == REAL

    def test_evidence_rule(self, indexes):
        assert check_rule_existence("Alaska R. Evid. 505", indexes[1], indexes[2]) == REAL

    def test_fabricated_rule(self, indexes):
        assert check_rule_existence("Civil Rule 913(b)", indexes[1], indexes[2]) == FABRICATED

    def test_namespaces_do_not_collide(self, indexes):
        # 90.3 is a civil rule, not an evidence rule.
        assert check_rule_existence("Civil Rule 90.3", indexes[1], indexes[2]) == REAL
        assert check_rule_existence("Alaska R. Evid. 90.3", indexes[1], indexes[2]) == FABRICATED

    def test_other_family_is_out_of_scope(self, indexes):
        assert check_rule_existence("Appellate Rule 5", indexes[1], indexes[2]) == OUT_OF_SCOPE


@pytest.mark.integration
def test_real_corpus_loads():
    corpus = Path(__file__).resolve().parents[1] / "data" / "corpus"
    if not (corpus / "statutes.jsonl").exists():
        pytest.skip("corpus not present")

    statutes = load_statute_index(corpus / "statutes.jsonl")
    civil = load_civil_rule_index(corpus / "rules.jsonl")
    evidence = load_evidence_rule_index(corpus / "rules-evidence.jsonl")

    assert check_statute_existence("AS 25.24.150", statutes) == REAL
    assert check_statute_existence("AS 25.24.946", statutes) == FABRICATED
    assert check_statute_existence("AS 11.56.807", statutes) == OUT_OF_SCOPE
    assert check_rule_existence("Civil Rule 90.3(b)", civil, evidence) == REAL
    assert check_rule_existence("Civil Rule 913", civil, evidence) == FABRICATED
    assert check_rule_existence("Alaska R. Evid. 505", civil, evidence) == REAL
