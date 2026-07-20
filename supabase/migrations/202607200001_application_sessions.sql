-- Persistent LINE application sessions and idempotent application completion.
-- Re-runnable: existing applicants and settings are not modified or deleted.

begin;

create extension if not exists pgcrypto;

create table if not exists public.application_sessions (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  line_user_id text not null,
  status text not null default 'active',
  current_question_key text,
  answers jsonb not null default '[]'::jsonb,
  started_at timestamptz not null default now(),
  last_activity_at timestamptz not null default now(),
  completed_at timestamptz,
  cancelled_at timestamptz,
  reminder_1h_sent_at timestamptz,
  reminder_24h_sent_at timestamptz,
  reminder_3d_sent_at timestamptz,
  last_event_id text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint application_sessions_status_check
    check (status in ('active', 'completed', 'cancelled')),
  constraint application_sessions_answers_array_check
    check (jsonb_typeof(answers) = 'array')
);

-- Complete a partially created table without dropping data.
alter table public.application_sessions add column if not exists id uuid default gen_random_uuid();
alter table public.application_sessions add column if not exists company_id text;
alter table public.application_sessions add column if not exists line_user_id text;
alter table public.application_sessions add column if not exists status text default 'active';
alter table public.application_sessions add column if not exists current_question_key text;
alter table public.application_sessions add column if not exists answers jsonb default '[]'::jsonb;
alter table public.application_sessions add column if not exists started_at timestamptz default now();
alter table public.application_sessions add column if not exists last_activity_at timestamptz default now();
alter table public.application_sessions add column if not exists completed_at timestamptz;
alter table public.application_sessions add column if not exists cancelled_at timestamptz;
alter table public.application_sessions add column if not exists reminder_1h_sent_at timestamptz;
alter table public.application_sessions add column if not exists reminder_24h_sent_at timestamptz;
alter table public.application_sessions add column if not exists reminder_3d_sent_at timestamptz;
alter table public.application_sessions add column if not exists last_event_id text;
alter table public.application_sessions add column if not exists created_at timestamptz default now();
alter table public.application_sessions add column if not exists updated_at timestamptz default now();

update public.application_sessions
set company_id = coalesce(company_id, 'default'),
    status = coalesce(status, 'active'),
    answers = case when jsonb_typeof(answers) = 'array' then answers else '[]'::jsonb end,
    started_at = coalesce(started_at, created_at, now()),
    last_activity_at = coalesce(last_activity_at, started_at, created_at, now()),
    created_at = coalesce(created_at, now()),
    updated_at = coalesce(updated_at, now())
where company_id is null
   or status is null
   or answers is null
   or jsonb_typeof(answers) is distinct from 'array'
   or started_at is null
   or last_activity_at is null
   or created_at is null
   or updated_at is null;

alter table public.application_sessions alter column id set not null;
alter table public.application_sessions alter column company_id set not null;
alter table public.application_sessions alter column line_user_id set not null;
alter table public.application_sessions alter column status set not null;
alter table public.application_sessions alter column answers set not null;
alter table public.application_sessions alter column started_at set not null;
alter table public.application_sessions alter column last_activity_at set not null;
alter table public.application_sessions alter column created_at set not null;
alter table public.application_sessions alter column updated_at set not null;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'application_sessions_pkey') then
    alter table public.application_sessions add constraint application_sessions_pkey primary key (id);
  end if;
  if not exists (select 1 from pg_constraint where conname = 'application_sessions_status_check') then
    alter table public.application_sessions add constraint application_sessions_status_check
      check (status in ('active', 'completed', 'cancelled'));
  end if;
  if not exists (select 1 from pg_constraint where conname = 'application_sessions_answers_array_check') then
    alter table public.application_sessions add constraint application_sessions_answers_array_check
      check (jsonb_typeof(answers) = 'array');
  end if;
end;
$$;

create unique index if not exists uq_application_sessions_active_user
  on public.application_sessions (company_id, line_user_id)
  where status = 'active';
create index if not exists idx_application_sessions_company_status_activity
  on public.application_sessions (company_id, status, last_activity_at);
create index if not exists idx_application_sessions_company_started
  on public.application_sessions (company_id, started_at desc);

-- Link a formal applicant to the session that created it. Existing applicants remain unchanged.
alter table public.applicants add column if not exists application_session_id uuid;
create unique index if not exists uq_applicants_application_session
  on public.applicants (application_session_id)
  where application_session_id is not null;

drop trigger if exists set_application_sessions_updated_at on public.application_sessions;
create trigger set_application_sessions_updated_at
before update on public.application_sessions
for each row execute function public.set_updated_at();

create or replace function public.complete_application_session(
  p_session_id uuid,
  p_company_id text,
  p_line_user_id text,
  p_name text,
  p_phone text,
  p_job text,
  p_motivation text,
  p_applicant_status text,
  p_event_id text default null
)
returns jsonb
language plpgsql
as $$
declare
  v_session public.application_sessions%rowtype;
  v_applicant jsonb;
  v_created boolean := false;
begin
  select * into v_session
  from public.application_sessions
  where id = p_session_id
    and company_id = p_company_id
    and line_user_id = p_line_user_id
  for update;

  if not found then
    raise exception 'application session not found';
  end if;

  if v_session.status = 'completed' then
    return jsonb_build_object('created', false, 'already_completed', true);
  end if;
  if v_session.status <> 'active' then
    raise exception 'application session is not active';
  end if;

  select to_jsonb(a.*) into v_applicant
  from public.applicants a
  where a.application_session_id = p_session_id
  order by a.created_at desc
  limit 1;

  if v_applicant is null then
    insert into public.applicants
      (company_id, application_session_id, line_user_id, name, phone, job, motivation, status)
    values
      (p_company_id, p_session_id, p_line_user_id, p_name, p_phone, p_job, p_motivation, p_applicant_status)
    returning to_jsonb(applicants.*) into v_applicant;
    v_created := true;
  end if;

  update public.application_sessions
  set status = 'completed',
      current_question_key = null,
      answers = '[]'::jsonb,
      completed_at = coalesce(completed_at, now()),
      last_activity_at = now(),
      last_event_id = coalesce(p_event_id, last_event_id)
  where id = p_session_id;

  return jsonb_build_object(
    'created', v_created,
    'already_completed', false,
    'applicant', v_applicant
  );
end;
$$;

commit;
