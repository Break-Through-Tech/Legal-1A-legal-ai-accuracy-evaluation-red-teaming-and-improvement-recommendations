# Milestone #3 Task Planning — November (draft)

Draft for the Canvas assignment *Milestone #3 Task Planning* and for creating the
November issues on the project board. Nothing here is committed or pushed yet.

**Team (after Maisha's withdrawal):** Abigail Briones, Thao (May) Bui, Carolyn Lee,
Fataiya Salifu, Sharan Subramanian.

**Milestone:** End-to-End Detection & Failure Analysis.
**Deliverable (project brief):** end-to-end hallucination detector + evaluation
notebook + categorized failure taxonomy.
**Fixed dates:** no labs November 23–28 · mock presentations in lab the week of
Nov 30 · final presentations the week of Dec 6.

**State of play (2026-11-02, corrected answer key):** existence is saturated
(273/273 planted fabrications, P 0.9964 / R 1.0000 over 2,491 authority targets),
planted fidelity recall is 0.900, and natural-misquote recall is 0.025 (1/40).
The open risks are (a) the November plan is not on the board, (b) the work is not
on GitHub, (c) natural misquotes need a failure analysis, not a silent patch.

---

## 1. End-to-end evaluation on the corrected key (§9-compliant)

**Owner:** Abigail · **Status:** implemented locally, needs publication.

Acceptance criteria:
- [ ] `main` (PR #20) merged into the working branch; no force-push.
- [ ] Existence deduped on `norm` per document → **2,491 targets**; `AS 11.56.807`
      and `AS 11.56.810` excluded (§9.2).
- [ ] Fidelity reported as **planted (primary)** and **natural (separate)**; never
      pooled (§9.3).
- [ ] Unlabeled passages reported separately, not as true/false negatives.
- [ ] `scripts/evaluate_pipeline.py` regenerates `reports/pipeline-evaluation.md`.
- [ ] PR opened; reviewers: coach + one teammate.

Evidence: `reports/pipeline-evaluation.md` (local).

## 2. Reproducible evaluation notebook

**Owner:** Abigail · **Status:** not started (`notebooks/` is empty).

Acceptance criteria:
- [ ] `notebooks/evaluate-pipeline.ipynb` imports `scripts/evaluate_pipeline.py`
      (one source of truth, no re-implementation).
- [ ] Runs from the frozen files and **reproduces every number** in the report
      (DATA_DICTIONARY §9.5).
- [ ] Calls the metric functions directly and asserts the report matches.
- [ ] Verifies `docx_sha256` from `manifest.json` for all 200 documents.

## 3. Failure taxonomy — natural misquotes

**Owner:** Abigail · **Status:** partially in report; Ben asked for this
explicitly ("of the 40 natural misquotes, 20 weren't caught by either team…
worth a place in your failure analysis").

Acceptance criteria:
- [ ] Categorize all 39 misses: **21 never extracted**, **17 extracted and scored
      faithful** (modal/quantifier/omission edits), **1 unverified**.
- [ ] Explain the mechanism in plain language: `unquoted_passages.py` compares only
      runs of ≥8 words that already match the source verbatim, so an inserted
      `only` or a dropped clause sits between runs and is never compared.
- [ ] Map categories to DATA_DICTIONARY §8.6 (e.g. "only if"→"if", dropped
      "only", dropped clause).
- [ ] Keep planted and natural populations separate in the write-up.

## 4. Regression set pinned to the answer key

**Owner:** Abigail · **Status:** not started.

Acceptance criteria:
- [ ] Fixture stores `(answer-key sha256, expected metrics per task)`.
- [ ] `make check` fails on drift **within the same key**, and requires an explicit
      baseline update when the key hash changes (Ben: "your scores will shift…
      that's expected, not a regression").
- [ ] Covers existence (per type), planted fidelity, natural fidelity, document risk.

## 5. Reconcile PR #18 and PR #19

**Owner:** May (author) · **Reviewer:** Abigail · **Status:** both open.

Acceptance criteria:
- [ ] Confirm both PRs mark Title 11 statutes `OUT_OF_SCOPE` (covers `AS 11.56.810`)
      and fix `doc-0042` (`&`/`and` case names).
- [ ] Flag the overlap between #18 and #19 and agree merge order with May and Ben —
      do not close either without their agreement.
- [ ] Confirm neither PR adds a Word lock file (`~$*.docx`); Ben flagged this for
      `citation-extractor-b`.

## 6. Package the detector + graded README

**Owner:** Abigail, reviewed by team · **Status:** README rewritten locally.

Acceptance criteria:
- [ ] `pip install -e .` exposes the `cite-check` CLI and `analyze_document` API.
- [ ] README documents install, quick start, library use, results, and limitations.
- [ ] README numbers match the regenerated report exactly.
- [ ] Submit the Canvas *AI Studio Project GitHub README* assignment after the PR lands.

## 7. Ranked improvement recommendations

**Owner:** Abigail · **Status:** drafted; needs updating to the new key.

Acceptance criteria:
- [ ] Each recommendation is specific, ranked by severity to user outcomes, and tied
      to evidence from the evaluation (brief, Part C).
- [ ] Resolved items are marked resolved (the five 900-range collisions) and kept as
      the audit record.
- [ ] New #1 is the natural-misquote gap; no recommendation asks for a change the
      evidence does not support.

## 8. Mock presentation (week of Nov 30)

**Owner:** team · **Status:** not started.

Acceptance criteria:
- [ ] 5-minute story: problem, method, existence result, fidelity split, top failure,
      recommendation.
- [ ] Dry-run with the coach before the mock presentation.
- [ ] Slides and speaker notes shared in the team channel.

## 9. Monthly Project Contributions — November (Canvas)

**Owner:** each member · **Status:** ongoing.

Acceptance criteria:
- [ ] Each member logs their November issues/PRs with links and a one-line outcome.
- [ ] Submitted before the deadline for the Canvas assignment.

---

### Suggested board columns

`Backlog` → `In progress` → `In review` → `Done`, with the nine items above created
as issues and assigned. Create the **November Milestone** on the board first; it does
not exist yet (only September and October do).
