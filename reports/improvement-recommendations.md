# Improvement Recommendations — Legal 1A Detector

Ranked by severity to the product and to the reported metrics. Every number
comes from the frozen benchmark via `scripts/evaluate_pipeline.py`; the full
breakdown is in [`pipeline-evaluation.md`](pipeline-evaluation.md).

> **Status update — 2026-11-02.** Re-scored against the 2026-11-01 consolidated
> answer key. Two things changed the ranking:
>
> 1. **The five benchmark collisions below are resolved by the new key.** All
>    five `AS 25.24.900/910/920` entries are now `exists: true`, and existence
>    recall is **1.000** (273/273 planted fabrications caught) with one case
>    false alarm that PR #19 fixes. Recommendation 1 is closed; keep it as the
>    record of the audit.
> 2. **The new key added 40 *natural* misquotes** — changes the drafting model
>    made itself. They are the hardest and most product-relevant population, and
>    the current detector catches **1 of 40** (recall 0.025) versus **36 of 40**
>    planted alterations (0.900). See the new recommendation below.
>
> **New #1 — High: the fidelity stage must compare copied clauses, not verbatim
> runs.** `unquoted_passages.py` selects only runs of ≥8 words that already
> match the source verbatim, then checks those runs. Any inserted or dropped
> modal, negation, quantifier or clause falls *between* the runs and is never
> compared — so the change that defines the error is excluded by construction.
> Evidence: of the 39 missed natural misquotes, 18 were extracted and still
> scored faithful or unverified (17 of those at **score 100**), and 21 were
> never extracted. Fix: align the
> document's clause to the matching source clause with a token diff
> (`difflib.SequenceMatcher`) and classify insert/delete/replace at the token
> level, including the key's own categories ("only if"→"if", dropped "only",
> dropped clause). Re-check precision on the 45 intentionally-unlabeled items in
> DATA_DICTIONARY §8.6 so the fix does not turn "shall"→"must" into a flag.

## 1. High — correct the five benchmark collisions before treating recall as a target *(resolved 2026-11-01)*

**Evidence.** All five existence false negatives are `fabricated_statute`
injections that exist in the frozen corpus:

| doc | citation | corpus says |
|---|---|---|
| doc-0059 | `AS 25.24.900` | real section |
| doc-0110 | `AS 25.24.910` | real section |
| doc-0152 | `AS 25.24.910` | real section |
| doc-0182 | `AS 25.24.920` | real section |
| doc-0198 | `AS 25.24.900` | real section |

The detector's statute precision is **1.000**: it makes no false alarms. Its
recall is capped at **0.964 on statutes** (0.982 overall) only because these
labels disagree with the corpus.

**Why it matters.** A correct detector is recorded as having missed a
hallucination, which is the most consequential error class. It also makes the
recall target look worse than the system is.

**Action.** Ask ProSeAI to either relabel these five entries or exclude them
from Stage-2 scoring, the same way §9 handles `AS 11.56.807`. Add a regression
test that asserts the corpus/citation relationship so the disagreement cannot
reappear silently.

## 2. High — resolve quote→source attachment before declaring a quote unverifiable

**Evidence.** Two of the four missed altered quotes were extracted but attached
to the wrong authority, so no source text could be found:

- `doc-0058` — `AS 25.20.060(b)`: the quote has **no** preceding citation in its
  paragraph, so `citation` is `None`.
- `doc-0179` — `AS 25.24.170`: the quote is attached to `AS 25.24.976(a)` (a
  fabricated citation) because it is the nearest citation before the quote.

Both are recorded as `missed_altered:source_not_found`. The checker cannot judge
a quote it cannot source.

**Action.** When `get_source_text` returns `None` for the attached citation:

1. try every other authority cited in the same paragraph and the previous one;
2. try the first citation **after** the quote in the same paragraph;
3. choose the candidate whose text best matches the quote (normalized overlap),
   and only then report `unverifiable`.

This is a contained change in `quote_extractor.attach_citation` /
`unquoted_passages.extract_passages`, and it should recover both cases without
weakening the exact/normalized tiers.

## 3. Medium — recover altered quotes whose source citation is not local

**Evidence.** Two altered quotes were never extracted because the paragraph does
not contain a resolvable source citation:

- `doc-0061` — the paragraph cites fabricated `AS 25.24.916`; the true source
  `AS 25.24.150(c)` appears nowhere nearby.
- `doc-0170` — `Civil Rule 90.3(a)` **is** cited, but the quoted run ends before
  the planted `"under all circumstances"`, and the adjacent source text does not
  end a clause, so the unquoted extractor does not extend the passage.

Both are `missed_altered:not_extracted`. They are 2 of the 40 altered quotes, so
this is a meaningful part of the 90% end-to-end fidelity recall.

**Action.**

- Build a small inverted index of 8-word shingles from the corpus to
  `source_cite`. When local citation lookup finds no source for an unquoted
  passage, use the index to identify the probable source, then run the normal
  fidelity check. Report matches from this fallback as lower confidence.
- For a long verbatim run followed by a short appended phrase, allow a bounded
  tail even when the source clause does not end at the run boundary, and surface
  it as a possible alteration rather than a confirmed one.

## 4. Medium — separate "confirmed alteration" from "possible alteration"

**Evidence.** Unquoted passages account for most of the noise:

- 2 key faithful quotes were flagged because they were unquoted paraphrases
  (`doc-0013` Civil Rule 90.3(a)(1), score 82.1; `doc-0057` AS 25.24.150, score
  84.8).
- 63 of 3,231 unkeyed unquoted passages were flagged.
- In review mode, **39 clean documents** are flagged, versus **4** in strict
  mode. Strict mode still recalls **103/103** corrupt documents.

**Why it matters.** A gate that flags ordinary paraphrase will be ignored by
reviewers, and a single hard boolean hides a real precision/recall tradeoff.

**Action.** Keep the strict flag for quoted passages and fabricated citations
(96.3% document precision, 100% recall). Route unquoted fuzzy matches to a
separate `possible_unquoted_alterations` queue with the score and the matched
source excerpt. If a single flag is required, use `review_required` only for
triage, not as the publication gate.

## 5. Medium — widen the fidelity benchmark beyond one repeated edit

**Evidence.** 35 of the 40 altered quotes are the same appended phrase,
`"under all circumstances"`. The checker's exact/normalized tiers catch every faithful
**quoted** passage; the fuzzy tier catches the planted edits at scores 79–99. That
does not establish behavior on deletions, reordered clauses, or semantically
similar substitutions.

**Action.** Add a held-out fidelity set with varied edits (dropped negation,
`shall`→`may`, swapped parties, reordered clauses, numeric changes) and report
the same tier breakdown. Until then, describe 90% end-to-end fidelity recall as
benchmark-specific.

## 6. Low — account for unkeyed real authorities

**Evidence.** The detector extracted **414 unkeyed citation occurrences (124
unique authorities)**. Only one was flagged: `E.H. v. State, Department of
Health and Social Services, Division of Family and Youth Services, 23 P.3d 1186
(Alaska 2001)` in `doc-0042`. That case is not in the key or the frozen corpus,
so the detector correctly reports it as unknown; it is a key/corpus coverage
gap, not a detector bug.

**Action.** Either add these real authorities to the corpus/key or label them as
known unkeyed citations, and keep excluding unkeyed extractions from precision.
A production deployment should treat "not in corpus" as **needs verification**,
not proof of fabrication, unless the corpus is known to be complete.

## 7. Low — keep the out-of-scope path explicit

**Evidence.** `AS 11.56.807` (`doc-0136`) is real Alaska law outside the
corpus's Title 25 / Title 18 ch. 65–66 scope. On `main` it is reported as
`fabricated` and is one of the four strict document false alarms. PR #18 adds
`OUT_OF_SCOPE` handling, after which it is excluded from both the citation verdict
and the risk flag.

**Action.** Merge PR #18 before publishing document-level numbers, then rerun the
evaluation. The expected change is one fewer clean-document false alarm with no
change to scored existence metrics.

## 8. Low — verify short-form case citations

**Evidence.** `case_parser.py` extracts reporter-only short forms and resolves them
to an earlier full citation (`role: "short_form"`), but `pipeline.py` verifies only
`full_case_citation` entries. A draft that cites a case only by reporter (or whose
full citation was missed) gets no existence check for that reference.

**Action.** Resolve `reporter_only` entries to their full citation when one exists in
the document, then run the same case checker. If no full citation exists, report the
short form as `unverified` rather than silently ignoring it.

## 9. Low — add a semantic tier only if real-world edits need it

**Evidence.** Every faithful **quoted** passage matched at the exact or
normalized tier, and every altered quote scored below 100 at the fuzzy tier. The
two faithful unquoted false alarms are better handled by the confidence split in
#4 than by a semantic tier. A sentence-transformer tier would add latency and a
model dependency without changing these results.

**Action.** Defer. Revisit after the varied fidelity set in #5 shows edits that
preserve meaning-level similarity but change legal meaning.

## Suggested order of work

| order | item | expected effect |
|---|---|---|
| 1 | Benchmark collisions (#1) | removes 5 apparently missed fabrications |
| 2 | Source attachment fallback (#2) | +2 altered quotes caught |
| 3 | Corpus-shingle fallback (#3) | +2 altered quotes caught |
| 4 | Strict/review split (#4) | cleaner production gate |
| 5 | Varied fidelity set (#5) | honest generalization estimate |
| 6 | Unkeyed/key coverage (#6) | fewer unexplained clean-document alerts |
| 7 | Merge #18, rerun (#7) | one fewer document false alarm |
| 8 | Short-form case resolution (#8) | checks reporter-only references |
| 9 | Semantic tier (#9) | only if #5 justifies it |
