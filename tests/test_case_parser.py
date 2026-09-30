from src.case_parser import (
    extract_case_name_from_context,
    extract_paragraph,
    normalize_citation,
)


def test_full_p3d_citation():
    text = "Smith v. Jones, 123 P.3d 456 (Alaska 2005)"
    citations, unparsed = extract_paragraph(text, "doc-test", 0)
    assert len(citations) == 1
    c = citations[0]
    assert c["case_name"] == "Smith v. Jones"
    assert c["reporter_cite"] == "123 P.3d 456"
    assert c["year"] == 2005
    assert c["paragraph_index"] == 0
    assert c["position_start"] == 0
    assert not unparsed


def test_p2d_and_abbreviated_parties():
    text = "D.D. v. L.A.H., 27 P.2d 757 (Alaska 2001)"
    citations, _ = extract_paragraph(text, "doc-test", 3)
    assert citations[0]["case_name"] == "D.D. v. L.A.H."
    assert citations[0]["reporter_cite"] == "27 P.2d 757"
    assert citations[0]["paragraph_index"] == 3


def test_leading_prose_removed():
    context = "As the court recognized in Pingree v. Cossette, "
    assert extract_case_name_from_context(context) == "Pingree v. Cossette"


def test_reporter_only_citation():
    text = "The court relied on 123 P.3d 456 for that proposition."
    citations, _ = extract_paragraph(text, "doc-test", 1)
    assert len(citations) == 1
    assert citations[0]["citation_type"] == "reporter_only"
    assert citations[0]["reporter_cite"] == "123 P.3d 456"


def test_normalized_form():
    assert normalize_citation("Smith v. Jones,   123 P.3d 456 (Alaska 2005)") == (
        "smith v. jones, 123 p.3d 456 (alaska 2005)"
    )


def test_subsequent_history():
    text = (
        "Smith v. Jones, 123 P.3d 456 (Alaska 2005), "
        "aff'd, 140 P.3d 100 (Alaska 2006)."
    )
    citations, _ = extract_paragraph(text, "doc-test", 0)
    full = citations[0]
    assert full["subsequent_history"] is not None
    assert full["subsequent_history"].lower().startswith("aff'd")


def test_malformed_citation_logged():
    text = "Smith v. Jones, 123 P.XYZ 456 (Alaska 2005)."
    citations, unparsed = extract_paragraph(text, "doc-test", 0)
    assert citations == []
    assert len(unparsed) >= 1
    assert unparsed[0]["status"] == "UNPARSED"


def test_document_and_position_metadata():
    text = "Background. Smith v. Jones, 123 P.3d 456 (Alaska 2005)."
    citations, _ = extract_paragraph(text, "doc-0042", 7)
    c = citations[0]
    assert c["document_id"] == "doc-0042"
    assert c["paragraph_index"] == 7
    assert c["position_start"] == text.index("Smith")
    assert c["position_end"] > c["position_start"]
