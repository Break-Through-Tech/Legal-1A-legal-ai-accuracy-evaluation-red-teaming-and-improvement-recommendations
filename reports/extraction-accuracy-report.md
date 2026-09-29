# Extraction Accuracy Report — Statutes & Rules (September Milestone)

**Date:** 2026-09-29
**Benchmark version:** Corrected (issue #9, merged 2026-09-21)
**Scope:** Statutes and court-rule citation extraction over all 200 benchmark documents.
**Team task:** Milestone #1, Task #2 (issue #3) — Statutes/Rules Citation Extractor. Shared with May Bui.
**Deliverable half:** the "extraction-accuracy report against the answer key" part of the September milestone.

## Method

The extractor parses each `.docx` with `python-docx` (paragraph-level, inline
citations) and matches Alaska statute and court-rule citation patterns with
regex. Matched strings are normalized to a canonical base form before
comparison, using the normalization rules established in the data audit and
documented in `DATA_DICTIONARY.md` §3.1:

| Citation type | Document form(s) observed | Normalized to |
|---|---|---|
| Statute | `AS 25.24.310(a)`, `Alaska Statute AS 25.20.060`, `Alaska Statute 25.24.160(a)(4)` | `AS 25.24.310` (pinpoint stripped) |
| Civil rule | `Civil Rule 90.3(a)(3)`, `Alaska Civil Rule 90.3`, `Rule 90.3` | `Alaska R. Civ. P. 90.3` |
| Evidence rule | `Alaska R. Evid. 104(a)` | `Alaska R. Evid. 104` |

Pinpoints (subsections) are stripped so extracted forms and answer-key forms
compare exactly. Case citations are out of scope for this task (Task #3, the
cases extractor, is owned by the other three teammates).

Code: `src/citation_extractor/` with unit tests in `tests/` (31 passing).
Runner: `scripts/run_extractor.py`.

## Results

**Evaluated against the corrected benchmark** (issue #9, merged 2026-09-21), which:
- Added 4 missing rules to the corpus (rules 3, 16.2, 86, 99)
- Corrected 31 mislabeled citations (exists: false → true)
- Documented the rule-citation format normalization (§3.1)
- Resolved AS 11.56.807 as real Alaska law outside corpus scope (§3.2, §9)

| Metric | Value |
|---|---|
| Answer-key statute + rule citations (200 docs) | 2,318 |
| **Globally unique** normalized citations in answer key | **244** |
| **Globally unique** normalized citations extracted | **244** |
| True positives (TP) | 244 |
| False positives (FP) | 0 |
| False negatives (FN) | 0 |
| **Precision** | **1.0000** |
| **Recall** | **1.0000** |
| **F1-Score** | **1.0000** |

Every unique statute or rule citation in the corrected answer key was found by
the parser. No citations were extracted that aren't in the answer key somewhere.

## Per-document check

While global metrics are perfect, 26 documents have **per-document omissions**
in the answer key: the extractor finds citations in those documents that the
answer key doesn't list for that specific document. Each extra was manually
verified against the source text and is a genuine citation, for example:

- `doc-0016` — `AS 25.24.160` ("under AS 25.24.160")
- `doc-0054` — `Alaska R. Civ. P. 90.7` ("Civil Rule 90.7(e)")
- `doc-0049` — `Alaska R. Evid. 706` ("Alaska R. Evid. 706(a)")
- `doc-0086` — `AS 25.20.070`, `AS 25.20.110`

These are **answer-key per-document omissions**, not parser false positives.
The citations exist in the global answer key (they appear in other documents),
but weren't recorded for these specific documents. The existence checker
(October) and any final F1 scoring should account for this.

## Edge cases verified

- **AS 11.56.807** — real Alaska law (Terroristic Threatening in the First
  Degree) outside the corpus's curated scope. Extracted correctly from
  `doc-0136`. Per issue #9, retained as `exists: false` (meaning "not in this
  corpus") and excluded from Stage-2 hallucination scoring.
- **Decimal vs non-decimal rule numbers** — `Civil Rule 90.3` (real) and
  `Civil Rule 903` (fabricated) are distinguished correctly.
- **Multiple pinpoints** — `(a)(3)`, `(d)(2)`, `(a)(2)(B)` all strip to base.
- **Bare "Rule X"** — normalizes to `Alaska R. Civ. P. X` (civil rule).
- **Evidence rules** — `Alaska R. Evid. X` extracted separately from civil rules.
- **Fabricated citations** — still extracted (correct behavior; extraction finds
  what's in the text, existence checking is a separate stage).

## Failure analysis

- **Missed citations:** 0. No known citation format in the answer key (or the
  documents) is missed by the current patterns.
- **False positives:** 0. No citations were extracted that aren't in the
  global answer key.
- **Known limitation:** footnote text is not parsed (the benchmark uses inline
  parenthetical citations, so this is not expected to matter here).
- **Known limitation:** duplicate normalized citations within a paragraph are
  merged (one record per normalized cite per paragraph), so per-paragraph
  counts are not exact multiplicity. Per-document unique counts are exact.

## Reproduction

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
PYTHONPATH=src .venv/bin/python scripts/run_extractor.py
```

Per-document results: `data/extraction-results.json`.

## Audit summary

Full 4-step audit performed:
1. **Discrepancy & Gap Analysis** — TP=244, FP=0, FN=0, Precision=1.0000, Recall=1.0000, F1=1.0000
2. **Rule & Schema Conformance** — normalization matches DATA_DICTIONARY.md §3.1, all field types correct
3. **Edge-Case Stress Test** — all edge cases pass (AS 11.56.807, decimal rules, multiple pinpoints, bare rules, evidence rules, fabricated citations)
4. **Remediation** — none required; extractor achieves perfect metrics against corrected benchmark
