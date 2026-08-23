BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

SELECT plan(15);

SELECT pg_catalog.set_config(
  'task7.company_a',
  'task7-company-' || pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.company_b',
  'task7-company-' || pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.user_a',
  'task7-user-' || pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.user_b',
  'task7-user-' || pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.session_main',
  pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.session_cancelled',
  pg_catalog.gen_random_uuid()::text,
  true
);
SELECT pg_catalog.set_config(
  'task7.session_stale',
  pg_catalog.gen_random_uuid()::text,
  true
);

CREATE TEMPORARY TABLE task7_rpc_results (
  scenario text PRIMARY KEY,
  result jsonb NOT NULL
) ON COMMIT DROP;

INSERT INTO public.application_sessions (id, company_id, line_user_id, status)
VALUES
  (
    pg_catalog.current_setting('task7.session_main')::uuid,
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'active'
  ),
  (
    pg_catalog.current_setting('task7.session_cancelled')::uuid,
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'cancelled'
  ),
  (
    pg_catalog.current_setting('task7.session_stale')::uuid,
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'active'
  );

INSERT INTO task7_rpc_results (scenario, result)
VALUES (
  'first completion',
  public.complete_application_session(
    pg_catalog.current_setting('task7.session_main')::uuid,
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'Task 7 synthetic applicant',
    NULL,
    'Synthetic role',
    'First completion',
    'synthetic-new',
    'task7-first-event'
  )
);

SELECT is(
  (SELECT result ->> 'created' FROM task7_rpc_results WHERE scenario = 'first completion'),
  'true',
  'first completion reports that it created an applicant'
);
SELECT is(
  (SELECT result ->> 'already_completed' FROM task7_rpc_results WHERE scenario = 'first completion'),
  'false',
  'first completion is not reported as a replay'
);
SELECT ok(
  (SELECT result ? 'applicant' FROM task7_rpc_results WHERE scenario = 'first completion'),
  'first completion returns the applicant payload'
);
SELECT is(
  (
    SELECT pg_catalog.count(*)::integer
    FROM public.applicants AS applicant
    WHERE applicant.application_session_id = pg_catalog.current_setting('task7.session_main')::uuid
      AND applicant.company_id = pg_catalog.current_setting('task7.company_a')
      AND applicant.line_user_id = pg_catalog.current_setting('task7.user_a')
  ),
  1,
  'first completion creates exactly one scoped applicant'
);
SELECT is(
  (
    SELECT session.status
    FROM public.application_sessions AS session
    WHERE session.id = pg_catalog.current_setting('task7.session_main')::uuid
      AND session.company_id = pg_catalog.current_setting('task7.company_a')
      AND session.line_user_id = pg_catalog.current_setting('task7.user_a')
  ),
  'completed',
  'first completion marks the scoped session completed'
);

INSERT INTO task7_rpc_results (scenario, result)
VALUES (
  'exact replay',
  public.complete_application_session(
    pg_catalog.current_setting('task7.session_main')::uuid,
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'Task 7 synthetic applicant',
    NULL,
    'Synthetic role',
    'First completion',
    'synthetic-new',
    'task7-replay-event'
  )
);

SELECT is(
  (SELECT result FROM task7_rpc_results WHERE scenario = 'exact replay'),
  '{"created": false, "already_completed": true}'::jsonb,
  'exact replay preserves the Backend-visible idempotency response'
);
SELECT is(
  (
    SELECT pg_catalog.count(*)::integer
    FROM public.applicants AS applicant
    WHERE applicant.application_session_id = pg_catalog.current_setting('task7.session_main')::uuid
      AND applicant.company_id = pg_catalog.current_setting('task7.company_a')
      AND applicant.line_user_id = pg_catalog.current_setting('task7.user_a')
  ),
  1,
  'exact replay does not create another applicant'
);

SELECT throws_ok(
  pg_catalog.format(
    'SELECT public.complete_application_session(%L::uuid, %L, %L, NULL, NULL, NULL, NULL, %L, NULL)',
    pg_catalog.current_setting('task7.session_cancelled'),
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'synthetic-new'
  ),
  'P0001',
  'application session is not active',
  'cancelled sessions are rejected'
);
SELECT is(
  (
    SELECT session.status
    FROM public.application_sessions AS session
    WHERE session.id = pg_catalog.current_setting('task7.session_cancelled')::uuid
  ),
  'cancelled',
  'cancelled session remains cancelled after rejection'
);

SELECT throws_ok(
  pg_catalog.format(
    'SELECT public.complete_application_session(%L::uuid, %L, %L, NULL, NULL, NULL, NULL, %L, NULL)',
    pg_catalog.current_setting('task7.session_main'),
    pg_catalog.current_setting('task7.company_b'),
    pg_catalog.current_setting('task7.user_a'),
    'synthetic-new'
  ),
  'P0001',
  'application session not found',
  'cross-company completion is rejected'
);
SELECT throws_ok(
  pg_catalog.format(
    'SELECT public.complete_application_session(%L::uuid, %L, %L, NULL, NULL, NULL, NULL, %L, NULL)',
    pg_catalog.current_setting('task7.session_main'),
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_b'),
    'synthetic-new'
  ),
  'P0001',
  'application session not found',
  'cross-user completion is rejected'
);

INSERT INTO public.applicants (
  company_id,
  application_session_id,
  line_user_id,
  name,
  status
)
VALUES (
  pg_catalog.current_setting('task7.company_b'),
  pg_catalog.current_setting('task7.session_stale')::uuid,
  pg_catalog.current_setting('task7.user_b'),
  'Task 7 stale synthetic applicant',
  'synthetic-new'
);

SELECT throws_ok(
  pg_catalog.format(
    'SELECT public.complete_application_session(%L::uuid, %L, %L, NULL, NULL, NULL, NULL, %L, NULL)',
    pg_catalog.current_setting('task7.session_stale'),
    pg_catalog.current_setting('task7.company_a'),
    pg_catalog.current_setting('task7.user_a'),
    'synthetic-new'
  ),
  '23505',
  'duplicate key value violates unique constraint "uq_applicants_application_session"',
  'a stale cross-scope applicant cannot be reused or duplicated'
);
SELECT is(
  (
    SELECT session.status
    FROM public.application_sessions AS session
    WHERE session.id = pg_catalog.current_setting('task7.session_stale')::uuid
      AND session.company_id = pg_catalog.current_setting('task7.company_a')
      AND session.line_user_id = pg_catalog.current_setting('task7.user_a')
  ),
  'active',
  'stale duplicate rejection leaves the scoped session active'
);
SELECT is(
  (
    SELECT pg_catalog.count(*)::integer
    FROM public.applicants AS applicant
    WHERE applicant.application_session_id = pg_catalog.current_setting('task7.session_stale')::uuid
      AND applicant.company_id = pg_catalog.current_setting('task7.company_a')
      AND applicant.line_user_id = pg_catalog.current_setting('task7.user_a')
  ),
  0,
  'stale duplicate rejection creates no scoped applicant'
);
SELECT is(
  (
    SELECT pg_catalog.count(*)::integer
    FROM public.applicants AS applicant
    WHERE applicant.application_session_id = pg_catalog.current_setting('task7.session_stale')::uuid
  ),
  1,
  'stale duplicate prevention preserves only the pre-existing applicant'
);

SELECT * FROM finish();

ROLLBACK;
