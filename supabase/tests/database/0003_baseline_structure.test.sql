BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

SELECT plan(14);

CREATE TEMPORARY TABLE task10_base_tables (
  table_name text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task10_base_tables (table_name)
VALUES
  ('app_settings'),
  ('applicant_status_settings'),
  ('applicants'),
  ('application_sessions'),
  ('contacts'),
  ('faq_categories'),
  ('faq_settings'),
  ('faqs'),
  ('inquiries'),
  ('interview_slots'),
  ('line_message_logs'),
  ('question_tree_settings');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_base_tables AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    WHERE relation.relkind = 'r'
  ),
  12::bigint,
  'all 12 baseline tables exist as ordinary public tables'
);

CREATE TEMPORARY TABLE task10_base_columns (
  table_name text NOT NULL,
  column_name text NOT NULL,
  data_type text NOT NULL,
  is_nullable boolean NOT NULL,
  column_default text,
  ordinal_position smallint NOT NULL,
  PRIMARY KEY (table_name, column_name)
) ON COMMIT DROP;

INSERT INTO task10_base_columns (
  table_name,
  column_name,
  data_type,
  is_nullable,
  column_default,
  ordinal_position
)
VALUES
  ('app_settings', 'company_id', 'text', false, NULL, 1),
  ('app_settings', 'key', 'text', false, NULL, 2),
  ('app_settings', 'value', 'jsonb', false, NULL, 3),
  ('app_settings', 'created_at', 'timestamp with time zone', false, 'now()', 4),
  ('app_settings', 'updated_at', 'timestamp with time zone', false, 'now()', 5),
  ('applicant_status_settings', 'company_id', 'text', false, NULL, 1),
  ('applicant_status_settings', 'status_key', 'text', false, NULL, 2),
  ('applicant_status_settings', 'name', 'text', false, NULL, 3),
  ('applicant_status_settings', 'sort_order', 'integer', false, '0', 4),
  ('applicant_status_settings', 'is_active', 'boolean', false, 'true', 5),
  ('applicant_status_settings', 'created_at', 'timestamp with time zone', false, 'now()', 6),
  ('applicant_status_settings', 'updated_at', 'timestamp with time zone', false, 'now()', 7),
  ('applicants', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('applicants', 'line_user_id', 'text', false, NULL, 2),
  ('applicants', 'name', 'text', true, NULL, 3),
  ('applicants', 'phone', 'text', true, NULL, 4),
  ('applicants', 'job', 'text', true, NULL, 5),
  ('applicants', 'motivation', 'text', true, NULL, 6),
  ('applicants', 'status', 'text', true, '''新規応募''::text', 7),
  ('applicants', 'created_at', 'timestamp with time zone', true, 'now()', 8),
  ('applicants', 'interview_status', 'text', true, '''未調整''::text', 9),
  ('applicants', 'interview_date', 'text', true, NULL, 10),
  ('applicants', 'memo', 'text', true, NULL, 11),
  ('applicants', 'company_id', 'text', true, NULL, 12),
  ('applicants', 'application_session_id', 'uuid', true, NULL, 13),
  ('applicants', 'tags', 'jsonb', false, '''[]''::jsonb', 14),
  ('application_sessions', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('application_sessions', 'company_id', 'text', false, NULL, 2),
  ('application_sessions', 'line_user_id', 'text', false, NULL, 3),
  ('application_sessions', 'status', 'text', false, '''active''::text', 4),
  ('application_sessions', 'current_question_key', 'text', true, NULL, 5),
  ('application_sessions', 'answers', 'jsonb', false, '''[]''::jsonb', 6),
  ('application_sessions', 'started_at', 'timestamp with time zone', false, 'now()', 7),
  ('application_sessions', 'last_activity_at', 'timestamp with time zone', false, 'now()', 8),
  ('application_sessions', 'completed_at', 'timestamp with time zone', true, NULL, 9),
  ('application_sessions', 'cancelled_at', 'timestamp with time zone', true, NULL, 10),
  ('application_sessions', 'reminder_1h_sent_at', 'timestamp with time zone', true, NULL, 11),
  ('application_sessions', 'reminder_24h_sent_at', 'timestamp with time zone', true, NULL, 12),
  ('application_sessions', 'reminder_3d_sent_at', 'timestamp with time zone', true, NULL, 13),
  ('application_sessions', 'last_event_id', 'text', true, NULL, 14),
  ('application_sessions', 'created_at', 'timestamp with time zone', false, 'now()', 15),
  ('application_sessions', 'updated_at', 'timestamp with time zone', false, 'now()', 16),
  ('contacts', 'line_user_id', 'text', false, NULL, 1),
  ('contacts', 'display_name', 'text', true, NULL, 2),
  ('contacts', 'status', 'text', true, '''友だち追加''::text', 3),
  ('contacts', 'created_at', 'timestamp with time zone', true, 'now()', 4),
  ('faq_categories', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('faq_categories', 'name', 'text', false, NULL, 2),
  ('faq_categories', 'sort_order', 'integer', true, '0', 3),
  ('faq_categories', 'is_active', 'boolean', true, 'true', 4),
  ('faq_categories', 'created_at', 'timestamp with time zone', true, 'now()', 5),
  ('faq_categories', 'updated_at', 'timestamp with time zone', true, 'now()', 6),
  ('faq_categories', 'company_id', 'text', true, NULL, 7),
  ('faq_settings', 'company_id', 'text', false, NULL, 1),
  ('faq_settings', 'faq_key', 'text', false, NULL, 2),
  ('faq_settings', 'answer', 'text', false, '''''::text', 3),
  ('faq_settings', 'is_visible', 'boolean', false, 'false', 4),
  ('faq_settings', 'created_at', 'timestamp with time zone', false, 'now()', 5),
  ('faq_settings', 'updated_at', 'timestamp with time zone', false, 'now()', 6),
  ('faqs', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('faqs', 'category_id', 'uuid', false, NULL, 2),
  ('faqs', 'question', 'text', false, NULL, 3),
  ('faqs', 'answer', 'text', false, '''''::text', 4),
  ('faqs', 'is_visible', 'boolean', false, 'false', 5),
  ('faqs', 'sort_order', 'integer', true, '0', 6),
  ('faqs', 'created_at', 'timestamp with time zone', true, 'now()', 7),
  ('faqs', 'updated_at', 'timestamp with time zone', true, 'now()', 8),
  ('faqs', 'company_id', 'text', true, NULL, 9),
  ('inquiries', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('inquiries', 'line_user_id', 'text', false, NULL, 2),
  ('inquiries', 'message', 'text', false, NULL, 3),
  ('inquiries', 'status', 'text', false, '''未対応''::text', 4),
  ('inquiries', 'created_at', 'timestamp with time zone', true, 'now()', 5),
  ('inquiries', 'company_id', 'text', false, NULL, 6),
  ('interview_slots', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('interview_slots', 'applicant_id', 'uuid', false, NULL, 2),
  ('interview_slots', 'interview_round', 'text', true, NULL, 3),
  ('interview_slots', 'candidate_1', 'text', true, NULL, 4),
  ('interview_slots', 'candidate_2', 'text', true, NULL, 5),
  ('interview_slots', 'candidate_3', 'text', true, NULL, 6),
  ('interview_slots', 'selected_date', 'text', true, NULL, 7),
  ('interview_slots', 'status', 'text', true, '''候補日送信前''::text', 8),
  ('interview_slots', 'created_at', 'timestamp with time zone', true, 'now()', 9),
  ('interview_slots', 'line_user_id', 'text', true, NULL, 10),
  ('interview_slots', 'slot_datetime', 'timestamp with time zone', true, NULL, 11),
  ('interview_slots', 'selected_at', 'timestamp with time zone', true, NULL, 12),
  ('interview_slots', 'company_id', 'text', true, NULL, 13),
  ('line_message_logs', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('line_message_logs', 'created_at', 'timestamp with time zone', false, 'now()', 2),
  ('line_message_logs', 'line_user_id', 'text', false, NULL, 3),
  ('line_message_logs', 'message', 'text', true, NULL, 4),
  ('line_message_logs', 'direction', 'text', true, NULL, 5),
  ('line_message_logs', 'message_type', 'text', true, NULL, 6),
  ('line_message_logs', 'company_id', 'text', true, NULL, 7),
  ('question_tree_settings', 'company_id', 'text', false, NULL, 1),
  ('question_tree_settings', 'tree', 'jsonb', false, '''{}''::jsonb', 2),
  ('question_tree_settings', 'created_at', 'timestamp with time zone', false, 'now()', 3),
  ('question_tree_settings', 'updated_at', 'timestamp with time zone', false, 'now()', 4);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_base_columns AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_attribute AS attribute
      ON attribute.attrelid = relation.oid
      AND attribute.attname = expected.column_name
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped
    LEFT JOIN pg_catalog.pg_attrdef AS column_default
      ON column_default.adrelid = relation.oid
      AND column_default.adnum = attribute.attnum
    WHERE pg_catalog.format_type(attribute.atttypid, attribute.atttypmod)
        = expected.data_type
      AND NOT attribute.attnotnull = expected.is_nullable
      AND pg_catalog.pg_get_expr(column_default.adbin, column_default.adrelid)
        IS NOT DISTINCT FROM expected.column_default
      AND attribute.attnum = expected.ordinal_position
  ),
  98::bigint,
  'all 98 baseline columns preserve names, order, types, nullability, and defaults'
);

CREATE TEMPORARY TABLE task10_base_constraints (
  table_name text NOT NULL,
  constraint_name text PRIMARY KEY,
  constraint_type "char" NOT NULL
) ON COMMIT DROP;

INSERT INTO task10_base_constraints (table_name, constraint_name, constraint_type)
VALUES
  ('app_settings', 'app_settings_pkey', 'p'),
  ('applicant_status_settings', 'applicant_status_settings_pkey', 'p'),
  ('applicant_status_settings', 'applicant_status_settings_company_id_name_key', 'u'),
  ('applicants', 'applicants_pkey', 'p'),
  ('applicants', 'applicants_tags_array_check', 'c'),
  ('application_sessions', 'application_sessions_pkey', 'p'),
  ('application_sessions', 'application_sessions_status_check', 'c'),
  ('application_sessions', 'application_sessions_answers_array_check', 'c'),
  ('contacts', 'contacts_pkey', 'p'),
  ('faq_categories', 'faq_categories_pkey', 'p'),
  ('faq_categories', 'faq_categories_name_key', 'u'),
  ('faq_settings', 'faq_settings_pkey', 'p'),
  ('faqs', 'faqs_pkey', 'p'),
  ('faqs', 'faqs_category_id_question_key', 'u'),
  ('faqs', 'faqs_category_id_fkey', 'f'),
  ('inquiries', 'inquiries_pkey', 'p'),
  ('interview_slots', 'interview_slots_pkey', 'p'),
  ('line_message_logs', 'line_message_logs_pkey', 'p'),
  ('question_tree_settings', 'question_tree_settings_pkey', 'p');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_base_constraints AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_constraint AS actual
      ON actual.conrelid = relation.oid
      AND actual.conname = expected.constraint_name
      AND actual.contype = expected.constraint_type
  ),
  19::bigint,
  'all 19 named baseline constraints preserve their relation and type'
);

CREATE TEMPORARY TABLE task10_base_indexes (
  table_name text NOT NULL,
  index_name text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task10_base_indexes (table_name, index_name)
VALUES
  ('app_settings', 'app_settings_pkey'),
  ('applicant_status_settings', 'applicant_status_settings_company_id_name_key'),
  ('applicant_status_settings', 'applicant_status_settings_pkey'),
  ('applicants', 'applicants_pkey'),
  ('application_sessions', 'application_sessions_pkey'),
  ('contacts', 'contacts_pkey'),
  ('faq_categories', 'faq_categories_name_key'),
  ('faq_categories', 'faq_categories_pkey'),
  ('faq_settings', 'faq_settings_pkey'),
  ('faqs', 'faqs_category_id_question_key'),
  ('faqs', 'faqs_pkey'),
  ('applicant_status_settings', 'idx_applicant_status_settings_company_sort'),
  ('applicants', 'idx_applicants_company_created_at'),
  ('application_sessions', 'idx_application_sessions_company_started'),
  ('application_sessions', 'idx_application_sessions_company_status_activity'),
  ('faq_categories', 'idx_faq_categories_active'),
  ('faq_categories', 'idx_faq_categories_company_sort'),
  ('faq_categories', 'idx_faq_categories_sort_order'),
  ('faq_settings', 'idx_faq_settings_company_visible'),
  ('faqs', 'idx_faqs_category_id'),
  ('faqs', 'idx_faqs_company_category_sort'),
  ('faqs', 'idx_faqs_sort_order'),
  ('faqs', 'idx_faqs_visible'),
  ('inquiries', 'idx_inquiries_company_created_at'),
  ('interview_slots', 'idx_interview_slots_applicant_id'),
  ('interview_slots', 'idx_interview_slots_company_applicant'),
  ('interview_slots', 'idx_interview_slots_company_line_datetime'),
  ('interview_slots', 'idx_interview_slots_line_user_id'),
  ('interview_slots', 'idx_interview_slots_status'),
  ('line_message_logs', 'idx_line_message_logs_company_created_at'),
  ('line_message_logs', 'idx_line_message_logs_created_at'),
  ('line_message_logs', 'idx_line_message_logs_line_user_id'),
  ('inquiries', 'inquiries_pkey'),
  ('interview_slots', 'interview_slots_pkey'),
  ('line_message_logs', 'line_message_logs_pkey'),
  ('question_tree_settings', 'question_tree_settings_pkey'),
  ('app_settings', 'uq_app_settings_company_key'),
  ('applicant_status_settings', 'uq_applicant_status_settings_company_key'),
  ('applicant_status_settings', 'uq_applicant_status_settings_company_name'),
  ('applicants', 'uq_applicants_application_session'),
  ('application_sessions', 'uq_application_sessions_active_user'),
  ('faq_settings', 'uq_faq_settings_company_key'),
  ('question_tree_settings', 'uq_question_tree_settings_company');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_base_indexes AS expected
    INNER JOIN pg_catalog.pg_class AS table_relation
      ON table_relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_index AS actual
      ON actual.indrelid = table_relation.oid
    INNER JOIN pg_catalog.pg_class AS index_relation
      ON index_relation.oid = actual.indexrelid
      AND index_relation.relname = expected.index_name
  ),
  43::bigint,
  'all 43 named baseline indexes remain attached to the expected tables'
);

CREATE TEMPORARY TABLE task10_base_triggers (
  table_name text NOT NULL,
  trigger_name text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task10_base_triggers (table_name, trigger_name)
VALUES
  ('app_settings', 'set_app_settings_updated_at'),
  ('applicant_status_settings', 'set_applicant_status_settings_updated_at'),
  ('application_sessions', 'set_application_sessions_updated_at'),
  ('faq_categories', 'trg_faq_categories_updated_at'),
  ('faq_settings', 'set_faq_settings_updated_at'),
  ('faqs', 'trg_faqs_updated_at'),
  ('question_tree_settings', 'set_question_tree_settings_updated_at');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_base_triggers AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_trigger AS actual
      ON actual.tgrelid = relation.oid
      AND actual.tgname = expected.trigger_name
      AND NOT actual.tgisinternal
    INNER JOIN pg_catalog.pg_proc AS routine
      ON routine.oid = actual.tgfoid
      AND routine.oid = pg_catalog.to_regprocedure('public.set_updated_at()')
  ),
  7::bigint,
  'all 7 named baseline triggers call public.set_updated_at()'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES
        ('public.set_updated_at()', 'trigger'),
        (
          'public.complete_application_session(uuid, text, text, text, text, text, text, text, text)',
          'jsonb'
        )
    ) AS expected(function_signature, return_type)
    INNER JOIN pg_catalog.pg_proc AS routine
      ON routine.oid = pg_catalog.to_regprocedure(expected.function_signature)
    WHERE pg_catalog.pg_get_function_result(routine.oid) = expected.return_type
  ),
  2::bigint,
  'both exact baseline function signatures and return types resolve'
);

CREATE TEMPORARY TABLE task10_inquiry_columns (
  table_name text NOT NULL,
  column_name text NOT NULL,
  data_type text NOT NULL,
  is_nullable boolean NOT NULL,
  column_default text,
  ordinal_position smallint NOT NULL,
  PRIMARY KEY (table_name, column_name)
) ON COMMIT DROP;

SELECT is(
  (
    SELECT relation.relkind
    FROM pg_catalog.pg_class AS relation
    WHERE relation.oid = pg_catalog.to_regclass('public.inquiry_replies')
  ),
  'r'::"char",
  'the inquiry replies relation exists separately as an ordinary public table'
);

SELECT is(
  (
    SELECT relation.relkind
    FROM pg_catalog.pg_class AS relation
    WHERE relation.oid = pg_catalog.to_regclass('public.inquiry_replies')
  ),
  'r'::"char",
  'the inquiry replies relation exists separately as an ordinary public table'
);

INSERT INTO task10_inquiry_columns (
  table_name,
  column_name,
  data_type,
  is_nullable,
  column_default,
  ordinal_position
)
VALUES
  ('inquiries', 'status', 'text', false, '''未対応''::text', 4),
  ('inquiries', 'company_id', 'text', false, NULL, 6),
  ('inquiries', 'assignee_name', 'text', true, NULL, 7),
  ('inquiries', 'last_replied_at', 'timestamp with time zone', true, NULL, 8),
  ('inquiries', 'updated_at', 'timestamp with time zone', false, 'now()', 9),
  ('line_message_logs', 'inquiry_reply_id', 'uuid', true, NULL, 8),
  ('inquiry_replies', 'id', 'uuid', false, 'gen_random_uuid()', 1),
  ('inquiry_replies', 'company_id', 'text', false, NULL, 2),
  ('inquiry_replies', 'inquiry_id', 'uuid', false, NULL, 3),
  ('inquiry_replies', 'assignee_name', 'text', false, NULL, 4),
  ('inquiry_replies', 'message', 'text', false, NULL, 5),
  ('inquiry_replies', 'delivery_status', 'text', false, '''pending''::text', 6),
  ('inquiry_replies', 'idempotency_key', 'uuid', false, NULL, 7),
  ('inquiry_replies', 'line_retry_key', 'uuid', false, NULL, 8),
  ('inquiry_replies', 'safe_error_code', 'text', true, NULL, 9),
  ('inquiry_replies', 'actor_user_id', 'uuid', true, NULL, 10),
  ('inquiry_replies', 'created_at', 'timestamp with time zone', false, 'now()', 11),
  ('inquiry_replies', 'updated_at', 'timestamp with time zone', false, 'now()', 12),
  ('inquiry_replies', 'sent_at', 'timestamp with time zone', true, NULL, 13);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_inquiry_columns AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_attribute AS attribute
      ON attribute.attrelid = relation.oid
      AND attribute.attname = expected.column_name
      AND attribute.attnum > 0
      AND NOT attribute.attisdropped
    LEFT JOIN pg_catalog.pg_attrdef AS column_default
      ON column_default.adrelid = relation.oid
      AND column_default.adnum = attribute.attnum
    WHERE pg_catalog.format_type(attribute.atttypid, attribute.atttypmod)
        = expected.data_type
      AND NOT attribute.attnotnull = expected.is_nullable
      AND pg_catalog.pg_get_expr(column_default.adbin, column_default.adrelid)
        IS NOT DISTINCT FROM expected.column_default
      AND attribute.attnum = expected.ordinal_position
  ),
  19::bigint,
  'inquiry workflow columns and changed base-column rules match separately'
);

CREATE TEMPORARY TABLE task10_inquiry_constraints (
  table_name text NOT NULL,
  constraint_name text PRIMARY KEY,
  constraint_type "char" NOT NULL
) ON COMMIT DROP;

INSERT INTO task10_inquiry_constraints (
  table_name,
  constraint_name,
  constraint_type
)
VALUES
  ('inquiries', 'inquiries_assignee_name_check', 'c'),
  ('inquiries', 'inquiries_status_check', 'c'),
  ('inquiries', 'inquiries_company_id_id_key', 'u'),
  ('inquiry_replies', 'inquiry_replies_pkey', 'p'),
  ('inquiry_replies', 'inquiry_replies_company_inquiry_fkey', 'f'),
  ('inquiry_replies', 'inquiry_replies_company_id_id_key', 'u'),
  ('inquiry_replies', 'inquiry_replies_company_inquiry_idempotency_key', 'u'),
  ('inquiry_replies', 'inquiry_replies_line_retry_key_key', 'u'),
  ('inquiry_replies', 'inquiry_replies_assignee_name_check', 'c'),
  ('inquiry_replies', 'inquiry_replies_message_check', 'c'),
  ('inquiry_replies', 'inquiry_replies_delivery_status_check', 'c'),
  ('line_message_logs', 'line_message_logs_inquiry_reply_company_check', 'c'),
  ('line_message_logs', 'line_message_logs_company_inquiry_reply_fkey', 'f');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_inquiry_constraints AS expected
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_constraint AS actual
      ON actual.conrelid = relation.oid
      AND actual.conname = expected.constraint_name
      AND actual.contype = expected.constraint_type
  ),
  13::bigint,
  'all 13 inquiry-specific named constraints preserve relation and type'
);

CREATE TEMPORARY TABLE task10_inquiry_indexes (
  table_name text NOT NULL,
  index_name text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task10_inquiry_indexes (table_name, index_name)
VALUES
  ('inquiries', 'inquiries_company_id_id_key'),
  ('inquiries', 'idx_inquiries_company_status_created_at'),
  ('inquiry_replies', 'inquiry_replies_pkey'),
  ('inquiry_replies', 'inquiry_replies_company_id_id_key'),
  ('inquiry_replies', 'inquiry_replies_company_inquiry_idempotency_key'),
  ('inquiry_replies', 'inquiry_replies_line_retry_key_key'),
  ('inquiry_replies', 'idx_inquiry_replies_company_inquiry_created_at'),
  ('inquiry_replies', 'idx_inquiry_replies_company_delivery_status_created_at'),
  ('line_message_logs', 'idx_line_message_logs_company_inquiry_reply'),
  ('line_message_logs', 'uq_line_message_logs_company_inquiry_reply');

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task10_inquiry_indexes AS expected
    INNER JOIN pg_catalog.pg_class AS table_relation
      ON table_relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_index AS actual
      ON actual.indrelid = table_relation.oid
    INNER JOIN pg_catalog.pg_class AS index_relation
      ON index_relation.oid = actual.indexrelid
      AND index_relation.relname = expected.index_name
  ),
  10::bigint,
  'all 10 inquiry-specific named indexes remain attached separately'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES
        ('inquiries', 'trg_inquiries_set_updated_at'),
        ('inquiry_replies', 'trg_inquiry_replies_set_updated_at')
    ) AS expected(table_name, trigger_name)
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = pg_catalog.to_regclass(
        pg_catalog.format('public.%I', expected.table_name)
      )
    INNER JOIN pg_catalog.pg_trigger AS actual
      ON actual.tgrelid = relation.oid
      AND actual.tgname = expected.trigger_name
      AND NOT actual.tgisinternal
    WHERE actual.tgfoid = pg_catalog.to_regprocedure('public.set_updated_at()')
  ),
  2::bigint,
  'both inquiry update triggers call public.set_updated_at()'
);

SELECT ok(
  pg_catalog.to_regprocedure(
    'public.finalize_inquiry_reply(text, uuid, uuid)'
  ) IS NOT NULL
  AND pg_catalog.pg_get_function_result(
    pg_catalog.to_regprocedure('public.finalize_inquiry_reply(text, uuid, uuid)')
  ) = 'jsonb',
  'the exact inquiry finalizer signature returns jsonb'
);

SELECT ok(
  (
    SELECT relation.relrowsecurity
    FROM pg_catalog.pg_class AS relation
    WHERE relation.oid = pg_catalog.to_regclass('public.inquiry_replies')
  )
  AND NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_policy AS policy
    WHERE policy.polrelid = pg_catalog.to_regclass('public.inquiry_replies')
  )
  AND NOT EXISTS (
    SELECT 1
    FROM (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    CROSS JOIN (
      VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
    ) AS table_privilege(privilege_name)
    WHERE pg_catalog.has_table_privilege(
      client_role.role_name,
      'public.inquiry_replies',
      table_privilege.privilege_name
    )
  )
  AND pg_catalog.has_table_privilege(
    'service_role',
    'public.inquiry_replies',
    'SELECT, INSERT, UPDATE'
  )
  AND NOT pg_catalog.has_table_privilege(
    'service_role',
    'public.inquiry_replies',
    'DELETE'
  )
  AND NOT EXISTS (
    SELECT 1
    FROM pg_catalog.pg_proc AS routine
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(
        routine.proacl,
        pg_catalog.acldefault('f', routine.proowner)
      )
    ) AS function_acl
    WHERE routine.oid = pg_catalog.to_regprocedure(
        'public.finalize_inquiry_reply(text, uuid, uuid)'
      )
      AND function_acl.grantee = 0
      AND function_acl.privilege_type = 'EXECUTE'
  )
  AND NOT pg_catalog.has_function_privilege(
    'anon',
    'public.finalize_inquiry_reply(text, uuid, uuid)',
    'EXECUTE'
  )
  AND NOT pg_catalog.has_function_privilege(
    'authenticated',
    'public.finalize_inquiry_reply(text, uuid, uuid)',
    'EXECUTE'
  )
  AND pg_catalog.has_function_privilege(
    'service_role',
    'public.finalize_inquiry_reply(text, uuid, uuid)',
    'EXECUTE'
  ),
  'inquiry table and finalizer privileges remain fail closed for browser roles'
);

SELECT * FROM finish();

ROLLBACK;
