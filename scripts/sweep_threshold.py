"""Sweep the fuzzy threshold and unrelated floor over saved quote-fidelity results.

Reads data/quote-fidelity-results.json (written by evaluate_quotes.py) and
reports, for each setting, how many altered quotes are caught and how many
false alarms are raised. A quote is flagged altered when
floor <= score < threshold. Exact/normalized matches are always faithful,
and quotes with no source are never flagged.

Extracted quotes that are not in the answer key are not labeled, but every
planted alteration is in the key, so flags on them count as false alarms.

The results file is generated, not committed. Run evaluate_quotes.py first:

    python scripts/evaluate_quotes.py
    python scripts/sweep_threshold.py
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from citation_extractor.quote_fidelity import FUZZY_THRESHOLD, UNRELATED_BELOW

RESULTS_PATH = ROOT / "data" / "quote-fidelity-results.json"

THRESHOLDS = [80, 85, 90, 92, 94, 95, 96, 97, 98, 99, 100]
FLOORS = [0, 50, 60, 65, 70, 75, 80, 85]


def flagged(item, threshold, floor):
    # Both tiers carry a fuzzy score; the floor decides which counts.
    return item["tier"] in ("fuzzy", "unrelated") and floor <= item["score"] < threshold


def safe_divide(a, b):
    return a / b if b else 0.0


def main():
    if not RESULTS_PATH.exists():
        sys.exit(f"Missing {RESULTS_PATH.relative_to(ROOT)}. Run python scripts/evaluate_quotes.py first.")
    with RESULTS_PATH.open("r", encoding="utf-8") as f:
        results = json.load(f)
    quotes = [q for q in results["quotes"] if q["extracted"]]
    extras = results["extras"]
    n_altered_total = sum(q["true"] for q in results["quotes"])

    def table(label, settings):
        print(f"\n{label}")
        print(f"{'thresh':>6} {'floor':>5} {'TP':>4} {'FN':>4} {'FP':>4} {'extra':>6} "
              f"{'recall':>8} {'e2e rec':>8} {'prec':>7} {'prec+ex':>8}")
        for t, floor in settings:
            tp = sum(q["true"] == 1 and flagged(q, t, floor) for q in quotes)
            fn = sum(q["true"] == 1 and not flagged(q, t, floor) for q in quotes)
            fp = sum(q["true"] == 0 and flagged(q, t, floor) for q in quotes)
            extra = sum(flagged(e, t, floor) for e in extras)
            print(
                f"{t:>6} {floor:>5} {tp:>4} {fn:>4} {fp:>4} {extra:>6} "
                f"{safe_divide(tp, tp + fn):>8.1%} {safe_divide(tp, n_altered_total):>8.1%} "
                f"{safe_divide(tp, tp + fp):>7.1%} {safe_divide(tp, tp + fp + extra):>8.1%}"
            )

    print("Positive class: ALTERED. 'extra' = flags on extracted quotes not in the key (false alarms).")
    print(f"Current settings: threshold={FUZZY_THRESHOLD:g}, floor={UNRELATED_BELOW:g}")
    table("THRESHOLD SWEEP (no floor)", [(t, 0) for t in THRESHOLDS])
    table(f"FLOOR SWEEP (threshold {FUZZY_THRESHOLD:g})", [(FUZZY_THRESHOLD, f) for f in FLOORS])

    print("\nFuzzy scores (exact/normalized excluded)")
    scored = ("fuzzy", "unrelated")
    for label, name in ((1, "altered (key)"), (0, "faithful (key)")):
        scores = sorted(round(q["score"], 1) for q in quotes if q["tier"] in scored and q["true"] == label)
        print(f"  {name:<16} {scores}")
    scores = sorted(round(e["score"], 1) for e in extras if e["tier"] in scored)
    print(f"  {'not in key':<16} {scores}")


if __name__ == "__main__":
    main()
