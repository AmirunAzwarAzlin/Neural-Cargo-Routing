"""Orchestrates classify -> identify SI/BL -> extract -> decide for one email.

Document reading is injected via `extract_document` so this module stays
testable without file I/O and swappable once non-.txt readers land.
"""
import re
from typing import Callable, Optional

from config import RULES_VERSION
from core.classify import classify_email
from core.decide import decide
from core.models import (
    Category,
    ComparisonResult,
    DecidedBy,
    DocumentExtraction,
    EmailResult,
    ReviewReason,
    Status,
)

ExtractFn = Callable[[str, str], Optional[DocumentExtraction]]


def _find_attachment(attachments: list[str], role: str) -> Optional[str]:
    pattern = re.compile(rf"_{role}\.", re.IGNORECASE)
    for a in attachments:
        if pattern.search(a):
            return a
    return None


def process_email(email: dict, extract_document: ExtractFn) -> EmailResult:
    category, rationale = classify_email(email)
    result = EmailResult(
        email_id=email["email_id"],
        category=category,
        category_decided_by=DecidedBy.RULE,
        category_rationale=rationale,
    )

    if category != Category.BL_COMPARISON:
        return result

    attachments = email.get("attachments") or []
    si_path = _find_attachment(attachments, "SI")
    bl_path = _find_attachment(attachments, "BL")

    si_doc = extract_document(si_path, "SI") if si_path else None
    bl_doc = extract_document(bl_path, "BL") if bl_path else None

    result.si_doc = si_doc
    result.bl_doc = bl_doc
    result.comparison = decide(si_doc, bl_doc)
    return result


def process_email_safe(email: dict, extract_document: ExtractFn) -> EmailResult:
    """Like process_email, but never raises. A Gemini failure, a missing
    attachment file, or any other unexpected error for one email must not
    take down the whole pipeline run and lose every prior result.
    """
    try:
        return process_email(email, extract_document)
    except Exception as exc:  # noqa: BLE001 - last-resort guard for one bad email
        email_id = email.get("email_id", "UNKNOWN")
        try:
            category, rationale = classify_email(email)
        except Exception:  # noqa: BLE001 - classification itself must not crash the fallback
            category, rationale = Category.GENERAL, "classification failed; pipeline error fallback"

        result = EmailResult(
            email_id=email_id,
            category=category,
            category_decided_by=DecidedBy.RULE,
            category_rationale=rationale,
        )
        if category == Category.BL_COMPARISON:
            reason = ReviewReason.MISSING_ATTACHMENT if isinstance(exc, FileNotFoundError) else ReviewReason.UNREADABLE
            result.comparison = ComparisonResult(
                status=Status.NEEDS_REVIEW,
                review_reason=reason,
                decided_by=DecidedBy.RULE,
                rules_version=RULES_VERSION,
                notes=f"Pipeline error: {exc}",
            )
        return result
