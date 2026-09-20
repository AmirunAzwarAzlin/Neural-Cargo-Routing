from typing import Literal

from pydantic import BaseModel

from core.models import COMPARED_FIELDS

DOC_KINDS = ["SI", "BL", "PACKING_LIST", "COMMERCIAL_INVOICE", "CERT_OF_ORIGIN", "OTHER", "UNKNOWN"]
DocKind = Literal["SI", "BL", "PACKING_LIST", "COMMERCIAL_INVOICE", "CERT_OF_ORIGIN", "OTHER", "UNKNOWN"]


class GeminiFieldValue(BaseModel):
    value: str | None = None
    evidence: str | None = None
    source_label: str | None = None


class GeminiExtraction(BaseModel):
    doc_kind: DocKind
    readable: bool
    shipper: GeminiFieldValue
    consignee: GeminiFieldValue
    notify_party: GeminiFieldValue
    port_of_loading: GeminiFieldValue
    port_of_discharge: GeminiFieldValue
    container_count: GeminiFieldValue
    gross_weight_kg: GeminiFieldValue

    def field_map(self) -> dict[str, GeminiFieldValue]:
        return {f: getattr(self, f) for f in COMPARED_FIELDS}
