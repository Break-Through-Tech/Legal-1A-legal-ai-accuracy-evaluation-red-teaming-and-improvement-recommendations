---

> ## Challenge Advisor: Update & Finalize Your Project Overview
>
> > 💡 **These grey text instructions are just for you, the team's Challenge Advisor; please delete them once you have completed the steps below.**
>
> We've pre-populated this Challenge Project Overview page — which is what will be shared with your Break Through Tech student team in August — using the details from your submission form. You should have received an email inviting you to join this repo as a Collaborator, enabling you to add files and make edits.
> 
> In order for your project to be finalized and assigned to a team, please:
> 1. **Review all sections below** and update or expand any content as needed, making sure to address the SME Feedback in the section immediately below. Look for square brackets to find the places below that require additional inputs from you (e.g., "About [Company / Org Name]").
> 2. **Add your dataset** to the [data folder](data) in this repo.
> 3. **Close the Issue assigned to you in this repo** to let us know that you have made your edits and the overview page is ready for final review. You can do this by going to the _Issues_ tab in the top left section of the menu above, add a comment that says "CA review complete", and click the button to Close the Issue. 
>
> If you're unfamiliar with how to edit a page like this in GitHub, check out [this tutorial](https://ubc-lib-geo.github.io/gis-workshop-waml-template/content/handson/edit-readme.html) for a quick overview (start with step 2 and only edit this page), and [this guide](https://ubc-lib-geo.github.io/gis-workshop-waml-template/content/markdown.html) on how to use Markdown to compose text.
>
>
> ❌ Remember that this is a public repo. Do NOT include: Proprietary data, PII, API keys, credentials, or anything confidential.

---
## 📋 BTT Internal Evaluation Notes
*(This section is for BTT staff and CAs only — remove before sharing with students)*

### Technical Vetting
| Check | Status | Notes |
| :--- | :--- | :--- |
| Python Compatibility | 🟢 | Project utilizes standard NLP libraries and Python-based evaluation metrics; compatible with Google Colab. |
| Data Readiness | 🟢 | Corpus is pre-processed and indexed in a vector database; gold-standard pairs are in structured CSV/JSON formats. |
| Resource Check | 🟡 | Relies on external API keys for LLM inference, creating a dependency risk if quotas are exhausted or models change. |

### Internal Scores
- **Student Fit Score:** 7/10
- **Technical Depth Score:** 8/10
- **Overall Recommendation:** REVISE

### Advisor Feedback Draft
This project offers a high-impact opportunity to engage with critical legal AI safety. By narrowing the target area to a single, well-defined failure mode and employing a highly structured attack framework instead of open-ended hacking, the Fellows can maintain focus and engagement. Additionally, replacing generic LLM calls with a fixed, smaller-scale model or simulated environment will ensure deterministic benchmarking and provide small wins that foster a sense of productivity.

---

# Legal AI Accuracy Evaluation, Red-Teaming & Improvement Recommendations

**Company / Org:** ProseAI  
**Challenge Advisor:** Benjamin Booker, benjaminbooker@gmail.com  
**AI Studio Coach:** Nagalakshmi Pulivarthi,nagalakshmi.pulivarthi@breakthroughtech.org  
**Program:** Break Through Tech AI Studio - Fall 2026  

---

## 🏢 About ProseAI
ProseAI is a legal technology organization dedicated to increasing access to justice for self-represented litigants in family court. Their primary mission involves developing reliable, AI-driven legal tools that provide accurate information while mitigating the risks of hallucinations and improper citations that can cause significant harm in legal proceedings.

---

## 🎯 The Challenge
### Project Summary
In this project, you will use a frozen benchmark of AI-generated legal documents and a fixed corpus of Alaska family-law statutes, court rules, and case citations and natural language processing techniques — citation parsing, existence checking, and quote-fidelity comparison using string and semantic similarity — to build a system that detects hallucinated legal citations: references to laws or cases that do not exist, or that misquote the source. This will help our company address the risk that AI-generated legal documents contain hallucinated or inaccurate citations, which can cause real harm to self-represented litigants in family court.

### Success Criteria

How Success Is Measured

The guiding principle: this project succeeds by producing a rigorous, honest measurement of the system, not by the system achieving a good score. A detector that reveals a high hallucination rate is a successful project, because surfacing the truth is precisely its purpose. The fellows are graded on the quality of their measurement and analysis, never on how well ProSe AI's generated documents happen to perform.

Success is measured across three components and one overarching criterion.

**Part A — Citation Extraction & Existence Checking.** Success is a working pipeline that reliably parses a document, extracts every statute and case citation, and correctly separates real citations from fabricated ones against the frozen answer key. The measure is correctness and reproducibility — high extraction recall (few citations missed) and accurate existence classification — not any particular number, but a trustworthy result the tool produces on demand, including on benchmark documents it processed for the first time.

**Part B — Quote-Fidelity & Detection Metrics.** Success is measured by how well the full detector distinguishes clean documents from corrupted ones. The team computes precision, recall, and F1 on the planted errors across the frozen benchmark, prioritizing recall on fabricated citations, since a missed fabrication is the most consequential error. The quote-fidelity checker should correctly flag altered or misquoted legal text using string and semantic similarity. The deeper measure of quality is honest error analysis — a clear account of *which* kinds of hallucinations the detector catches and which it misses, assembled into a categorized failure taxonomy.

**Part C — Improvement Recommendations.** Success is measured by actionability. Each recommendation should be specific, ranked by its severity to user outcomes, and tied directly to evidence from Parts A and B. The bar: a reader can tell from each recommendation exactly what to change and why it matters. "Fidelity checker misses paraphrased holdings — recall drops to 0.55 on altered quotes versus 0.9 on fabricated citations; add paraphrase-aware matching" passes; "improve the checker" does not.

**Overarching criterion: reusability.** The ultimate measure of success is whether ProSe AI can re-run the complete detector against an updated version of the document-generation system after the project ends and obtain a trustworthy before-and-after comparison without the fellows present. The strategic purpose of this project is a permanent quality gate and standing regression suite — not a one-time report. If that re-run is possible in January, the project has delivered its lasting value regardless of how any individual metric came out.

### Project Milestones
Use these milestones to guide your work. Your team will create a GitHub Projects board to track tasks within each milestone.

| Month | Milestone | Key Activities |
|---|---|---|
| September | Foundation & Citation Extraction | • Explore the frozen benchmark and citation corpus: document structure, citation patterns, statute vs. case-law references.<br>• Build the citation extractor: parse a document and pull out every statute reference and case citation as structured data.<br>• Measure extraction recall against the answer key and analyze what gets missed.<br>• **Deliverable:** Citation extractor module + extraction-accuracy report against the answer key. |
| October | Existence & Quote-Fidelity Verification | • Build the existence checker: verify whether each extracted citation actually appears in the corpus, flagging fabrications.<br>• Build the quote-fidelity checker: compare quoted holding/statute text to the true source using string and semantic similarity.<br>• Combine both into a per-document hallucination-risk score and tune the flagging thresholds.<br>• **Deliverable:** Existence + fidelity verification modules with tuned thresholds. |
| November | End-to-End Detection & Failure Analysis | • Run the full detector across the frozen benchmark of clean and deliberately-corrupted documents.<br>• Compute detection metrics — precision, recall, F1 — against the planted errors, prioritizing recall on fabricated citations.<br>• Analyze failure cases (missed fabrications, false alarms) and categorize them into a failure taxonomy; assemble a regression set.<br>• **Deliverable:** End-to-end hallucination detector + evaluation notebook + categorized failure taxonomy. |
| December | Packaging, Final Report & Presentation | • Synthesize results into prioritized findings and recommendations.<br>• Package the detector as a clean, documented Python module with a simple API and a reproducible evaluation notebook.<br>• Present findings and recommendations to ProSe AI stakeholders.<br>• **Deliverable:** Final report (PDF) + open-source detection library (GitHub) + prioritized recommendations + presentation slides. |

> **Note for the team:** Please create a GitHub Projects board in this repository to break these milestones into weekly tasks. Go to the **Projects** tab → **New project** → Choose **Board** → Add columns for each month.

---

## 📊 Dataset

**Name and Source:** 
The project uses a frozen, labeled benchmark assembled by ProSe AI from public Alaska family-law sources. It has three parts: (1) a **citation corpus** — the real text of Alaska statutes and rules of civil procedure covering domestic relations (custody, child support, protective orders), plus real Alaska family-law case citations drawn from CourtListener (the Free Law Project's public database); (2) a **labeled document benchmark** of 200 AI-generated legal documents built with fictional party names, where roughly half are clean and half contain deliberately planted errors (fabricated citations and altered quotes); and (3) an **answer key** marking every citation in every document as real or fabricated, and every quote as faithful or altered. The statutes, rules, and opinions are public record with no personally identifiable information, and all sample documents use fictional parties.

**How it will be shared:**
ProSe AI will deliver the benchmark pre-processed and frozen before the program begins, as structured files (JSON (answer key, manifest) + JSONL (corpus) + DOCX (the documents themselves)) plus a data dictionary defining every field, the label schema, how the corrupted documents were generated, and known limitations. Because the benchmark is fixed, the team works against a stable, reproducible target from day one — every evaluation run is deterministic. The pre-trained embedding and cross-encoder models the team uses are free and public on Hugging Face; no paid services or vector index are required. If the team chooses to regenerate sample documents (optional — the benchmark ships pre-generated), ProSe AI will provide the necessary API keys at no cost.

---

## 🛠️ Suggested Approach

**ML Problem Type:** * Natural Language Processing (NLP), Transfer Learning / Pre-trained Models (Deep Learning / Neural Networks if the re-ranker stretch goal is attempted)


**Recommended Libraries:**
- pandas — load and manipulate the benchmark documents and citation corpus
- sentence-transformers — embed quoted passages and source text for semantic fidelity checks 
- rapidfuzz — fast string comparison for citation existence lookups and quote matching
- scikit-learn — precision/recall/F1 and threshold tuning against the answer key

**Evaluation Metrics:**
- Precision / Recall / F1 on hallucination detection against the answer key — recall on fabricated citations prioritized, since a missed fabrication is the most consequential error
- Citation extraction recall — the share of true citations the parser pulls from each document
- Quote-fidelity accuracy — how often the semantic similarity check correctly separates faithful quotes from altered ones

---

## 📚 Resources to Get Started

The following resources will help your team understand the problem space and potential technical approaches for this project:

**Background Reading:**
- [Hallucination-Free? Assessing the Reliability of Leading AI Legal Research Tools (Stanford, Journal of Empirical Legal Studies, 2025)](https://dho.stanford.edu/wp-content/uploads/Legal_RAG_Hallucinations.pdf) — the foundational study measuring hallucination rates of 17–33% even in RAG-based legal AI tools; defines exactly the failure mode this project targets
- [What the Science Says About Hallucinations in Legal Research (AI Law Librarians, 2026)](https://www.ailawlibrarians.com/2026/02/19/what-the-science-says-about-hallucinations-in-legal-research/) — accessible plain-language survey of the research, including why statute/rule interpretation is especially error-prone


**Technical Tutorials:**
- [Sentence Transformers — Semantic Textual Similarity](https://sbert.net/docs/quickstart.html) — the core technique for the quote-fidelity check: scoring how closely a quoted passage matches its true source
- [Sentence Transformers — Cross-Encoders (Rerankers)](https://sbert.net/examples/cross_encoder/applications/README.html) — documentation for the optional re-ranker stretch goal
- [scikit-learn — Precision, Recall & F1 metrics](https://scikit-learn.org/stable/modules/model_evaluation.html#precision-recall-f-measure-metrics) — computing the detection metrics against the answer key
- [RapidFuzz documentation](https://rapidfuzz.github.io/RapidFuzz/) — fast string matching for citation existence and quote comparison

**Code Examples:**
- [Sentence Transformers computing similarity — quickstart code](https://sbert.net/docs/sentence_transformer/usage/usage.html) — minimal working examples of embedding text pairs and scoring similarity

**Other:**
- [Mata v. Avianca — the case that started it](https://www.courtlistener.com/docket/63107798/mata-v-avianca-inc/) — the real 2023 sanction over ChatGPT-fabricated citations; useful motivating context for why this project matters
- [Stanford HAI summary of the legal hallucination findings](https://hai.stanford.edu/news/ai-trial-legal-models-hallucinate-1-out-6-queries) — short, shareable overview for team members newer to the domain

---

## 🤝 How We'll Work Together

**Official check-ins:** During our biweekly 45-minute AI Studio Lab Section meeting block (2nd and 4th week of every month)

 **Other ways to reach out to me with questions:** 
- Your team's channel within Break Through Tech's Discord space — best for quick, day-to-day questions
- Email (please copy your teammates and your AI Studio Coach so everyone stays in the loop)
- Request a team check-in on Zoom — best for anything that needs a live walkthrough or discussion
- *Note: I will aim to respond within 48 hours. Please reach out to your AI Studio Coach with urgent or time-sensitive questions.*

> 💡 **Challenge Advisor: Please update the above based on your availability and preference. If you are not able to answer questions or meet with fellows outside of the biweekly Lab Section check-ins, simply write in "N/A (only available during the official check-in times)"**

**Recommended free coding / collaboration tools**
- Google Colab (free tier) — primary development environment; runs all the Python work including the optional re-ranker on a free T4 GPU, no local setup required
- GitHub — version control and collaboration; where the team's code, notebooks, and final open-source library live
- Hugging Face — free hosting for the pre-trained embedding/cross-encoder models the project uses (and optionally the frozen benchmark dataset)
- Google Drive — shared storage for the benchmark files and corpus, mounts directly into Colab
- Discord — day-to-day team communication (your Break Through Tech channel)

That's the full working toolchain and every piece is genuinely free and Colab-compatible,

---

## 🚀 Getting Started

1. **Review this overview document** and note any questions for our first meeting
2. **Begin reviewing the dataset** using the link above
3. **Read the GitHub Projects documentation** [here](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects)

I’m excited to work with you!

---

## ❓ Questions?

Please bring any questions to our first meeting during the week of August 24th (Break Through Tech’s Bridge to Studio - Session C). 
