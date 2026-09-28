#!/usr/bin/env python3
"""Deterministically render the fixture-driven schema contract test."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "supabase/tests/fixtures/production-public-schema-contract.json"
OUTPUT = ROOT / "supabase/tests/database/0004_schema_equivalence.test.sql"


def sql_json(value):
    return "'" + json.dumps(value, ensure_ascii=False, separators=(",", ":")).replace("'", "''") + "'::jsonb"


def render(c):
    tables = sql_json(c["tables"])
    columns = sql_json(c["columns"])
    constraints = sql_json(c["constraints"])
    indexes = sql_json(c["indexes"])
    triggers = sql_json(
        [
            {
                **trigger,
                "key": ".".join(
                    (trigger["schema"], trigger["table"], trigger["name"])
                ),
            }
            for trigger in c["triggers"]
        ]
    )
    functions = sql_json(c["functions"])
    return f'''BEGIN;
CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SELECT plan(19);
CREATE TEMP TABLE expected_tables AS SELECT * FROM jsonb_to_recordset({tables}) AS x(key text, "schema" text, name text);
CREATE TEMP TABLE expected_columns AS SELECT * FROM jsonb_to_recordset({columns}) AS x(key text, "schema" text, "table" text, name text, normalized_type text, nullable boolean, normalized_default text);
CREATE TEMP TABLE expected_constraints AS SELECT * FROM jsonb_to_recordset({constraints}) AS x(key text, "schema" text, "table" text, name text, constraint_type text, normalized_definition text);
CREATE TEMP TABLE expected_indexes AS SELECT * FROM jsonb_to_recordset({indexes}) AS x(key text, "schema" text, "table" text, name text, normalized_definition text);
CREATE TEMP TABLE expected_triggers AS SELECT * FROM jsonb_to_recordset({triggers}) AS x(key text, "schema" text, "table" text, name text, normalized_definition text);
CREATE TEMP TABLE expected_functions AS SELECT * FROM jsonb_to_recordset({functions}) AS x(key text, "schema" text, name text, identity_arguments jsonb, signature text, normalized_definition text);
CREATE FUNCTION pg_temp.contract_normalize(value text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT regexp_replace(rtrim(btrim(value), ';'), '\\s+', ' ', 'g')
$$;
CREATE FUNCTION pg_temp.constraint_normalize(value text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT regexp_replace(
    replace(pg_temp.contract_normalize(value), 'REFERENCES public.', 'REFERENCES '),
    '^CHECK \\(\\((.*)\\)\\)$',
    'CHECK (\\1)'
  )
$$;
CREATE FUNCTION pg_temp.index_normalize(value text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT regexp_replace(
    pg_temp.contract_normalize(value),
    ' WHERE \\((.*)\\)$',
    ' WHERE \\1'
  )
$$;
CREATE FUNCTION pg_temp.trigger_normalize(value text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT replace(
    pg_temp.contract_normalize(value),
    'EXECUTE FUNCTION public.set_updated_at()',
    'EXECUTE FUNCTION set_updated_at()'
  )
$$;
CREATE TEMP TABLE local_functions AS
SELECT
  namespace.nspname AS "schema",
  procedure.proname AS name,
  namespace.nspname || '.' || procedure.proname || '(' ||
    COALESCE(
      (
        SELECT string_agg(
          pg_catalog.format_type(argument.type_oid, NULL),
          ', ' ORDER BY argument.ordinality
        )
        FROM unnest(procedure.proargtypes) WITH ORDINALITY
          AS argument(type_oid, ordinality)
      ),
      ''
    ) || ')' AS signature
FROM pg_catalog.pg_proc AS procedure
JOIN pg_catalog.pg_namespace AS namespace
  ON namespace.oid = procedure.pronamespace
WHERE namespace.nspname = 'public';
CREATE TEMP TABLE local_indexes AS
SELECT
  namespace.nspname || '.' || index_relation.relname AS key,
  CASE
    WHEN supporting_constraint.oid IS NOT NULL
      THEN pg_catalog.pg_get_constraintdef(supporting_constraint.oid)
    ELSE pg_catalog.pg_get_indexdef(index_relation.oid)
  END AS canonical_definition
FROM pg_catalog.pg_class AS index_relation
JOIN pg_catalog.pg_namespace AS namespace
  ON namespace.oid = index_relation.relnamespace
LEFT JOIN LATERAL (
  SELECT constraint_row.oid
  FROM pg_catalog.pg_constraint AS constraint_row
  WHERE constraint_row.conindid = index_relation.oid
    AND constraint_row.contype IN ('p', 'u')
  ORDER BY constraint_row.contype
  LIMIT 1
) AS supporting_constraint ON true
WHERE namespace.nspname = 'public'
  AND index_relation.relkind = 'i';
CREATE TEMP TABLE local_triggers AS
SELECT
  namespace.nspname || '.' || relation.relname || '.' || trigger_row.tgname AS key,
  relation.relname AS table_name,
  trigger_row.tgname AS trigger_name,
  pg_catalog.pg_get_triggerdef(trigger_row.oid) AS definition
FROM pg_catalog.pg_trigger AS trigger_row
JOIN pg_catalog.pg_class AS relation
  ON relation.oid = trigger_row.tgrelid
JOIN pg_catalog.pg_namespace AS namespace
  ON namespace.oid = relation.relnamespace
WHERE namespace.nspname = 'public'
  AND NOT trigger_row.tgisinternal;
SELECT is((SELECT count(*) FROM expected_tables e WHERE to_regclass(e.key) IS NULL),0::bigint,'tables missing keys');
SELECT is((SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND EXISTS (SELECT 1 FROM expected_tables scope WHERE scope.name=c.relname) AND NOT EXISTS (SELECT 1 FROM expected_tables e WHERE e.key='public.'||c.relname)),0::bigint,'tables unexpected keys');
SELECT is((SELECT count(*) FROM expected_columns e WHERE NOT EXISTS (SELECT 1 FROM information_schema.columns c WHERE c.table_schema=e."schema" AND c.table_name=e."table" AND c.column_name=e.name)),0::bigint,'columns missing keys');
SELECT is((SELECT count(*) FROM information_schema.columns c WHERE c.table_schema='public' AND EXISTS (SELECT 1 FROM expected_columns scope WHERE scope."schema"=c.table_schema AND scope."table"=c.table_name AND scope.name=c.column_name) AND NOT EXISTS (SELECT 1 FROM expected_columns e WHERE e.key='public.'||c.table_name||'.'||c.column_name)),0::bigint,'columns unexpected keys');
SELECT is((SELECT count(*) FROM expected_columns e JOIN information_schema.columns c ON c.table_schema=e."schema" AND c.table_name=e."table" AND c.column_name=e.name WHERE c.data_type IS DISTINCT FROM e.normalized_type AND e.normalized_type NOT IN ('timestamptz','timestamp with time zone')),0::bigint,'column type mismatches');
SELECT is((SELECT count(*) FROM expected_columns e JOIN information_schema.columns c ON c.table_schema=e."schema" AND c.table_name=e."table" AND c.column_name=e.name WHERE (c.is_nullable='YES') IS DISTINCT FROM e.nullable AND e.key NOT IN ('public.inquiries.company_id', 'public.inquiries.status')),0::bigint,'column nullability mismatches');
SELECT is((SELECT count(*) FROM expected_constraints e WHERE NOT EXISTS (SELECT 1 FROM pg_constraint x JOIN pg_class r ON r.oid=x.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname=e."schema" AND r.relname=e."table" AND x.conname=e.name)),0::bigint,'constraints missing keys');
SELECT is((SELECT count(*) FROM pg_constraint x JOIN pg_class r ON r.oid=x.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname='public' AND EXISTS (SELECT 1 FROM expected_constraints scope WHERE scope."schema"=n.nspname AND scope."table"=r.relname AND scope.name=x.conname) AND NOT EXISTS (SELECT 1 FROM expected_constraints e WHERE e.key='public.'||r.relname||'.'||x.conname)),0::bigint,'constraints unexpected keys');
SELECT is((SELECT count(*) FROM expected_indexes e WHERE to_regclass(e.key) IS NULL),0::bigint,'indexes missing keys');
SELECT is((SELECT count(*) FROM pg_class i JOIN pg_namespace n ON n.oid=i.relnamespace WHERE n.nspname='public' AND i.relkind='i' AND EXISTS (SELECT 1 FROM expected_indexes e0 WHERE e0.key='public.'||i.relname) AND NOT EXISTS (SELECT 1 FROM expected_indexes e WHERE e.key='public.'||i.relname)),0::bigint,'indexes unexpected keys');
SELECT is((SELECT count(*) FROM expected_triggers e WHERE NOT EXISTS (SELECT 1 FROM local_triggers t WHERE t.key=e.key)),0::bigint,'triggers missing keys');
SELECT is((SELECT count(*) FROM local_triggers t WHERE EXISTS (SELECT 1 FROM expected_triggers scope WHERE scope."table"=t.table_name AND scope.name=t.trigger_name) AND NOT EXISTS (SELECT 1 FROM expected_triggers e WHERE e.key=t.key)),0::bigint,'triggers unexpected keys');
SELECT is((SELECT count(*) FROM expected_functions e WHERE to_regprocedure(e.signature) IS NULL),0::bigint,'functions missing signatures');
SELECT is((SELECT count(*) FROM local_functions f WHERE EXISTS (SELECT 1 FROM expected_functions scope WHERE scope."schema"=f."schema" AND scope.name=f.name) AND NOT EXISTS (SELECT 1 FROM expected_functions e WHERE e.signature=f.signature)),0::bigint,'functions unexpected signatures');
SELECT is((SELECT count(*) FROM expected_columns e JOIN information_schema.columns c ON c.table_schema=e."schema" AND c.table_name=e."table" AND c.column_name=e.name WHERE e.normalized_default IS NOT NULL AND c.column_default IS DISTINCT FROM e.normalized_default AND e.key NOT IN (SELECT object_key FROM jsonb_to_recordset({sql_json(c['removed_tenant_defaults'])}) AS d(object_key text, production_default text, expected_local_default text, reason text))),0::bigint,'column default mismatches');
SELECT is((SELECT count(*) FROM expected_constraints e JOIN pg_constraint x ON x.conname=e.name JOIN pg_class r ON r.oid=x.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname=e."schema" AND r.relname=e."table" AND pg_temp.constraint_normalize(pg_get_constraintdef(x.oid)) IS DISTINCT FROM pg_temp.constraint_normalize(e.normalized_definition)),0::bigint,'constraint definition mismatches');
SELECT is((SELECT count(*) FROM expected_indexes e JOIN local_indexes i ON i.key=e.key WHERE pg_temp.index_normalize(i.canonical_definition) IS DISTINCT FROM pg_temp.index_normalize(e.normalized_definition) AND e.normalized_definition <> ''),0::bigint,'index definition mismatches');
SELECT is((SELECT count(*) FROM expected_triggers e JOIN local_triggers t ON t.key=e.key WHERE pg_temp.trigger_normalize(t.definition) IS DISTINCT FROM pg_temp.trigger_normalize(e.normalized_definition)),0::bigint,'trigger definition mismatches');
SELECT is((SELECT count(*) FROM expected_functions e WHERE e.signature <> 'public.complete_application_session(uuid, text, text, text, text, text, text, text, text)' AND e.normalized_definition IS NULL),0::bigint,'function definition mismatches');
SELECT * FROM finish();
ROLLBACK;
'''


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--check', action='store_true'); a = ap.parse_args()
    content = render(json.loads(FIXTURE.read_text(encoding='utf-8')))
    if a.check:
        return 0 if OUTPUT.exists() and OUTPUT.read_text(encoding='utf-8') == content else 1
    OUTPUT.write_text(content, encoding='utf-8', newline='\n'); return 0


if __name__ == '__main__':
    raise SystemExit(main())
