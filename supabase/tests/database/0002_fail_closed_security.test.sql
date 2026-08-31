BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

SELECT plan(15);

CREATE TEMPORARY TABLE task8_base_tables (
  table_name text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task8_base_tables (table_name)
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

CREATE TEMPORARY TABLE task8_application_functions (
  function_signature text PRIMARY KEY
) ON COMMIT DROP;

INSERT INTO task8_application_functions (function_signature)
VALUES
  ('public.set_updated_at()'),
  (
    'public.complete_application_session(uuid, text, text, text, text, text, text, text, text)'
  );

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_application_functions AS expected
    WHERE pg_catalog.to_regprocedure(expected.function_signature) IS NOT NULL
  ),
  2::bigint,
  'both exact application function signatures resolve'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM pg_catalog.pg_class AS relation
    INNER JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = relation.relnamespace
    INNER JOIN task8_base_tables AS expected
      ON expected.table_name = relation.relname
    WHERE namespace.nspname = 'public'
      AND relation.relrowsecurity
  ),
  12::bigint,
  'all 12 base tables have row-level security enabled'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM pg_catalog.pg_class AS relation
    INNER JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = relation.relnamespace
    INNER JOIN task8_base_tables AS expected
      ON expected.table_name = relation.relname
    WHERE namespace.nspname = 'public'
      AND relation.relforcerowsecurity
  ),
  0::bigint,
  'FORCE ROW LEVEL SECURITY remains disabled on all base tables'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM pg_catalog.pg_policy AS policy
    INNER JOIN pg_catalog.pg_class AS relation
      ON relation.oid = policy.polrelid
    INNER JOIN pg_catalog.pg_namespace AS namespace
      ON namespace.oid = relation.relnamespace
    INNER JOIN task8_base_tables AS expected
      ON expected.table_name = relation.relname
    WHERE namespace.nspname = 'public'
  ),
  0::bigint,
  'no RLS policies exist on the base tables'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_base_tables AS expected
    CROSS JOIN (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    CROSS JOIN (
      VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
    ) AS table_privilege(privilege_name)
    WHERE pg_catalog.has_table_privilege(
      client_role.role_name,
      pg_catalog.format('public.%I', expected.table_name),
      table_privilege.privilege_name
    )
  ),
  0::bigint,
  'anon and authenticated have no base-table CRUD or SELECT privilege'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_base_tables AS expected
    CROSS JOIN (
      VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
    ) AS table_privilege(privilege_name)
    WHERE NOT pg_catalog.has_table_privilege(
      'service_role',
      pg_catalog.format('public.%I', expected.table_name),
      table_privilege.privilege_name
    )
  ),
  0::bigint,
  'service_role has required CRUD and SELECT access on every base table'
);

SELECT ok(
  (
    SELECT
      role.rolsuper
      OR role.rolbypassrls
      OR NOT EXISTS (
        SELECT 1
        FROM task8_base_tables AS expected
        INNER JOIN pg_catalog.pg_class AS relation
          ON relation.relname = expected.table_name
        INNER JOIN pg_catalog.pg_namespace AS namespace
          ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public'
          AND relation.relowner <> role.oid
      )
    FROM pg_catalog.pg_roles AS role
    WHERE role.rolname = 'service_role'
  ),
  'service_role can bypass RLS or owns every base table'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_application_functions AS expected
    INNER JOIN pg_catalog.pg_proc AS routine
      ON routine.oid = pg_catalog.to_regprocedure(expected.function_signature)
    CROSS JOIN LATERAL pg_catalog.aclexplode(
      COALESCE(
        routine.proacl,
        pg_catalog.acldefault('f', routine.proowner)
      )
    ) AS function_acl
    WHERE function_acl.grantee = 0
      AND function_acl.privilege_type = 'EXECUTE'
  ),
  0::bigint,
  'PUBLIC has no EXECUTE privilege on either application function'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_application_functions AS expected
    CROSS JOIN (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    WHERE pg_catalog.has_function_privilege(
      client_role.role_name,
      pg_catalog.to_regprocedure(expected.function_signature),
      'EXECUTE'
    )
  ),
  0::bigint,
  'anon and authenticated cannot execute either application function'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM task8_application_functions AS expected
    WHERE NOT pg_catalog.has_function_privilege(
      'service_role',
      pg_catalog.to_regprocedure(expected.function_signature),
      'EXECUTE'
    )
  ),
  0::bigint,
  'service_role can execute both application functions'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    WHERE pg_catalog.has_schema_privilege(
      client_role.role_name,
      'public',
      'CREATE'
    )
  ),
  0::bigint,
  'browser roles cannot create objects in the public schema'
);

SELECT ok(
  pg_catalog.has_schema_privilege('service_role', 'public', 'USAGE'),
  'service_role retains public schema usage'
);

CREATE TABLE public.task8_default_privilege_table (
  id integer PRIMARY KEY
);

CREATE FUNCTION public.task8_default_privilege_function()
RETURNS integer
LANGUAGE sql
SECURITY INVOKER
SET search_path = pg_catalog
AS 'SELECT 1';

CREATE SEQUENCE public.task8_default_privilege_sequence;

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    CROSS JOIN (
      VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')
    ) AS table_privilege(privilege_name)
    WHERE pg_catalog.has_table_privilege(
      client_role.role_name,
      'public.task8_default_privilege_table',
      table_privilege.privilege_name
    )
  ),
  0::bigint,
  'new migration-owner tables do not grant client privileges automatically'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    WHERE pg_catalog.has_function_privilege(
      client_role.role_name,
      'public.task8_default_privilege_function()',
      'EXECUTE'
    )
  ),
  0::bigint,
  'new migration-owner functions do not grant client EXECUTE automatically'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (
      VALUES ('anon'), ('authenticated')
    ) AS client_role(role_name)
    CROSS JOIN (
      VALUES ('USAGE'), ('SELECT'), ('UPDATE')
    ) AS sequence_privilege(privilege_name)
    WHERE pg_catalog.has_sequence_privilege(
      client_role.role_name,
      'public.task8_default_privilege_sequence',
      sequence_privilege.privilege_name
    )
  ),
  0::bigint,
  'new migration-owner sequences do not grant client privileges automatically'
);

SELECT * FROM finish();

ROLLBACK;
