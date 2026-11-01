# ProSe AI — Hallucinated-Citation Benchmark: Data Dictionary

**Deliverable:** Detecting Hallucinated Legal Citations in AI-Generated Court Documents
**Prepared by:** ProSe AI, for the Break Through Tech AI Studio 2026 Challenge
**Status:** Frozen benchmark — do not regenerate; integrity is verified by the per-document `docx_sha256` values in `manifest.json`.

---

## 1. What this benchmark is

A fixed, labeled set of AI-generated Alaska family-law legal documents, built with fictional
party names. Roughly half are **clean** (no errors were planted: no injected citations and no
planted altered quotes) and roughly half are **corrupt** (containing deliberately planted errors —
fabricated citations and altered quotes).

> ⚠️ **"Clean" means "nothing was planted", not "nothing can be flagged."** An earlier version
> of this paragraph said clean documents have "every citation real and every quote faithful",
> which contradicted §4.1 and was not quite true: the drafting model occasionally cited an
> authority that was real but had not been retrieved for that document, and those citations
> appear in clean documents. They are now labeled `exists: true` (see the corrections note in
> §3.2), so a detector that flags nothing in a clean document is still correct — but the
> guarantee is about **planting**, not about the model's citation behaviour. Every document ships with an **answer key** marking each citation as
real or fabricated. Quote labels are a sample, not an inventory; see §8.6.

> ⚠️ **Clean documents can contain natural misquotes.** The drafting model sometimes changed
> source wording on its own. Those changes were not planted, so a document that has one is still
> clean. Where they are labeled, they carry `planted: false` (§4.3, §8.6).

The benchmark exists to let a team build and measure a **hallucinated-citation detector**:
a tool that reads a generated legal document and flags citations that do not exist, or that
misquote their source. Because the errors are planted by construction, the answer key is
**ground truth by construction** — no legal judgment is required to use it. The team does
not decide what is correct law; ProSe AI has already established that by controlling exactly
which authorities each document was told to cite, and exactly which of those were then
corrupted.

---

## 2. Files in the benchmark

| File | Contents |
|------|----------|
| `benchmark/documents/doc-NNNN.docx` | The generated legal documents (Word format). Some clean, some corrupt. |
| `benchmark/answer-key.json` | One record per document: every citation labeled real/fabricated, plus quote labels where present (see §8.6). The scoring target. |
| `benchmark/manifest.json` | Document inventory + `docx_sha256` (full SHA-256 of each `.docx` file, the integrity check) + `hash` (the original fingerprint, see §4.1) + clean/corrupt counts. |
| `data/corpus/*.jsonl` | The citation corpus: real Alaska statutes, court rules, and case citations with source text. The lookup target for existence and fidelity checks. |

---

## 3. The citation corpus (the lookup target)

The detector verifies each cited authority against this corpus. It contains four authority
types, each as structured JSON records (one JSON object per line, `.jsonl`):

| Corpus file | Authority type | Approx. size |
|-------------|----------------|--------------|
| `statutes.jsonl` | Alaska Statutes (Title 25 family law; Title 18 ch. 65–66 DV/protective orders) | ~500 records |
| `rules.jsonl` | Alaska Rules of Civil Procedure (incl. Rule 90.3 child support) | ~185 records |
| `rules-evidence.jsonl` | Alaska Rules of Evidence + commentary | ~302 records |
| `cases.jsonl` | Published Alaska Supreme Court family-law opinions | ~1,255 cases |

**Field layout differs slightly by file — read the citation and source text from these fields:**

| File | Citation string | Source text | Notes |
|------|-----------------|-------------|-------|
| `statutes.jsonl` | `citation` (e.g. `"AS 25.24.150"`) | `source_text` | Also: `title`, `jurisdiction`, `cross_refs`. |
| `rules.jsonl` | `citation` (e.g. `"Alaska R. Civ. P. 90.3"`) | `source_text` | Civil rules; `subrule` may be set. |
| `cases.jsonl` | `citation`; also `case_name` + `reporter_cite` separately | `source_text` | `year` and `court` also present. `holding` and `pinpoint` are empty on all 1,255 records. 23 records have no `reporter_cite`. 89 reporter cites each appear on two records, usually caption variants, so a reporter lookup can return two records. 5 of those reporters are key authorities. |
| `rules-evidence.jsonl` | **constructed** from `ruleNumber` (+ `subrule`) — there is no single `citation` field; e.g. `ruleNumber:"505"` → `"Alaska R. Evid. 505"` | `text` (not `source_text`) | Evidence rules use `ruleNumber`/`ruleTitle`/`text`; `ruleset:"evidence"`. Commentary records have `type:"rule_commentary"`. |

So three of the four files (`statutes`, `rules`, `cases`) expose a ready-made `citation` string and `source_text`. Only `rules-evidence.jsonl` differs: build the citation from `ruleNumber` and read text from `text`.

Records marked non-retrievable or non-citable (`retrievable:false`, or rule commentary that is
persuasive rather than binding) are present for completeness but were **not** used as citation
sources when generating documents; a detector may treat them as valid-existing authorities but
they will rarely appear in the benchmark.

Two non-corpus build artifacts may also be present in the folder — `rules-evidence-manifest.json`
and `rules-evidence-report.json`. These are parser outputs, not corpus data, and can be ignored.

**Source of the underlying law:** the Alaska Legislature's public statutes, the Alaska Court
System's published rules, and public court-opinion metadata from CourtListener (Free Law
Project). All public record; no PII.

### 3.1 ⚠️ RULE CITATIONS: the documents and the corpus use DIFFERENT FORMS — you must normalize

**This is the single most likely thing to break a detector, and it is not a defect in either
artifact.** Real Alaska filings cite rules in shorthand; the corpus stores the formal citation.
Both are correct. They do not match as strings.

| where | form | example | count in the benchmark |
|-------|------|---------|------------------------|
| **documents** | `Civil Rule NN` | `Civil Rule 90.3(a)` | 642 |
| **documents** | bare `Rule NN` | `Rule 90.3` | 80 |
| **documents** | `Alaska R. Evid. NN` | `Alaska R. Evid. 505` | 58 |
| **corpus** (`rules.jsonl`) | `Alaska R. Civ. P. NN` | `Alaska R. Civ. P. 90.3` | 172 records; the other 13 end in `, Commentary` |
| **corpus** (`rules-evidence.jsonl`) | ⛔ **no `citation` field at all** | build from `ruleNumber` + `subrule` | all records |

⛔ **A naive exact-match of the document's citation string against the corpus `citation` field
matches 53 of 780 rule citations (6.8%) and would wrongly report 639 REAL rule citations as
fabricated.**

⚠️ **Normalizing only the `Civil Rule` prefix is not enough.** The 639 real rule citations a
naive match misses are 559 `Civil Rule` citations plus 80 bare `Rule NN` citations, so fixing
only the `Civil Rule` prefix still leaves those 80 unmatched.

#### What to do instead

> **Match rules on the normalized rule NUMBER, never on the citation string.**

1. Extract the rule number from the document citation, accepting all of
   `Alaska R. Civ. P.` · `Civil Rule` · `Alaska R. Evid.` · `Evidence Rule` · bare `Rule`.
2. Extract the rule number from the corpus: from `citation` for `rules.jsonl`; from
   `ruleNumber` for `rules-evidence.jsonl` (which has no `citation` field).
3. Compare numbers, not strings. Strip any `(subrule)` suffix before comparing — the corpus
   stores one record per subrule, all sharing the same rule-level `citation`, so one rule
   number legitimately maps to **many** corpus records.
4. Keep civil and evidence rules in separate namespaces: `Civil Rule 90.3` and
   `Alaska R. Evid. 90.3` are different authorities that would collide on number alone.

⚠️ **5 fabricated civil rules share a number with a real evidence rule.** Alaska Evidence Rules
901 and 903 are real, and these planted citations use the same numbers in the civil family. They
are **correctly labeled fabricated**: there is no Civil Rule 901 or 903, and each one replaced a
real civil rule. **A detector matching on rule number alone, without the rule family, would
wrongly pass them.**

| Document | Fabricated citation | `replaced_real` |
|----------|---------------------|-----------------|
| `doc-0008` | `Civil Rule 903(e)` | `Civil Rule 65(e)` |
| `doc-0010` | `Civil Rule 901(a)` | `Civil Rule 90.3(a)` |
| `doc-0132` | `Civil Rule 903(e)` | `Civil Rule 65(e)` |
| `doc-0173` | `Civil Rule 903(a)` | `Civil Rule 90.3(a)` |
| `doc-0194` | `Civil Rule 903(a)` | `Civil Rule 90.3(a)` |

⚠️ Statutes and cases do **not** have this problem. Statute citations match `citation` in
`statutes.jsonl` once the pinpoint is stripped (`AS 25.24.150(c)` → `AS 25.24.150`). Case citations should be matched on **reporter cite**
(`"987 P.2d 183"`), not case name — see §8.

---

### 3.2 📌 Corrections applied 2026-09-21 (after a student audit)

Three corrections were made to the delivered set. **No document was regenerated; every
document hash in `manifest.json` remains valid.**

1. **`rules.jsonl`: 155 → 185 records.** Alaska Civil Rules **3** (Commencement of Action and
   Venue), **16.2** (Informal Trials in Domestic Relations Cases), **86** (Habeas Corpus) and
   **99** (Telephonic Participation in Civil Cases) are real, active rules that documents cite
   but that the original corpus slice omitted — 50 citations pointed at authorities the corpus
   could not confirm. Added from the same Alaska Court System source as the rest of the file.
2. **31 citation labels corrected `exists: false` → `true`** in `answer-key.json`. These were
   real authorities present in the corpus but labeled as though fabricated; see §8 for the
   cause. *(A 32nd, `AS 11.56.807`, is also real but is **outside** the corpus — it keeps
   `exists: false` and is explained below.)*
3. **This dictionary** gained §3.1, the correction note in §1, and the `raw_extracted` field
   in §4.2.

#### ⚠️ TWO CITATIONS ARE REAL LAW BUT SIT OUTSIDE THE CORPUS — `AS 11.56.807` AND `AS 11.56.810`

`doc-0136` (a **clean** document) cites **`AS 11.56.807` — "Terroristic threatening in the
first degree", Alaska Statutes Title 11, Chapter 56.** Confirmed against authoritative sources
(Alaska Statutes, akleg.gov, Justia) on 2026-09-21. The same document cites **`AS 11.56.810` —
"Terroristic threatening in the second degree"**, in the list form `AS 11.56.807 or 11.56.810`.
Confirmed against akleg.gov on 2026-11-01 and added to the key by §3.3.

> ⛔ **THESE ARE REAL LAW. THEY ARE NOT FABRICATIONS, AND NOTHING IN THIS BENCHMARK SHOULD BE READ
> AS CALLING THEM THAT.** The drafting model cited genuine Alaska criminal statutes in a family-law
> document — a reasonable thing to do when a protective-order matter touches threatening
> conduct.

**Both are labeled `exists: false`, and that is deliberate.** Throughout this benchmark `exists`
means *"present in THIS corpus"* — and this corpus is scoped to Title 25 and Title 18 ch. 65–66
(family law and domestic violence). Title 11 is not in it at all. Flipping either label to `true`
would break that meaning and would make the answer key disagree with the corpus it is scored
against.

⚠️⚠️ **CONSEQUENCE FOR SCORING, AND IT IS THE ONE THING TO GET RIGHT.** §9 says a citation is a
true positive for "hallucination" when its `exists` is `false`. Applied literally to these two
citations, **a detector that correctly recognises either one as real Alaska law is scored as
having MISSED a hallucination** — a false negative against the recall metric §9 asks you to
emphasise.

> **Required handling: EXCLUDE both citations from Stage-2 scoring** rather than count them
> either way (see §9). They are the only two of their kind in the benchmark — 2 of 3,584
> citations — so excluding them changes no reported figure materially, and counting them
> penalises exactly the detectors that are working correctly.

**There are now no unresolved citations in this benchmark.** Every citation is either confirmed
present in the corpus, confirmed planted, or — in these two cases — confirmed real law that the
corpus deliberately does not cover.

### 3.3 📌 Corrections applied 2026-11-01 (final consolidated correction)

A full audit compared the answer key with the text of all 200 documents. `answer-key.json`,
`manifest.json` and this dictionary were corrected. **No document or corpus file changed.**
`manifest.json` gained `docx_sha256` for every document, and its existing `hash` values are
unchanged.

| Measure | Before | After |
|---------|--------|-------|
| Citation entries | 3,490 | 3,584 |
| `exists: true` | 3,211 | 3,309 |
| `exists: false`, planted (injected citations) | 278 | 273 |
| `exists: false`, real law outside the corpus, excluded from Stage 2 | 1 | 2 |
| Authority targets (unique `norm` per document, §4.4) | 2,398 | 2,493 |
| Planted errors (injected citations + 40 planted altered quotes) | 318 | 313 |
| Quote rows | 163 | 202 |
| Quote rows: altered, planted | 40 | 40 |
| Quote rows: altered, natural | 0 | 40 |
| Quote rows: faithful | 123 | 122 |

1. **5 injected statutes relabeled as real.** The injector picked 900-range section numbers at
   random and never checked them. Five landed on real, active sections: `AS 25.24.900`
   (`doc-0059`, `doc-0198`), `AS 25.24.910` (`doc-0110`, `doc-0152`) and `AS 25.24.920`
   (`doc-0182`). They are now `exists: true`, `injected: false`, and each document's
   `n_errors_planted` dropped by 1. `replaced_real` stays on these 5 entries as the record of
   what happened.

   ⚠️ **These sentences still cite the wrong statute.** `doc-0059` cites `AS 25.24.900`, on
   military residency, for the best-interests factors. An existence check cannot catch that, and
   no label in this benchmark scores it.
2. **95 omitted authorities added** to the documents that cite them:
   - **46 injection leftovers.** The injector replaced the first occurrence of a citation and
     removed its label, so later occurrences stayed in the text unlabeled.
   - **17 full case citations** the key's extractor could not parse, because of commas in the
     caption or no `v.`.
   - **32 range or list endpoints** written without an `AS` prefix, such as the `18.66.180` in
     `AS 18.66.100 through 18.66.180`. One of these is `AS 11.56.810`.
3. **39 `cite` strings corrected, labels unchanged:**
   - 3 real entries named a pinpoint the text does not contain, because injection overwrote it:
     `AS 18.66.110(a)` in `doc-0125`, `AS 25.27.062(a)` in `doc-0175` and `AS 25.24.170(a)` in
     `doc-0179` now omit the `(a)`.
   - 25 fabricated citations gained the pinpoint the text gives them, such as `AS 25.24.969(2)`.
   - 2 fabricated bare rules became `Civil Rule 920` (`doc-0036`) and `Civil Rule 964`
     (`doc-0196`), as the text reads. `Civil Rule 978(b)` (`doc-0189`), counted in the 25 above,
     got the same fix.
   - 9 case names regained the start the extractor dropped (7 `State, Child Support Enforcement
     Division v. Bromley`, 2 `del Rosario v. Clare`).
4. **`norm` added to every citation entry.** See §4.4.
5. **1 exact duplicate removed.** The 2026-09-21 cleanup turned `The Nelson v. Nelson, 263 P.3d 49
   (Alaska 2011)` in `doc-0082` into a string that already had an entry. The plain copy is gone,
   and the entry carrying `raw_extracted` stays. This is the only citation entry removed: every
   pinpoint and form variant remains.
6. **40 natural misquotes labeled** (§8.6), and the 40 planted rows gained `planted: true`.
   `doc-0083`'s faithful row for `AS 25.24.150(c)(6)` became one of the 40, because it described
   the passage that dropped "of each parent". No `condition`, `injected`, `n_errors_planted` or
   citation label changed.
7. **`docx_sha256` added to `manifest.json`,** computed from the `.docx` files, so the documents
   can be verified directly (§4.1).

**Known corpus limitation:** the corpus does **not** include the Alaska Administrative Code
(AAC) — e.g. the CSSD child-support regulations. Documents were generated to cite only
statutes, rules, and cases, so no benchmark citation depends on the AAC. A detector should
treat administrative-regulation citations as out of scope for existence checking against
this corpus.

---

## 4. The answer key — record schema

`answer-key.json` is an array of per-document records. One record looks like this
(a real **corrupt** example):

```json
{
  "doc_id": "sample-corrupt",
  "condition": "corrupt",
  "doc_type": "modify_custody_visitation",
  "citations": [
    {
      "cite": "Civil Rule 913",
      "norm": "Alaska R. Civ. P. 913",
      "type": "rule",
      "exists": false,
      "quote_status": "na",
      "injected": "fabricated_rule",
      "replaced_real": "Civil Rule 90.3"
    },
    {
      "cite": "See Hayes v. Hayes, 614 P.2d 743 (Alaska 1996)",
      "norm": "614 P.2d 743",
      "type": "case",
      "exists": false,
      "quote_status": "na",
      "injected": "wrong_reporter",
      "replaced_real": "See Hayes v. Hayes, 922 P.2d 896 (Alaska 1996)"
    },
    {
      "cite": "AS 25.20.110",
      "norm": "AS 25.20.110",
      "type": "statute",
      "exists": true,
      "quote_status": "na",
      "injected": false
    }
  ],
  "quotes": [
    { "source_cite": "AS 25.24.160(a)", "quote_status": "faithful", "injected": false }
  ],
  "n_errors_planted": 2,
  "hash": "934271639c5f0acd"
}
```

### 4.1 Document-level fields

| Field | Type | Meaning |
|-------|------|---------|
| `doc_id` | string | Unique document id, e.g. `doc-0042`. Matches the filename `documents/doc-0042.docx`. |
| `condition` | `"clean"` \| `"corrupt"` | Whether this document had errors planted. Clean documents have no injected citations and no planted altered quotes. They can have natural rows (§8.6). |
| `doc_type` | string | The family-law document category (see §6). |
| `citations` | array | Every authority cited in the document. Pinpoint and form variants keep separate entries, so one authority can have several (see §4.2 and §4.4). |
| `quotes` | array | Labeled passages, planted and natural (see §4.3). A sample, not an inventory: many passages have no row. Empty on 74 clean documents and 30 corrupt documents (see §8.6). |
| `n_errors_planted` | integer | Total planted errors (fabricated/wrong citations + altered quotes). Present on corrupt docs. Excludes the 5 injected statutes that landed on real sections (§3.3) and all natural misquotes. |
| `hash` | string | SHA-256 (first 16 hex chars) of the pre-render draft text. A stable document fingerprint, also in `manifest.json`. ⚠️ **It cannot be recomputed from the `.docx`:** rendering adds the caption, strips markdown and drops anything before the first heading, and the draft text is not part of the benchmark. To confirm a document is unmodified, use `docx_sha256` in `manifest.json`. |

### 4.2 Citation-entry fields

| Field | Type | Meaning |
|-------|------|---------|
| `cite` | string | The citation as it appears in the document. *(For 7 entries this is the **cleaned** citation and `raw_extracted` holds the original — see below. For range or list endpoints written without a prefix, `cite` adds the `AS`.)* |
| `norm` | string | The authority this entry refers to, with pinpoints and form differences removed. **The scoring unit:** dedupe on this field (see §4.4). |
| `type` | `"statute"` \| `"rule"` \| `"case"` | Kind of authority. |
| `exists` | boolean | **The Stage-2 label.** `true` = a real authority present in the corpus. `false` = **not present in this corpus** — which for every entry except two means fabricated by construction. ⚠️ **The exceptions, documented in §3.2:** `AS 11.56.807` and `AS 11.56.810` in `doc-0136` are `false` because Title 11 is outside the corpus's scope, **not because they are fabricated — they are confirmed real Alaska law.** They are the only such entries, and §9 excludes both from Stage-2 scoring. |
| `quote_status` | `"na"` | Always `"na"` on citation entries. Quote fidelity is tracked only in the `quotes` array (see §4.3). |
| `injected` | `false` \| string | `false` for a genuine (untouched) citation, and for the 5 injected statutes that landed on real sections (§3.3). Otherwise the **corruption type** that produced this citation (see §5). |
| `replaced_real` | string | *(on injected citations and the 5 entries in §3.3)* The real citation that was replaced by this fabricated one. Useful for analysis; not needed for scoring. |
| `raw_extracted` | string | *(7 entries only)* The original extractor output, where it over-captured words preceding the case name — e.g. `"The Gorton v. Mann, 281 P.3d 81 (Alaska 2012)"` or `"Alaska Supreme Court. See Ruppe v. Ruppe, …"`. `cite` holds the cleaned citation; this field preserves the realistic hard case, because your extractor will face the same sentence. |

### 4.3 Quote-entry fields

| Field | Type | Meaning |
|-------|------|---------|
| `source_cite` | string | The authority the passage was drawn from. It names the original authority even where the document now cites a planted fake in its place (for example `doc-0028`, `doc-0049`, `doc-0132`, `doc-0179`). |
| `quote_status` | `"faithful"` \| `"altered"` | **The Stage-3 label.** `"faithful"` = the passage matches the true source. `"altered"` = the wording differs from the source, whether planted or changed by the drafting model. |
| `injected` | `false` \| `"altered_quote"` | `"altered_quote"` for a planted fidelity error. `false` for a faithful quote or a natural misquote. |
| `planted` | boolean | *(only on altered quotes)* `true` for the 40 planted alterations. `false` for the 40 natural misquotes. |
| `altered_text` / `original_text` | string | *(only on altered quotes)* The passage as the document has it, and the source wording. Rows can describe copied text outside quote marks. Natural `altered_text` is a short verbatim stretch around the change. |

**Quote rows are a sample.** The generator recorded quotes only for corrupt documents, and kept one
row per `source_cite` in a document, so a second passage from the same source has no row of its
own. Faithful rows carry no text, so each labels a (document, `source_cite`) pair, not a specific
passage. Natural rows are per passage, so a document can have two for one source (`doc-0073`).

### 4.4 `norm` and the scoring unit

Every citation entry has a `norm`: the authority it refers to, regardless of pinpoint or form.

| Citation type | `norm` form | Example |
|---------------|-------------|---------|
| Statute | `AS T.CC.SSS`, pinpoints stripped | `AS 25.24.160(a)(4)` → `AS 25.24.160` |
| Civil rule | `Alaska R. Civ. P. N`, pinpoints stripped. Bare `Rule N` is civil. | `Rule 90.3(a)` → `Alaska R. Civ. P. 90.3` |
| Evidence rule | `Alaska R. Evid. N`, pinpoints stripped | `Alaska R. Evid. 505(a)` → `Alaska R. Evid. 505` |
| Case | Reporter cite only | `See Hayes v. Hayes, 922 P.2d 896 (Alaska 1996)` → `922 P.2d 896` |

**How to dedupe.** Within each document, group entries by `norm` and score one target per group.
Reduce your extractor's output to the same form and compare per document. Every entry in a group
carries the same `exists` label. The 3,584 entries reduce to 2,493 authority targets, or 2,491
after the §9 exclusions. Do not dedupe across documents: the same authority in two documents is
two targets.

⚠️ **`norm` removes pinpoints and citation form, and nothing else.** Keep rule family and the
decimal: `Civil Rule 90.3` is not `Civil Rule 903`, and `Alaska R. Evid. 903` is a different
authority from either. Match cases on reporter, not name: every `wrong_reporter` entry carries a
real case name.

**Completeness rule.** Every authority cited by section, rule number or reporter in a document's
text appears in that document's key entry. In a range or list, each stated endpoint counts, and
sections inside a range are not expanded. Chapter-level references (`AS 11.41`), `Id.`, name-only
short forms and court form numbers are not counted.

⚠️ **The rule holds at authority level, not pinpoint level.** 123 first-level pinpoints in the text
have no entry of their own, because their authority is already listed under another form. The key
usually records one pinpoint level, and only 3 entries go deeper. Do not treat a pinpoint without
its own entry as an unlabeled citation.

---

## 5. Corruption types (how the errors were planted)

Errors are planted **by construction**: each document was first drafted citing only a known
list of real authorities (retrieved from the corpus), then — for documents assigned the
`corrupt` condition — one to three of those real citations were programmatically replaced
with a fabricated one, and/or one quoted passage was altered. The answer key records exactly
what was changed, so the ground truth is exact.

| `injected` value | Stage tested | What was done |
|------------------|--------------|----------------|
| `fabricated_statute` | Existence (Stage 2) | A real statute (e.g. `AS 25.24.200`) replaced by a non-existent section in the same title/chapter (900-range, e.g. `AS 25.24.946`). Looks plausible; catchable only by corpus lookup. |
| `fabricated_rule` | Existence (Stage 2) | A real court rule (e.g. `Civil Rule 90.3(b)`) replaced by a non-existent rule number (e.g. `Civil Rule 913(b)`). |
| `fabricated_case` | Existence (Stage 2) | A real case citation replaced by an entirely invented case name + reporter (e.g. `Restol v. Manshen, 512 P.3d 88 (Alaska 2011)`). |
| `wrong_reporter` | Existence (Stage 2) | A **real case name** kept, but the reporter volume/page fabricated (e.g. `Hayes v. Hayes, 922 P.2d 896` → `Hayes v. Hayes, 614 P.2d 743`). Tests whether the checker verifies the *full* citation, not just the case name. |
| `altered_quote` | Fidelity (Stage 3) | A verbatim quotation kept attached to its real source, but the quoted text materially changed (e.g. "shall" → "may", "substantial change in circumstances" → "substantial passage of time"). The citation still exists; the *quote* no longer matches the source. |

All fabricated citations are designed to be **plausible** — they resemble real citations in
form — so the detector must actually verify against the corpus rather than flag obviously
malformed strings.

⚠️ **Natural misquotes are outside this menu.** The drafting model made them, not the injector.
They have `injected: false` and `planted: false`, and they do not count toward `n_errors_planted`
(see §8.6).

⚠️ **Five injected statutes landed on real sections.** They are labeled `exists: true`, not
fabricated. See §3.3.

⚠️ **5 fabricated civil rules share a number with a real evidence rule.** They stay fabricated.
See §3.1.

⚠️ **9 fabricated reporters resolve to real but unrelated opinions.** Volumes and pages were
picked at random, and these 9 happen to exist in the reporter. All 9 are absent from this corpus
and stay `exists: false`, so a corpus lookup is unaffected. **A detector using an outside
database must match caption AND reporter together**, because a reporter-only lookup would pass
these as real. Checked against CourtListener on 2026-11-01.

| Document | Fabricated citation | `injected` | The reporter actually belongs to |
|----------|---------------------|------------|----------------------------------|
| `doc-0028` | `Halvers v. Pruitt, 404 P.3d 837 (Alaska 1999)` | `fabricated_case` | Young v. Station 27, Inc. |
| `doc-0047` | `Restol v. Manshen, 351 P.3d 100 (Alaska 2021)` | `fabricated_case` | Keyes v. Keyes |
| `doc-0049` | `Corbeau v. Dietrich, 445 P.3d 830 (Alaska 2009)` | `fabricated_case` | In re United States |
| `doc-0050` | `Rooney v. Rooney, 515 P.2d 554 (Alaska 1996)` | `wrong_reporter` | Curtis Lumber Co. v. Sortor |
| `doc-0091` | `Restol v. Manshen, 391 P.3d 385 (Alaska 2020)` | `fabricated_case` | State v. Walker |
| `doc-0162` | `Bunn v. House, 851 P.2d 498 (Alaska 1997)` | `wrong_reporter` | State v. Pennington |
| `doc-0169` | `Berkbigler v. Berkbigler, 787 P.2d 329 (Alaska 1996)` | `wrong_reporter` | State v. Campbell |
| `doc-0172` | `Restol v. Manshen, 408 P.3d 791 (Alaska 2014)` | `fabricated_case` | Anastos v. State, Department of Family Services |
| `doc-0173` | `Bunn v. House, 526 P.2d 416 (Alaska 1997)` | `wrong_reporter` | Ross v. Industrial Commission |

---

## 6. Document types

Each document is one of five common Alaska family-law filing categories, chosen to exercise
different regions of the corpus:

| `doc_type` | Exercises |
|------------|-----------|
| `married_divorcing_with_children` | Divorce/dissolution (AS 25.24), custody, child support (Rule 90.3), property division |
| `unmarried_custody` | Custody/paternity for unmarried parents (AS 25.20), best-interests factors |
| `modify_custody_visitation` | Modification standard (AS 25.20.110), the "substantial change" case law |
| `domestic_violence` | DV protective orders (AS 18.66), related evidence rules |
| `child_support` | Rule 90.3 and commentary, support enforcement/modification |

`married_divorcing_with_children` has 32 documents, and each of the other four types has 42.

---

## 7. Document format & extraction notes

- Documents are Microsoft Word `.docx`. Read them with a standard library (e.g. `python-docx`).
- **Read paragraph text, not runs.** Citations appear as plain text within paragraph prose.
  `paragraph.text` yields complete citation strings; iterating individual runs is unnecessary
  and can fragment a citation. This keeps extraction robust to any styling.
- Citations appear inline in argument prose (e.g. "...pursuant to AS 25.20.110..."),
  matching how the production system drafts them.
- Quoted source text, where present, appears in quotation marks.
- Party names are fictional. No PII appears anywhere.

---

## 8. Known limitations & characteristics

Documented honestly so the team can interpret detection metrics correctly:

1. **Existence-heavy, fidelity-lighter.** Most planted errors are citation-existence errors
   (fabricated statutes/rules/cases, wrong reporters). Altered-quote (fidelity) errors are
   present but less frequent, because the generator paraphrases case law by policy and quotes
   verbatim mainly from statutes/rules. Expect more Stage-2 test cases than Stage-3 cases;
   report fidelity metrics with that smaller sample size in mind.

2. **Injected errors reflect the corruption menu in §5, not every conceivable hallucination.**
   Because errors are planted, the benchmark's "hard cases" are limited to the types listed.
   A real production system may hallucinate in ways not represented here. This benchmark
   measures detection of *these* well-defined error types; it is not a claim about coverage
   of all possible real-world hallucinations.

3. **AAC not in corpus.** Administrative regulations (Alaska Administrative Code) are out of
   scope; no benchmark citation depends on them (see §3).

4. **One jurisdiction, one practice area.** All documents are Alaska family law. Generalization
   to other states or practice areas is a stretch goal, not something this benchmark measures.

5. **Recall on fabrications is the priority metric.** A missed fabrication (false negative) is
   the most consequential error for the real product — it means a fabricated citation could
   reach a user. Tune and report accordingly: prioritize recall on `exists: false` citations,
   and report precision/recall/F1 separately for existence (Stage 2) and fidelity (Stage 3).

6. **Quote labels are a sample, and the documents contain natural misquotes.** There are 202 quote
   rows: 40 planted alterations, 40 natural misquotes and 122 faithful. Many passages have no row:
   74 clean documents and 30 corrupt documents have empty `quotes` arrays, although clean documents
   contain 208 long quoted spans (double-quoted, 60 characters or more). The generator recorded
   quotes only for corrupt documents, so this does not mean those documents paraphrased.
   **Unlabeled passages must not be scored as negatives** (§9).

   **What was labeled.** Every quoted span and every copied statute or rule passage in the 200
   documents was checked against the corpus. Natural labels (`planted: false`) mark a material
   change inside quote marks, or a modal, negation, quantifier or number change in copied text
   outside quote marks. The AS 25.30.310, AS 25.24.170 and `doc-0004` rows below were labeled after
   individual review because they change the rule stated or its cross-reference.

   | Natural misquote | Rows | Documents |
   |------------------|------|-----------|
   | Civil Rule 65(b): "only if" became "if", "when" or "where" | 10 | 0121, 0123, 0128, 0129, 0136, 0146, 0150, 0152, 0156, 0158 |
   | AS 25.30.300: "only if" became "if" or "when" | 7 | 0047, 0050, 0056, 0060, 0073 (two rows), 0078 |
   | AS 25.30.310(a): "and that substantial evidence is no longer available" dropped | 5 | 0005, 0082, 0088, 0095, 0112 |
   | AS 25.24.170(a): "unmarried 18-year-old children" became "minor children" | 5 | 0170, 0175, 0177, 0191, 0197 |
   | Civil Rule 90.7(a): "only when" became "when" | 3 | 0052, 0063, 0068 |
   | AS 25.24.150(c)(6): "of each parent" dropped, the only natural change inside quote marks | 1 | 0083 |
   | AS 25.24.150(c): cross-reference to AS 25.20.060 - 25.20.130 became AS 25.24.150(c) | 1 | 0004 |
   | Civil Rule 90.3(a)(3): "for any period" became "only for periods" | 1 | 0020 |
   | Civil Rule 90.3(a)(4)(A): "only" added | 1 | 0197 |
   | Civil Rule 90.3(d)(1)(A)(i): "who may be" dropped | 1 | 0037 |
   | Civil Rule 26.1(b): "a party" became "each party"; "all" dropped | 2 | 0039, 0035 |
   | Civil Rule 65(e): "any" dropped | 1 | 0148 |
   | AS 25.24.310: "any" dropped | 1 | 0054 |
   | Civil Rule 90.6: "either party" became "any party" | 1 | 0066 |

   ⚠️ **The AS 25.30.300 rows are wording changes, not legal errors.** The statute lists four
   alternative bases, "only if (1) ... (2) ... (3) ... (4)", so citing one basis without "only" is
   still accurate law. They are labeled because Stage 3 measures fidelity to the wording.

   **Not labeled by rule:** punctuation, case, hyphenation, ellipsis omissions, `[bracketed]` edits,
   dropped list labels such as `(1)`, equivalent wording (is/are, a/an, singular/plural), and
   ordinary paraphrase in unquoted text. `doc-0012`'s "is just as" for "are just as" is therefore
   unlabeled, although the words differ.

   **Reviewed and intentionally unlabeled (45 items):**

   | Group | Items | Documents | Why unlabeled |
   |-------|-------|-----------|---------------|
   | "Shall" and "must" swapped in copied text | 11 | 0005, 0041, 0045, 0061, 0066, 0073, 0085, 0088, 0092, 0099, 0156 | Same force |
   | Other modal swaps ("will" to "shall" or "is", "shall be" to "is") | 6 | 0005, 0057, 0075, 0084, 0123, 0163 | Same force |
   | Modal replaced by a lead-in such as "requires that" | 3 | 0002, 0033, 0130 | The obligation is preserved |
   | AS 25.30.300 with "only" qualified or outside the quotation | 6 | 0004, 0042, 0048, 0053, 0058, 0080 | "If, among other bases" is accurate, and in 0004 and 0058 the quoted words are correct |
   | Change inside a passage attributed to a fabricated citation | 7 | 0016, 0040, 0043, 0061, 0070, 0071, 0122 | The change comes from a planted citation, already labeled in `citations` |
   | Cross-reference changed in a short phrase | 3 | 0052, 0094, 0114 | A short reference, with no rule stated |
   | Copied from rule commentary and credited to the court | 1 | 0187 | Commentary is not rule text |
   | Quantifier changed, meaning unchanged | 8 | 0011, 0039, 0053, 0070, 0130, 0142, 0146, 0159 | No rule changes |

---

## 9. How to score against this benchmark (summary)

1. **Extract** every citation and quoted passage from each `.docx`.
2. **Stage 2 — existence:** for each extracted citation, decide real vs. fabricated. Score
   against the `exists` field. A citation is a true positive for "hallucination" when the
   detector flags a citation whose answer-key `exists` is `false`.
   - **Score one target per authority per document:** dedupe on `norm` (§4.4).
   - ⚠️ **Two exceptions — exclude `AS 11.56.807` and `AS 11.56.810` (both in `doc-0136`) from
     Stage-2 scoring entirely, neither a hit nor a miss.** They are confirmed real Alaska law
     that sits outside this corpus's curated scope, so scoring them as hallucinations penalises
     detectors that correctly recognise them as real. See §3.2 for the confirmation and the
     reasoning. **These are the only citations excluded; the rule above applies unchanged to
     all other 3,582 entries (2,491 authority targets).**
3. **Stage 3 — fidelity:** for each passage, decide faithful vs. altered, and report two separate
   results:
   - **Planted score (primary).** Score against the 40 rows with `planted: true` and the faithful
     rows. Natural misquotes count as neither a hit nor a miss here.
   - **Natural misquotes (separate metric).** Report how many of the 40 rows with `planted: false`
     the detector found. Do not merge this into the planted score.
   - ⚠️ **Quote labels are a sample, so unlabeled passages must not be scored as negatives.** A
     flag on an unlabeled passage is neither a false positive nor a true positive, and a passage
     left unflagged is not a true negative. Report flags on unlabeled passages separately (§8.6).
4. Report precision, recall, and F1 — separately for existence and fidelity — with emphasis
   on **recall of fabricated citations**.
5. The evaluation notebook should reproduce every reported number from the frozen files, and
   the per-document `docx_sha256` in `manifest.json` lets anyone confirm the documents are
   unmodified. The older `hash` field cannot be recomputed from the `.docx` files (§4.1).
