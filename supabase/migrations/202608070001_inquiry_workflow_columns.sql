-- Formal inquiry workflow metadata without guessing legacy tenant or status values.
-- This migration must not be applied unless public.set_updated_at() exists.

begin;

do $$
begin
  if to_regclass('public.inquiries') is null then
    raise exception 'public.inquiries must exist before inquiry workflow migration';
  end if;

  if exists (
    select 1
    from public.inquiries
    where company_id is null
  ) then
    raise exception 'inquiries with null company_id require an explicit tenant mapping';
  end if;

  if exists (
    select 1
    from public.inquiries
    where status is null
  ) then
    raise exception 'inquiries with null status require explicit review';
  end if;

  if exists (
    select 1
    from public.inquiries
    where status not in ('未対応', '対応中', '対応済み')
  ) then
    raise exception 'inquiries with unsupported status require explicit review';
  end if;
end;
$$;

alter table public.inquiries
  add column if not exists assignee_name text,
  add column if not exists last_replied_at timestamptz,
  add column if not exists updated_at timestamptz default now();

do $$
begin
  if exists (
    select 1
    from public.inquiries
    where updated_at is null
  ) then
    raise exception 'inquiries with null updated_at require explicit review';
  end if;
end;
$$;

alter table public.inquiries
  alter column company_id set not null,
  alter column status set not null,
  alter column updated_at set not null,
  add constraint inquiries_assignee_name_check
    check (
      assignee_name is null
      or (char_length(assignee_name) between 1 and 80 and btrim(assignee_name) <> '')
    ),
  add constraint inquiries_status_check
    check (status in ('未対応', '対応中', '対応済み')),
  add constraint inquiries_company_id_id_key unique (company_id, id);

create index if not exists idx_inquiries_company_status_created_at
  on public.inquiries (company_id, status, created_at desc);

drop trigger if exists trg_inquiries_set_updated_at on public.inquiries;
create trigger trg_inquiries_set_updated_at
before update on public.inquiries
for each row execute function public.set_updated_at();

commit;
