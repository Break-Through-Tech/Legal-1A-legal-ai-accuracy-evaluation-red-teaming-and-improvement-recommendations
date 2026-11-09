"""Tests for the per-document hallucination-risk score."""

import json

import pytest

from citation_extractor.document_risk import (
    ALTERED_QUOTE,
    POSSIBLE_ALTERATION,
    RISK_THRESHOLD,
    assess_document,
    existence_findings,
    quote_findings,
    score_document,
)
from citation_extractor.existence import load_corpus_name_index, load_corpus_reporter_index
from citation_extractor.extractor import Citation
from citation_extractor.labels import FABRICATED, OUT_OF_SCOPE, REAL, WRONG_REPORTER


# ---------- score_document ----------

def test_no_findings_scores_zero():
    assert score_document([]) == 0.0


def test_only_real_and_out_of_scope_scores_zero():
    assert score_document([REAL, REAL, OUT_OF_SCOPE]) == 0.0


def test_one_fabrication_scores_one():
    assert score_document([REAL, FABRICATED]) == pytest.approx(1.0)


def test_findings_combine():
    # 1 - (1 - 0.5) * (1 - 0.2) = 0.6
    assert score_document([WRONG_REPORTER, POSSIBLE_ALTERATION]) == pytest.approx(0.6)


def test_unknown_label_weighs_zero():
    assert score_document(["some_new_finding"]) == 0.0


# ---------- assess_document ----------

def test_fabrication_is_flagged():
    result = assess_document([REAL, FABRICATED])
    assert result["flagged"] is True
    assert result["counts"] == {FABRICATED: 1}


def test_weak_flags_alone_are_not_flagged():
    # 1 - 0.8 * 0.8 = 0.36, below the 0.5 threshold
    result = assess_document([POSSIBLE_ALTERATION, POSSIBLE_ALTERATION])
    assert result["score"] < RISK_THRESHOLD
    assert result["flagged"] is False


def test_altered_quote_is_flagged():
    assert assess_document([ALTERED_QUOTE])["flagged"] is True


def test_counts_skip_zero_weight_findings():
    assert assess_document([REAL, OUT_OF_SCOPE, WRONG_REPORTER])["counts"] == {WRONG_REPORTER: 1}


def test_custom_threshold():
    assert assess_document([WRONG_REPORTER], threshold=0.9)["flagged"] is False


# ---------- existence_findings ----------

@pytest.fixture
def case_indexes(tmp_path):
    """Small hermetic case corpus, same layout as cases.jsonl."""
    corpus = tmp_path / "cases.jsonl"
    corpus.write_text(json.dumps({"case_name": "Hayes v. Hayes", "reporter_cite": "922 P.2d 896"}))
    return load_corpus_reporter_index(corpus), load_corpus_name_index(corpus)


def test_existence_findings_labels_each_citation(case_indexes):
    reporter_index, name_index = case_indexes
    statutes = [
        Citation(text="AS 25.24.150", normalized="AS 25.24.150", type="statute"),
        Citation(text="AS 25.24.946", normalized="AS 25.24.946", type="statute"),
    ]
    cases = [{"case_name": "Hayes v. Hayes", "reporter_cite": "922 P.2d 896"}]
    findings = existence_findings(
        statutes, cases, {"as 25.24.150"}, set(), set(), reporter_index, name_index
    )
    assert sorted(findings) == sorted([REAL, FABRICATED, REAL])


def test_repeated_citation_counts_once(case_indexes):
    reporter_index, name_index = case_indexes
    cases = [{"case_name": "Restol v. Manshen", "reporter_cite": "512 P.3d 88"}] * 3
    findings = existence_findings([], cases, set(), set(), set(), reporter_index, name_index)
    assert findings == [FABRICATED]


# ---------- quote_findings ----------

SOURCE = (
    "In determining the best interests of the child the court shall consider "
    "the physical, emotional, mental, religious, and social needs of the child."
)
SOURCE_CORPUS = {"AS 25.24.150": SOURCE}


def passage(text, quoted=True, citation="AS 25.24.150(c)"):
    """A passage dict shaped like unquoted_passages.extract_passages output."""
    return {"text": text, "citation": citation, "quoted": quoted}


def test_faithful_quote_is_real():
    findings = quote_findings([passage("the court shall consider the physical")], SOURCE_CORPUS)
    assert findings == [REAL]


ALTERED = (
    "the physical, emotional, mental, religious, and social needs of the child "
    "under all circumstances"
)


def test_altered_quote_in_quote_marks():
    assert quote_findings([passage(ALTERED)], SOURCE_CORPUS) == [ALTERED_QUOTE]


def test_altered_unquoted_passage_is_possible_alteration():
    assert quote_findings([passage(ALTERED, quoted=False)], SOURCE_CORPUS) == [POSSIBLE_ALTERATION]


def test_short_altered_quote_falls_below_unrelated_floor():
    # Known limit of quote_fidelity's floor (70): on a short quote the appended
    # phrase is a large share of the text, so it scores ~66 and is not judged.
    text = "the social needs of the child under all circumstances"
    assert quote_findings([passage(text)], SOURCE_CORPUS) == []


def test_unjudged_passages_add_no_finding():
    # no citation, citation not in corpus, and text unrelated to its source
    passages = [
        passage("the court shall consider", citation=None),
        passage("the court shall consider", citation="AS 25.24.946"),
        passage("I will make sure you never see the kids again"),
    ]
    assert quote_findings(passages, SOURCE_CORPUS) == []
