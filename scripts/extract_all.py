"""Run the case parser across all benchmark DOCX files."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.case_parser import extract_document, normalize  # noqa: E402

DOCUMENTS_DIR = ROOT / "data" / "benchmark" / "documents"
CORPUS_PATH = ROOT / "data" / "corpus" / "cases.jsonl"
OUTPUT_PATH = ROOT / "data" / "extracted_citations.json"


def load_reporter_index(path):
    """Build reporter -> corpus cases index used for corpus-assisted extraction."""
    index = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            case = json.loads(line)
            reporter = normalize(case.get("reporter_cite"))
            if reporter:
                index.setdefault(reporter, []).append(case)
    return index


def main():
    if not DOCUMENTS_DIR.exists():
        raise FileNotFoundError(
            f"Missing {DOCUMENTS_DIR}. Put the 200 doc-XXXX.docx files in '/data/benchmark/documents' folder."
        )
    if not CORPUS_PATH.exists():
        raise FileNotFoundError(f"Missing corpus: {CORPUS_PATH}")

    files = sorted(
        p for p in DOCUMENTS_DIR.iterdir()
        if p.is_file() and re.fullmatch(r"doc-\d{4}\.docx", p.name, re.IGNORECASE)
    )
    if len(files) != 200:
        raise ValueError(f"Expected 200 DOCX files, found {len(files)} in {DOCUMENTS_DIR}")

    reporter_index = load_reporter_index(CORPUS_PATH)
    results = [extract_document(path, reporter_index) for path in files]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    recognized = sum(len(r["citations"]) for r in results)
    unparsed = sum(len(r["unparsed_candidates"]) for r in results)

    print(f"Documents processed: {len(results)}")
    print(f"Recognized citations: {recognized}")
    print(f"Unparsed candidates: {unparsed}")
    print(f"Output: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
