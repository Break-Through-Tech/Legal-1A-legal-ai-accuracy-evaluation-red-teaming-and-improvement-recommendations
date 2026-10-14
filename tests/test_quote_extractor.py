"""Tests for quote extraction. Examples are taken from real benchmark documents."""

import pytest

from citation_extractor.quote_extractor import (
    attach_citation,
    extract_quotes,
    find_quotes,
    is_legal_quote,
)

# From doc-0014
RULE_PARA = (
    'Because David Bergstrom is seeking primary physical custody, child support is '
    'governed by Civil Rule 90.3(a), which provides that "a child support award in a '
    'case in which one parent is awarded primary physical custody as defined by '
    'paragraph (f) will be calculated as an amount equal to the adjusted annual income '
    'of the non-custodial parent multiplied by a percentage specified in subparagraph '
    '(a)(2)." For two children, that percentage is twenty-seven percent.'
)

# From doc-0002 (two quotes, two different statutes)
TWO_CITE_PARA = (
    'The division of marital property must be "in a just manner" under AS 25.24.160(a)(4). '
    'AS 25.24.230(a)(3) requires that the division of property "fairly allocate the '
    'economic effect of dissolution".'
)


# ---------- find_quotes ----------

def test_find_straight_quote():
    quotes = find_quotes(RULE_PARA)
    assert len(quotes) == 1
    assert quotes[0]["text"].startswith("a child support award")
    assert quotes[0]["text"].endswith("(a)(2).")  # period inside the quote is kept


def test_find_curly_quote():
    quotes = find_quotes("the court must consider “the circumstances and necessities of each party”.")
    assert [q["text"] for q in quotes] == ["the circumstances and necessities of each party"]


def test_find_multiple_quotes_in_order():
    quotes = find_quotes(TWO_CITE_PARA)
    assert [q["text"] for q in quotes] == [
        "in a just manner",
        "fairly allocate the economic effect of dissolution",
    ]


def test_positions_point_at_quote_text():
    q = find_quotes(RULE_PARA)[0]
    assert RULE_PARA[q["start"]:q["end"]] == q["text"]


# ---------- is_legal_quote ----------

def test_rejects_hereinafter_label():
    para = 'the petition of Priya Larsen (hereinafter "Petitioner") for dissolution'
    q = find_quotes(para)[0]
    assert not is_legal_quote(q, para)


def test_rejects_short_quote():
    para = 'he said it was "fine" yesterday'
    q = find_quotes(para)[0]
    assert not is_legal_quote(q, para)


def test_accepts_statute_quote():
    q = find_quotes(RULE_PARA)[0]
    assert is_legal_quote(q, RULE_PARA)


# ---------- attach_citation ----------

def test_attaches_preceding_rule():
    q = find_quotes(RULE_PARA)[0]
    assert attach_citation(RULE_PARA, q["start"]) == "Civil Rule 90.3(a)"


def test_attaches_nearest_preceding_citation():
    second = find_quotes(TWO_CITE_PARA)[1]
    assert attach_citation(TWO_CITE_PARA, second["start"]) == "AS 25.24.230(a)(3)"


def test_no_preceding_citation_returns_none():
    first = find_quotes(TWO_CITE_PARA)[0]  # its statute comes AFTER the quote
    assert attach_citation(TWO_CITE_PARA, first["start"]) is None


# ---------- extract_quotes (real document) ----------

def test_extract_quotes_doc_0014():
    quotes = extract_quotes("data/benchmark/documents/doc-0014.docx", doc_id="doc-0014")
    cites = [q["citation"] for q in quotes]
    assert "Civil Rule 90.3(a)" in cites
    assert any(q["text"].startswith("the desirability of awarding the family home") for q in quotes)
    assert all(q["doc_id"] == "doc-0014" for q in quotes)
