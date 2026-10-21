"""Tests for finding verbatim passages that are not in quote marks."""

from citation_extractor.quote_fidelity import check_quote
from citation_extractor.unquoted_passages import find_unquoted_passages

SOURCE = (
    "A petition for dissolution of marriage may be filed when incompatibility of "
    "temperament has caused the irremediable breakdown of the marriage. The court "
    "shall consider the physical, emotional, mental, religious, and social needs of the child."
)
SOURCES = {"AS 25.24.200": SOURCE}


def only(paragraph):
    passages = find_unquoted_passages(paragraph, SOURCES)
    assert len(passages) == 1
    return passages[0]


def test_finds_verbatim_passage_without_quote_marks():
    p = only("Under AS 25.24.200, a petition may be filed when incompatibility of "
             "temperament has caused the irremediable breakdown of the marriage. The statute applies.")
    assert "incompatibility of temperament has caused the irremediable breakdown" in p["text"]
    assert p["citation"] == "AS 25.24.200"
    assert check_quote(p["text"], SOURCE)["faithful"] is True


def test_citation_after_passage():
    p = only("The court shall consider the physical, emotional, mental, religious, and social "
             "needs of the child. AS 25.24.200.")
    assert check_quote(p["text"], SOURCE)["faithful"] is True


def test_words_added_at_end_of_source_clause_are_included():
    p = only("A petition may be filed when incompatibility of temperament has caused the "
             "irremediable breakdown of the marriage in every case. The statute applies.")
    assert p["text"].endswith("breakdown of the marriage in every case")
    assert check_quote(p["text"], SOURCE)["faithful"] is False


def test_trailing_citation_is_not_an_addition():
    p = only("A petition may be filed when incompatibility of temperament has caused the "
             "irremediable breakdown of the marriage under AS 25.24.200.")
    assert p["text"].endswith("breakdown of the marriage")


def test_paraphrase_after_mid_clause_run_is_not_included():
    # The run stops mid-clause in the source ("...mental, religious"), so the
    # drafter's own continuation is paraphrase, not an addition.
    p = only("The court shall consider the physical, emotional, mental, religious, and moral fitness of each parent.")
    assert "moral" not in p["text"]


def test_short_overlap_is_not_a_passage():
    assert find_unquoted_passages("The court shall consider the evidence.", SOURCES) == []
