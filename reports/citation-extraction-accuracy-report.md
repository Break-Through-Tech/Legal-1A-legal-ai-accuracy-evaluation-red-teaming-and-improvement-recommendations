# Extraction Accuracy Report — Case Citations (September Milestone)

**Date:** 2026-09-29
**Scope:** Case citation extraction and verification over all 200 benchmark documents.
**Deliverable:** Case-parser module in `src/` with passing `pytest`, extracted-citations output for all 200 documents, and results against the answer key.

## Method

The case citation extractor parses each `.docx` using `python-docx` while preserving paragraph-level structure and citation positions.

Case citations require more structure than statute and rule citations because the extractor must identify multiple components, including the party names, reporter citation, jurisdiction, and year. For example:

`Smith v. Jones, 123 P.3d 456 (Alaska 2005)`

The extraction process is reporter-centered. The parser first identifies reporter patterns such as:

`123 P.3d 456 (Alaska 2005)`

For full citations, the reporter is checked against the case corpus in `cases.jsonl`. When the reporter corresponds to a known case, the associated case name is searched for in the surrounding document text. If corpus-assisted extraction cannot resolve the case name, the parser falls back to extracting the party names directly from the surrounding text.

This fallback is important because fabricated citations may contain reporters that do not exist in the corpus.

The parser also recognizes reporter-only citations such as:

`123 P.3d 456`

and records citation-like text that cannot be parsed as an unparsed candidate rather than silently dropping it.

For each recognized citation, the extractor records structured information including:

* citation text
* normalized citation
* case name
* reporter citation
* year, when present
* document ID
* paragraph index
* start and end position
* extraction method
* citation type

Common subsequent-history language is also detected separately.

Case existence verification is performed after extraction. The extracted case name is matched against the known case corpus, and the reporter citation is then compared with the reporter associated with that case.

The resulting classification is:

* **REAL** — case name exists and reporter matches
* **FABRICATED** — case name is not found or the reporter does not match the known case
* **UNPARSED / UNVERIFIED** — insufficient information was extracted to make the normal case-name/reporter determination

Code: `src/case_parser.py`
Unit tests: `tests/test_case_parser.py`
Extraction runner: `scripts/extract_all.py`
Evaluation runner: `scripts/evaluate.py`

## Results

The extractor was run across all 200 benchmark documents.

The extraction run produced:

| Metric                          |      Value |
| ------------------------------- | ---------: |
| Documents processed             |        200 |
| Recognized citation occurrences |      1,666 |
| Unparsed candidates             |          0 |
| Answer-key case citations       |      1,172 |
| Answer-key citations found      |      1,172 |
| Answer-key citations missing    |          0 |
| **Extraction recall**           | **1.0000** |

All 1,172 case citations represented in the answer key were successfully found by the extractor.

The larger number of recognized citation occurrences (1,666) reflects all citation occurrences detected in the documents, including repeated citations and additional extracted occurrences; it should not be interpreted as 1,666 unique answer-key cases.

## Case Verification Results

The extracted answer-key cases were also evaluated for REAL versus FABRICATED classification.

| Metric                    |      Value |
| ------------------------- | ---------: |
| Cases evaluated           |      1,172 |
| True positives (TP)       |         51 |
| False positives (FP)      |          0 |
| False negatives (FN)      |          0 |
| True negatives (TN)       |      1,121 |
| **Accuracy**              | **1.0000** |
| **Fabrication Precision** | **1.0000** |
| **Fabrication Recall**    | **1.0000** |
| **Fabrication F1-Score**  | **1.0000** |

For these metrics, **FABRICATED is treated as the positive class**.

Therefore:

* TP = fabricated citation correctly classified as fabricated
* FP = real citation incorrectly classified as fabricated
* FN = fabricated citation incorrectly classified as real
* TN = real citation correctly classified as real

The system correctly identified all 51 fabricated citations and all 1,121 real citations represented in the benchmark evaluation.

## Extraction Strategy

The case extractor uses a two-stage approach for full case citations.

### 1. Reporter-centered extraction

The parser first identifies a reporter citation such as:

`358 P.3d 1284 (Alaska 2015)`

The reporter is used to retrieve candidate cases from `cases.jsonl`. If the corresponding case name occurs in the surrounding document text, that case name is selected.

This provides a corpus-assisted extraction path for known citations.

### 2. Text-based fallback

If the reporter cannot resolve the case through the corpus, the parser examines the text immediately preceding the reporter and attempts to identify the party names surrounding `v.`.

This allows the extractor to process citations that are malformed or fabricated rather than requiring the reporter to already exist in the reference corpus.

Extraction and existence verification therefore remain separate concepts: a citation does not need to be real in order to be extracted.

## Edge Cases Handled

The extractor includes handling for several case-citation variations encountered during development:

* **P.2d and P.3d reporters**
* **Abbreviated party names**, including forms such as `D.D. v. L.A.H.`
* **Party names containing initials and punctuation**
* **Reporter-only citations**, such as `123 P.3d 456`
* **Citations embedded within surrounding prose**
* **Repeated case citations**
* **Incorrect reporter citations for otherwise real case names**
* **Unknown case names**
* **Common subsequent-history signals**
* **Citation-like strings that fail recognized patterns**, which are logged for failure analysis rather than silently discarded

The parser preserves paragraph and character-position information so each extracted citation can be traced back to its location in the source document.

## Unit Testing

The case parser includes automated tests using `pytest`.

The tests cover core extraction behavior, including:

* standard full case citations
* P.2d and P.3d reporter formats
* abbreviated party names
* citations surrounded by prose
* reporter-only citations
* citation normalization
* subsequent-history handling
* malformed/unparsed citation-like strings
* document, paragraph, and position metadata

The test suite passes against the submitted parser implementation.

## Failure Analysis

**Answer-key citations missed:** 0.

All 1,172 answer-key case citations were located by the extractor, producing extraction recall of 1.0000.

**Unparsed candidates:** 0 in the 200-document extraction run.

**False positives in fabrication detection:** 0.

No answer-key citation labeled real was classified as fabricated.

**False negatives in fabrication detection:** 0.

No answer-key citation labeled fabricated was classified as real.

The perfect benchmark results should be interpreted specifically as performance on the provided 200-document benchmark. They do not establish perfect accuracy on arbitrary legal documents or citation formats outside the benchmark distribution.

## Reproduction

From the repository root, install the required dependencies and run the test suite:

```bash
pip install python-docx pytest
pytest -q
```

Run case extraction across the benchmark documents:

```bash
python scripts/extract_all.py
```

This produces:

`outputs/extracted_citations.json`

Then evaluate the extracted citations against the answer key:

```bash
python scripts/evaluate.py
```

## Output

Full extracted citation output:

`outputs/extracted_citations.json`

The output contains structured citation records for all processed documents, including document and paragraph location information, normalized citation data, extraction method, and verification result.

## Audit Summary

The case citation system was evaluated across all 200 benchmark documents.

1. **Extraction Coverage** — 1,172/1,172 answer-key case citations found; extraction recall = 1.0000.
2. **Case Verification** — 51 fabricated and 1,121 real answer-key citations classified correctly.
3. **Classification Metrics** — accuracy = 1.0000, fabrication precision = 1.0000, fabrication recall = 1.0000, and fabrication F1 = 1.0000.
4. **Parser Validation** — automated `pytest` coverage verifies major citation formats, malformed inputs, normalization, and positional metadata.
5. **Failure Logging** — citation-like text that does not match supported patterns is designed to be retained as an unparsed candidate rather than silently discarded.
6. **Benchmark Limitation** — results represent performance on the provided 200-document benchmark and should not be generalized to all legal citation formats without additional external testing.
