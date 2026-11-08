# Unified Detector — End-to-End Evaluation

Scores the integrated pipeline against `answer-key.json`. The detector reads only the documents and the frozen corpus; the key is used only for scoring and for pairing key quotes with extracted passages.

Positive class is the planted error. **Checker-only** scores only cases where extraction found the item; **end-to-end** counts a missed item as not flagged. `AS 11.56.807` and `AS 11.56.810` (doc-0136) are excluded from existence scoring per DATA_DICTIONARY §3.2/§9: both are real Title 11 law outside the corpus, so neither is a hit nor a miss.

Documents scored: **200**

## Headline metrics

| task | view | n | TP | FP | FN | TN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|---|
| existence | checker-only | 2491 | 273 | 1 | 0 | 2217 | 0.9964 | 1.0000 | 0.9982 |
| existence | end-to-end | 2491 | 273 | 1 | 0 | 2217 | 0.9964 | 1.0000 | 0.9982 |
| fidelity (planted, §9.3) | checker-only | 157 | 36 | 2 | 2 | 117 | 0.9474 | 0.9474 | 0.9474 |
| fidelity (planted, §9.3) | end-to-end | 162 | 36 | 2 | 4 | 120 | 0.9474 | 0.9000 | 0.9231 |
| document risk (strict) | end-to-end | 200 | 103 | 4 | 0 | 93 | 0.9626 | 1.0000 | 0.9810 |
| document risk (review) | end-to-end | 200 | 103 | 39 | 0 | 58 | 0.7254 | 1.0000 | 0.8408 |

## Existence by authority type

**Checker-only**

| type | n | precision | recall | F1 |
|---|---|---|---|---|
| statute | 932 | 1.0000 | 1.0000 | 1.0000 |
| rule | 454 | 1.0000 | 1.0000 | 1.0000 |
| case | 1105 | 0.9808 | 1.0000 | 0.9903 |

**End-to-end**

| type | n | precision | recall | F1 |
|---|---|---|---|---|
| statute | 932 | 1.0000 | 1.0000 | 1.0000 |
| rule | 454 | 1.0000 | 1.0000 | 1.0000 |
| case | 1105 | 0.9808 | 1.0000 | 0.9903 |

## Existence by injected error type (end-to-end)

| injected | n | caught | missed | recall |
|---|---|---|---|---|
| `fabricated_statute` | 134 | 134 | 0 | 100.0% |
| `fabricated_rule` | 88 | 88 | 0 | 100.0% |
| `fabricated_case` | 21 | 21 | 0 | 100.0% |
| `wrong_reporter` | 30 | 30 | 0 | 100.0% |

Case verdict reason (fabricated vs wrong reporter), among extracted injected case citations: **51/51** correct.

## Fidelity

Scored exactly as DATA_DICTIONARY §9.3 asks: the **planted score is primary** (positives = the 40 planted alterations; negatives = the faithful rows), and **natural misquotes are reported separately** as a hit rate over the 40 `planted: false` rows. The two are never merged.

### Planted score (primary)

| slice | n | TP | FP | FN | TN | precision | recall | F1 |
|---|---|---|---|---|---|---|---|---|
| end-to-end | 162 | 36 | 2 | 4 | 120 | 0.9474 | 0.9000 | 0.9231 |
| checker-only | 157 | 36 | 2 | 2 | 117 | 0.9474 | 0.9474 | 0.9474 |
| quoted key quotes | 109 | 21 | 0 | 2 | 86 | 1.0000 | 0.9130 | 0.9545 |
| unquoted key passages | 48 | 15 | 2 | 0 | 31 | 0.8824 | 1.0000 | 0.9375 |

### Natural misquotes (separate metric — not in the planted score)

| view | n | caught | recall |
|---|---|---|---|
| end-to-end | 40 | 1 | 0.0250 |
| checker-only | 19 | 1 | 0.0526 |

Planted quote errors are not representative of this population: most natural changes are unquoted modal, quantifier or omission edits, and string similarity scores the extracted span as faithful.

### Diagnostic (not a §9 score)

Pooling both populations over all 202 quote rows gives recall 0.4625. Report it only as a diagnostic; §9.3 forbids using it as the fidelity result.

### By injected type

| injected | n | caught | missed | recall |
|---|---|---|---|---|
| `altered_quote` | 40 | 36 | 4 | 90.0% |

## Extraction coverage

| item | key items | found by detector | coverage |
|---|---|---|---|
| statute/rule authorities (unique per doc) | 1386 | 1386 | 100.0% |
| case citations | 1105 | 1105 | 100.0% |
| key quotes | 202 | 176 | 87.1% |
| — quoted | 110 | 110 | 100.0% |
| — unquoted | 66 | 66 | 100.0% |

## Clean documents flagged (strict)

False alarms on documents with no planted errors. In `doc-0136` both `AS 11.56.807` and `AS 11.56.810` are §9 exclusions (real Title 11 law outside the corpus), so they are not scored; the flag clears once PR #18's statute-scope handling is merged.

| doc | cause | detail |
|---|---|---|
| doc-0012 | unkeyed quoted passage | `AS 25.24.220(d)(2)` score 97.7 |
| doc-0042 | unkeyed citation | `E.H. v. State, Department of Health and Social Services, Division of Family and Youth Services, 23 P.3d 1186 (Alaska 2001)` (fabricated) |
| doc-0136 | §9 out-of-scope citation, unkeyed citation | `AS 11.56.807` (fabricated); `AS 11.56.810` (fabricated) |
| doc-0144 | unkeyed quoted passage | `AS 25.24.140(b)` score 84.3 |

## Failure taxonomy

### Existence (end-to-end)

| category | count | example |
|---|---|---|
| `correct_real` | 2217 | doc-0001 — AS 25.24.220 (real) |
| `detected_fabrication` | 273 | doc-0001 — Civil Rule 913(b) (fabricated) |
| `false_alarm:corpus_gap` | 1 | doc-0042 — E.H. v. State, Department of Health and Social Services, Division of Family and Youth Services, 23 P.3d 1186 (Alaska 2001) (fabricated) |

### Fidelity (end-to-end)

| category | count | example |
|---|---|---|
| `correct_faithful` | 120 | doc-0013 — AS 25.24.150 (score 100.0, normalized) |
| `detected_altered` | 37 | doc-0001 — Civil Rule 90.3(a) (score 92.4, fuzzy) |
| `missed_altered:not_extracted` | 23 | doc-0035 — Civil Rule 26.1(b) |
| `missed_altered:wrong_source_match` | 17 | doc-0005 — AS 25.30.310(a) (score 100.0, exact) |
| `missed_altered:source_not_found` | 3 | doc-0058 — AS 25.20.060(b) |
| `false_alarm:unquoted_paraphrase` | 2 | doc-0013 — Civil Rule 90.3(a)(1) (score 82.1, fuzzy) |

### Failure categories by injected type

| injected | category | count |
|---|---|---|
| `fabricated_statute` | `detected_fabrication` | 134 |
| `fabricated_rule` | `detected_fabrication` | 88 |
| `fabricated_case` | `detected_fabrication` | 21 |
| `wrong_reporter` | `detected_fabrication` | 30 |

| injected | category | count |
|---|---|---|
| `altered_quote` | `detected_altered` | 36 |
| `altered_quote` | `missed_altered:not_extracted` | 2 |
| `altered_quote` | `missed_altered:source_not_found` | 2 |

### Unkeyed detector output

- Citations extracted but not listed in that document's key: **364 occurrences** across **109 unique authorities** (flagged: 1).
- Quoted/unquoted passages not in the key: **3590** (flagged: 64). These are not scored; the key omits real citations and most unquoted text is legitimate paraphrase.

| unkeyed citation type | count | flagged |
|---|---|---|
| statute | 1 | 1 |
| rule | 0 | 0 |
| case | 363 | 0 |

| unkeyed passage | count | flagged |
|---|---|---|
| quoted | 376 | 2 |
| unquoted | 3214 | 62 |

## Design decisions

- **No single risk score.** The document flag is a boolean, and the counts behind it are reported separately. A weighted scalar would hide which error type drove the alert.
- **Out-of-scope and unverified are not scored.** They are excluded from the headline metrics and reported separately, because neither is a confirmed fabrication or alteration.
- **The answer key is scoring-only.** The §9 exclusion and the benchmark labels live in the evaluation layer; the detector itself reads only the documents and the frozen corpus.

## Notes for interpretation

- **Checker-only vs end-to-end.** Checker-only isolates the corpus lookup/fidelity decision. End-to-end is what ProSeAI sees: a missed citation or passage is a miss, even if the checker would have been right.
- **Benchmark collision.** Five `fabricated_statute` injections (`AS 25.24.900/910/920`) are real sections in the frozen corpus, so a correct corpus lookup reports them as real. They surface as `missed_fabrication:benchmark_collision`, not as detector failures.
- **Unkeyed citations.** The answer key omits some real citations that appear in the documents; they are reported above and excluded from precision rather than counted as false positives.
- **Unquoted passages.** Detecting copied statute text without quote marks is lower precision by design; unkeyed flags are reported as possible alterations, not scored as false positives in the fidelity metrics.
- **Unkeyed flags still affect document risk.** A flagged citation or quoted passage that the key does not list is not scored in the citation/quote metrics, but it can still make a document flagged; those cases are listed under *Clean documents flagged*.
- **Small fidelity sample.** The benchmark has 40 altered quotes, 35 of them the same appended phrase, so fidelity recall should be re-checked on more varied edits.
- Existence items skipped (not scored): **2** (§9 exclusion, out-of-scope, or unparseable).
