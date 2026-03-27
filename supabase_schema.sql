-- =============================================================================
-- Koby AI — unified Supabase schema (run once in SQL Editor)
-- =============================================================================
--
-- WHY TWO "KINDS" OF TABLES?
--
-- 1) CORE RAG / VECTOR (this file, first sections)
--    - documents, document_chunks, embedding index, match_document_chunks()
--    - Used by Django for: PDF upload → storage → chunking → vector search
--    - Requires pgvector; embedding size must match your model (384 = all-MiniLM-L6-v2)
--
-- 2) FEEDBACK
--    - feedback — admin/manager contributions (already used by core/supabase_utils.py)
--
-- 3) OPTIONAL GENERIC CHAT LOG (chat_logs)
--    - Simple question/answer/sources log if you write to it from clients
--    - Different from user_search_logs (see below)
--
-- 4) DJANGO ANALYTICS (what we added for Render + session users)
--    - app_users — mirror of Django users (email, name, role; NO passwords)
--    - user_auth_events — register / login / logout
--    - user_search_logs — what the Python app logs: query + user_email + search_type
--    These are filled by the Django server with SUPABASE_SERVICE_ROLE_KEY.
--
-- chat_logs vs user_search_logs:
--   - chat_logs: generic shape (question, answer, sources JSON) — optional.
--   - user_search_logs: analytics with django_user_id, user_email, user_name, search_type,
--     success/error — this is what core/views.py writes today.
--
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensions (Supabase: enable in Dashboard → Database → Extensions if needed)
-- -----------------------------------------------------------------------------
create extension if not exists vector;
create extension if not exists pgcrypto;

-- -----------------------------------------------------------------------------
-- Core: PDFs + vector chunks (RAG)
-- -----------------------------------------------------------------------------
create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  filename text not null,
  storage_path text not null unique,
  uploader text,
  user_id text,
  status text not null default 'uploaded',
  chunk_count integer default 0,
  indexed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.document_chunks (
  id bigint generated always as identity primary key,
  document_id uuid not null references public.documents(id) on delete cascade,
  page_number integer,
  chunk_index integer not null,
  text text not null,
  embedding vector(384) not null,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.feedback (
  id uuid primary key default gen_random_uuid(),
  question text not null,
  answer text not null,
  question_type text default 'general',
  user_id text,
  user_email text,
  rating numeric default 0,
  improvement_type text default 'enhancement',
  status text default 'pending',
  created_at timestamptz not null default now()
);

-- Optional generic chat log (not used by default Django code; user_search_logs is)
create table if not exists public.chat_logs (
  id uuid primary key default gen_random_uuid(),
  user_id text,
  question text not null,
  answer text,
  sources jsonb default '[]'::jsonb,
  created_at timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- Django user mirror + auth + search analytics (from Django / service role)
-- -----------------------------------------------------------------------------
create table if not exists public.app_users (
  id uuid primary key default gen_random_uuid(),
  django_user_id text not null unique,
  email text not null unique,
  name text default '',
  role text default 'user',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  last_login_at timestamptz
);

create table if not exists public.user_auth_events (
  id uuid primary key default gen_random_uuid(),
  django_user_id text not null,
  user_email text,
  event_type text not null check (event_type in ('register', 'login', 'logout')),
  created_at timestamptz not null default now()
);

create index if not exists user_auth_events_email_idx on public.user_auth_events (user_email);
create index if not exists user_auth_events_created_idx on public.user_auth_events (created_at desc);

create table if not exists public.user_search_logs (
  id uuid primary key default gen_random_uuid(),
  django_user_id text,
  user_email text,
  user_name text,
  query_text text not null,
  response_preview text,
  search_type text not null default 'text',
  success boolean not null default true,
  error_message text,
  metadata jsonb default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists user_search_logs_email_idx on public.user_search_logs (user_email);
create index if not exists user_search_logs_django_idx on public.user_search_logs (django_user_id);
create index if not exists user_search_logs_created_idx on public.user_search_logs (created_at desc);

comment on table public.app_users is 'Mirror of Django core_user for analytics; updated on login/register.';
comment on table public.user_auth_events is 'Auth lifecycle events from Django.';
comment on table public.user_search_logs is 'Search/chat queries logged by Django (identified by email / django_user_id).';

-- -----------------------------------------------------------------------------
-- Vector index (tune lists after you have representative data)
-- -----------------------------------------------------------------------------
create index if not exists document_chunks_embedding_ivfflat
  on public.document_chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- -----------------------------------------------------------------------------
-- Similarity RPC (used by core/supabase_utils.match_document_chunks)
-- -----------------------------------------------------------------------------
create or replace function public.match_document_chunks(
  query_embedding vector(384),
  match_count int default 5
)
returns table (
  id bigint,
  document_id uuid,
  page_number int,
  chunk_index int,
  text text,
  metadata jsonb,
  similarity float
)
language sql
stable
as $$
  select
    dc.id,
    dc.document_id,
    dc.page_number,
    dc.chunk_index,
    dc.text,
    dc.metadata,
    1 - (dc.embedding <=> query_embedding) as similarity
  from public.document_chunks dc
  order by dc.embedding <=> query_embedding
  limit match_count;
$$;

-- -----------------------------------------------------------------------------
-- Row Level Security (anon users: restrictive; Django service role bypasses RLS)
-- -----------------------------------------------------------------------------
alter table public.documents enable row level security;
alter table public.document_chunks enable row level security;
alter table public.feedback enable row level security;
alter table public.chat_logs enable row level security;
alter table public.app_users enable row level security;
alter table public.user_auth_events enable row level security;
alter table public.user_search_logs enable row level security;

drop policy if exists "documents owner read" on public.documents;
create policy "documents owner read"
on public.documents for select
using (auth.uid()::text = user_id or user_id is null);

drop policy if exists "documents owner write" on public.documents;
create policy "documents owner write"
on public.documents for insert
with check (auth.uid()::text = user_id or user_id is null);

drop policy if exists "chunks readable by owner" on public.document_chunks;
create policy "chunks readable by owner"
on public.document_chunks for select
using (
  exists (
    select 1 from public.documents d
    where d.id = document_id
      and (d.user_id = auth.uid()::text or d.user_id is null)
  )
);

-- feedback + chat_logs: RLS on with no policies = deny direct anon access; Django service role bypasses RLS.
-- Add policies here only if you query these tables from the browser with Supabase Auth.
