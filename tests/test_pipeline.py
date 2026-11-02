"""Tests for the unified document detector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from docx import Document

from citation_extractor.labels import FABRICATED, REAL
from citation_extractor.pipeline import (
    analyze_document,
    check_citation,
    load_indexes,
    parse_case_citation,
)
from citation_extractor.scoring import binary_metrics


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )


@pytest.fixture()
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    _write_jsonl(
        root / "statutes.jsonl",
        [
            {
                "citation": "AS 25.24.150",
                "source_text": "The court shall consider the best interests of the child.",
            }
        ],
    )
    _write_jsonl(
        root / "rules.jsonl",
        [
            {
                "citation": "Alaska R. Civ. P. 90.3",
                "source_text": (
                    "A child support award will be calculated as an amount equal "
                    "to the adjusted annual income of the non-custodial parent."
                ),
            }
        ],
    )
    _write_jsonl(
        root / "rules-evidence.jsonl",
        [{"ruleNumber": "505", "text": "Evidence rules apply.", "type": "rule"}],
    )
    _write_jsonl(
        root / "cases.jsonl",
        [
            {
                "case_name": "Ruppe v. Ruppe",
                "reporter_cite": "358 P.3d 1284",
                "court": "Alaska",
                "year": 2015,
            }
        ],
    )
    return root


@pytest.fixture()
def document(tmp_path: Path) -> Path:
    path = tmp_path / "doc-0001.docx"
    doc = Document()
    paragraphs = [
        "Under AS 25.24.150, the court considers the best interests of the child.",
        "The draft also cites AS 25.24.946, which does not exist in the corpus.",
        "Civil Rule 90.3 provides that \u201ca child support award will be calculated "
        "as an amount equal to the adjusted annual income of the non-custodial "
        "parent.\u201d",
        "The court in Ruppe v. Ruppe, 358 P.3d 1284 (Alaska 2015) agreed.",
        "A fabricated authority, Fake v. Fake, 999 P.3d 1 (Alaska 2020), is cited.",
        "The draft quotes AS 25.24.150 as \u201cthe court may consider the best "
        "interests of the child.\u201d",
    ]
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(path)
    return path


def test_parse_case_citation():
    parsed = parse_case_citation("See Ruppe v. Ruppe, 358 P.3d 1284 (Alaska 2015)")
    assert parsed == {"case_name": "Ruppe v. Ruppe", "reporter": "358 P.3d 1284"}
    assert parse_case_citation("not a case") is None


def test_check_citation_uses_corpus(corpus):
    indexes = load_indexes(corpus)
    assert check_citation("AS 25.24.150(a)", "statute", indexes) == REAL
    assert check_citation("AS 25.24.946", "statute", indexes) == FABRICATED
    assert check_citation("Civil Rule 90.3(a)", "rule", indexes) == REAL
    assert check_citation("Civil Rule 913", "rule", indexes) == FABRICATED


def test_analyze_document_combines_stages(corpus, document):
    report = analyze_document(document, indexes=load_indexes(corpus))

    verdicts = {(c["type"], c["cite"]): c["verdict"] for c in report["citations"]}
    assert verdicts[("statute", "AS 25.24.150")] == REAL
    assert verdicts[("statute", "AS 25.24.946")] == FABRICATED
    assert verdicts[("rule", "Alaska R. Civ. P. 90.3")] == REAL
    assert verdicts[("case", "Ruppe v. Ruppe, 358 P.3d 1284 (Alaska 2015)")] == REAL
    assert any(
        c["verdict"] == FABRICATED and "Fake" in c["cite"]
        for c in report["citations"]
    )

    statuses = {q["status"] for q in report["quotes"]}
    assert "faithful" in statuses
    assert "altered" in statuses

    assert report["risk"]["fabricated_citations"] == 2
    assert report["risk"]["quoted_altered_quotes"] == 1
    assert report["risk"]["flagged"] is True
    assert report["risk"]["review_required"] is True


def test_risk_counts_unique_authorities(corpus, tmp_path):
    path = tmp_path / "doc-0002.docx"
    doc = Document()
    doc.add_paragraph("AS 25.24.150 applies here.")
    doc.add_paragraph("Again, AS 25.24.150(a) applies.")
    doc.save(path)

    report = analyze_document(path, indexes=load_indexes(corpus))
    assert report["risk"]["fabricated_citations"] == 0
    assert report["risk"]["unique_authorities"] == 1
    assert len(report["citations"]) == 2


def test_binary_metrics_uses_error_as_positive_class():
    metrics = binary_metrics([1, 1, 0, 0], [1, 0, 0, 1])
    assert metrics["tp"] == 1
    assert metrics["fn"] == 1
    assert metrics["fp"] == 1
    assert metrics["tn"] == 1
    assert metrics["precision"] == 0.5
    assert metrics["recall"] == 0.5


def test_cli_returns_gate_exit_code(corpus, document, capsys):
    from citation_extractor.__main__ import main

    assert main([str(document), "--corpus-dir", str(corpus), "--no-fail"]) == 0
    assert main([str(document), "--corpus-dir", str(corpus)]) == 1
    output = capsys.readouterr().out
    assert "FLAGGED" in output


@pytest.mark.integration
def test_real_document_doc_0001():
    root = Path(__file__).resolve().parents[1]
    report = analyze_document(root / "data" / "benchmark" / "documents" / "doc-0001.docx")
    assert report["risk"]["fabricated_citations"] == 3
    assert report["risk"]["quoted_altered_quotes"] >= 1
