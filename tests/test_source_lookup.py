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


# ADDED (2026-11-17): locate_sources on verbatim, altered and unrelated text.
# ---------- locate_sources: find a passage's real section by content ----------

from citation_extractor.source_lookup import locate_sources

LOCATE_CORPUS = {
    "AS 25.24.150": ("In making an order for custody the court shall consider the physical, "
                     "emotional, mental, religious, and social needs of the child and the "
                     "capability and desire of each parent to meet these needs."),
    "AS 25.20.060": ("Neither parent, regardless of the question of the child's legitimacy, is "
                     "entitled to preference in the awarding of custody."),
}


def test_locates_section_a_passage_was_copied_from():
    text = "the physical, emotional, mental, religious, and social needs of the child"
    assert locate_sources(text, LOCATE_CORPUS) == ["AS 25.24.150"]


def test_locates_an_altered_passage():
    text = "is entitled to preference in the awarding of custody under all circumstances"
    assert locate_sources(text, LOCATE_CORPUS) == ["AS 25.20.060"]


def test_locates_nothing_for_unrelated_text():
    assert locate_sources("the weather was fine and the river was high today", LOCATE_CORPUS) == []
