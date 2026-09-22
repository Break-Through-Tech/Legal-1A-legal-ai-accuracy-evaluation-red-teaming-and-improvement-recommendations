# ProSe AI — Hallucinated-Citation Benchmark: Data Dictionary

**Deliverable:** Detecting Hallucinated Legal Citations in AI-Generated Court Documents
**Prepared by:** ProSe AI, for the Break Through Tech AI Studio 2026 Challenge
**Status:** Frozen benchmark — do not regenerate; integrity is verified by the per-document hashes in `manifest.json`.

---

## 1. What this benchmark is

A fixed, labeled set of AI-generated Alaska family-law legal documents, built with fictional
party names. Roughly half are **clean** (no errors were planted: no injected citations and no
altered quotes) and roughly half are **corrupt** (containing deliberately planted errors —
fabricated citations and altered quotes).

> ⚠️ **"Clean" means "nothing was planted", not "nothing can be flagged."** An earlier version
> of this paragraph said clean documents have "every citation real and every quote faithful",
> which contradicted §4.1 and was not quite true: the drafting model occasionally cited an
> authority that was real but had not been retrieved for that document, and those citations
> appear in clean documents. They are now labeled `exists: true` (see the corrections note in
> §3.1), so a detector that flags nothing in a clean document is still correct — but the
> guarantee is about **planting**, not about the model's citation behaviour. Every document ships with an **answer key** marking each citation as
real or fabricated and each quote as faithful or altered.

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
| `benchmark/answer-key.json` | One record per document: every citation labeled real/fabricated, every quote labeled faithful/altered. The scoring target. |
| `benchmark/manifest.json` | Document inventory + per-document SHA-256 hashes (the freeze fingerprint) + clean/corrupt counts. |
| `data/corpus/*.jsonl` | The citation corpus: real Alaska statutes, court rules, and case citations with source text. The lookup target for existence and fidelity checks. |

---

## 3. The citation corpus (the lookup target)

The detector verifies each cited authority against this corpus. It contains four authority
types, each as structured JSON records (one JSON object per line, `.jsonl`):

| Corpus file | Authority type | Approx. size |
|-------------|----------------|--------------|
| `statutes.jsonl` | Alaska Statutes (Title 25 family law; Title 18 ch. 65–66 DV/protective orders) | ~500 records |
| `rules.jsonl` | Alaska Rules of Civil Procedure (incl. Rule 90.3 child support) | ~155 records |
| `rules-evidence.jsonl` | Alaska Rules of Evidence + commentary | ~302 records |
| `cases.jsonl` | Published Alaska Supreme Court family-law opinions | ~1,255 cases |

**Field layout differs slightly by file — read the citation and source text from these fields:**

| File | Citation string | Source text | Notes |
|------|-----------------|-------------|-------|
| `statutes.jsonl` | `citation` (e.g. `"AS 25.24.150"`) | `source_text` | Also: `title`, `jurisdiction`, `cross_refs`. |
| `rules.jsonl` | `citation` (e.g. `"Alaska R. Civ. P. 90.3"`) | `source_text` | Civil rules; `subrule` may be set. |
| `cases.jsonl` | `citation`; also `case_name` + `reporter_cite` separately | `source_text` | `holding`, `pinpoint`, `year`, `court` also present. |
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
| **documents** | `Civil Rule NN` | `Civil Rule 90.3(a)` | 632 |
| **documents** | bare `Rule NN` | `Rule 90.3` | 83 |
| **documents** | `Alaska R. Evid. NN` | `Alaska R. Evid. 505` | 57 |
| **corpus** (`rules.jsonl`) | `Alaska R. Civ. P. NN` | `Alaska R. Civ. P. 90.3` | all 185 records |
| **corpus** (`rules-evidence.jsonl`) | ⛔ **no `citation` field at all** | build from `ruleNumber` + `subrule` | all records |

⛔ **A naive exact-match of the document's citation string against the corpus `citation` field
matches 52 of 772 rule citations (6.7%) and would wrongly report 632 REAL rule citations as
fabricated.**

⚠️ **Normalizing only the `Civil Rule` prefix is not enough.** Two different quantities in this
benchmark both happen to equal 632: the number of `Civil Rule` citations, and the number of
real rule citations a naive match would miss. They are **not the same set** — fixing only the
`Civil Rule` prefix still misses the 83 bare `Rule NN` citations, while the headline number
appears to come out right.

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

⚠️ Statutes and cases do **not** have this problem. Statute citations match `citation` in
`statutes.jsonl` directly. Case citations should be matched on **reporter cite**
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

#### ⚠️ ONE CITATION IS REAL LAW BUT SITS OUTSIDE THE CORPUS — `AS 11.56.807`

`doc-0136` (a **clean** document) cites **`AS 11.56.807` — "Terroristic threatening in the
first degree", Alaska Statutes Title 11, Chapter 56.** Confirmed against authoritative sources
(Alaska Statutes, akleg.gov, Justia) on 2026-09-21.

> ⛔ **IT IS REAL LAW. IT IS NOT A FABRICATION, AND NOTHING IN THIS BENCHMARK SHOULD BE READ AS
> CALLING IT ONE.** The drafting model cited a genuine Alaska criminal statute in a family-law
> document — a reasonable thing to do when a protective-order matter touches threatening
> conduct.

**Its label is `exists: false`, and that is deliberate.** Throughout this benchmark `exists`
means *"present in THIS corpus"* — and this corpus is scoped to Title 25 and Title 18 ch. 65–66
(family law and domestic violence). Title 11 is not in it at all. Flipping the label to `true`
would break that meaning and would make the answer key disagree with the corpus it is scored
against.

⚠️⚠️ **CONSEQUENCE FOR SCORING, AND IT IS THE ONE THING TO GET RIGHT.** §9 says a citation is a
true positive for "hallucination" when its `exists` is `false`. Applied literally to this one
citation, **a detector that correctly recognises `AS 11.56.807` as real Alaska law is scored as
having MISSED a hallucination** — a false negative against the recall metric §9 asks you to
emphasise.

> **Recommended handling: EXCLUDE this single citation from Stage-2 scoring** rather than count
> it either way. It is the only one of its kind in the benchmark — 1 of 3,490 citations — so
> excluding it changes no reported figure materially, and counting it penalises exactly the
> detectors that are working correctly.

**There are now no unresolved citations in this benchmark.** Every citation is either confirmed
present in the corpus, confirmed planted, or — in this single case — confirmed real law that the
corpus deliberately does not cover.

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
      "type": "rule",
      "exists": false,
      "quote_status": "na",
      "injected": "fabricated_rule",
      "replaced_real": "Civil Rule 90.3"
    },
    {
      "cite": "See Hayes v. Hayes, 614 P.2d 743 (Alaska 1996)",
      "type": "case",
      "exists": false,
      "quote_status": "na",
      "injected": "wrong_reporter",
      "replaced_real": "See Hayes v. Hayes, 922 P.2d 896 (Alaska 1996)"
    },
    {
      "cite": "AS 25.20.110",
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
| `condition` | `"clean"` \| `"corrupt"` | Whether this document had errors planted. Clean documents have no injected citations and no altered quotes. |
| `doc_type` | string | The family-law document category (see §6). |
| `citations` | array | One entry per citation appearing in the document (see §4.2). |
| `quotes` | array | One entry per verbatim quoted passage the document drew from a source (see §4.3). May be empty if the document paraphrased throughout. |
| `n_errors_planted` | integer | Total planted errors (fabricated/wrong citations + altered quotes). Present on corrupt docs. |
| `hash` | string | SHA-256 (first 16 hex chars) of the final document text. Freeze/integrity fingerprint. |

### 4.2 Citation-entry fields

| Field | Type | Meaning |
|-------|------|---------|
| `cite` | string | The citation as it appears in the document. *(For 7 entries this is the **cleaned** citation and `raw_extracted` holds the original — see below.)* |
| `type` | `"statute"` \| `"rule"` \| `"case"` | Kind of authority. |
| `exists` | boolean | **The Stage-2 label.** `true` = a real authority present in the corpus. `false` = **not present in this corpus** — which for every entry except one means fabricated by construction. ⚠️ **The exception, documented in §3.2:** `AS 11.56.807` in `doc-0136` is `false` because Title 11 is outside the corpus's scope, **not because it is fabricated — it is confirmed real Alaska law.** It is the only such entry; consider excluding it from Stage-2 scoring. |
| `quote_status` | `"na"` \| `"faithful"` \| `"altered"` | Fidelity status of a quote attached to this citation. `"na"` when the citation carries no quoted text. (Quote fidelity is primarily tracked in the `quotes` array; see §4.3.) |
| `injected` | `false` \| string | `false` for a genuine (untouched) citation. Otherwise the **corruption type** that produced this citation (see §5). |
| `replaced_real` | string | *(only on injected citations)* The real citation that was replaced by this fabricated one. Useful for analysis; not needed for scoring. |
| `raw_extracted` | string | *(7 entries only)* The original extractor output, where it over-captured words preceding the case name — e.g. `"The Gorton v. Mann, 281 P.3d 81 (Alaska 2012)"` or `"Alaska Supreme Court. See Ruppe v. Ruppe, …"`. `cite` holds the cleaned citation; this field preserves the realistic hard case, because your extractor will face the same sentence. |

### 4.3 Quote-entry fields

| Field | Type | Meaning |
|-------|------|---------|
| `source_cite` | string | The authority the quoted passage was drawn from. |
| `quote_status` | `"faithful"` \| `"altered"` | **The Stage-3 label.** `"faithful"` = the quoted text matches the true source. `"altered"` = the quoted text was deliberately changed and no longer matches. |
| `injected` | `false` \| `"altered_quote"` | `false` for a faithful quote; `"altered_quote"` for a planted fidelity error. |
| `altered_text` / `original_text` | string | *(only on altered quotes)* The changed text and the original, for analysis. |

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

Documents are distributed roughly evenly across the five types.

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

---

## 9. How to score against this benchmark (summary)

1. **Extract** every citation and quoted passage from each `.docx`.
2. **Stage 2 — existence:** for each extracted citation, decide real vs. fabricated. Score
   against the `exists` field. A citation is a true positive for "hallucination" when the
   detector flags a citation whose answer-key `exists` is `false`.
   - ⚠️ **One exception — exclude `AS 11.56.807` (in `doc-0136`) from Stage-2 scoring
     entirely, neither a hit nor a miss.** It is confirmed real Alaska law that sits outside
     this corpus's curated scope, so scoring it as a hallucination penalises detectors that
     correctly recognise it as real. See §3.2 for the confirmation and the reasoning. **This
     is the only citation excluded; the rule above applies unchanged to all other 3,489.**
3. **Stage 3 — fidelity:** for each quoted passage, decide faithful vs. altered. Score against
   `quote_status`.
4. Report precision, recall, and F1 — separately for existence and fidelity — with emphasis
   on **recall of fabricated citations**.
5. The evaluation notebook should reproduce every reported number from the frozen files, and
   the per-document `hash` in `manifest.json` lets anyone confirm the documents are unmodified.
