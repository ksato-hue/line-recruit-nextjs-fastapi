-- Atomically finalize a LINE-accepted inquiry reply and its projections.

begin;

create function public.finalize_inquiry_reply(
  p_company_id text,
  p_inquiry_id uuid,
  p_reply_id uuid
)
returns jsonb
language plpgsql
security invoker
set search_path = pg_catalog
as $function$
declare
  v_reply_message text;
  v_reply_assignee_name text;
  v_reply_delivery_status text;
  v_reply_sent_at timestamptz;
  v_line_user_id text;
  v_inquiry_status text;
  v_inquiry_updated_at timestamptz;
  v_sent_at timestamptz;
  v_log_id uuid;
  v_log_direction text;
  v_log_message_type text;
  v_log_message text;
  v_log_line_user_id text;
  v_updated_reply_id uuid;
begin
  select
    r.message,
    r.assignee_name,
    r.delivery_status,
    r.sent_at
  into
    v_reply_message,
    v_reply_assignee_name,
    v_reply_delivery_status,
    v_reply_sent_at
  from public.inquiry_replies as r
  where r.company_id = p_company_id
    and r.inquiry_id = p_inquiry_id
    and r.id = p_reply_id
  for update;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'INQUIRY_REPLY_NOT_FOUND';
  end if;

  select
    i.line_user_id,
    i.status,
    i.updated_at
  into
    v_line_user_id,
    v_inquiry_status,
    v_inquiry_updated_at
  from public.inquiries as i
  where i.company_id = p_company_id
    and i.id = p_inquiry_id
  for update;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'INQUIRY_NOT_FOUND';
  end if;

  if v_reply_delivery_status <> 'sent' then
    if v_reply_delivery_status not in ('sending', 'delivery_unknown') then
      raise exception using
        errcode = '55000',
        message = 'INQUIRY_REPLY_NOT_FINALIZABLE';
    end if;

    if v_inquiry_status <> '対応中' then
      raise exception using
        errcode = '55000',
        message = 'INQUIRY_NOT_IN_PROGRESS';
    end if;

    v_sent_at := pg_catalog.now();

    update public.inquiry_replies as r
    set
      delivery_status = 'sent',
      safe_error_code = null,
      sent_at = v_sent_at
    where r.company_id = p_company_id
      and r.inquiry_id = p_inquiry_id
      and r.id = p_reply_id
      and r.delivery_status = v_reply_delivery_status
    returning r.id into v_updated_reply_id;

    if not found then
      raise exception using
        errcode = '55000',
        message = 'INQUIRY_REPLY_UPDATE_CONFLICT';
    end if;

    insert into public.line_message_logs (
      company_id,
      line_user_id,
      message,
      direction,
      message_type,
      inquiry_reply_id
    )
    select
      p_company_id,
      v_line_user_id,
      v_reply_message,
      'outbound',
      'inquiry_reply',
      p_reply_id
    where not exists (
      select 1
      from public.line_message_logs as existing_log
      where existing_log.company_id = p_company_id
        and existing_log.inquiry_reply_id = p_reply_id
    )
    returning id into v_log_id;
  end if;

  if v_reply_delivery_status = 'sent' or v_log_id is null then
    select
      l.id,
      l.direction,
      l.message_type,
      l.message,
      l.line_user_id
    into
      v_log_id,
      v_log_direction,
      v_log_message_type,
      v_log_message,
      v_log_line_user_id
    from public.line_message_logs as l
    where l.company_id = p_company_id
      and l.inquiry_reply_id = p_reply_id
    for update;

    if not found then
      raise exception using
        errcode = '23514',
        message = 'INQUIRY_REPLY_LOG_INTEGRITY_ERROR';
    end if;

    if v_log_direction is distinct from 'outbound'
      or v_log_message_type is distinct from 'inquiry_reply'
      or v_log_message is distinct from v_reply_message
      or v_log_line_user_id is distinct from v_line_user_id
    then
      raise exception using
        errcode = '23514',
        message = 'INQUIRY_REPLY_LOG_INTEGRITY_ERROR';
    end if;
  end if;

  if v_reply_delivery_status = 'sent' then
    return pg_catalog.jsonb_build_object(
      'inquiry_id', p_inquiry_id,
      'reply_id', p_reply_id,
      'line_message_log_id', v_log_id,
      'delivery_status', v_reply_delivery_status,
      'inquiry_status', v_inquiry_status,
      'sent_at', v_reply_sent_at,
      'inquiry_updated_at', v_inquiry_updated_at
    );
  end if;

  update public.inquiries as i
  set
    status = '対応済み',
    assignee_name = v_reply_assignee_name,
    last_replied_at = v_sent_at,
    updated_at = v_sent_at
  where i.company_id = p_company_id
    and i.id = p_inquiry_id
    and i.status = '対応中'
  returning i.updated_at into v_inquiry_updated_at;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'INQUIRY_NOT_IN_PROGRESS';
  end if;

  return pg_catalog.jsonb_build_object(
    'inquiry_id', p_inquiry_id,
    'reply_id', p_reply_id,
    'line_message_log_id', v_log_id,
    'delivery_status', 'sent',
    'inquiry_status', '対応済み',
    'sent_at', v_sent_at,
    'inquiry_updated_at', v_inquiry_updated_at
  );
end;
$function$;

revoke execute on function public.finalize_inquiry_reply(text, uuid, uuid)
from public;
revoke execute on function public.finalize_inquiry_reply(text, uuid, uuid)
from anon;
revoke execute on function public.finalize_inquiry_reply(text, uuid, uuid)
from authenticated;
grant execute on function public.finalize_inquiry_reply(text, uuid, uuid)
to service_role;

commit;
