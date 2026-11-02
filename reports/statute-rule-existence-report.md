# Statute & Court-Rule Existence — Stage-2 Evaluation

Predictions come from the frozen corpus only; scores are against the answer key's `exists` field (DATA_DICTIONARY §9). Cases are scored separately in `scripts/evaluate.py`.

Out of scope (not scored): 1: `AS 11.56.807` (doc-0136).

| metric | value |
|---|---|
| true positives | 2090 |
| false positives | 5 |
| true negatives | 222 |
| false negatives | 0 |
| **precision** | 0.9976 |
| **recall** | 1.0000 |
| **F1** | 0.9988 |

## False positives (corpus says real, answer key says fabricated)

| doc | cite | injected |
|---|---|---|
| doc-0059 | AS 25.24.900 | fabricated_statute |
| doc-0110 | AS 25.24.910 | fabricated_statute |
| doc-0152 | AS 25.24.910 | fabricated_statute |
| doc-0182 | AS 25.24.920 | fabricated_statute |
| doc-0198 | AS 25.24.900 | fabricated_statute |

All false positives are `fabricated_statute` injections in the 900-range that collide with real corpus sections (AS 25.24.900/910/920). By the benchmark's own definition (`exists` = present in this corpus, §1/§3.2) these citations do exist, so a correct corpus lookup is penalised here. See the team's finding for the recommended correction.

## False negatives (corpus says fabricated, answer key says real)

None.
