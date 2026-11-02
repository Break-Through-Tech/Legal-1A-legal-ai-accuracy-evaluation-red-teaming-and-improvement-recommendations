"""Command-line quality gate for the Legal 1A detector.

    python -m citation_extractor path/to/document.docx
    python -m citation_extractor path/to/documents/ --json
    cite-check path/to/document.docx

Exits 1 when a document is flagged (a fabricated citation or an altered quote
in quote marks), so it can be used directly in CI or a pre-publication check.
Use ``--no-fail`` to always exit 0.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .pipeline import analyze_document, load_indexes
from .source_lookup import DEFAULT_CORPUS_DIR


def _documents(paths: list[str]) -> list[Path]:
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found.extend(sorted(path.rglob("*.docx")))
        elif path.is_file():
            found.append(path)
        else:
            raise FileNotFoundError(path)
    return found


def _print_human(report: dict) -> None:
    risk = report["risk"]
    verdict = "FLAGGED" if risk["flagged"] else "clear"
    print(
        f"{report['doc_id']}: {verdict} — "
        f"{risk['fabricated_citations']} fabricated citation(s), "
        f"{risk['quoted_altered_quotes']} altered quote(s)"
    )
    for citation in report["citations"]:
        if citation["verdict"] in ("fabricated", "wrong_reporter"):
            print(
                f"  [{citation['verdict']}] {citation['cite']} "
                f"(paragraph {citation['paragraph_index']})"
            )
    for quote in report["quotes"]:
        if quote["flagged"] and quote["quoted"]:
            print(
                f"  [altered quote] {quote['citation']} "
                f"(score {quote['score']:.1f}): {quote['text'][:90]}"
            )
    if risk["possible_unquoted_alterations"]:
        print(
            f"  review: {risk['possible_unquoted_alterations']} unquoted passage(s) "
            "may also have been altered"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="cite-check", description="Detect fabricated legal citations and altered quotes."
    )
    parser.add_argument("paths", nargs="+", help="a .docx file or a directory of .docx files")
    parser.add_argument(
        "--corpus-dir",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="frozen corpus directory (default: data/corpus)",
    )
    parser.add_argument("--json", action="store_true", help="print the full report as JSON")
    parser.add_argument(
        "--no-fail",
        action="store_true",
        help="exit 0 even when a document is flagged",
    )
    args = parser.parse_args(argv)

    try:
        paths = _documents(args.paths)
    except FileNotFoundError as error:
        print(f"error: no such file or directory: {error}", file=sys.stderr)
        return 2
    if not paths:
        print("error: no .docx files found", file=sys.stderr)
        return 2

    indexes = load_indexes(args.corpus_dir)
    reports = [analyze_document(path, indexes=indexes) for path in paths]

    if args.json:
        payload = reports[0] if len(reports) == 1 else reports
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        for i, report in enumerate(reports):
            if i:
                print()
            _print_human(report)

    if not args.no_fail and any(report["risk"]["flagged"] for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
