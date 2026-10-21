"""Tests for source-text lookup against the real corpus."""

import pytest

from citation_extractor.source_lookup import (
    DEFAULT_CORPUS_DIR,
    clean_whitespace,
    get_source_text,
    load_corpus,
)


@pytest.fixture(scope="module")
def corpus():
    # Loaded once and shared by every test in this file.
    if not (DEFAULT_CORPUS_DIR / "statutes.jsonl").exists():
        pytest.skip("corpus not present")
    return load_corpus()


# ---------- clean_whitespace ----------

def test_clean_whitespace_joins_pdf_line_breaks():
    assert clean_whitespace("A child\nsupport  award\n") == "A child support award"


# ---------- statutes ----------

@pytest.mark.integration
def test_statute_with_pinpoint(corpus):
    text = get_source_text("AS 25.24.150(c)", corpus)
    assert "the physical, emotional, mental, religious, and social needs of the child" in text


@pytest.mark.integration
def test_statute_has_no_line_breaks(corpus):
    assert "\n" not in get_source_text("AS 25.24.150", corpus)


@pytest.mark.integration
def test_repealed_statute_has_no_text(corpus):
    # AS 25.05.010 is repealed; its source_text is the string "None".
    assert get_source_text("AS 25.05.010", corpus) is None


@pytest.mark.integration
def test_fabricated_statute_returns_none(corpus):
    assert get_source_text("AS 25.24.946", corpus) is None


# ---------- civil rules ----------

@pytest.mark.integration
def test_civil_rule_joins_all_subrules(corpus):
    text = get_source_text("Civil Rule 90.3(a)", corpus)
    assert "Guidelines—Primary Physical Custody" in text   # from subrule (a)
    assert "Shared, Divided, and Hybrid Physical Custody" in text  # from subrule (b)


@pytest.mark.integration
def test_rule_spellings_give_same_text(corpus):
    assert (
        get_source_text("Civil Rule 90.3", corpus)
        == get_source_text("Rule 90.3(a)(1)", corpus)
        == get_source_text("Alaska R. Civ. P. 90.3", corpus)
    )


@pytest.mark.integration
def test_fabricated_rule_returns_none(corpus):
    assert get_source_text("Civil Rule 913(b)", corpus) is None


# ---------- evidence rules ----------

@pytest.mark.integration
def test_evidence_rule(corpus):
    text = get_source_text("Alaska R. Evid. 505(a)", corpus)
    assert "Spousal Immunity" in text


@pytest.mark.integration
def test_evidence_rule_excludes_commentary(corpus):
    assert "has been substantially revised" not in get_source_text("Alaska R. Evid. 505", corpus)
