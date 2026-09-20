#!/usr/bin/env python3
"""Evaluates the pipeline against the hand-labeled dev set (tests/dev_labels.json).

Reports (measured, dev-set only — NOT the competition's private reference set):
  - classification macro-F1 across the 5 categories
  - defect-detection F1 (has_defect) on BL_COMPARISON emails with a definite OK/MISMATCH label
  - end-to-end exact defect_fields-set match rate on that same subset
  - review_reason exact-match rate on NEEDS_REVIEW dev emails
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from core.pipeline import process_email
from readers.dispatch import read_document
from storage.local_files import list_emails

CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]


def macro_f1(y_true: list[str], y_pred: list[str], labels: list[str]) -> tuple[float, dict]:
    per_label = {}
    f1_sum = 0.0
    for label in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == label and p == label)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != label and p == label)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        per_label[label] = {"precision": precision, "recall": recall, "f1": f1, "support": y_true.count(label)}
        f1_sum += f1
    return f1_sum / len(labels), per_label


def main():
    data_dir = settings.data_dir
    dev_labels = json.loads(Path("tests/dev_labels.json").read_text(encoding="utf-8"))
    dev_labels.pop("_note", None)

    emails_by_id = {e["email_id"]: e for e in list_emails(data_dir)}

    def extractor(att_path: str, role: str):
        return read_document(data_dir, att_path, role)

    y_true_cat, y_pred_cat = [], []
    defect_true, defect_pred = [], []
    exact_defect_matches = 0
    exact_defect_total = 0
    reason_correct = 0
    reason_total = 0
    mismatches = []

    for eid, truth in dev_labels.items():
        email = emails_by_id.get(eid)
        if email is None:
            print(f"WARNING: {eid} not found in data/inbox, skipping")
            continue
        result = process_email(email, extractor)
        pred = result.to_submission_entry()

        y_true_cat.append(truth["category"])
        y_pred_cat.append(pred["category"])
        if pred["category"] != truth["category"]:
            mismatches.append((eid, "category", truth["category"], pred["category"]))

        if truth["category"] == "BL_COMPARISON" and truth["status"] in ("OK", "MISMATCH"):
            defect_true.append(truth["has_defect"])
            defect_pred.append(pred["has_defect"])
            exact_defect_total += 1
            if set(pred["defect_fields"]) == set(truth["defect_fields"]) and pred["status"] == truth["status"]:
                exact_defect_matches += 1
            else:
                mismatches.append((eid, "defect_fields/status", truth, pred))

        if truth["status"] == "NEEDS_REVIEW":
            reason_total += 1
            if pred["review_reason"] == truth["review_reason"]:
                reason_correct += 1
            else:
                mismatches.append((eid, "review_reason", truth["review_reason"], pred["review_reason"]))

    cat_f1, per_label = macro_f1(y_true_cat, y_pred_cat, CATEGORIES)

    tp = sum(1 for t, p in zip(defect_true, defect_pred) if t and p)
    fp = sum(1 for t, p in zip(defect_true, defect_pred) if not t and p)
    fn = sum(1 for t, p in zip(defect_true, defect_pred) if t and not p)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    defect_f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    print(f"Dev set size: {len(dev_labels)}")
    print(f"\nClassification macro-F1: {cat_f1:.3f}")
    for label, m in per_label.items():
        print(f"  {label:15s} P={m['precision']:.2f} R={m['recall']:.2f} F1={m['f1']:.2f} (n={m['support']})")

    print(f"\nDefect-detection F1 (has_defect, n={len(defect_true)}): {defect_f1:.3f} (P={precision:.2f} R={recall:.2f})")
    print(f"End-to-end exact defect_fields+status match: {exact_defect_matches}/{exact_defect_total} "
          f"({exact_defect_matches / exact_defect_total:.1%})" if exact_defect_total else "N/A")
    print(f"Review-reason exact match: {reason_correct}/{reason_total} "
          f"({reason_correct / reason_total:.1%})" if reason_total else "N/A")

    if mismatches:
        print(f"\n{len(mismatches)} disagreement(s) with dev labels:")
        for m in mismatches:
            print(" -", m)


if __name__ == "__main__":
    main()
