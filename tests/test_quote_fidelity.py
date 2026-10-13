"""Tests for quote-fidelity checking."""

from citation_extractor.quote_fidelity import check_quote, normalize_text

SOURCE = (
    "In determining the best interests of the child the court shall consider "
    "(1) the physical, emotional, mental, religious, and social needs of the child; "
    "(2) the capability and desire of each parent to meet these needs; "
    "(3) the child's preference if the child is of sufficient age and capacity."
)


# ---------- normalize_text ----------

def test_normalize_ignores_case_punctuation_and_curly_quotes():
    assert normalize_text("The Child’s  “Preference”;\n") == "the child s preference"


# ---------- faithful ----------

def test_exact_match():
    result = check_quote("the capability and desire of each parent to meet these needs", SOURCE)
    assert result["tier"] == "exact"
    assert result["faithful"] is True


def test_curly_apostrophe_and_case_are_normalized():
    result = check_quote("The child’s preference if the child is of sufficient age", SOURCE)
    assert result["tier"] == "normalized"
    assert result["faithful"] is True


def test_line_breaks_in_quote():
    result = check_quote("the court shall\nconsider", SOURCE)
    assert result["faithful"] is True


def test_ellipsis_skips_omitted_text():
    result = check_quote("the court shall consider . . . the capability and desire of each parent", SOURCE)
    assert result["tier"] == "normalized"
    assert result["faithful"] is True


# ---------- altered ----------

def test_appended_phrase_is_altered():
    # The most common planted alteration in the benchmark.
    result = check_quote(
        "the physical, emotional, mental, religious, and social needs of the child "
        "under all circumstances",
        SOURCE,
    )
    assert result["tier"] == "fuzzy"
    assert result["faithful"] is False


def test_swapped_word_is_altered():
    result = check_quote("In determining the best interests of the child the court may consider", SOURCE)
    assert result["faithful"] is False


def test_quote_longer_than_source_with_added_words_is_altered():
    short_source = "the court shall consider the needs of the child"
    result = check_quote(short_source + " under all circumstances and in every case", short_source)
    assert result["faithful"] is False


def test_ellipsis_pieces_out_of_order_are_not_normalized_match():
    result = check_quote("the capability and desire . . . the court shall consider", SOURCE)
    assert result["tier"] == "fuzzy"


def test_partial_word_does_not_count_as_match():
    # "needs of the chil" must not match inside "needs of the child".
    result = check_quote("social needs of the chil", SOURCE)
    assert result["tier"] != "normalized"


# ---------- no source ----------

def test_missing_source():
    result = check_quote("anything at all here", None)
    assert result == {"tier": "no_source", "score": None, "faithful": None, "closest": None}
