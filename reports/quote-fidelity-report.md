# Quote-Fidelity Report — Statutes and Rules (October Milestone)

**Date:** 2026-10-13
**Scope:** Quote-fidelity verification of every quoted passage of statute or court-rule text in the 200 benchmark documents, scored against `quote_status` in `answer-key.json`.
**Deliverable:** Quote-fidelity module with unit tests, plus metrics and threshold analysis.

## Summary

| | Quoted passages only | Quoted + unquoted passages |
|---|---|---|
| Altered quotes found by extraction | 23 / 40 | 38 / 40 |
| **Altered recall (end to end)** | **52.5%** (21/40) | **90.0%** (36/40) |
| **Altered precision (answer-key quotes)** | **100%** (21/21) | **94.7%** (36/38) |
| Flags on passages not in the answer key | 2 | 65 |
| Precision counting those flags as false alarms | 91.3% | 35.0% |

- **The checker itself is accurate.** It catches 36 of the 38 altered quotes it is given, including all 5 word-level edits (`shall` → `may`, `primary` → `sole`, a dropped `not`).
- **Most remaining errors come from extraction.** Many drafts copy statute text with no quote marks. Searching for those passages raises recall from 52.5% to 90%, but it also adds 63 flags on ordinary prose.
- **Recommendation:** report quoted-passage flags as high-confidence alterations, and unquoted-passage flags as lower-confidence "possible alteration, needs review". See [Recommendation](#recommendation).
- **Benchmark caveat:** 35 of the 40 planted alterations are the same appended phrase, "under all circumstances". These numbers will likely overstate performance on real alterations. See [Benchmark caveat](#benchmark-caveat).

## Method

The pipeline has four stages:

```
document ──► 1. extract passages ──► 2. look up source text ──► 3. compare ──► faithful / altered
              (quoted + unquoted)     (statute / rule corpus)     (tiered)
```

### 1. Extract passages

- **Quoted passages** (`quote_extractor.py`). This stage takes text between straight or curly quote marks, at least 3 words long, and skips defined-term labels like `(hereinafter "Petitioner")`. Each quote is attached to the nearest statute or rule citation before it in the same paragraph.
- **Unquoted passages** (`unquoted_passages.py`). Drafts often copy statute text straight into a sentence without quote marks. For each paragraph, this stage aligns the paragraph's words against the source text of every authority cited in that paragraph or the one before it. The citation may come before or after the passage. Any run of 8 or more words that appears verbatim, in order, in the source is a passage. The run is extended past its end only when it reaches the end of a source clause and the draft adds 1–4 words before its own punctuation. That is where appended alterations land. A trailing citation such as "under AS 25.24.150" does not count as added words.

### 2. Look up source text

`source_lookup.py` maps any citation spelling (`AS 25.24.160(a)(4)`, `Civil Rule 90.3(a)`, `Rule 90.3`, `Alaska R. Evid. 505(b)`) to the full text of that section or rule. It handles three corpus quirks:

- repealed statutes have the string `"None"` as their text
- civil rules are stored one record per subrule and are joined into one text
- evidence-rule commentary records are skipped

PDF line breaks are collapsed. Every one of the 163 answer-key quotes resolves to source text.

### 3. Compare (tiered)

`quote_fidelity.check_quote` tries each tier in order and stops at the first that decides:

| Tier | Test | Verdict |
|---|---|---|
| exact | Quote is a substring of the source | faithful |
| normalized | Match after ignoring case, punctuation, curly quotes, list markers like `(1)`, and whitespace. Ellipses and `[brackets]` split the quote into pieces that must appear in order. | faithful |
| fuzzy | Score (0–100) the quote against the closest stretch of the source (rapidfuzz) | altered if 70 ≤ score < 100 |
| unrelated | Fuzzy score below 70: the quote is not from this source (testimony, wrong citation) | not judged |
| no_source | Citation missing or not in the corpus | not judged |

The fuzzy score compares the whole quote against the closest window of source text. It deliberately does not use rapidfuzz's `partial_ratio` score directly. That score is 100 when the quote is longer than the source and contains it, so it would miss words added to a short source.

## Threshold analysis

The tiers alone almost separate the classes. In both modes, **every faithful quote in quote marks matched at the exact or normalized tier**, and every altered quote fell through to fuzzy. That leaves two settings to choose: the threshold (the score needed to count as faithful) and the floor (below it, a quote is "unrelated" rather than altered).

### Threshold: 100

Quoted passages only:

| Threshold | Altered caught (of 23) | False alarms (key) | False alarms (not in key) |
|---|---|---|---|
| 90 | 8 | 0 | 17 |
| 95 | 16 | 0 | 17 |
| 98 | 20 | 0 | 18 |
| **100** | **21** | **0** | **18** |

- **Raising the threshold costs almost nothing.** No faithful quote reaches the fuzzy tier, so there is no faithful quote to protect by setting it lower.
- **The meaningful alterations score highest.** The five word-level edits score 95.6–99.0, because changing one word in a long quote changes few characters. **A threshold of 95 would miss every one of them.** The appended-phrase alterations score 79–93.
- A threshold of 100 means "no clean match = altered".

### Floor: 70

At a threshold of 100, most false alarms on passages not in the answer key are **testimony or wrong-statute quotes**, for example "make Ashley regret it" attached to AS 18.66.100. They score 49–67 against the attached statute and would be flagged at any threshold. Altered quotes score 79 or higher, because they are the real text with a few words changed:

```
not from this source   49.5 ─────────── 66.7
altered quotes                              79.2 ───────────────────── 99.0
                                      ↑ floor = 70
```

Floor sweep, quoted passages only, threshold 100:

| Floor | Altered caught (of 23) | False alarms (not in key) |
|---|---|---|
| 0 (none) | 21 | 18 |
| 60 | 21 | 3 |
| **70** | **21** | **2** |
| 80 | 20 | 2 |
| 85 | 18 | 1 |

Any floor from 70 to 75 gives the same result. At 80 the lowest-scoring altered quote (79.2) starts to be lost. **Caveat:** the gap between 67 and 79 comes from a sample of 21 altered quotes. Treat 70 as a starting point to re-check on new data, not a proven boundary.

Both settings live in `quote_fidelity.py` (`FUZZY_THRESHOLD`, `UNRELATED_BELOW`). `scripts/sweep_threshold.py` reproduces the full tables for the current results.

## Results

### Extraction coverage

| | Quoted only | Quoted + unquoted | Of which unquoted |
|---|---|---|---|
| Altered quotes found | 23 / 40 (57%) | 38 / 40 (95%) | 15 |
| Faithful quotes found | 86 / 123 (70%) | 120 / 123 (98%) | 34 |

Of the 54 answer-key quotes the quote extractor misses, 47 have no quote marks in the document. Of the other 7, 5 are in quote marks but attached to a fabricated citation planted in place of the real one (e.g. `Civil Rule 994(a)` for `90.3(f)`), and 2 could not be located in the document text.

### Fidelity (quoted + unquoted, threshold 100, floor 70)

| | Precision | Recall | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|---|---|
| Checker (extracted passages) | 94.7% | 94.7% | 94.7% | 36 | 2 | 2 | 118 |
| End to end (missed passages count as not flagged) | 94.7% | 90.0% | 92.3% | 36 | 2 | 4 | 121 |

By tier, extracted answer-key passages:

| Tier | n | Altered | Faithful |
|---|---|---|---|
| exact | 49 | 0 | 49 |
| normalized | 69 | 0 | 69 |
| fuzzy | 38 | 36 | 2 |
| no_source | 2 | 2 | 0 |

### Remaining errors

**Altered quotes missed (4):**

- **Not extracted (2):** `doc-0061` and `doc-0170`.
- **No source (2), not detectable by this stage:**
  - `doc-0179`: the quote is attached to `AS 25.24.976(a)`, a fabricated citation planted in place of `AS 25.24.170`. The existence checker flags it.
  - `doc-0058`: the quote has no citation before it in its paragraph.

**Faithful quotes flagged (2), both unquoted:** a drafter copied the start of a statute clause and finished it in their own words:

- "...minus certain enumerated deductions" (score 82.1)
- "...the court shall consider all relevant factors" (score 84.8)

**Flags on passages not in the answer key (65):** 2 are quoted, 63 unquoted.

- **Most are ordinary prose after a copied clause**, such as "...against Petitioner" or "...as a relevant factor". Structurally, these look the same as an appended alteration.
- **Some are real problems the answer key does not label as quote errors.** In `doc-0016`, a copied passage cites the planted fabricated `AS 25.24.908` where the source reads `AS 25.24.160`. In `doc-0004`, a copied passage changes the source's cross-reference from `AS 25.20.060` to `AS 25.24.150`.

**Faithful quotes not paired with any passage (3):** `doc-0049` (`Alaska R. Evid. 706(a)`, where the document cites the planted fabricated `Alaska R. Evid. 930(a)` instead), plus `doc-0132` and `doc-0135` (`Civil Rule 65(e)`).

## Benchmark caveat

The planted alterations are not diverse:

| Alteration | Count |
|---|---|
| "under all circumstances" appended | 35 |
| `primary` → `sole` | 2 |
| `shall` → `may` | 2 |
| `not` deleted | 1 |

- **A detector that searched for the phrase "under all circumstances" would score very well and generalize to nothing.** No rule in this module looks for that phrase or any other specific wording.
- **The 5 word-level edits are the best evidence of generalization.** All 5 are caught, but all 5 are in quote marks.
- **The unquoted-passage append rule is untested on other alteration types.** It was built for appended words, and appended words are 35 of the 40 planted alterations.
- **Swap detection for unquoted text was tried and removed.** The rule flagged a changed word between two verbatim runs. It caught none of the planted alterations and raised about 600 false alarms, because in unquoted text a changed word is ordinary paraphrase.

## Semantic tier: not implemented

The plan included a sentence-transformers similarity tier after fuzzy. It was left out:

- **Planted alterations barely change a sentence's embedding.** Appending "under all circumstances" or swapping `shall` for `may` leaves an altered quote almost identical to its source in embedding space. That near-identity is what makes these alterations dangerous, and it would push a semantic score toward "faithful".
- **No faithful quote needs rescuing.** Every faithful quote in quote marks already matches at the exact or normalized tier, so a looser semantic test has nothing to recover.

A semantic model could help with the unquoted-passage false alarms, by telling a drafter's own continuation apart from an inserted qualifier. That would be a classifier over the added words, not a similarity tier.

## Recommendation

1. **Quoted-passage flags: report as altered quotes.** 100% precision on the answer key and 91% counting all false alarms.
2. **Unquoted-passage flags: report as "possible alteration, review the added words".** They find 15 altered passages that would otherwise be missed, but about 1 in 4 of these flags is correct (15 of 80).
3. **Reports of fidelity results should state the benchmark caveat.**

## Limitations and next steps

- **Citation attachment.** Quotes attach to the nearest preceding citation in the same paragraph. This produced the testimony false alarms (now handled by the floor) and one undetected alteration (`doc-0058`). Searching after the quote, or in the previous paragraph, would help.
- **Pinpoints are ignored.** A quote cited to `AS 25.24.150(c)` is checked against all of section 150. The check confirms a quote is in the section, not that it is in the cited subsection.
- **Heavily rewritten alterations go unjudged.** An altered quote scoring under 70 would be labeled "unrelated" rather than altered. No planted alteration comes close (the lowest is 79.2).
- **Cross-reference changes inside copied passages** (the `doc-0004` and `doc-0016` cases) could become their own check.
- **Case-law quotes are out of scope.** Every answer-key quote is from a statute or rule.

## Reproducing

```bash
source .venv/bin/activate
pytest                                         # 80 tests
python scripts/evaluate_quotes.py              # quoted + unquoted; writes data/quote-fidelity-results.json
python scripts/evaluate_quotes.py --quoted-only
python scripts/sweep_threshold.py              # threshold and floor sweeps over the saved results
```

**Code:**

| File | Role |
|---|---|
| `src/citation_extractor/quote_extractor.py` | Extract quoted passages |
| `src/citation_extractor/unquoted_passages.py` | Extract unquoted passages |
| `src/citation_extractor/source_lookup.py` | Look up source text |
| `src/citation_extractor/quote_fidelity.py` | Compare quote to source |
| `tests/test_quote_extractor.py`, `test_source_lookup.py`, `test_quote_fidelity.py`, `test_unquoted_passages.py` | Unit tests |