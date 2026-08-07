-- Correlate outbound inquiry replies with their LINE message-log entries.
-- Existing log rows remain valid because inquiry_reply_id is nullable.

begin;

alter table public.line_message_logs
  add column if not exists inquiry_reply_id uuid;

alter table public.line_message_logs
  add constraint line_message_logs_inquiry_reply_company_check
  check (inquiry_reply_id is null or company_id is not null),
  add constraint line_message_logs_company_inquiry_reply_fkey
  foreign key (company_id, inquiry_reply_id)
  references public.inquiry_replies (company_id, id)
  on delete restrict;

create index if not exists idx_line_message_logs_company_inquiry_reply
  on public.line_message_logs (company_id, inquiry_reply_id);

create unique index if not exists uq_line_message_logs_company_inquiry_reply
  on public.line_message_logs (company_id, inquiry_reply_id)
  where inquiry_reply_id is not null;

commit;
