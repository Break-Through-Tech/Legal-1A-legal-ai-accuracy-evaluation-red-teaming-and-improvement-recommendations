"""Tests for case existence checking (existence.py).

Covers the case half of the Stage-2 existence checker (DATA_DICTIONARY §9):
whether an extracted case citation is real, real-with-the-wrong-reporter, or
fabricated, decided from the case corpus alone.
"""

import json
from pathlib import Path

import pytest

from citation_extractor.existence import (
    FABRICATED,
    REAL,
    WRONG_REPORTER,
    check_case_existence,
    load_corpus_name_index,
    load_corpus_reporter_index,
    names_compatible,
    normalize_key,
)


@pytest.fixture
def indexes(tmp_path):
    """Small hermetic corpus mirroring cases.jsonl's field layout."""
    corpus = tmp_path / "cases.jsonl"
    corpus.write_text(
        "\n".join(
            json.dumps(record)
            for record in [
                {"case_name": "Hayes v. Hayes", "reporter_cite": "922 P.2d 896"},
                {"case_name": "Del Rosario v. Clare", "reporter_cite": "987 P.2d 183"},
                {"case_name": "Kyoko Perry v. Adam Perry", "reporter_cite": "449 P.3d 700"},
            ]
        )
    )
    return load_corpus_name_index(corpus), load_corpus_reporter_index(corpus)


class TestIndexes:
    def test_reporter_index_keys_are_normalized(self, indexes):
        name_index, reporter_index = indexes
        assert "922 p.2d 896" in reporter_index
        assert "hayes v. hayes" in name_index

    def test_name_index_groups_records(self, indexes):
        name_index, _ = indexes
        assert len(name_index["hayes v. hayes"]) == 1


class TestNormalizeKey:
    def test_casefolds_and_collapses_whitespace(self):
        assert normalize_key("  Hayes   v.  HAYES ") == "hayes v. hayes"

    def test_trims_edge_punctuation(self):
        assert normalize_key("Hayes v. Hayes, ") == "hayes v. hayes"

    def test_empty_input(self):
        assert normalize_key("") == ""

    # ADDED (2026-10-20): "&" and "and" normalize to the same key.
    def test_ampersand_matches_and(self):
        assert normalize_key("Dep't of Health & Social Services") == normalize_key(
            "Dep't of Health and Social Services"
        )


class TestNamesCompatible:
    def test_exact_match(self):
        assert names_compatible("hayes v. hayes", "hayes v. hayes")

    def test_short_caption_suffix(self):
        # "rosario v. clare" vs "del rosario v. clare"
        assert names_compatible("rosario v. clare", "del rosario v. clare")

    def test_unrelated_names_do_not_match(self):
        assert not names_compatible("hayes v. hayes", "perry v. perry")

    def test_empty_is_false(self):
        assert not names_compatible("", "hayes v. hayes")


class TestCheckCaseExistence:
    def test_real_case(self, indexes):
        name_index, reporter_index = indexes
        assert check_case_existence("Hayes v. Hayes", "922 P.2d 896", reporter_index, name_index) == REAL

    def test_short_caption_resolves_by_reporter(self, indexes):
        name_index, reporter_index = indexes
        assert check_case_existence("Rosario v. Clare", "987 P.2d 183", reporter_index, name_index) == REAL

    def test_wrong_reporter(self, indexes):
        # real case name, reporter that is not its own
        name_index, reporter_index = indexes
        assert (
            check_case_existence("Hayes v. Hayes", "614 P.2d 743", reporter_index, name_index)
            == WRONG_REPORTER
        )

    def test_fabricated_case(self, indexes):
        name_index, reporter_index = indexes
        assert (
            check_case_existence("Restol v. Manshen", "512 P.3d 88", reporter_index, name_index)
            == FABRICATED
        )

    # ADDED (2026-10-20): reporter-only short cites have no case name to compare.
    def test_reporter_only_cite_in_corpus_is_real(self, indexes):
        name_index, reporter_index = indexes
        assert check_case_existence(None, "987 P.2d 183", reporter_index, name_index) == REAL

    def test_reporter_only_cite_not_in_corpus_is_fabricated(self, indexes):
        name_index, reporter_index = indexes
        assert check_case_existence(None, "512 P.3d 88", reporter_index, name_index) == FABRICATED


def test_real_corpus():
    corpus = Path(__file__).resolve().parents[1] / "data" / "corpus" / "cases.jsonl"
    if not corpus.exists():
        pytest.skip("corpus not present")

    name_index = load_corpus_name_index(corpus)
    reporter_index = load_corpus_reporter_index(corpus)

    # a real case straight from the corpus
    assert check_case_existence("Kyoko Perry v. Adam Perry", "449 P.3d 700", reporter_index, name_index) == REAL
    # real name, fabricated reporter (benchmark "wrong_reporter" corruption)
    assert (
        check_case_existence("Peter Chapman v. Julia Chapman", "725 P.3d 476", reporter_index, name_index)
        == WRONG_REPORTER
    )
    # invented case
    assert (
        check_case_existence("Restol v. Manshen", "512 P.3d 88", reporter_index, name_index) == FABRICATED
    )
