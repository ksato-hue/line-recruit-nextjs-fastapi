-- Tenant-scoped inquiry reply history. This migration is additive and contains no business-data writes.

begin;

create extension if not exists pgcrypto;

do $$
begin
  if to_regprocedure('public.set_updated_at()') is null then
    raise exception 'public.set_updated_at() must exist before inquiry replies migration';
  end if;
end;
$$;

create table public.inquiry_replies (
  id uuid primary key default gen_random_uuid(),
  company_id text not null,
  inquiry_id uuid not null,
  assignee_name text not null,
  message text not null,
  delivery_status text not null default 'pending',
  idempotency_key uuid not null,
  line_retry_key uuid not null,
  safe_error_code text,
  actor_user_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  sent_at timestamptz,
  constraint inquiry_replies_company_inquiry_fkey
    foreign key (company_id, inquiry_id)
    references public.inquiries (company_id, id)
    on delete restrict,
  constraint inquiry_replies_company_id_id_key unique (company_id, id),
  constraint inquiry_replies_company_inquiry_idempotency_key
    unique (company_id, inquiry_id, idempotency_key),
  constraint inquiry_replies_line_retry_key_key unique (line_retry_key),
  constraint inquiry_replies_assignee_name_check
    check (char_length(assignee_name) between 1 and 80 and btrim(assignee_name) <> ''),
  constraint inquiry_replies_message_check check (btrim(message) <> ''),
  constraint inquiry_replies_delivery_status_check
    check (delivery_status in ('pending', 'sending', 'sent', 'failed', 'delivery_unknown'))
);

create index idx_inquiry_replies_company_inquiry_created_at
  on public.inquiry_replies (company_id, inquiry_id, created_at desc);
create index idx_inquiry_replies_company_delivery_status_created_at
  on public.inquiry_replies (company_id, delivery_status, created_at);

alter table public.inquiry_replies enable row level security;

revoke all on table public.inquiry_replies from public;
revoke all on table public.inquiry_replies from anon;
revoke all on table public.inquiry_replies from authenticated;
grant select, insert, update on table public.inquiry_replies to service_role;

create trigger trg_inquiry_replies_set_updated_at
before update on public.inquiry_replies
for each row execute function public.set_updated_at();

commit;
