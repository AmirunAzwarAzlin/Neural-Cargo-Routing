"""Read/write access to Supabase for the dashboard. Uses the service key
server-side only; never imported by client-facing static assets."""
from collections import Counter
from typing import Optional

from supabase import Client

from config import RULES_VERSION
from core.decide import decide
from core.models import COMPARED_FIELDS, DocumentExtraction, ExtractedField, FieldState
from storage.supabase_store import DEFAULT_PAGE_SIZE, fetch_all, get_client, insert_review_action

PAGE_SIZE = DEFAULT_PAGE_SIZE


def client() -> Client:
    return get_client()


def dashboard_summary(c: Client) -> dict:
    comparisons = fetch_all(lambda: c.table("comparisons").select("*"), page_size=PAGE_SIZE)
    classifications = fetch_all(
        lambda: c.table("classifications").select("email_id,category,decided_by"), page_size=PAGE_SIZE
    )
    fields = fetch_all(lambda: c.table("extracted_fields").select("field,method"), page_size=PAGE_SIZE)
    runs = c.table("pipeline_runs").select("*").order("started_at", desc=True).limit(1).execute().data

    category_counts = Counter(row["category"] for row in classifications)
    status_counts = Counter(row["status"] for row in comparisons)
    reason_counts = Counter(row["review_reason"] for row in comparisons if row["review_reason"])

    defect_field_counts = Counter()
    for row in comparisons:
        for f in (row.get("defect_fields") or []):
            defect_field_counts[f] += 1

    decision_source_counts = Counter(row["decided_by"] for row in classifications)
    field_method_counts = Counter(row["method"] for row in fields)

    total_emails = sum(category_counts.values())
    comparison_requests = category_counts.get("BL_COMPARISON", 0)
    auto_resolved = status_counts.get("OK", 0) + status_counts.get("MISMATCH", 0)
    needs_review = status_counts.get("NEEDS_REVIEW", 0)

    run = runs[0] if runs else None

    return {
        "total_emails": total_emails,
        "comparison_requests": comparison_requests,
        "auto_resolved": auto_resolved,
        "needs_review": needs_review,
        "category_counts": dict(category_counts),
        "status_counts": dict(status_counts),
        "reason_counts": dict(reason_counts),
        "defect_field_counts": dict(defect_field_counts.most_common()),
        "classification_decision_sources": dict(decision_source_counts),
        "field_extraction_methods": dict(field_method_counts),
        "run": run,
    }


def list_queue(c: Client, status: Optional[str] = None, reason: Optional[str] = None) -> list[dict]:
    def build():
        q = c.table("comparisons").select("*, emails(subject, from_addr)").order("email_id")
        if status:
            q = q.eq("status", status)
        if reason:
            q = q.eq("review_reason", reason)
        return q

    return fetch_all(build, page_size=PAGE_SIZE)


def get_email_detail(c: Client, email_id: str) -> dict:
    email = c.table("emails").select("*").eq("email_id", email_id).single().execute().data
    classification = (
        c.table("classifications").select("*").eq("email_id", email_id)
        .order("created_at", desc=True).limit(1).execute().data
    )
    documents = c.table("documents").select("*").eq("email_id", email_id).execute().data
    doc_fields = {}
    for doc in documents:
        rows = c.table("extracted_fields").select("*").eq("document_id", doc["id"]).execute().data
        doc_fields[doc["id"]] = rows
    comparison = c.table("comparisons").select("*").eq("email_id", email_id).execute().data
    actions = (
        c.table("review_actions").select("*").eq("email_id", email_id)
        .order("created_at", desc=True).execute().data
    )
    return {
        "email": email,
        "classification": classification[0] if classification else None,
        "documents": documents,
        "doc_fields": doc_fields,
        "comparison": comparison[0] if comparison else None,
        "actions": actions,
    }


def fields_for_display(field_rows: list[dict]) -> list[dict]:
    """All COMPARED_FIELDS in canonical order, so a field Gemini discarded
    or never found still gets a row (and a Fix form) instead of vanishing
    from the detail page just because extracted_fields has no row for it."""
    by_field = {r["field"]: r for r in field_rows}
    return [
        by_field.get(field) or {
            "field": field,
            "raw_value": None,
            "normalized_value": None,
            "state": "absent",
            "source_label": None,
            "method": None,
            "evidence_quote": None,
        }
        for field in COMPARED_FIELDS
    ]


def _doc_extraction_from_rows(doc_row: dict, field_rows: list[dict]) -> DocumentExtraction:
    fields = {}
    for r in field_rows:
        fields[r["field"]] = ExtractedField(
            field=r["field"],
            source_label=r["source_label"],
            raw_value=r["raw_value"],
            normalized_value=r["normalized_value"],
            state=FieldState(r["state"]),
            method=r["method"],
            confidence=r["confidence"],
            evidence_quote=r["evidence_quote"],
        )
    return DocumentExtraction(
        role=doc_row["role"],
        filename=doc_row["filename"],
        doc_kind=doc_row["doc_kind"],
        readable=doc_row["readable"],
        fields=fields,
    )


def correct_field(c: Client, document_id: str, field: str, new_value: str) -> None:
    """Human overrides one extracted field's value on one document (SI or BL)."""
    normalized = None
    from core.normalize import normalize_field

    normalized = normalize_field(field, new_value)
    existing = (
        c.table("extracted_fields").select("id").eq("document_id", document_id).eq("field", field)
        .execute().data
    )
    payload = {
        "document_id": document_id,
        "field": field,
        "raw_value": new_value,
        "normalized_value": normalized,
        "state": "value" if new_value else "blank",
        "method": "human",
        "confidence": 1.0,
        "evidence_quote": None,
        "source_label": "human correction",
    }
    if existing:
        c.table("extracted_fields").update(payload).eq("id", existing[0]["id"]).execute()
    else:
        c.table("extracted_fields").insert(payload).execute()


def correct_doc(c: Client, document_id: str, doc_kind: str, readable: bool) -> None:
    """Human overrides one document's doc_kind/readable classification —
    the only way to unblock the 'unreadable'/'wrong_doc_type' NEEDS_REVIEW
    reasons, which decide() short-circuits on before it ever looks at any
    extracted field."""
    c.table("documents").update({
        "doc_kind": doc_kind,
        "readable": readable,
        "doc_kind_method": "human",
    }).eq("id", document_id).execute()


def apply_review_action(
    c: Client,
    email_id: str,
    actor: str,
    action: str,
    field: Optional[str],
    reason: Optional[str],
) -> dict:
    detail = get_email_detail(c, email_id)
    documents = detail["documents"]
    si_row = next((d for d in documents if d["role"] == "SI"), None)
    bl_row = next((d for d in documents if d["role"] == "BL"), None)

    before_comparison = detail["comparison"]

    if action == "correct" and si_row and bl_row:
        # A correction changed extracted data (a field value or a document's
        # doc_kind/readable) — re-decide with it, and record that a human
        # input drove this result.
        si_doc = _doc_extraction_from_rows(si_row, detail["doc_fields"][si_row["id"]])
        bl_doc = _doc_extraction_from_rows(bl_row, detail["doc_fields"][bl_row["id"]])
        new_comparison = decide(si_doc, bl_doc)
        c.table("comparisons").update({
            "status": new_comparison.status.value,
            "review_reason": new_comparison.review_reason.value if new_comparison.review_reason else None,
            "has_defect": new_comparison.has_defect,
            "defect_fields": new_comparison.defect_fields,
            "per_field": [fc.model_dump(mode="json") for fc in new_comparison.per_field],
            "decided_by": "human",
            "rules_version": RULES_VERSION,
            "notes": new_comparison.notes,
            "review_status": "corrected",
            "reviewed_by": actor,
            "reviewed_at": "now()",
            "updated_at": "now()",
        }).eq("email_id", email_id).execute()
        after_comparison = new_comparison.model_dump(mode="json")
    else:
        # confirm / reject: record the human decision without silently
        # recomputing and overwriting the verdict being confirmed/rejected.
        review_status = "confirmed" if action == "confirm" else "rejected" if action == "reject" else "pending"
        c.table("comparisons").update({
            "review_status": review_status,
            "reviewed_by": actor,
            "reviewed_at": "now()",
        }).eq("email_id", email_id).execute()
        after_comparison = before_comparison

    insert_review_action(c, email_id, actor, action, field, before_comparison, after_comparison, reason)
    return after_comparison
