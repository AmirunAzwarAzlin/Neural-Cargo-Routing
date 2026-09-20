# SDOC — Shipping Document Verification (Hackathon Brief)

**Thesis:** AI interprets messy documents; deterministic software makes the verification decision; humans resolve genuine uncertainty.

**Problem.** A shipping ops inbox mixes document-comparison requests with SI submissions, invoice questions, and spam. For a comparison request, staff manually match a Shipping Instruction (SI) against a draft Bill of Lading (BL) across seven fields, under inconsistent labels and formats, and must catch real discrepancies without raising false alarms.

**Approach.** Classify every email with deterministic rules (sender domain + phrase signals, 100% precision/recall on a 42-email hand-labeled dev set spanning all 5 categories). For `BL_COMPARISON` emails, read the SI/BL attachments with the right tool for the format — a deterministic alias-table parser for `.txt` (192 of 520 attachments need no LLM at all), Gemini structured extraction with evidence validation for PDF/DOCX/XLSX, and Gemini vision with mandatory two-independent-read agreement for scanned pages. Every extracted field carries its exact source quote, which is checked against the source document before being trusted. Normalize, then compare all 7 fields independently in plain Python, then apply a fixed decision precedence: `missing_attachment` → `wrong_doc_type` → `unreadable` → `missing_value` → `MISMATCH`/`OK`. Gemini never sees or sets `has_defect`.

**What's built and verified against the real 520-email dataset (not a subset):**
- Full pipeline run producing a `submission.json` that validates against `sample_submission.json`'s exact shape — 454 `OK`, 48 `MISMATCH`, 18 `NEEDS_REVIEW` (all 4 reasons represented).
- A live human-review-and-recompute loop verified on real data: correcting one field on a genuine mismatch (`email_004`) narrowed `defect_fields` from `[consignee, notify_party]` to `[notify_party]` and re-persisted, with an audit trail entry.
- Supabase-backed dashboard: funnel (520 → 129 comparison requests → 111 auto-resolved → 18 escalated), per-field discrepancy counts, decision-source breakdown (rule vs. Gemini vs. human), runtime.
- 46 passing automated tests covering the file-type detector, the alias parser, every normalizer, the comparator, all 4 review-reason paths, and the submission schema validator.
- Two real safeguards caught mid-build and documented with evidence in the README's failure-analysis table: Gemini merging an address line into a name field (fixed via a prompt constraint), and a scanned-document field correctly discarded when two independent vision reads disagreed (system escalated instead of guessing).

**Not built:** the Cross-Document Transaction Verification extension (SI/BL ↔ commercial invoice ↔ MyInvois e-Invoice). Given a ~24-hour build window, that time went into making the core solid across all four attachment formats rather than adding a second feature. It is scoped in the README as Future Work with the exact design (separate `tv_*` tables, separate export, feature-flagged, never touching the core `defect_fields` enum) but zero of it is implemented.

**Stack.** Python/FastAPI, Pydantic, `google-genai` (Gemini), Supabase (Postgres, RLS on, service key server-side only), Jinja2 + vanilla CSS/JS, pytest.

**Repo:** two documents only (this one and `README.md`), `data/` and `.env` gitignored, pre-commit hook blocking secret-shaped strings.
