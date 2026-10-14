"""Source-text lookup: citation -> the true text of that statute or rule.

The quote-fidelity checker compares a quoted passage against this text.

Corpus quirks handled here (see DATA_DICTIONARY §3 and §3.1):
  - statutes.jsonl: one record per section. Repealed sections have
    source_text set to the STRING "None" -> treat as no text.
  - rules.jsonl: one record per SUBRULE, all sharing the rule-level citation
    ("Alaska R. Civ. P. 90.3" appears once each for (a), (b), (c), ...).
    Join them, in file order, into one text per rule.
  - rules-evidence.jsonl: no citation field -> build "Alaska R. Evid. {ruleNumber}";
    text lives in "text"; skip records with type "rule_commentary".
  - All files: PDF line breaks fall mid-sentence ("A child\\nsupport award").
    Collapse runs of whitespace to a single space so passages can match.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .extractor import normalize_citation

DEFAULT_CORPUS_DIR = Path(__file__).resolve().parents[2] / "data" / "corpus"


def clean_whitespace(text: str) -> str:
    """Collapse every run of whitespace (spaces, newlines, tabs) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_corpus(corpus_dir: str | Path = DEFAULT_CORPUS_DIR) -> dict[str, str]:
    """Build {normalized citation: source text} for statutes and rules.

    Keys use the same canonical form as normalize_citation, e.g.
        "AS 25.24.150", "Alaska R. Civ. P. 90.3", "Alaska R. Evid. 505"
    so that get_source_text can look up any document citation directly.
    Citations with no usable text are left out.
    """
    corpus_dir = Path(corpus_dir)
    texts: dict[str, list[str]] = {}  # citation -> list of text pieces (subrules)

    def add(cite: str, text: str | None) -> None:
        # Repealed sections store the string "None" rather than null.
        if not text or text == "None":
            return
        texts.setdefault(normalize_citation(cite), []).append(text)

    # Statutes: one record per section.
    for r in _read_jsonl(corpus_dir / "statutes.jsonl"):
        add(r["citation"], r.get("source_text"))

    # Civil rules: one record per subrule, in file order.
    for r in _read_jsonl(corpus_dir / "rules.jsonl"):
        add(r["citation"], r.get("source_text"))

    # Evidence rules: no citation field; skip commentary records.
    for r in _read_jsonl(corpus_dir / "rules-evidence.jsonl"):
        if r.get("type") == "rule_commentary":
            continue
        add(f"Alaska R. Evid. {r['ruleNumber']}", r.get("text"))

    return {cite: clean_whitespace(" ".join(pieces)) for cite, pieces in texts.items()}


def get_source_text(cite: str, corpus: dict[str, str]) -> str | None:
    """Return the source text for a document citation, or None if not in corpus.

    Accepts any form the documents use: "AS 25.24.160(a)(4)",
    "Civil Rule 90.3(a)", "Rule 90.3", "Alaska R. Evid. 505(b)", ...
    """
    return corpus.get(normalize_citation(cite))
