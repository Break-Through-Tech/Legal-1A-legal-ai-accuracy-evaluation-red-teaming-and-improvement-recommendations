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


def test_bracketed_edit_is_faithful():
    # "[s]" is the legal convention for an editor's change.
    result = check_quote("the court shall consider[s] (1) the physical, emotional", SOURCE)
    assert result["tier"] == "normalized"


def test_dropped_list_marker_is_faithful():
    # Source reads "...shall consider (1) the physical..."; quote omits "(1)".
    result = check_quote("the court shall consider the physical, emotional, mental", SOURCE)
    assert result["tier"] == "normalized"


def test_spelled_out_section_range_is_faithful():
    # Corpus writes ranges with an em dash; doc-0144 spells it "through".
    source = "(2) for protection under AS 18.66.100 — 18.66.180; (3) directing one spouse"
    result = check_quote("for protection under AS 18.66.100 through 18.66.180.", source)
    assert result["tier"] == "normalized"
    assert result["faithful"] is True


def test_through_between_words_is_kept():
    # Only "through" between two numbers is a range; ordinary prose keeps it.
    result = check_quote("the court shall consider through the physical", SOURCE)
    assert result["faithful"] is not True


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
    result = check_quote(short_source + " under all circumstances", short_source)
    assert result["tier"] == "fuzzy"
    assert result["faithful"] is False


def test_unrelated_quote_is_not_judged():
    # Testimony attached to the nearest statute is not an altered quote of it.
    result = check_quote("I will make sure you never see the kids again", SOURCE)
    assert result["tier"] == "unrelated"
    assert result["faithful"] is None


def test_ellipsis_pieces_out_of_order_are_not_normalized_match():
    result = check_quote("the capability and desire . . . the court shall consider", SOURCE)
    assert result["tier"] not in ("exact", "normalized")
    assert result["faithful"] is not True


def test_partial_word_does_not_count_as_match():
    # "needs of the chil" must not match inside "needs of the child".
    result = check_quote("social needs of the chil", SOURCE)
    assert result["tier"] != "normalized"


# ---------- no source ----------

def test_missing_source():
    result = check_quote("anything at all here", None)
    assert result == {"tier": "no_source", "score": None, "faithful": None, "closest": None}
