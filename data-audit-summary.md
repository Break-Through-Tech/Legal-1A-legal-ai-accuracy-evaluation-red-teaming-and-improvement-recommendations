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

## Answer-key sanity (internally consistent)

- **200/200** records, `doc_id`s match the manifest 1:1 (no orphans, no dupes).
- **Condition split:** 97 clean / 103 corrupt.
- **Doc-type distribution:** child_support 42 · domestic_violence 42 ·
  modify_custody_visitation 42 · unmarried_custody 42 ·
  married_divorcing_with_children 32.
- **Corrupt docs always carry planted errors** (0 corrupt docs with no injected
  error; 0 clean docs with an injected error) — the `exists` / `quote_status`
  labels are trustworthy for scoring.
- **`n_errors_planted` distribution (corrupt only):** 3 → 54 docs, 4 → 29, 2 → 20.
- **Corruption menu present:** fabricated_statute 139 · fabricated_rule 88 ·
  wrong_reporter 30 · fabricated_case 21 · altered_quote 40 (total 318 planted
  errors across 103 docs).
- **Citation volume:** 3,490 citations total (~17.4/doc, range 8–32):
  statute 1,546 · case 1,172 · rule 772. Quotes on 69 docs (163 quotes).

## ⚠️ Findings that affect the extractor

1. **Rule-citation format mismatch (blocker for naive matching).** Documents cite
   civil rules as **`Civil Rule 90.3`** / **`Rule 90.3`** (715 rule cites), but the
   corpus stores them as **`Alaska R. Civ. P. 90.3`**. Evidence rules are already
   `Alaska R. Evid. X` in both (48 cites). → Normalize civil-rule forms before
   corpus lookup; a string-equality `exists` check will falsely fail 715 real cites.

2. **Manifest hash not reproducible from my extraction.** Recomputing SHA-256 over
   raw `.docx` bytes (and over normalized paragraph text) did **not** match the
   manifest hash. The dictionary says the hash is over "the final document text,"
   but that normalization isn't specified precisely enough to reproduce. → Treat
   the manifest hash as a version stamp, not a check we can currently re-verify;
   if we need integrity verification, agree on an exact text-normalization recipe.

3. **Case citations are full reporter cites.** All 1,172 case cites carry a
   reporter (e.g. `Hayes v. Hayes, 922 P.2d 896 (Alaska 1996)`); `wrong_reporter`
   errors (30) keep the case name and swap the volume/page. → The existence check
   must verify the **full cite** (name + reporter), not just the case name, to
   catch `wrong_reporter`.

4. **AAC out of scope, confirmed.** No benchmark citation references the Alaska
   Administrative Code; a detector can treat admin-regulation cites as out of
   scope (§3, §8).

5. **Recall-first target confirmed (§8.5).** 278 of 318 planted errors are
   existence errors; fidelity has a smaller sample (40). Report Stage 2 and
   Stage 3 metrics separately.

## Ownership

September tasks per the challenge board (Legal-1A project, issue #2/#3):
data audit + schema review = **Abigail**; statutes/rules citation extractor =
shared with **May Bui**. This summary is the audit deliverable for #2.

## Next

- [ ] Start the citation extractor (issue #3) — parse DOCX paragraphs, normalize
      civil-rule forms, verify against corpus.
- [ ] Confirm the hash-reproducibility question with the ProSe AI team.