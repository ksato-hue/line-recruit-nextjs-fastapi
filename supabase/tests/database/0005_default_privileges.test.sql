BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

SELECT plan(3);

CREATE TABLE public.task12_default_privilege_table (
  id integer PRIMARY KEY
);
CREATE SEQUENCE public.task12_default_privilege_sequence;
CREATE FUNCTION public.task12_default_privilege_function()
RETURNS integer
LANGUAGE sql
SECURITY INVOKER
SET search_path = pg_catalog
AS 'SELECT 1';

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (VALUES ('anon'), ('authenticated')) AS role_name(name)
    CROSS JOIN (VALUES ('SELECT'), ('INSERT'), ('UPDATE'), ('DELETE')) AS privilege(name)
    WHERE pg_catalog.has_table_privilege(
      role_name.name,
      'public.task12_default_privilege_table',
      privilege.name
    )
  ),
  0::bigint,
  'migration-owner tables do not grant browser CRUD privileges automatically'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (VALUES ('anon'), ('authenticated')) AS role_name(name)
    CROSS JOIN (VALUES ('USAGE'), ('SELECT'), ('UPDATE')) AS privilege(name)
    WHERE pg_catalog.has_sequence_privilege(
      role_name.name,
      'public.task12_default_privilege_sequence',
      privilege.name
    )
  ),
  0::bigint,
  'migration-owner sequences do not grant browser privileges automatically'
);

SELECT is(
  (
    SELECT pg_catalog.count(*)
    FROM (VALUES ('anon'), ('authenticated')) AS role_name(name)
    WHERE pg_catalog.has_function_privilege(
      role_name.name,
      'public.task12_default_privilege_function()',
      'EXECUTE'
    )
  ),
  0::bigint,
  'migration-owner functions do not grant browser EXECUTE automatically'
);

SELECT * FROM finish();

ROLLBACK;
