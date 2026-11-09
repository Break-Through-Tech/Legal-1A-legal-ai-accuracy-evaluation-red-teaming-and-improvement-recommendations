# Statute & Court-Rule Existence — Stage-2 Evaluation

Predictions come from the frozen corpus only; scores are against the answer key's `exists` field (DATA_DICTIONARY §9). Cases are scored separately in `scripts/evaluate.py`.

Out of scope (not scored): 2: `AS 11.56.807` (doc-0136), `AS 11.56.810` (doc-0136).

| metric | value |
|---|---|
| true positives | 2156 |
| false positives | 0 |
| true negatives | 222 |
| false negatives | 0 |
| **precision** | 1.0000 |
| **recall** | 1.0000 |
| **F1** | 1.0000 |

## False positives (corpus says real, answer key says fabricated)

None.

## False negatives (corpus says fabricated, answer key says real)

None.
