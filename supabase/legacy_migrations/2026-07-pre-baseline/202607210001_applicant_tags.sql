-- Applicant tags used by the admin applicant detail and update API.
-- Re-runnable: existing applicant rows are preserved and receive an empty tag array only when unset.

begin;

alter table public.applicants
  add column if not exists tags jsonb default '[]'::jsonb;

update public.applicants
set tags = '[]'::jsonb
where tags is null;

alter table public.applicants
  alter column tags set default '[]'::jsonb,
  alter column tags set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'applicants_tags_array_check'
      and conrelid = 'public.applicants'::regclass
  ) then
    alter table public.applicants
      add constraint applicants_tags_array_check
      check (jsonb_typeof(tags) = 'array');
  end if;
end;
$$;

commit;
