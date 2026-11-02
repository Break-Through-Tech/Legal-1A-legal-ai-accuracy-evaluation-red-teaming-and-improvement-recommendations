"""Reproducible end-to-end evaluation of the unified detector.

Scores the pipeline against ``answer-key.json`` at two levels:

1. **Checker-only** — the citation or quote was found, so this measures the
   existence/fidelity decision itself.
2. **End-to-end** — extraction and checking together; a missed citation or
   quote counts as *not flagged*.

Positive class is the planted error: ``exists = false`` for existence and
``quote_status = "altered"`` for fidelity. Per DATA_DICTIONARY §9, the single
citation ``AS 11.56.807`` (doc-0136) is excluded from Stage-2 scoring.

The answer key is used only for scoring and for pairing key quotes with the
passages the detector extracted. Predictions use the documents and the frozen
corpus only.

Writes:
    reports/pipeline-evaluation.md
    data/pipeline-results.json          (generated; gitignored)

Usage:
    python scripts/evaluate_pipeline.py
    python scripts/evaluate_pipeline.py --limit 10 --report /tmp/report.md
    python scripts/evaluate_pipeline.py --check   # fail if the committed report is stale
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.case_parser import normalize_case_key
from citation_extractor.existence import normalize_key
from citation_extractor.extractor import normalize_citation
from citation_extractor.labels import FABRICATED, OUT_OF_SCOPE, REAL, WRONG_REPORTER
from citation_extractor.pipeline import (
    analyze_document,
    check_citation,
    load_indexes,
    parse_case_citation,
)
from citation_extractor.scoring import binary_metrics
from citation_extractor.source_lookup import clean_whitespace

ANSWER_KEY = ROOT / "data" / "benchmark" / "answer-key.json"
DOCUMENTS_DIR = ROOT / "data" / "benchmark" / "documents"
CORPUS_DIR = ROOT / "data" / "corpus"
REPORT = ROOT / "reports" / "pipeline-evaluation.md"
RESULTS = ROOT / "data" / "pipeline-results.json"

# DATA_DICTIONARY §3.2 / §9: both are confirmed real law outside the corpus
# scope (Title 11), so neither is a hit nor a miss.
EXCLUDED = {("doc-0136", "AS 11.56.807"), ("doc-0136", "AS 11.56.810")}


def pct(value: float) -> str:
    return f"{value:.1%}"


def subset(rows: list[dict], **fields) -> list[dict]:
    return [r for r in rows if all(r.get(k) == v for k, v in fields.items())]


def _target_key(row: dict) -> tuple[str, str, str]:
    """Scoring unit per DATA_DICTIONARY §4.4: one target per authority per document."""
    cite, ctype = row["cite"], row["type"]
    if ctype == "case":
        parsed = parse_case_citation(cite)
        norm = (
            normalize_key(parsed["reporter"]) if parsed else normalize_key(cite)
        )
    else:
        norm = normalize_citation(cite).casefold()
    return (row["doc_id"], ctype, norm)


def dedupe_targets(rows: list[dict]) -> list[dict]:
    """Collapse pinpoints and form variants to one row per (document, norm)."""
    seen: dict[tuple[str, str, str], dict] = {}
    for row in rows:
        seen.setdefault(_target_key(row), row)
    return list(seen.values())


def checker_only_existence(answer_key: list[dict], indexes: dict) -> tuple[list[dict], list[dict]]:
    rows, skipped = [], []
    for document in answer_key:
        doc_id = document["doc_id"]
        for entry in document.get("citations", []):
            if (doc_id, entry["cite"]) in EXCLUDED:
                skipped.append({"doc_id": doc_id, "cite": entry["cite"], "reason": "§9 exclusion"})
                continue
            verdict = check_citation(entry["cite"], entry["type"], indexes)
            if verdict is None or verdict == OUT_OF_SCOPE:
                skipped.append(
                    {
                        "doc_id": doc_id,
                        "cite": entry["cite"],
                        "reason": "unparsed" if verdict is None else "out_of_scope",
                    }
                )
                continue
            rows.append(
                {
                    "doc_id": doc_id,
                    "cite": entry["cite"],
                    "type": entry["type"],
                    "injected": entry.get("injected") or "false",
                    "truth": 0 if entry["exists"] else 1,
                    "pred": int(verdict in (FABRICATED, WRONG_REPORTER)),
                    "verdict": verdict,
                    "extracted": True,
                }
            )
    return rows, skipped


def pair_case_entries(key_entries: list[dict], detector_cases: list[dict]):
    """Pair answer-key case entries with extracted cases, exact then substring."""
    used = set()
    pairs = []
    for entry in key_entries:
        parsed = parse_case_citation(entry["cite"])
        match_index = None
        if parsed is not None:
            for i, case in enumerate(detector_cases):
                if i in used:
                    continue
                if (
                    normalize_key(case.get("case_name")) == normalize_key(parsed["case_name"])
                    and normalize_key(case.get("reporter_cite")) == normalize_key(parsed["reporter"])
                ):
                    match_index = i
                    break
            if match_index is None:
                answer_name = normalize_key(parsed["case_name"])
                for i, case in enumerate(detector_cases):
                    if i in used:
                        continue
                    extracted_name = normalize_key(case.get("case_name"))
                    if (
                        normalize_key(case.get("reporter_cite")) == normalize_key(parsed["reporter"])
                        and answer_name
                        and answer_name in extracted_name
                    ):
                        match_index = i
                        break
        if match_index is None:
            pairs.append((entry, None))
        else:
            used.add(match_index)
            pairs.append((entry, detector_cases[match_index]))
    return pairs, used


def end_to_end_existence(
    answer_key: list[dict], reports: dict[str, dict], indexes: dict
) -> tuple[list[dict], list[dict]]:
    rows, unkeyed = [], []
    for document in answer_key:
        doc_id = document["doc_id"]
        report = reports.get(doc_id)
        if report is None:
            continue

        key_map = {}
        case_entries = []
        for entry in document.get("citations", []):
            if (doc_id, entry["cite"]) in EXCLUDED:
                continue
            if entry["type"] == "case":
                case_entries.append(entry)
                continue
            key = (entry["type"], normalize_citation(entry["cite"]).casefold())
            record = key_map.setdefault(
                key,
                {
                    "cite": entry["cite"],
                    "type": entry["type"],
                    "injected": entry.get("injected") or "false",
                    "fabricated": False,
                },
            )
            if not entry["exists"]:
                record["fabricated"] = True
                record["injected"] = entry.get("injected") or "false"

        detector_map = {}
        for citation in report["citations"]:
            if citation["type"] in ("statute", "rule"):
                detector_map[(citation["type"], citation["normalized"].casefold())] = citation

        matched_keys = set()
        for key, record in key_map.items():
            detected = detector_map.get(key)
            if detected is not None:
                matched_keys.add(key)
            verdict = detected["verdict"] if detected else None
            if verdict == OUT_OF_SCOPE:
                continue
            in_corpus = check_citation(record["cite"], record["type"], indexes) in (
                REAL,
                WRONG_REPORTER,
            )
            rows.append(
                {
                    "doc_id": doc_id,
                    "cite": record["cite"],
                    "type": record["type"],
                    "injected": record["injected"],
                    "truth": int(record["fabricated"]),
                    "pred": int(verdict in (FABRICATED, WRONG_REPORTER)) if detected else 0,
                    "verdict": verdict,
                    "extracted": detected is not None,
                    "in_corpus": in_corpus,
                }
            )

        for citation in detector_map.values():
            key = (citation["type"], citation["normalized"].casefold())
            if key in matched_keys:
                continue
            if citation["normalized"].casefold() == "as 11.56.807":
                continue
            unkeyed.append(
                {
                    "doc_id": doc_id,
                    "cite": citation["cite"],
                    "type": citation["type"],
                    "verdict": citation["verdict"],
                    "flagged": citation["verdict"] in (FABRICATED, WRONG_REPORTER),
                }
            )

        detector_cases = [c for c in report["citations"] if c["type"] == "case"]
        pairs, used_cases = pair_case_entries(case_entries, detector_cases)
        for entry, detected in pairs:
            verdict = detected["verdict"] if detected else None
            in_corpus = check_citation(entry["cite"], "case", indexes) in (
                REAL,
                WRONG_REPORTER,
            )
            rows.append(
                {
                    "doc_id": doc_id,
                    "cite": entry["cite"],
                    "type": "case",
                    "injected": entry.get("injected") or "false",
                    "truth": 0 if entry["exists"] else 1,
                    "pred": int(verdict in (FABRICATED, WRONG_REPORTER)) if detected else 0,
                    "verdict": verdict,
                    "extracted": detected is not None,
                    "in_corpus": in_corpus,
                }
            )

        seen_unkeyed_cases = set()
        for i, citation in enumerate(detector_cases):
            if i in used_cases:
                continue
            normalized = normalize_case_key(citation["cite"]).casefold()
            if normalized in seen_unkeyed_cases:
                continue
            seen_unkeyed_cases.add(normalized)
            unkeyed.append(
                {
                    "doc_id": doc_id,
                    "cite": citation["cite"],
                    "type": "case",
                    "verdict": citation["verdict"],
                    "flagged": citation["verdict"] in (FABRICATED, WRONG_REPORTER),
                }
            )

    return rows, unkeyed


def find_altered_quote(key_quote: dict, extracted: list[dict], used: set[int]):
    altered = clean_whitespace(key_quote["altered_text"])
    for contains in (lambda text: altered in text, lambda text: text in altered):
        for i, item in enumerate(extracted):
            if i not in used and contains(clean_whitespace(item["text"])):
                return i, item
    return None


def find_faithful_quote(key_quote: dict, extracted: list[dict], used: set[int]):
    cite = key_quote["source_cite"]
    for i, item in enumerate(extracted):
        if i in used or not item.get("citation"):
            continue
        if normalize_citation(item["citation"]) == normalize_citation(cite):
            return i, item
    return None


def fidelity_rows(answer_key: list[dict], reports: dict[str, dict]):
    rows, unkeyed = [], []
    for document in answer_key:
        doc_id = document["doc_id"]
        report = reports.get(doc_id)
        if report is None:
            continue
        extracted = report["quotes"]
        used = set()
        ordered = sorted(
            document.get("quotes", []), key=lambda q: q["quote_status"] != "altered"
        )
        for key_quote in ordered:
            is_altered = key_quote["quote_status"] == "altered"
            match = (
                find_altered_quote(key_quote, extracted, used)
                if is_altered
                else find_faithful_quote(key_quote, extracted, used)
            )
            if match is None:
                rows.append(
                    {
                        "doc_id": doc_id,
                        "source_cite": key_quote["source_cite"],
                        "truth": int(is_altered),
                        "pred": 0,
                        "extracted": False,
                        "quoted": None,
                        "tier": "not_extracted",
                        "score": None,
                        "status": "not_extracted",
                        "injected": key_quote.get("injected") or "false",
                        "planted": key_quote.get("planted"),
                    }
                )
                continue
            index, item = match
            used.add(index)
            rows.append(
                {
                    "doc_id": doc_id,
                    "source_cite": key_quote["source_cite"],
                    "truth": int(is_altered),
                    "pred": int(item["status"] == "altered"),
                    "extracted": True,
                    "quoted": item["quoted"],
                    "tier": item["tier"],
                    "score": item["score"],
                    "status": item["status"],
                    "injected": key_quote.get("injected") or "false",
                    "planted": key_quote.get("planted"),
                }
            )

        for i, item in enumerate(extracted):
            if i in used:
                continue
            unkeyed.append(
                {
                    "doc_id": doc_id,
                    "citation": item.get("citation"),
                    "quoted": item["quoted"],
                    "tier": item["tier"],
                    "score": item["score"],
                    "flagged": item["flagged"],
                }
            )
    return rows, unkeyed


def document_risk_rows(answer_key: list[dict], reports: dict[str, dict]) -> list[dict]:
    rows = []
    for document in answer_key:
        report = reports.get(document["doc_id"])
        if report is None:
            continue
        rows.append(
            {
                "doc_id": document["doc_id"],
                "truth": int(bool(document.get("n_errors_planted"))),
                "pred": int(report["risk"]["flagged"]),
                "pred_required": int(report["risk"]["review_required"]),
                "condition": document["condition"],
                "planted": document.get("n_errors_planted", 0),
                "fabricated": report["risk"]["fabricated_citations"],
                "altered": report["risk"]["altered_quotes"],
            }
        )
    return rows


def existence_category(row: dict) -> str:
    if row["truth"] == 1 and row["pred"] == 1:
        return "detected_fabrication"
    if row["truth"] == 1 and row["pred"] == 0:
        if not row["extracted"]:
            return "missed_fabrication:not_extracted"
        if row["in_corpus"]:
            return "missed_fabrication:benchmark_collision"
        return "missed_fabrication:checker_miss"
    if row["truth"] == 0 and row["pred"] == 1:
        if not row["in_corpus"]:
            return "false_alarm:corpus_gap"
        return "false_alarm:normalization_gap"
    return "correct_real"


def fidelity_category(row: dict) -> str:
    if row["truth"] == 1 and row["pred"] == 1:
        return "detected_altered"
    if row["truth"] == 1 and row["pred"] == 0:
        if not row["extracted"]:
            return "missed_altered:not_extracted"
        if row["status"] == "unverified":
            return "missed_altered:source_not_found"
        if row["tier"] in ("exact", "normalized"):
            return "missed_altered:wrong_source_match"
        return "missed_altered:scored_faithful"
    if row["truth"] == 0 and row["pred"] == 1:
        return (
            "false_alarm:quoted_faithful"
            if row["quoted"]
            else "false_alarm:unquoted_paraphrase"
        )
    return "correct_faithful"


def clean_document_alerts(
    risk_rows: list[dict], reports: dict[str, dict]
) -> list[str]:
    """Explain every clean document the detector flagged."""
    lines = [
        "| doc | cause | detail |",
        "|---|---|---|",
    ]
    found = False
    for row in risk_rows:
        if row["truth"] != 0 or row["pred"] != 1:
            continue
        found = True
        report = reports[row["doc_id"]]
        causes = []
        details = []
        citations = [
            c
            for c in report["citations"]
            if c["verdict"] in (FABRICATED, WRONG_REPORTER)
        ]
        unique_cites = {}
        for citation in citations:
            unique_cites.setdefault(citation["normalized"].casefold(), citation)
        for citation in unique_cites.values():
            if citation["normalized"].casefold() == "as 11.56.807":
                causes.append("§9 out-of-scope citation")
            else:
                causes.append("unkeyed citation")
            details.append(f"`{citation['cite']}` ({citation['verdict']})")
        quoted = [
            q
            for q in report["quotes"]
            if q["flagged"] and q["quoted"]
        ]
        if quoted:
            causes.append("unkeyed quoted passage")
            details.append(
                " / ".join(
                    f"`{q['citation']}` score {q['score']:.1f}" for q in quoted
                )
            )
        lines.append(f"| {row['doc_id']} | {', '.join(causes)} | {'; '.join(details)} |")
    if not found:
        lines.append("| — | none | — |")
    return lines


def category_table(rows: list[dict], categorise) -> list[str]:
    counts = Counter(categorise(row) for row in rows)
    examples = {}
    for row in rows:
        examples.setdefault(categorise(row), row)
    lines = ["| category | count | example |", "|---|---|---|"]
    for category, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        example = examples[category]
        if "source_cite" in example:
            detail = f"{example['doc_id']} — {example['source_cite']}"
            if example.get("score") is not None:
                detail += f" (score {example['score']:.1f}, {example['tier']})"
        else:
            detail = f"{example['doc_id']} — {example['cite']}"
            if example.get("verdict"):
                detail += f" ({example['verdict']})"
        lines.append(f"| `{category}` | {count} | {detail} |")
    return lines


def taxonomy_by_injected(
    rows: list[dict], error_types: list[str], categorise
) -> list[str]:
    lines = ["| injected | category | count |", "|---|---|---|"]
    for kind in error_types:
        segment = subset(rows, injected=kind)
        if not segment:
            continue
        counts = Counter(categorise(row) for row in segment)
        for category, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"| `{kind}` | `{category}` | {count} |")
    return lines


def injected_table(rows: list[dict], error_types: list[str]) -> list[str]:
    lines = ["| injected | n | caught | missed | recall |", "|---|---|---|---|---|"]
    for kind in error_types:
        segment = subset(rows, injected=kind)
        if not segment:
            continue
        caught = sum(r["pred"] for r in segment)
        lines.append(
            f"| `{kind}` | {len(segment)} | {caught} | {len(segment) - caught} | "
            f"{pct(caught / len(segment))} |"
        )
    return lines


def coverage_table(
    existence_rows: list[dict],
    fidelity: list[dict],
) -> list[str]:
    stat_rule = [r for r in existence_rows if r["type"] in ("statute", "rule")]
    cases = [r for r in existence_rows if r["type"] == "case"]
    quotes = fidelity
    quoted = [r for r in quotes if r.get("quoted") is True]
    unquoted = [r for r in quotes if r.get("quoted") is False]
    lines = [
        "| item | key items | found by detector | coverage |",
        "|---|---|---|---|",
        f"| statute/rule authorities (unique per doc) | {len(stat_rule)} | "
        f"{sum(r['extracted'] for r in stat_rule)} | "
        f"{pct(sum(r['extracted'] for r in stat_rule) / len(stat_rule))} |",
        f"| case citations | {len(cases)} | {sum(r['extracted'] for r in cases)} | "
        f"{pct(sum(r['extracted'] for r in cases) / len(cases))} |",
        f"| key quotes | {len(quotes)} | {sum(r['extracted'] for r in quotes)} | "
        f"{pct(sum(r['extracted'] for r in quotes) / len(quotes))} |",
    ]
    if quoted:
        lines.append(
            f"| — quoted | {len(quoted)} | {sum(r['extracted'] for r in quoted)} | "
            f"{pct(sum(r['extracted'] for r in quoted) / len(quoted))} |"
        )
    if unquoted:
        lines.append(
            f"| — unquoted | {len(unquoted)} | {sum(r['extracted'] for r in unquoted)} | "
            f"{pct(sum(r['extracted'] for r in unquoted) / len(unquoted))} |"
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="score only the first N documents")
    parser.add_argument(
        "--answer-key",
        type=Path,
        default=ANSWER_KEY,
        help="answer key to score against (default: data/benchmark/answer-key.json)",
    )
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write files; fail if the committed report is out of date",
    )
    args = parser.parse_args()
    if args.check and args.limit:
        parser.error("--check cannot be combined with --limit")

    answer_key = json.loads(args.answer_key.read_text(encoding="utf-8"))
    if args.limit:
        answer_key = answer_key[: args.limit]
    indexes = load_indexes(CORPUS_DIR)

    reports = {}
    for i, document in enumerate(answer_key, 1):
        doc_id = document["doc_id"]
        path = DOCUMENTS_DIR / f"{doc_id}.docx"
        reports[doc_id] = analyze_document(path, doc_id=doc_id, indexes=indexes)
        if args.verbose and (i % 25 == 0 or i == len(answer_key)):
            print(f"  analysed {i}/{len(answer_key)}", file=sys.stderr)

    checker_rows, skipped = checker_only_existence(answer_key, indexes)
    existence_rows, unkeyed_citations = end_to_end_existence(answer_key, reports, indexes)
    fidelity, unkeyed_quotes = fidelity_rows(answer_key, reports)
    risk_rows = document_risk_rows(answer_key, reports)

    # §4.4 / §9: score one target per authority per document, not per entry.
    checker_rows = dedupe_targets(checker_rows)
    existence_rows = dedupe_targets(existence_rows)

    checker_fidelity = [r for r in fidelity if r["extracted"]]
    # §9.3: the planted score is the primary fidelity result; natural
    # misquotes are a separate metric and are not merged into it.
    planted_fidelity = [
        r for r in fidelity if r["truth"] == 0 or r.get("planted") is True
    ]
    natural_fidelity = [
        r for r in fidelity if r["truth"] == 1 and r.get("planted") is not True
    ]

    existence_by_type = {}
    for ctype in ("statute", "rule", "case"):
        existence_by_type[ctype] = subset(existence_rows, type=ctype)
    checker_by_type = {}
    for ctype in ("statute", "rule", "case"):
        checker_by_type[ctype] = subset(checker_rows, type=ctype)

    lines = [
        "# Unified Detector — End-to-End Evaluation",
        "",
        "Scores the integrated pipeline against `answer-key.json`. The detector "
        "reads only the documents and the frozen corpus; the key is used only "
        "for scoring and for pairing key quotes with extracted passages.",
        "",
        "Positive class is the planted error. **Checker-only** scores only cases "
        "where extraction found the item; **end-to-end** counts a missed item as "
        "not flagged. `AS 11.56.807` and `AS 11.56.810` (doc-0136) are excluded "
        "from existence scoring per DATA_DICTIONARY §3.2/§9: both are real "
        "Title 11 law outside the corpus, so neither is a hit nor a miss.",
        "",
        f"Documents scored: **{len(answer_key)}**"
        + (" (partial run)" if args.limit else ""),
        "",
        "## Headline metrics",
        "",
        "| task | view | n | TP | FP | FN | TN | precision | recall | F1 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for label, view, rows in (
        ("existence", "checker-only", checker_rows),
        ("existence", "end-to-end", existence_rows),
        ("fidelity (planted, §9.3)", "checker-only", [r for r in planted_fidelity if r["extracted"]]),
        ("fidelity (planted, §9.3)", "end-to-end", planted_fidelity),
        ("document risk (strict)", "end-to-end", risk_rows),
        (
            "document risk (review)",
            "end-to-end",
            [dict(row, pred=row["pred_required"]) for row in risk_rows],
        ),
    ):
        m = binary_metrics([r["truth"] for r in rows], [r["pred"] for r in rows])
        lines.append(
            f"| {label} | {view} | "
            f"{m['support']} | {m['tp']} | {m['fp']} | {m['fn']} | {m['tn']} | "
            f"{m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
        )

    lines += ["", "## Existence by authority type", "", "**Checker-only**", ""]
    lines += ["| type | n | precision | recall | F1 |", "|---|---|---|---|---|"]
    for ctype, rows in checker_by_type.items():
        if not rows:
            continue
        m = binary_metrics([r["truth"] for r in rows], [r["pred"] for r in rows])
        lines.append(
            f"| {ctype} | {m['support']} | {m['precision']:.4f} | "
            f"{m['recall']:.4f} | {m['f1']:.4f} |"
        )
    lines += ["", "**End-to-end**", ""]
    lines += ["| type | n | precision | recall | F1 |", "|---|---|---|---|---|"]
    for ctype, rows in existence_by_type.items():
        if not rows:
            continue
        m = binary_metrics([r["truth"] for r in rows], [r["pred"] for r in rows])
        lines.append(
            f"| {ctype} | {m['support']} | {m['precision']:.4f} | "
            f"{m['recall']:.4f} | {m['f1']:.4f} |"
        )

    lines += ["", "## Existence by injected error type (end-to-end)", ""]
    lines += injected_table(
        existence_rows,
        ["fabricated_statute", "fabricated_rule", "fabricated_case", "wrong_reporter"],
    )

    correct_reason = 0
    reason_total = 0
    for row in existence_rows:
        if not row["extracted"]:
            continue
        if row["injected"] == "wrong_reporter":
            reason_total += 1
            correct_reason += row["verdict"] == WRONG_REPORTER
        elif row["injected"] == "fabricated_case":
            reason_total += 1
            correct_reason += row["verdict"] == FABRICATED
    lines += [
        "",
        f"Case verdict reason (fabricated vs wrong reporter), among extracted "
        f"injected case citations: **{correct_reason}/{reason_total}** correct.",
    ]

    lines += ["", "## Fidelity", ""]
    lines += [
        "Scored exactly as DATA_DICTIONARY §9.3 asks: the **planted score is "
        "primary** (positives = the 40 planted alterations; negatives = the "
        "faithful rows), and **natural misquotes are reported separately** as a "
        "hit rate over the 40 `planted: false` rows. The two are never merged.",
        "",
        "### Planted score (primary)",
        "",
        "| slice | n | TP | FP | FN | TN | precision | recall | F1 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for label, rows in (
        ("end-to-end", planted_fidelity),
        ("checker-only", [r for r in planted_fidelity if r["extracted"]]),
        ("quoted key quotes", [r for r in planted_fidelity if r.get("quoted") is True]),
        ("unquoted key passages", [r for r in planted_fidelity if r.get("quoted") is False]),
    ):
        if not rows:
            continue
        m = binary_metrics([r["truth"] for r in rows], [r["pred"] for r in rows])
        lines.append(
            f"| {label} | {m['support']} | {m['tp']} | {m['fp']} | {m['fn']} | "
            f"{m['tn']} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} |"
        )

    lines += [
        "",
        "### Natural misquotes (separate metric — not in the planted score)",
        "",
        "| view | n | caught | recall |",
        "|---|---|---|---|",
    ]
    for label, rows in (
        ("end-to-end", natural_fidelity),
        ("checker-only", [r for r in natural_fidelity if r["extracted"]]),
    ):
        if not rows:
            continue
        caught = sum(r["pred"] for r in rows)
        lines.append(
            f"| {label} | {len(rows)} | {caught} | {caught / len(rows):.4f} |"
        )
    lines += [
        "",
        "Planted quote errors are not representative of this population: most "
        "natural changes are unquoted modal, quantifier or omission edits, and "
        "string similarity scores the extracted span as faithful.",
        "",
        "### Diagnostic (not a §9 score)",
        "",
        f"Pooling both populations over all {len(fidelity)} quote rows gives "
        f"recall {binary_metrics([r['truth'] for r in fidelity], [r['pred'] for r in fidelity])['recall']:.4f}. "
        "Report it only as a diagnostic; §9.3 forbids using it as the fidelity result.",
    ]
    lines += ["", "### By injected type", ""]
    lines += injected_table(fidelity, ["altered_quote"])

    lines += ["", "## Extraction coverage", ""]
    lines += coverage_table(existence_rows, fidelity)

    lines += [
        "",
        "## Clean documents flagged (strict)",
        "",
        "False alarms on documents with no planted errors. In `doc-0136` both "
        "`AS 11.56.807` and `AS 11.56.810` are §9 exclusions (real Title 11 law "
        "outside the corpus), so they are not scored; the flag clears once "
        "PR #18's statute-scope handling is merged.",
        "",
    ]
    lines += clean_document_alerts(risk_rows, reports)

    lines += ["", "## Failure taxonomy", "", "### Existence (end-to-end)", ""]
    lines += category_table(existence_rows, existence_category)
    lines += ["", "### Fidelity (end-to-end)", ""]
    lines += category_table(fidelity, fidelity_category)

    lines += ["", "### Failure categories by injected type", ""]
    lines += taxonomy_by_injected(
        existence_rows,
        ["fabricated_statute", "fabricated_rule", "fabricated_case", "wrong_reporter"],
        existence_category,
    )
    lines += [""]
    lines += taxonomy_by_injected(fidelity, ["altered_quote"], fidelity_category)

    lines += ["", "### Unkeyed detector output", ""]
    citation_counts = Counter((u["type"], u["flagged"]) for u in unkeyed_citations)
    quote_counts = Counter((u["quoted"], u["flagged"], u["tier"]) for u in unkeyed_quotes)
    unique_unkeyed = {
        (
            u["type"],
            (
                normalize_case_key(u["cite"])
                if u["type"] == "case"
                else normalize_citation(u["cite"])
            ).casefold(),
        )
        for u in unkeyed_citations
    }
    lines += [
        f"- Citations extracted but not listed in that document's key: "
        f"**{len(unkeyed_citations)} occurrences** across "
        f"**{len(unique_unkeyed)} unique authorities** "
        f"(flagged: {sum(u['flagged'] for u in unkeyed_citations)}).",
        f"- Quoted/unquoted passages not in the key: **{len(unkeyed_quotes)}** "
        f"(flagged: {sum(u['flagged'] for u in unkeyed_quotes)}). "
        "These are not scored; the key omits real citations and most unquoted text "
        "is legitimate paraphrase.",
        "",
        "| unkeyed citation type | count | flagged |",
        "|---|---|---|",
    ]
    for ctype in ("statute", "rule", "case"):
        total = sum(count for (t, _), count in citation_counts.items() if t == ctype)
        flagged = sum(count for (t, f), count in citation_counts.items() if t == ctype and f)
        lines.append(f"| {ctype} | {total} | {flagged} |")
    lines += [
        "",
        "| unkeyed passage | count | flagged |",
        "|---|---|---|",
        f"| quoted | {sum(c for (q, _, _), c in quote_counts.items() if q)} | "
        f"{sum(c for (q, f, _), c in quote_counts.items() if q and f)} |",
        f"| unquoted | {sum(c for (q, _, _), c in quote_counts.items() if not q)} | "
        f"{sum(c for (q, f, _), c in quote_counts.items() if not q and f)} |",
    ]

    lines += [
        "",
        "## Design decisions",
        "",
        "- **No single risk score.** The document flag is a boolean, and the counts "
        "behind it are reported separately. A weighted scalar would hide which "
        "error type drove the alert.",
        "- **Out-of-scope and unverified are not scored.** They are excluded from "
        "the headline metrics and reported separately, because neither is a "
        "confirmed fabrication or alteration.",
        "- **The answer key is scoring-only.** The §9 exclusion and the benchmark "
        "labels live in the evaluation layer; the detector itself reads only the "
        "documents and the frozen corpus.",
        "",
        "## Notes for interpretation",
        "",
        "- **Checker-only vs end-to-end.** Checker-only isolates the corpus "
        "lookup/fidelity decision. End-to-end is what ProSeAI sees: a missed "
        "citation or passage is a miss, even if the checker would have been right.",
        "- **Benchmark collision.** Five `fabricated_statute` injections "
        "(`AS 25.24.900/910/920`) are real sections in the frozen corpus, so a "
        "correct corpus lookup reports them as real. They surface as "
        "`missed_fabrication:benchmark_collision`, not as detector failures.",
        "- **Unkeyed citations.** The answer key omits some real citations that "
        "appear in the documents; they are reported above and excluded from "
        "precision rather than counted as false positives.",
        "- **Unquoted passages.** Detecting copied statute text without quote "
        "marks is lower precision by design; unkeyed flags are reported as "
        "possible alterations, not scored as false positives in the fidelity "
        "metrics.",
        "- **Unkeyed flags still affect document risk.** A flagged citation or "
        "quoted passage that the key does not list is not scored in the "
        "citation/quote metrics, but it can still make a document flagged; "
        "those cases are listed under *Clean documents flagged*.",
        "- **Small fidelity sample.** The benchmark has 40 altered quotes, 35 of "
        "them the same appended phrase, so fidelity recall should be re-checked "
        "on more varied edits.",
        f"- Existence items skipped (not scored): **{len(skipped)}** "
        "(§9 exclusion, out-of-scope, or unparseable).",
        "",
    ]

    report_text = "\n".join(lines)
    if args.check:
        current = args.report.read_text(encoding="utf-8") if args.report.exists() else ""
        if current != report_text:
            print(
                f"error: {args.report} is out of date; run `make evaluate`",
                file=sys.stderr,
            )
            return 1
        print(f"report is up to date: {args.report}")
        return 0

    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report_text, encoding="utf-8")

    args.results.parent.mkdir(parents=True, exist_ok=True)
    args.results.write_text(
        json.dumps(
            {
                "documents": len(answer_key),
                "existence_checker_only": checker_rows,
                "existence_end_to_end": existence_rows,
                "fidelity": fidelity,
                "document_risk": risk_rows,
                "unkeyed_citations": unkeyed_citations,
                "unkeyed_quotes": unkeyed_quotes,
                "skipped": skipped,
                "summary": {
                    "existence_checker_only": binary_metrics(
                        [r["truth"] for r in checker_rows],
                        [r["pred"] for r in checker_rows],
                    ),
                    "existence_end_to_end": binary_metrics(
                        [r["truth"] for r in existence_rows],
                        [r["pred"] for r in existence_rows],
                    ),
                    "fidelity_planted": binary_metrics(
                        [r["truth"] for r in planted_fidelity],
                        [r["pred"] for r in planted_fidelity],
                    ),
                    "fidelity_planted_checker_only": binary_metrics(
                        [r["truth"] for r in planted_fidelity if r["extracted"]],
                        [r["pred"] for r in planted_fidelity if r["extracted"]],
                    ),
                    "fidelity_natural": {
                        "n": len(natural_fidelity),
                        "caught": sum(r["pred"] for r in natural_fidelity),
                        "recall": (
                            sum(r["pred"] for r in natural_fidelity)
                            / len(natural_fidelity)
                            if natural_fidelity
                            else 0.0
                        ),
                    },
                    "fidelity_pooled_diagnostic": binary_metrics(
                        [r["truth"] for r in fidelity],
                        [r["pred"] for r in fidelity],
                    ),
                    "document_risk": binary_metrics(
                        [r["truth"] for r in risk_rows],
                        [r["pred"] for r in risk_rows],
                    ),
                    "document_risk_review": binary_metrics(
                        [r["truth"] for r in risk_rows],
                        [r["pred_required"] for r in risk_rows],
                    ),
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    for key, rows in (
        ("existence (checker-only)", checker_rows),
        ("existence (end-to-end)", existence_rows),
        ("fidelity planted (end-to-end)", planted_fidelity),
        ("fidelity planted (checker)", [r for r in planted_fidelity if r["extracted"]]),
        ("fidelity pooled (diagnostic)", fidelity),
        ("document risk (strict)", risk_rows),
        (
            "document risk (review)",
            [dict(row, pred=row["pred_required"]) for row in risk_rows],
        ),
    ):
        m = binary_metrics([r["truth"] for r in rows], [r["pred"] for r in rows])
        print(
            f"{key:<28} n={m['support']:<5} "
            f"P={m['precision']:.4f} R={m['recall']:.4f} F1={m['f1']:.4f} "
            f"(TP={m['tp']} FP={m['fp']} FN={m['fn']} TN={m['tn']})"
        )
    natural_caught = sum(r["pred"] for r in natural_fidelity)
    if natural_fidelity:
        print(
            f"{'fidelity natural (separate)':<28} n={len(natural_fidelity):<5} "
            f"caught={natural_caught} recall={natural_caught / len(natural_fidelity):.4f}"
        )
    print(f"report:  {args.report}")
    print(f"results: {args.results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
