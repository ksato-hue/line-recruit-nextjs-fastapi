-- MVP security foundation and company-scoped settings.
-- This migration is designed to be re-runnable and does not delete existing data.

begin;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create table if not exists public.faq_settings (
  company_id text not null,
  faq_key text not null,
  answer text not null default '',
  is_visible boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (company_id, faq_key)
);

create table if not exists public.app_settings (
  company_id text not null,
  key text not null,
  value jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (company_id, key)
);

create table if not exists public.question_tree_settings (
  company_id text primary key,
  tree jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Complete partially created setting tables without dropping existing columns or rows.
alter table public.faq_settings add column if not exists company_id text;
alter table public.faq_settings add column if not exists faq_key text;
alter table public.faq_settings add column if not exists answer text default '';
alter table public.faq_settings add column if not exists is_visible boolean default false;
alter table public.faq_settings add column if not exists created_at timestamptz default now();
alter table public.faq_settings add column if not exists updated_at timestamptz default now();

alter table public.app_settings add column if not exists company_id text;
alter table public.app_settings add column if not exists key text;
alter table public.app_settings add column if not exists value jsonb;
alter table public.app_settings add column if not exists created_at timestamptz default now();
alter table public.app_settings add column if not exists updated_at timestamptz default now();

alter table public.question_tree_settings add column if not exists company_id text;
alter table public.question_tree_settings add column if not exists tree jsonb default '{}'::jsonb;
alter table public.question_tree_settings add column if not exists created_at timestamptz default now();
alter table public.question_tree_settings add column if not exists updated_at timestamptz default now();

create unique index if not exists uq_faq_settings_company_key
  on public.faq_settings (company_id, faq_key);
create unique index if not exists uq_app_settings_company_key
  on public.app_settings (company_id, key);
create unique index if not exists uq_question_tree_settings_company
  on public.question_tree_settings (company_id);

-- Existing installations may already have one or more of these application tables.
-- Add company_id without dropping or rewriting any business columns.
alter table if exists public.applicants add column if not exists company_id text;
alter table if exists public.inquiries add column if not exists company_id text;
alter table if exists public.interview_slots add column if not exists company_id text;
alter table if exists public.line_message_logs add column if not exists company_id text;
alter table if exists public.faq_categories add column if not exists company_id text;
alter table if exists public.faqs add column if not exists company_id text;

-- Preserve existing rows by assigning them to the current single-tenant identifier.
-- Optional legacy tables are handled conditionally so a missing table does not abort the migration.
-- If production uses a COMPANY_ID other than "default", change these rows deliberately
-- after reviewing the tenant mapping and before enabling multi-tenant access.
do $$
declare
  table_name text;
begin
  foreach table_name in array array[
    'applicants', 'inquiries', 'interview_slots', 'line_message_logs',
    'faq_categories', 'faqs'
  ]
  loop
    if to_regclass('public.' || table_name) is not null then
      execute format('update public.%I set company_id = %L where company_id is null', table_name, 'default');
      execute format('alter table public.%I alter column company_id set default %L', table_name, 'default');
    end if;
  end loop;
end;
$$;

do $$
begin
  if to_regclass('public.applicants') is not null then
    create index if not exists idx_applicants_company_created_at
      on public.applicants (company_id, created_at desc);
  end if;
  if to_regclass('public.inquiries') is not null then
    create index if not exists idx_inquiries_company_created_at
      on public.inquiries (company_id, created_at desc);
  end if;
  if to_regclass('public.interview_slots') is not null then
    create index if not exists idx_interview_slots_company_applicant
      on public.interview_slots (company_id, applicant_id);
    create index if not exists idx_interview_slots_company_line_datetime
      on public.interview_slots (company_id, line_user_id, slot_datetime);
  end if;
  if to_regclass('public.line_message_logs') is not null then
    create index if not exists idx_line_message_logs_company_created_at
      on public.line_message_logs (company_id, created_at desc);
  end if;
  if to_regclass('public.faq_categories') is not null then
    create index if not exists idx_faq_categories_company_sort
      on public.faq_categories (company_id, sort_order);
  end if;
  if to_regclass('public.faqs') is not null then
    create index if not exists idx_faqs_company_category_sort
      on public.faqs (company_id, category_id, sort_order);
  end if;
end;
$$;
create index if not exists idx_faq_settings_company_visible
  on public.faq_settings (company_id, is_visible);

drop trigger if exists set_faq_settings_updated_at on public.faq_settings;
create trigger set_faq_settings_updated_at
before update on public.faq_settings
for each row execute function public.set_updated_at();

drop trigger if exists set_app_settings_updated_at on public.app_settings;
create trigger set_app_settings_updated_at
before update on public.app_settings
for each row execute function public.set_updated_at();

drop trigger if exists set_question_tree_settings_updated_at on public.question_tree_settings;
create trigger set_question_tree_settings_updated_at
before update on public.question_tree_settings
for each row execute function public.set_updated_at();

commit;
