"""Supabase persistence layer. All writes use the service key server-side;
this module is never imported by anything served to a browser."""
import hashlib
from typing import Optional

from supabase import Client, create_client

from config import RULES_VERSION, settings
from core.models import DocumentExtraction, EmailResult


def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_key)


def start_pipeline_run(client: Client, total_emails: int) -> str:
    row = client.table("pipeline_runs").insert({
        "rules_version": RULES_VERSION,
        "total_emails": total_emails,
    }).execute()
    return row.data[0]["id"]


def finish_pipeline_run(client: Client, run_id: str, notes: str | None = None) -> None:
    client.table("pipeline_runs").update({
        "finished_at": "now()",
        "notes": notes,
    }).eq("id", run_id).execute()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def persist_email_result(
    client: Client,
    run_id: Optional[str],
    email: dict,
    result: EmailResult,
    attachment_bytes: dict[str, bytes] | None = None,
) -> None:
    attachment_bytes = attachment_bytes or {}

    client.table("emails").upsert({
        "email_id": email["email_id"],
        "pipeline_run_id": run_id,
        "from_addr": email.get("from"),
        "subject": email.get("subject"),
        "body": email.get("body"),
        "attachments": email.get("attachments") or [],
    }).execute()

    client.table("classifications").insert({
        "email_id": result.email_id,
        "category": result.category.value,
        "confidence": 1.0,
        "decided_by": result.category_decided_by.value,
        "rationale": result.category_rationale,
    }).execute()

    for doc in (result.si_doc, result.bl_doc):
        if doc is None:
            continue
        doc_row = _persist_document(client, result.email_id, doc, attachment_bytes)
        _persist_fields(client, doc_row["id"], doc)

    if result.comparison is not None:
        cmp = result.comparison
        client.table("comparisons").upsert({
            "email_id": result.email_id,
            "status": cmp.status.value,
            "review_reason": cmp.review_reason.value if cmp.review_reason else None,
            "has_defect": cmp.has_defect,
            "defect_fields": cmp.defect_fields,
            "per_field": [fc.model_dump(mode="json") for fc in cmp.per_field],
            "decided_by": cmp.decided_by.value,
            "rules_version": cmp.rules_version,
            "notes": cmp.notes,
        }, on_conflict="email_id").execute()


def _persist_document(client: Client, email_id: str, doc: DocumentExtraction, attachment_bytes: dict[str, bytes]) -> dict:
    raw = attachment_bytes.get(doc.filename or "", b"")
    row = client.table("documents").insert({
        "email_id": email_id,
        "role": doc.role,
        "filename": doc.filename,
        "sha256": _sha256(raw) if raw else None,
        "doc_kind": doc.doc_kind,
        "readable": doc.readable,
        "text_dump": doc.raw_text,
    }).execute()
    return row.data[0]


def _persist_fields(client: Client, document_id: str, doc: DocumentExtraction) -> None:
    if not doc.fields:
        return
    rows = [
        {
            "document_id": document_id,
            "field": f.field,
            "source_label": f.source_label,
            "raw_value": f.raw_value,
            "normalized_value": f.normalized_value,
            "state": f.state.value,
            "method": f.method.value,
            "confidence": f.confidence,
            "evidence_quote": f.evidence_quote,
        }
        for f in doc.fields.values()
    ]
    client.table("extracted_fields").insert(rows).execute()


def insert_review_action(
    client: Client,
    email_id: str,
    actor: str,
    action: str,
    field: str | None,
    before: dict | None,
    after: dict | None,
    reason: str | None,
) -> None:
    client.table("review_actions").insert({
        "email_id": email_id,
        "actor": actor,
        "action": action,
        "field": field,
        "before": before,
        "after": after,
        "reason": reason,
    }).execute()
