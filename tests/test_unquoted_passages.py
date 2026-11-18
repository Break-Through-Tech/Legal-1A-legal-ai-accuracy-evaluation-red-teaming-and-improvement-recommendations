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


# ADDED (2026-11-17): chained passages and judge_passage.
# --- passages broken by a small edit (natural misquotes) ---

from citation_extractor.unquoted_passages import judge_passage

EDIT_SOURCE = (
    "The court shall consider the physical, emotional, mental, religious, and social "
    "needs of the child and any other factor the court considers relevant to the dispute."
)
EDIT_SOURCES = {"AS 25.24.200": EDIT_SOURCE}


def chained(paragraph):
    passages = find_unquoted_passages(paragraph, EDIT_SOURCES)
    assert len(passages) == 1
    return passages[0]


def test_one_dropped_word_still_finds_the_passage():
    # "other" dropped: both halves are under 8 words, but together they are one passage.
    p = chained("The court shall consider the physical, emotional, mental, religious, and social "
                "needs of the child and any factor the court considers relevant to the dispute. AS 25.24.200.")
    assert p["chained"] is True
    assert p["dropped_words"] == ["other"]
    assert p["added_words"] == []


def test_dropped_function_word_is_judged_altered():
    p = chained("The court shall consider the physical, emotional, mental, religious, and social "
                "needs of the child and any factor the court considers relevant to the dispute. AS 25.24.200.")
    assert judge_passage(p, EDIT_SOURCE)["faithful"] is False


def test_content_word_edit_is_paraphrase_not_altered():
    # "factor" -> "matter" and "dispute" -> "case": content words, so not judged.
    p = chained("The court shall consider the physical, emotional, mental, religious, and social "
                "needs of the child and any other matter the court considers relevant to the case. AS 25.24.200.")
    result = judge_passage(p, EDIT_SOURCE)
    assert result["tier"] == "paraphrase"
    assert result["faithful"] is None


def test_verbatim_passage_is_not_chained():
    p = only("Under AS 25.24.200, a petition may be filed when incompatibility of "
             "temperament has caused the irremediable breakdown of the marriage.")
    assert p["chained"] is False
    assert judge_passage(p, SOURCE)["faithful"] is True


# ADDED (2026-11-17): RISK_WORDS rule: a dropped risk word is altered, content words alone are not.
RISK_SOURCE = (
    "A temporary restraining order may be granted without written or oral notice to the "
    "adverse party only if it clearly appears from specific facts shown by affidavit."
)


def test_dropped_risk_word_with_content_words_is_judged_altered():
    # "written or oral" and "only" are left out; nothing is added. "only" carries legal force.
    sources = {"Civil Rule 65(b)": RISK_SOURCE}
    paragraph = ("A temporary restraining order may be granted without notice to the adverse "
                 "party if it clearly appears from specific facts shown by affidavit. Civil Rule 65(b).")
    passages = find_unquoted_passages(paragraph, sources)
    assert len(passages) == 1 and passages[0]["chained"] is True
    assert passages[0]["added_words"] == []
    assert judge_passage(passages[0], RISK_SOURCE)["faithful"] is False


def test_dropped_content_words_alone_are_paraphrase():
    source = ("The court shall consider the physical, emotional, mental, religious, and social "
              "needs of the child and the stability of the home environment of each parent in the dispute.")
    paragraph = ("The court shall consider the physical, emotional, mental, religious, and social "
                 "needs of the child and the stability of each parent in the dispute. AS 25.24.200.")
    passages = find_unquoted_passages(paragraph, {"AS 25.24.200": source})
    assert len(passages) == 1
    assert judge_passage(passages[0], source)["tier"] == "paraphrase"


# ADDED (2026-11-17): the appended tail after "(a)(2)" must be included (doc-0170).
def test_appended_phrase_after_a_list_marker_is_included():
    # "(a)(2)" sits between the copied words and the appended "under all circumstances".
    source = ("a child support award shall be calculated as an amount equal to the adjusted "
              "annual income multiplied by a percentage specified in subparagraph (a)(2).")
    paragraph = ("Support is calculated as an amount equal to the adjusted annual income multiplied "
                 "by a percentage specified in subparagraph (a)(2) under all circumstances. Rule 90.3.")
    passages = find_unquoted_passages(paragraph, {"Rule 90.3": source})
    assert len(passages) == 1
    assert passages[0]["text"].endswith("under all circumstances")
    assert check_quote(passages[0]["text"], source)["faithful"] is False
