"""Metric helpers shared by the pipeline evaluation.

Positive class is always the error class being detected: a fabricated citation
for existence, an altered quote for fidelity.
"""

from __future__ import annotations

from sklearn.metrics import confusion_matrix, precision_recall_fscore_support


def binary_metrics(y_true: list[int], y_pred: list[int]) -> dict:
    """Precision/recall/F1 for the positive (error) class, plus the confusion matrix."""
    if not y_true:
        return {
            "support": 0,
            "tp": 0,
            "fp": 0,
            "tn": 0,
            "fn": 0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "accuracy": 0.0,
        }

    tp, fn, fp, tn = confusion_matrix(y_true, y_pred, labels=[1, 0]).ravel()
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=[1, 0], average=None, zero_division=0
    )
    total = tp + fn + fp + tn
    return {
        "support": int(total),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
        "precision": float(precision[0]),
        "recall": float(recall[0]),
        "f1": float(f1[0]),
        "accuracy": float((tp + tn) / total),
    }
