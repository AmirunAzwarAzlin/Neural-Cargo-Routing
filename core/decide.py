from config import RULES_VERSION
from core.compare import compare_documents
from core.models import ComparisonResult, DecidedBy, DocumentExtraction, FieldState, ReviewReason, Status


def decide(si_doc: DocumentExtraction | None, bl_doc: DocumentExtraction | None) -> ComparisonResult:
    base = {"decided_by": DecidedBy.RULE, "rules_version": RULES_VERSION}

    # 1. missing_attachment
    if si_doc is None or bl_doc is None:
        missing = "SI" if si_doc is None else "BL"
        return ComparisonResult(
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_ATTACHMENT,
            notes=f"{missing} attachment not present.",
            **base,
        )

    # 2. unreadable — must be checked before doc-kind, since a document we
    # could not read at all cannot be positively identified as "the wrong
    # kind" (e.g. non-.txt formats not yet supported, corrupt/0-byte files,
    # garbled scans). doc_kind="UNKNOWN" is our sentinel for "not yet read".
    if not si_doc.readable or not bl_doc.readable or si_doc.doc_kind == "UNKNOWN" or bl_doc.doc_kind == "UNKNOWN":
        unreadable = "SI" if (not si_doc.readable or si_doc.doc_kind == "UNKNOWN") else "BL"
        return ComparisonResult(
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.UNREADABLE,
            notes=f"{unreadable} document could not be read.",
            **base,
        )

    # 3. wrong_doc_type — the document was read successfully but its content
    # (header/banner) shows it is not actually an SI or BL.
    if si_doc.doc_kind != "SI" or bl_doc.doc_kind != "BL":
        wrong = []
        if si_doc.doc_kind != "SI":
            wrong.append(f"SI slot holds a {si_doc.doc_kind} document")
        if bl_doc.doc_kind != "BL":
            wrong.append(f"BL slot holds a {bl_doc.doc_kind} document")
        return ComparisonResult(
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.WRONG_DOC_TYPE,
            notes="; ".join(wrong),
            **base,
        )

    per_field = compare_documents(si_doc, bl_doc)

    # 4. missing_value
    missing_fields = [
        fc.field for fc in per_field
        if fc.si_state != FieldState.VALUE or fc.bl_state != FieldState.VALUE
    ]
    unresolved_fields = [fc.field for fc in per_field if fc.unresolved]
    if missing_fields or unresolved_fields:
        notes = []
        if missing_fields:
            notes.append(f"Blank/absent field(s): {', '.join(missing_fields)}")
        if unresolved_fields:
            notes.append(f"Unparseable value(s): {', '.join(unresolved_fields)}")
        # The submission.json shape keeps has_defect/defect_fields empty for
        # any NEEDS_REVIEW (scripts/validate_submission.py enforces this),
        # but a real mismatch on a field that *does* have values on both
        # sides must not become invisible just because a different field is
        # blank — surface it in notes instead of silently dropping it.
        known_defects = [fc.field for fc in per_field if not fc.match]
        if known_defects:
            notes.append(f"Also differs: {', '.join(known_defects)}")
        return ComparisonResult(
            status=Status.NEEDS_REVIEW,
            review_reason=ReviewReason.MISSING_VALUE,
            per_field=per_field,
            notes="; ".join(notes),
            **base,
        )

    # 5. MISMATCH or OK
    defect_fields = [fc.field for fc in per_field if not fc.match]
    if defect_fields:
        return ComparisonResult(
            status=Status.MISMATCH,
            has_defect=True,
            defect_fields=defect_fields,
            per_field=per_field,
            **base,
        )
    return ComparisonResult(
        status=Status.OK,
        has_defect=False,
        defect_fields=[],
        per_field=per_field,
        **base,
    )
