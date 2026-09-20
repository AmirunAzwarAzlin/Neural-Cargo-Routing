#!/usr/bin/env python3
"""Single entrypoint: process all 520 emails and write submission.json.

Usage: python scripts/run_pipeline.py [--data-dir data] [--out submission.json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings
from core.pipeline import process_email
from readers.dispatch import read_document
from storage.local_files import list_emails


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default=settings.data_dir)
    parser.add_argument("--out", default="submission.json")
    parser.add_argument("--persist", action="store_true", help="write results to Supabase")
    args = parser.parse_args()

    emails = list_emails(args.data_dir)

    supabase_client = None
    run_id = None
    if args.persist:
        from storage.supabase_store import get_client, start_pipeline_run

        supabase_client = get_client()
        run_id = start_pipeline_run(supabase_client, len(emails))
    submission = {}
    category_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    reason_counts: dict[str, int] = {}

    start = time.time()

    def extractor(att_path: str, role: str):
        return read_document(args.data_dir, att_path, role)

    for i, email in enumerate(emails):
        result = process_email(email, extractor)
        submission[result.email_id] = result.to_submission_entry()
        category_counts[result.category.value] = category_counts.get(result.category.value, 0) + 1
        entry = submission[result.email_id]
        status_counts[entry["status"]] = status_counts.get(entry["status"], 0) + 1
        if entry["review_reason"]:
            reason_counts[entry["review_reason"]] = reason_counts.get(entry["review_reason"], 0) + 1

        if supabase_client is not None:
            from storage.local_files import read_attachment_bytes
            from storage.supabase_store import persist_email_result

            att_bytes = {}
            for doc in (result.si_doc, result.bl_doc):
                if doc is not None and doc.filename:
                    try:
                        att_bytes[doc.filename] = read_attachment_bytes(args.data_dir, doc.filename)
                    except FileNotFoundError:
                        pass
            try:
                persist_email_result(supabase_client, run_id, email, result, att_bytes)
            except Exception as e:  # noqa: BLE001 - never let a DB hiccup kill the run
                print(f"WARNING: failed to persist {result.email_id}: {e}")

        if (i + 1) % 100 == 0:
            print(f"...{i + 1}/{len(emails)}")

    elapsed = time.time() - start

    Path(args.out).write_text(json.dumps(submission, indent=2), encoding="utf-8")

    if supabase_client is not None:
        from storage.supabase_store import finish_pipeline_run

        finish_pipeline_run(supabase_client, run_id, notes=f"{elapsed:.1f}s for {len(emails)} emails")

    print(f"Processed {len(emails)} emails in {elapsed:.2f}s ({elapsed / max(len(emails),1)*1000:.1f} ms/email)")
    print("Category counts:", category_counts)
    print("Status counts:", status_counts)
    print("Review reasons:", reason_counts)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
