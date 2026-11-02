# Legal 1A — Citation & Quote Hallucination Detector

An end-to-end detector for AI-drafted Alaska family-law documents. It finds:

- **fabricated citations** — a statute, court rule, or case that is not in the frozen corpus;
- **wrong-reporter citations** — a real case name attached to a reporter volume/page that is not its own;
- **altered quotes** — a passage in quotation marks that no longer matches its source;
- **possible unquoted alterations** — statute text copied without quote marks and changed.

The detector is built for the ProSeAI benchmark and packaged so it can be re-run as a standing quality gate on new drafts.

## Results at a glance

Full details, failure taxonomy, and per-type breakdowns are in [`reports/pipeline-evaluation.md`](reports/pipeline-evaluation.md). Positive class is the planted error, per DATA_DICTIONARY §9.

Scored against the 2026-11-01 consolidated answer key (3,584 citation entries, 202 quote rows).

Scored per DATA_DICTIONARY §9: one target per authority per document, and the fidelity planted score kept separate from natural misquotes.

| task | view | n | precision | recall | F1 |
|---|---|---|---|---|---|
| existence | end-to-end | 2,491 authority targets | 0.996 | 1.000 | 0.998 |
| — statute | end-to-end | 932 | 1.000 | 1.000 | 1.000 |
| — rule | end-to-end | 454 | 1.000 | 1.000 | 1.000 |
| — case | end-to-end | 1,105 | 0.981 | 1.000 | 0.990 |
| fidelity (planted, primary) | end-to-end | 162 rows | 0.947 | 0.900 | 0.923 |
| fidelity (natural, separate) | end-to-end | 40 rows | — | 0.025 (1/40) | — |
| document risk (strict) | end-to-end | 200 documents | 0.963* | 1.000 | 0.981 |

\* 0.981 after PR #19 lands: it clears the `doc-0136` out-of-scope false alarm and the `doc-0042` case-name (`&`/`and`) false alarm. The two remaining strict false alarms (`doc-0012`, `doc-0144`) are genuine misquotes the answer key does not label.

Existence is saturated: every planted fabrication is caught (273/273). The open problem is **fidelity on the drafting model's own misquotes** — 1 of 40 caught. Most are *unquoted* modal, quantifier or omission edits, and the extractor only compares verbatim runs, so the change is excluded before scoring. The two populations are reported separately, as §9.3 requires.

> The older `reports/statute-rule-existence-report.md` scores the *real* class as positive (precision 0.9976, recall 1.0). `reports/pipeline-evaluation.md` scores the *error* class as positive as §9 requires, which is why the recall figure differs.

## Install

```bash
python -m venv .venv
.venv/bin/pip install -e ".[eval,dev]"
```

Core dependencies are `python-docx` and `rapidfuzz`. `scikit-learn` is only needed for evaluation. The 32 MB corpus is not bundled in the wheel; run from a clone of this repo or point `--corpus-dir` at `data/corpus`.

## Quick start

```bash
# one document; exits 1 when flagged, so it works in CI
cite-check data/benchmark/documents/doc-0001.docx

# a directory of documents, as JSON
cite-check data/benchmark/documents --json > reports.json

# always exit 0 (useful when triaging)
cite-check draft.docx --no-fail
```

Example output:

```
doc-0001: FLAGGED — 3 fabricated citation(s), 1 altered quote(s)
  [fabricated] AS 25.24.946 (paragraph 28)
  [fabricated] Alaska R. Civ. P. 907 (paragraph 32)
  [fabricated] Alaska R. Civ. P. 913 (paragraph 57)
  [altered quote] Civil Rule 90.3(a) (score 92.4): will be calculated as an amount ...
```

## Library use

```python
from citation_extractor import analyze_document, load_indexes

indexes = load_indexes()            # load the corpus once
report = analyze_document("draft.docx", indexes=indexes)

report["risk"]
# {
#   "flagged": True,                 # strict: fabricated citation or quoted alteration
#   "review_required": True,         # also includes unquoted possible alterations
#   "fabricated_citations": 1,
#   "wrong_reporter_citations": 0,
#   "altered_quotes": 1,
#   "quoted_altered_quotes": 1,
#   "possible_unquoted_alterations": 0,
#   "out_of_scope_citations": 0,
#   "unverified_quotes": 0,
#   "unique_authorities": 14,
# }

for citation in report["citations"]:
    print(citation["type"], citation["cite"], citation["verdict"])

for quote in report["quotes"]:
    if quote["flagged"]:
        print(quote["citation"], quote["tier"], quote["score"])
```

`analyze_document` returns every citation occurrence, every quoted/unquoted passage, and the risk summary. Verdicts come only from the frozen corpus; the answer key is never read by the detector.

## Reproduce the evaluation

```bash
make verify          # tests + verify the committed report is current
# or individually:
make test
make evaluate
```

This rewrites `reports/pipeline-evaluation.md` and `data/pipeline-results.json` (gitignored). The evaluator reports two views:

- **checker-only** — the item was extracted, so this isolates the corpus/fidelity decision;
- **end-to-end** — extraction and checking together; a missed item counts as not flagged.

It also reports document-level risk, extraction coverage, a failure taxonomy grouped by injected error type, and every clean document the detector flagged.

## Verification

```bash
make verify
```

`make verify` runs the test suite and regenerates the report in memory to confirm
the committed `reports/pipeline-evaluation.md` is current. Ran successfully with
Python 3.14.7, rapidfuzz 3.14.6, and scikit-learn 1.9.1. Repeated evaluation runs
produce byte-identical report and result files.

## How it works

1. **Extraction.** Statutes and rules use regexes in `extractor.py`; cases use the reporter parser in `case_parser.py`. Paragraph and character positions are preserved.
2. **Existence.** `statute_rule_existence.py` and `existence.py` look up the frozen corpus only. Rules match on the normalized rule number (never the citation string) and keep civil and evidence rules in separate namespaces. Statutes outside the corpus scope return `out_of_scope` rather than `fabricated`.
3. **Fidelity.** `source_lookup.py` maps a citation to its true text; `quote_fidelity.py` compares the passage in tiers — exact, normalized, then fuzzy (`rapidfuzz`). `unquoted_passages.py` finds copied text that is not in quote marks.
4. **Risk.** `pipeline.py` combines the verdicts. The strict flag is a fabricated/wrong-reporter citation or an altered **quoted** passage. `review_required` additionally includes unquoted possible alterations and passages whose source could not be found.

## Benchmark

- 200 Alaska family-law `.docx` documents: 97 clean, 103 corrupt.
- 3,490 answer-key citations: 1,546 statutes, 772 rules, 1,172 cases.
- 163 quoted passages: 123 faithful, 40 altered.
- Existence scoring excludes `AS 11.56.807` (doc-0136) per DATA_DICTIONARY §9: it is confirmed real Alaska law outside the corpus's curated scope.

See `data/benchmark/DATA_DICTIONARY.md` for the full schema and scoring rules.

## Project layout

```
src/citation_extractor/
  pipeline.py               end-to-end detector
  extractor.py              statute/rule extraction
  case_parser.py            case extraction
  existence.py              case existence checking
  statute_rule_existence.py statute/rule existence checking
  source_lookup.py          citation -> true source text
  quote_extractor.py        quoted-passage extraction
  quote_fidelity.py         exact/normalized/fuzzy fidelity
  unquoted_passages.py      copied text without quote marks
  scoring.py                precision/recall/F1 helpers
  __main__.py               cite-check CLI
scripts/
  evaluate_pipeline.py      end-to-end evaluation + failure taxonomy
  evaluate.py               case-only evaluation
  evaluate_statute_rule_existence.py
  evaluate_quotes.py
reports/
  pipeline-evaluation.md
  improvement-recommendations.md
  statute-rule-existence-report.md
  quote-fidelity-report.md
```

## Known limitations

- **Fidelity sample is narrow.** 35 of the 40 altered quotes are the same appended phrase ("under all circumstances"), so the 90% end-to-end recall should be re-checked on more varied edits.
- **Unquoted passages are lower precision.** Copied text without quote marks is often legitimate paraphrase; the detector exposes those flags as `review_required` rather than treating them as confirmed hallucinations.
- **Corpus scope.** The corpus covers all of Alaska Title 25 and Title 18 chapters 65–66. Real authorities outside that scope (for example `AS 11.56.807`) return `out_of_scope` and are not counted as fabrications.
- **Short-form cases.** The case parser extracts reporter-only short forms but the pipeline verifies only full name+reporter citations; a short form is checked only when a full citation for it appears in the same document.
- **Synthetic benchmark.** Planted errors cover the documented corruption menu, not every way a model can hallucinate. Results are evidence for these error types, not a claim of general legal accuracy.

Improvement work, ranked by severity and tied to evidence, is in [`reports/improvement-recommendations.md`](reports/improvement-recommendations.md).

## Acknowledgements

Built by the Legal 1A team in the Break Through Tech AI Studio program, in partnership with ProSeAI. The benchmark, corpus, and data dictionary are provided by ProSeAI.
