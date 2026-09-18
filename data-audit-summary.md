# Data Audit Summary — Legal 1A (ProSe AI)

**Audit date:** 2026-09-18
**Auditor:** Abigail Briones Aranda

Verification of the frozen benchmark against the data dictionary (§9) and a
pre-flight look at the citation-corpus shape before writing the extractor.

## Component inventory (all 5 present)

| Component | Location | Verified |
|---|---|---|
| Corpus | `data/corpus/*.jsonl` | ✅ 4 files, see below |
| Benchmark docs | `data/benchmark/documents/doc-0001..0200.docx` | ✅ 200 files |
| Answer key | `data/benchmark/answer-key.json` | ✅ 200 records |
| Manifest | `data/benchmark/manifest.json` | ✅ 200 entries, hashes match key |
| Data dictionary | `data/benchmark/DATA_DICTIONARY.md` | ✅ read, §9 followed |

## Corpus sizes (match dictionary §3)

| File | Records | Citation field | Source field |
|---|---|---|---|
| `statutes.jsonl` | 500 | `citation` (e.g. `AS 25.05.010`) | `source_text` |
| `rules.jsonl` | 155 | `citation` (e.g. `Alaska R. Civ. P. 12`) | `source_text` |
| `rules-evidence.jsonl` | 302 | constructed: `Alaska R. Evid. {ruleNumber}` | `text` |
| `cases.jsonl` | 1,255 | `citation` + `case_name`/`reporter_cite` | `source_text` |

## Answer-key sanity

- **200/200** records, `doc_id`s match the manifest 1:1 (no orphans, no dupes).
- **Condition split:** 97 clean / 103 corrupt.
- **Doc-type distribution:** child_support 42 · domestic_violence 42 ·
  modify_custody_visitation 42 · unmarried_custody 42 ·
  married_divorcing_with_children 32.
- **`n_errors_planted` distribution (corrupt only):** 3 → 54 docs, 4 → 29, 2 → 20.
- **Corruption menu present:** fabricated_statute 139 · fabricated_rule 88 ·
  wrong_reporter 30 · fabricated_case 21 · altered_quote 40 (total 318 planted
  errors across 103 docs, all of them marked `injected`).
- **Citation volume:** 3,490 citations total (~17.4/doc, range 8–32):
  statute 1,546 · case 1,172 · rule 772. Quotes on 69 docs (163 quotes).

> ⚠️ **The `exists` labels are NOT fully trustworthy.** 32 citations are marked
> `exists: false` with **no `injected` marker**, and **21 of them sit in `clean`
> documents** — which the dictionary says should contain no fabricated citations.
> 19 of the 32 actually exist in the corpus (12 exact matches, 7 more after
> stripping leading prose like "The " / "See " / "Petitioner. In "). See finding 2.

## ⚠️ Findings that affect the extractor

1. **Rule-citation format mismatch (blocker for naive matching).** Documents cite
   civil rules as **`Civil Rule 90.3`** / **`Rule 90.3`** (715 total rule cites in
   this form: 632 real + 83 fabricated), but the corpus stores them as
   **`Alaska R. Civ. P. 90.3`**. Evidence rules are already `Alaska R. Evid. X`
   in both (57 cites). → Normalize civil-rule forms before corpus lookup; a
   string-equality corpus lookup will falsely mark 632 real cites as not found.

1b. **4 real citations are NOT in the corpus (data-quality flag for the team).**
    `Civil Rule 16.2(e)`, `Civil Rule 3(h)`, `Civil Rule 86(l)`, `Civil Rule 99(a)`
    are marked `exists: true` in the answer key, but none of these rule numbers
    appears in `rules.jsonl` (corpus contains civil rules 12, 26, 40, 41, 52, 53,
    58, 59, 60, 65, 77, 78, 90, 100 only). A strict corpus lookup will therefore
    **false-negative** these as fabricated. → Flag to ProSe AI; either the key or
    the corpus needs a fix, or the detector should whitelist them.

2. **Answer-key `exists` labels have a systematic inconsistency (critical).**
    32 citations are marked `exists: false` with **no `injected` marker**, and
    **21 of them are in `clean` documents** — which the data dictionary defines
    as containing no fabricated citations. Breaking down the 32:
    - **12 are exact corpus matches** still labeled `exists: false`
      (`AS 18.66.180`, `AS 18.66.990` — retrievable, active, binding; several
      `* v. Bromley, 987 P.2d 183` where the doc omits the "State," party).
    - **7 more match after stripping leading prose** in the cite string
      (`The Nelson v. Nelson`, `See Ruppe v. Ruppe`,
      `Petitioner. In Stephan P. v. Cecilia A.`, etc.).
    - **13 are genuinely absent** from the corpus — real fabrications that were
      planted but never marked `injected` (e.g. `AS 11.56.807`, several
      `Dawn Golden v. Timothy B. Golden, 563 P.3d 1131`).
    → **Implication for scoring:** a correct existence checker will disagree with
    the answer key on up to 19 of these (12 exact + 7 prose-stripped) and "miss"
    13 unmarked fabrications. The team must decide how to score against this —
    flag to ProSe AI before trusting `exists` as ground truth.

3. **Manifest hash not reproducible from my extraction.** Recomputing SHA-256 (and
   MD5/SHA-1) over 11 candidate text forms — raw `.docx` bytes, `document.xml`,
   run joins, and paragraph joins with several separators — did **not** match the
   manifest hashes. The dictionary says the hash is over "the final document text,"
   but that normalization isn't specified precisely enough to reproduce. → Treat
   the manifest hash as a version stamp, not a check we can currently re-verify;
   if we need integrity verification, agree on an exact text-extraction recipe.

4. **Positive controls (no normalization needed for these).** All 1,394 real
   statute cites match `statutes.jsonl` `citation` exactly (1,546 total − 152
   fabricated), and all 52 real evidence-rule cites match the constructed
   `Alaska R. Evid. {ruleNumber}` form. The normalization work is confined to
   civil rules (finding 1) and case-name prose (finding 2).

5. **Case citations are full reporter cites.** All 1,172 case cites carry a
   reporter (e.g. `Hayes v. Hayes, 922 P.2d 896 (Alaska 1996)`); `wrong_reporter`
   errors (30) keep the case name and swap the volume/page. → The existence check
   must verify the **full cite** (name + reporter), not just the case name, to
   catch `wrong_reporter`. Also strip leading prose ("The ", "See ", "Petitioner. In ").

6. **AAC out of scope, confirmed.** Zero citations in the answer key and zero
   `.AAC` mentions in the 200 documents; a detector can treat admin-regulation
   cites as out of scope (§3, §8).

7. **Recall-first target confirmed (§8.5).** 278 of 318 planted errors are
   existence errors; fidelity has a smaller sample (40). Report Stage 2 and
   Stage 3 metrics separately.

## Ownership

September tasks per the team's challenge board (Legal-1A project, tasks #2/#3):
data audit + schema review = **Abigail** (this document); the statutes/rules
citation extractor (September deliverable) = shared with **May Bui** per the
team's task assignment. This fulfills the September milestone's first activity
("explore the frozen benchmark and citation corpus: document structure, citation
patterns, statute vs. case-law references") and the "when done" step of board
task #2 ("commit a short data-audit summary to the repo").

## Next

- [ ] Start the citation extractor (issue #3) — parse DOCX paragraphs, normalize
      civil-rule forms, verify against corpus (measure extraction recall against
      the answer key).
- [ ] Confirm the hash-extraction recipe with the ProSe AI team (finding 2).
- [ ] Ask ProSe AI about the 4 corpus-missing rules (Civil Rule 3, 16.2, 86, 99)
      marked real in the answer key (finding 1b).