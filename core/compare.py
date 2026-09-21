from core.models import COMPARED_FIELDS, DocumentExtraction, FieldComparison, FieldState
from core.normalize import normalize_field


def compare_documents(si: DocumentExtraction, bl: DocumentExtraction) -> list[FieldComparison]:
    results = []
    for field in COMPARED_FIELDS:
        si_f = si.fields.get(field)
        bl_f = bl.fields.get(field)
        si_state = si_f.state if si_f else FieldState.ABSENT
        bl_state = bl_f.state if bl_f else FieldState.ABSENT

        si_norm = normalize_field(field, si_f.raw_value) if si_f and si_f.raw_value else None
        bl_norm = normalize_field(field, bl_f.raw_value) if bl_f and bl_f.raw_value else None
        if si_f:
            si_f.normalized_value = si_norm
        if bl_f:
            bl_f.normalized_value = bl_norm

        both_have_values = si_state == FieldState.VALUE and bl_state == FieldState.VALUE
        unresolved = both_have_values and (si_norm is None or bl_norm is None)
        match = (si_norm == bl_norm) if both_have_values and not unresolved else not unresolved

        results.append(
            FieldComparison(
                field=field,
                si_value=si_f.raw_value if si_f else None,
                bl_value=bl_f.raw_value if bl_f else None,
                si_state=si_state,
                bl_state=bl_state,
                match=match,
                unresolved=unresolved,
            )
        )
    return results
