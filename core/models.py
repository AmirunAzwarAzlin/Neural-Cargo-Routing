from enum import Enum
from typing import Optional

from pydantic import BaseModel

COMPARED_FIELDS = [
    "shipper",
    "consignee",
    "notify_party",
    "port_of_loading",
    "port_of_discharge",
    "container_count",
    "gross_weight_kg",
]


class Category(str, Enum):
    BL_COMPARISON = "BL_COMPARISON"
    SI_REQUEST = "SI_REQUEST"
    INVOICE_QUERY = "INVOICE_QUERY"
    GENERAL = "GENERAL"
    SPAM = "SPAM"


class Status(str, Enum):
    OK = "OK"
    MISMATCH = "MISMATCH"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ReviewReason(str, Enum):
    MISSING_ATTACHMENT = "missing_attachment"
    WRONG_DOC_TYPE = "wrong_doc_type"
    UNREADABLE = "unreadable"
    MISSING_VALUE = "missing_value"


class DecidedBy(str, Enum):
    RULE = "rule"
    GEMINI = "gemini"
    HUMAN = "human"


class FieldState(str, Enum):
    ABSENT = "absent"
    BLANK = "blank"
    VALUE = "value"


class ExtractedField(BaseModel):
    field: str
    source_label: Optional[str] = None
    raw_value: Optional[str] = None
    normalized_value: Optional[str] = None
    state: FieldState = FieldState.ABSENT
    method: DecidedBy = DecidedBy.RULE
    confidence: float = 1.0
    evidence_quote: Optional[str] = None


class DocumentExtraction(BaseModel):
    role: str  # "SI" or "BL"
    filename: Optional[str] = None
    doc_kind: str = "UNKNOWN"  # SI|BL|PACKING_LIST|COMMERCIAL_INVOICE|CERT_OF_ORIGIN|OTHER|UNKNOWN
    readable: bool = True
    fields: dict[str, ExtractedField] = {}
    raw_text: Optional[str] = None
    sha256: Optional[str] = None


class FieldComparison(BaseModel):
    field: str
    si_value: Optional[str] = None
    bl_value: Optional[str] = None
    si_state: FieldState = FieldState.ABSENT
    bl_state: FieldState = FieldState.ABSENT
    match: bool = True


class ComparisonResult(BaseModel):
    status: Status
    review_reason: Optional[ReviewReason] = None
    has_defect: bool = False
    defect_fields: list[str] = []
    per_field: list[FieldComparison] = []
    decided_by: DecidedBy = DecidedBy.RULE
    rules_version: str = ""
    notes: Optional[str] = None


class EmailResult(BaseModel):
    email_id: str
    category: Category
    category_decided_by: DecidedBy = DecidedBy.RULE
    category_rationale: Optional[str] = None
    comparison: Optional[ComparisonResult] = None
    si_doc: Optional[DocumentExtraction] = None
    bl_doc: Optional[DocumentExtraction] = None

    def to_submission_entry(self) -> dict:
        cmp = self.comparison
        if cmp is None:
            return {
                "category": self.category.value,
                "status": Status.OK.value,
                "review_reason": None,
                "defect_fields": [],
                "has_defect": False,
            }
        return {
            "category": self.category.value,
            "status": cmp.status.value,
            "review_reason": cmp.review_reason.value if cmp.review_reason else None,
            "defect_fields": cmp.defect_fields,
            "has_defect": cmp.has_defect,
        }
