-- Company-scoped applicant statuses used by the admin UI and API.
-- Re-runnable and does not modify existing applicant status values.

begin;

create table if not exists public.applicant_status_settings (
  company_id text not null,
  status_key text not null,
  name text not null,
  sort_order integer not null default 0,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (company_id, status_key),
  unique (company_id, name)
);

alter table public.applicant_status_settings add column if not exists company_id text;
alter table public.applicant_status_settings add column if not exists status_key text;
alter table public.applicant_status_settings add column if not exists name text;
alter table public.applicant_status_settings add column if not exists sort_order integer default 0;
alter table public.applicant_status_settings add column if not exists is_active boolean default true;
alter table public.applicant_status_settings add column if not exists created_at timestamptz default now();
alter table public.applicant_status_settings add column if not exists updated_at timestamptz default now();

create unique index if not exists uq_applicant_status_settings_company_key
  on public.applicant_status_settings (company_id, status_key);
create unique index if not exists uq_applicant_status_settings_company_name
  on public.applicant_status_settings (company_id, name);
create index if not exists idx_applicant_status_settings_company_sort
  on public.applicant_status_settings (company_id, sort_order);

drop trigger if exists set_applicant_status_settings_updated_at on public.applicant_status_settings;
create trigger set_applicant_status_settings_updated_at
before update on public.applicant_status_settings
for each row execute function public.set_updated_at();

insert into public.applicant_status_settings
  (company_id, status_key, name, sort_order, is_active)
values
  ('default', 'new', '新規応募', 1, true),
  ('default', 'in_progress', '応募途中', 2, true),
  ('default', 'completed', '応募完了', 3, true),
  ('default', 'interview_adjusting', '面接調整中', 4, true),
  ('default', 'interview_confirmed', '面接確定', 5, true),
  ('default', 'casual_interview', 'カジュアル面接', 6, true),
  ('default', 'hired', '採用', 7, true),
  ('default', 'rejected', '不採用', 8, true)
on conflict (company_id, status_key) do nothing;

commit;

-- Legacy status migration policy:
-- Existing applicants keep their current text value. Add the same value in the settings UI
-- before editing those applicants, or rename a matching status through the API so applicants
-- are migrated together. A status used by any applicant cannot be deleted.

