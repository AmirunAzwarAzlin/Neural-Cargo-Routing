-- SDOC schema. RLS is enabled on every table with no anon/authenticated
-- policies: only the server-side Supabase service key (which bypasses RLS)
-- can read or write. Never ship the service key to a browser.

create extension if not exists pgcrypto;

create table if not exists pipeline_runs (
    id uuid primary key default gen_random_uuid(),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    rules_version text not null,
    total_emails integer,
    notes text
);
alter table pipeline_runs enable row level security;

create table if not exists emails (
    email_id text primary key,
    pipeline_run_id uuid references pipeline_runs(id) on delete set null,
    from_addr text,
    subject text,
    body text,
    attachments jsonb not null default '[]'::jsonb,
    created_at timestamptz not null default now()
);
alter table emails enable row level security;

create table if not exists classifications (
    id uuid primary key default gen_random_uuid(),
    email_id text not null references emails(email_id) on delete cascade,
    category text not null check (category in ('BL_COMPARISON','SI_REQUEST','INVOICE_QUERY','GENERAL','SPAM')),
    confidence real not null default 1.0,
    decided_by text not null check (decided_by in ('rule','gemini','human')),
    rationale text,
    created_at timestamptz not null default now()
);
alter table classifications enable row level security;
create unique index if not exists classifications_email_id_idx on classifications(email_id);

create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    email_id text not null references emails(email_id) on delete cascade,
    role text not null check (role in ('SI','BL')),
    filename text,
    sha256 text,
    detected_type text,
    doc_kind text not null default 'UNKNOWN',
    readable boolean not null default true,
    -- how doc_kind/readable were determined; lets a human override an
    -- unreadable/wrong_doc_type classification (see BUG-06 review workflow)
    doc_kind_method text not null default 'rule' check (doc_kind_method in ('rule','gemini','human')),
    text_dump text,
    created_at timestamptz not null default now()
);
alter table documents enable row level security;
create index if not exists documents_email_id_idx on documents(email_id);
create unique index if not exists documents_email_id_role_idx on documents(email_id, role);

create table if not exists extracted_fields (
    id uuid primary key default gen_random_uuid(),
    document_id uuid not null references documents(id) on delete cascade,
    field text not null check (field in (
        'shipper','consignee','notify_party','port_of_loading',
        'port_of_discharge','container_count','gross_weight_kg'
    )),
    source_label text,
    raw_value text,
    normalized_value text,
    state text not null check (state in ('absent','blank','value')),
    method text not null check (method in ('rule','gemini','human')),
    confidence real not null default 1.0,
    evidence_quote text,
    created_at timestamptz not null default now()
);
alter table extracted_fields enable row level security;
create index if not exists extracted_fields_document_id_idx on extracted_fields(document_id);
create unique index if not exists extracted_fields_document_id_field_idx on extracted_fields(document_id, field);

create table if not exists comparisons (
    id uuid primary key default gen_random_uuid(),
    email_id text not null references emails(email_id) on delete cascade,
    status text not null check (status in ('OK','MISMATCH','NEEDS_REVIEW')),
    review_reason text check (review_reason in ('wrong_doc_type','missing_attachment','unreadable','missing_value')),
    has_defect boolean not null default false,
    defect_fields jsonb not null default '[]'::jsonb,
    per_field jsonb not null default '[]'::jsonb,
    decided_by text not null check (decided_by in ('rule','gemini','human')),
    rules_version text not null,
    notes text,
    -- human review outcome, independent of status: confirm/reject must
    -- persist without silently overwriting the verdict being reviewed
    -- (see BUG-06)
    review_status text not null default 'pending' check (review_status in ('pending','confirmed','rejected','corrected')),
    reviewed_by text,
    reviewed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
alter table comparisons enable row level security;
create unique index if not exists comparisons_email_id_idx on comparisons(email_id);

-- Append-only audit trail: no update/delete policy is ever granted.
create table if not exists review_actions (
    id uuid primary key default gen_random_uuid(),
    email_id text not null references emails(email_id) on delete cascade,
    actor text not null,
    action text not null check (action in ('confirm','correct','reject')),
    field text,
    before jsonb,
    after jsonb,
    reason text,
    created_at timestamptz not null default now()
);
alter table review_actions enable row level security;
create index if not exists review_actions_email_id_idx on review_actions(email_id);

create table if not exists gemini_cache (
    cache_key text primary key,
    kind text not null,
    model text not null,
    prompt_version text not null,
    response jsonb not null,
    created_at timestamptz not null default now()
);
alter table gemini_cache enable row level security;

-- Migration-safe for databases where these tables already existed before
-- the BUG-06/BUG-07 fixes (the CREATE TABLE blocks above only apply to a
-- fresh database).
alter table documents add column if not exists doc_kind_method text not null default 'rule';
alter table comparisons add column if not exists review_status text not null default 'pending';
alter table comparisons add column if not exists reviewed_by text;
alter table comparisons add column if not exists reviewed_at timestamptz;
