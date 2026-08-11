# Staging Supabase Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 空のSupabase projectから、productionのcurrent-state構造、fail-closed権限、既存問い合わせworkflowを再現できるcanonical migration chainを、productionを変更せず構築・検証する。

**Architecture:** Productionの監査済み構造をbusiness dataなしのbaseline migrationへ写し、直後の独立security migrationでclient rolesを遮断する。2026年7月の4 migrationはhash付きarchiveへ移し、2026年8月の問い合わせ4 migrationは内容・version・filenameを維持する。Local replay、構造fingerprint、権限negative test、application回帰をすべて通した後だけ、承認済みSupabase CLI経路から空のstagingへ全chainを適用する。

**Tech Stack:** PostgreSQL / PL/pgSQL, Supabase CLI, Docker-compatible local runtime, pgTAP, Python 3.12 `unittest`, FastAPI/Supabase Python client, Node.js 24 / Next.js 14.

## Global Constraints

- 唯一の仕様は `docs/superpowers/specs/2026-08-10-staging-supabase-baseline-design.md` とする。仕様変更が必要なら実装を止め、同specの別承認を得る。
- Production project `dcexrqivikbchxawjzsn`はread-only参照元である。全Taskで`db push`、migration apply、`migration repair`、DDL、DML、function invocation、schema/history変更を禁止する。
- Staging project `eygotkbexkjzzvcxqfea`への変更はTask 15まで禁止する。Task 15もユーザーの明示承認がなければ実行しない。
- Productionとstagingのproject refを同一terminalへ同時linkしない。Production refをSupabase CLIへ渡さない。
- Read-only MCPをwrite可能へ変更しない。Staging applyはTask 15で固定する承認済みSupabase CLI deployment経路だけを使う。
- Migrationへbusiness row、production tenant literal、API key、URL、LINE identifier、Auth user、Storage object、PIIを含めない。
- `supabase/baselines/2026-07-24-public-schema-baseline.sql`は監査資料として維持し、直接applyしない。
- Existing inquiry migrations `202608070001`〜`202608070004`はbyte-for-byte維持する。
- Baselineとsecurity migrationの数値versionはTask 2のGate出力で確定する。このplanでは推測しない。
- Task 2が生成する `supabase/migration-chain.lock.json` の `baseline_path` と `security_path` を、以後のTaskにおけるmigration fileの具体的repo-relative pathとする。Gate通過前にmigration fileを作らない。
- Baselineとsecurityは同じPR/review単位とし、stagingでは一回のapproved `supabase db push --linked`内で問い合わせ4 migrationとともにversion順で連続適用する。全6 migrationの成功とsecurity post-state確認までBackend/Frontend/Render/LINE webhookをstagingへ接続しない。
- Stagingの途中失敗をhistory repairや手動DDLで直さない。空のdisposable project再作成はユーザーの別承認を得る。
- SQL migrationを変更するTaskでは必ず、先に失敗するstaticまたはpgTAP testを追加し、REDの原因を記録してから最小実装へ進む。
- 各commit直前に `git diff --check`、`git status --short`、対象testを実行する。無関係な差分をcommitしない。
- Supabase CLI、Docker、psqlは2026-08-11の計画時点の端末では未導入である。実装担当者は勝手にinstallせず、Task 1の承認Gateを通す。

## Fixed Existing Interfaces

- Backend client creation: `backend/main.py:39-46` の `SUPABASE_URL` / `SUPABASE_KEY` と `create_client(...)`。
- Application completion call: `backend/main.py` の `handle_message(...)`内 `supabase.rpc("complete_application_session", payload).execute()`。
- RPC signature: `public.complete_application_session(p_session_id uuid, p_company_id text, p_line_user_id text, p_name text, p_phone text, p_job text, p_motivation text, p_applicant_status text, p_event_id text default null) returns jsonb`。
- RPC result contract: first completion returns `created`, `already_completed`, `applicant`; completed replay returns `created=false`, `already_completed=true` without a second applicant insert。
- Update trigger function: `public.set_updated_at() returns trigger`。
- Existing inquiry migration order:
  1. `supabase/migrations/202608070001_inquiry_workflow_columns.sql`
  2. `supabase/migrations/202608070002_inquiry_replies.sql`
  3. `supabase/migrations/202608070003_line_message_log_inquiry_reply.sql`
  4. `supabase/migrations/202608070004_finalize_inquiry_reply.sql`
- Backend full regression command: from `backend/`, `python -m unittest discover -s tests -p "test_*.py" -v`。
- Frontend regression commands: from `frontend/`, `npm ci`, `npm run typecheck`, `npm run build`。

---

### Task 1: Isolate implementation and establish the toolchain Gate

**Files:**
- Create: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- Read: `docs/superpowers/specs/2026-08-10-staging-supabase-baseline-design.md`
- Read: `.github/workflows/ci.yml`
- Read: `backend/requirements-dev.txt`
- Read: `frontend/package.json`

**Interfaces:**
- Consumes: approved design commit `691a3aa90ec45ed1ba8a2715af06641cff6f5c68` and clean implementation base.
- Produces: isolated branch/worktree, exact CLI/Docker versions, initial regression evidence, and an explicit GO/NO-GO record.

- [ ] From the current repository, create the implementation isolation required by `using-git-worktrees`: `git worktree add -b agent/staging-supabase-baseline-implementation ../line-recruit-staging-supabase-baseline 691a3aa90ec45ed1ba8a2715af06641cff6f5c68`.
- [ ] In the new worktree, run `git status --short`, `git branch --show-current`, and `git rev-parse HEAD`; expect an empty status, branch `agent/staging-supabase-baseline-implementation`, and the approved design commit.
- [ ] Run `Get-Command supabase,docker,psql -ErrorAction SilentlyContinue`. If Supabase CLI or Docker-compatible runtime is absent, stop and request approval for the exact installation/version policy; do not start Task 2.
- [ ] After approved installation, record `supabase --version`, `docker version --format '{{.Server.Version}}'`, `python --version`, `node --version`, and `npm --version` in the verification report. Do not record credentials, URLs, tokens, or Docker environment details beyond versions.
- [ ] Run the starting regression: `python -m pip check`; `python -m compileall backend`; from `backend/`, `python -m unittest discover -s tests -p "test_*.py" -v`; from `frontend/`, `npm ci`, `npm run typecheck`, `npm run build`.
- [ ] Expected RED/stop result: any missing tool, dirty worktree, wrong base commit, failing regression, or unapproved installation produces `NO-GO: Task 1` in the report and ends the run without migration files.
- [ ] Expected GREEN result: all tools have recorded versions and the existing Backend/Frontend checks pass.
- [ ] Run `git diff --check` and commit only the sanitized evidence: `git add docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "docs: record baseline implementation preflight"`.

### Task 2: Select migration versions through a reviewed, machine-readable Gate

**Files:**
- Create: `backend/tests/test_staging_migration_chain.py`
- Create: `supabase/migration-chain.lock.json`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- Read: `supabase/migrations/*.sql`

**Interfaces:**
- Consumes: exact Supabase CLI version from Task 1, repository migration prefixes, staging history from project `eygotkbexkjzzvcxqfea`.
- Produces: concrete `baseline_version`, `security_version`, `baseline_path`, `security_path`, CLI version, inquiry migration SHA-256 values, and approved database role in `supabase/migration-chain.lock.json`.

- [ ] Write `backend/tests/test_staging_migration_chain.py` first. It must fail while the lock file is absent and must require: numeric versions matching the existing 12-digit convention; `baseline_version < security_version < 202608070001`; no collision in `git log --all --name-only -- supabase`; exact suffixes `public_schema_current_state_baseline.sql` and `fail_closed_security_privileges.sql`; `backend_database_role == "service_role"`; and SHA-256 entries for all four inquiry files.
- [ ] Run from `backend/`: `python -m unittest tests.test_staging_migration_chain -v`. Expected RED: missing `supabase/migration-chain.lock.json`.
- [ ] Verify the staging MCP configuration only: `codex mcp list` must show `supabase-staging`, project ref `eygotkbexkjzzvcxqfea`, `read_only=true`, enabled OAuth. Production MCP is not invoked.
- [ ] Use `supabase link --project-ref eygotkbexkjzzvcxqfea` in the isolated worktree, then `supabase migration list --linked`. Expect remote history 0. If OAuth/DB connection fails, project ref differs, or any remote version exists, record `NO-GO: Task 2` and stop before creating the lock file.
- [ ] Enumerate every numeric migration prefix from current files and `git log --all --name-only -- supabase/migrations`. Candidate versions must be two unused 12-digit values strictly before `202608070001`, ordered baseline then security, and accepted by the exact Supabase CLI version when listed locally.
- [ ] Record the two candidate versions and derived exact paths in the report and obtain explicit PR review approval of both values. No migration file is created during this review.
- [ ] Create `supabase/migration-chain.lock.json` with the approved concrete values, `supabase_cli_version`, `backend_database_role: "service_role"`, all six final active paths in order, and SHA-256 values for the four inquiry migration files.
- [ ] Run `python -m unittest tests.test_staging_migration_chain -v`. Expected GREEN: one unambiguous six-file chain and no version collision.
- [ ] Run `git diff --check` and commit: `git add backend/tests/test_staging_migration_chain.py supabase/migration-chain.lock.json docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "test: lock staging migration order"`.

### Task 3: Archive the 2026-07 legacy migrations byte-for-byte

**Files:**
- Modify: `backend/tests/test_staging_migration_chain.py`
- Create: `supabase/legacy_migrations/2026-07-pre-baseline/MANIFEST.md`
- Move without content change:
  - `supabase/migrations/202607190001_mvp_security_foundation.sql` -> `supabase/legacy_migrations/2026-07-pre-baseline/202607190001_mvp_security_foundation.sql`
  - `supabase/migrations/202607190002_admin_configuration.sql` -> `supabase/legacy_migrations/2026-07-pre-baseline/202607190002_admin_configuration.sql`
  - `supabase/migrations/202607200001_application_sessions.sql` -> `supabase/legacy_migrations/2026-07-pre-baseline/202607200001_application_sessions.sql`
  - `supabase/migrations/202607210001_applicant_tags.sql` -> `supabase/legacy_migrations/2026-07-pre-baseline/202607210001_applicant_tags.sql`

**Interfaces:**
- Consumes: four active July files and their first-add Git commits.
- Produces: immutable archive plus manifest containing original filename, SHA-256, original commit, artifact relationship, unproven remote-history status, and archive reason.

- [ ] Extend `test_staging_migration_chain.py` to require all four archive files, reject those four prefixes under `supabase/migrations/`, and recompute each manifest SHA-256. Run the test before moving files; expected RED is missing archive/manifest and legacy files still active.
- [ ] Before any move, run `Get-FileHash -Algorithm SHA256` and `git log --diff-filter=A --format=%H --` separately for `supabase/migrations/202607190001_mvp_security_foundation.sql`, `supabase/migrations/202607190002_admin_configuration.sql`, `supabase/migrations/202607200001_application_sessions.sql`, and `supabase/migrations/202607210001_applicant_tags.sql`. Record only filenames, hashes, and commit IDs.
- [ ] Use `git mv` for all four files. Do not normalize line endings or formatting.
- [ ] Create `MANIFEST.md` with one row per file and the exact evidence required by the design. State that production artifacts correspond structurally but remote migration application is unproven, and that the canonical chain must not replay these files.
- [ ] Verify byte identity by hashing the four blobs returned by `git show HEAD:supabase/migrations/202607190001_mvp_security_foundation.sql`, `git show HEAD:supabase/migrations/202607190002_admin_configuration.sql`, `git show HEAD:supabase/migrations/202607200001_application_sessions.sql`, and `git show HEAD:supabase/migrations/202607210001_applicant_tags.sql`; compare them with the archived working-tree hashes and expect four exact matches.
- [ ] Run `python -m unittest tests.test_staging_migration_chain -v`. Expected GREEN: legacy files exist only under the archive and the four inquiry files remain active with original hashes.
- [ ] Run `git diff --check`, inspect `git diff --summary`, and commit: `git add backend/tests/test_staging_migration_chain.py supabase/migrations supabase/legacy_migrations && git commit -m "chore: archive pre-baseline migrations"`.

### Task 4: Characterize application company inserts and the current RPC contract

**Files:**
- Modify only if a missing case is found:
  - `backend/tests/test_applicant_tenant_scope.py`
  - `backend/tests/test_dashboard_inquiry_tenant_scope.py`
  - `backend/tests/test_interview_message_tenant_scope.py`
  - `backend/tests/test_faq_status_session_tenant_scope.py`
- Create: `backend/tests/test_application_session_rpc_contract.py`
- Read: `backend/main.py`

**Interfaces:**
- Consumes: `backend.main.handle_message`, `COMPANY_ID`, mocked Supabase query/RPC objects.
- Produces: tests proving six legacy-table inserts carry explicit company ID and the existing `complete_application_session` request/result behavior is preserved.

- [ ] Add the missing characterization cases before changing SQL. Cover `applicants`, `inquiries`, `interview_slots`, `line_message_logs`, `faq_categories`, and `faqs`; each insert assertion must inspect the payload and require `company_id == backend.main.COMPANY_ID`.
- [ ] In `test_application_session_rpc_contract.py`, model the current Backend call for a first completion and replay. Require the exact RPC name and parameter names from Fixed Existing Interfaces; require one applicant on replay and the documented JSON key behavior.
- [ ] Run from `backend/`: `python -m unittest tests.test_applicant_tenant_scope tests.test_dashboard_inquiry_tenant_scope tests.test_interview_message_tenant_scope tests.test_faq_status_session_tenant_scope tests.test_application_session_rpc_contract -v`.
- [ ] Expected RED: only a genuinely unprotected insert or missing RPC characterization may fail. If production code omits `company_id` or relies on a fixed default, stop this baseline branch and open a separate application-fix branch; do not add a tenant default to the baseline.
- [ ] Minimal implementation for this Task is tests only. Existing protected paths should become GREEN without `backend/main.py` changes.
- [ ] Run the focused suite again and then the Backend full suite. Expected GREEN: all explicit-company and RPC request tests pass.
- [ ] Run `git diff --check` and commit test-only changes: `git add backend/tests && git commit -m "test: characterize baseline application contracts"`.

### Task 5: Create the secure `set_updated_at()` contract first

**Files:**
- Modify: `backend/tests/test_staging_migration_chain.py`
- Create: path equal to `baseline_path` in `supabase/migration-chain.lock.json`

**Interfaces:**
- Consumes: locked baseline path and `public.set_updated_at() returns trigger` signature.
- Produces: the first minimal baseline migration content defining only the approved extension and secure trigger function contract.

- [ ] Add a failing static test requiring the baseline file to: begin a transaction; ensure only `pgcrypto` among application-required extensions; define `public.set_updated_at()` as `SECURITY INVOKER`; set `search_path = pg_catalog`; assign `NEW.updated_at` using a `pg_catalog`-qualified time function; and contain no grant to PUBLIC/anon/authenticated.
- [ ] Run `python -m unittest tests.test_staging_migration_chain -v`. Expected RED: locked baseline path does not exist.
- [ ] Create the migration at the exact locked `baseline_path` with the minimal extension/function definition and transaction boundary. Do not add tables or the application completion function yet.
- [ ] Run the focused test. Expected GREEN: the function contract is fixed and the file contains no business DML.
- [ ] Read `baseline_path` from `supabase/migration-chain.lock.json`, pass that exact value as the path argument to `git diff --`, and verify the migration contains no key, URL, tenant literal, row insert, update, or delete.
- [ ] Run `git diff --check` and commit: `git add backend/tests/test_staging_migration_chain.py supabase/migration-chain.lock.json supabase/migrations && git commit -m "feat: secure baseline timestamp function"`.

### Task 6: Implement the current-state structural baseline

**Files:**
- Modify: path equal to `baseline_path` in `supabase/migration-chain.lock.json`
- Modify: `backend/tests/test_staging_migration_chain.py`
- Create: `supabase/tests/fixtures/production-public-schema-contract.json`
- Read: `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`
- Read: `supabase/baselines/2026-07-24-public-schema-baseline.sql`

**Interfaces:**
- Consumes: approved base inventory of 12 tables, 19 constraints, 43 indexes, 7 triggers, 2 function signatures; sanitized schema evidence.
- Produces: deterministic structural DDL for the 12 tables, 19 constraints, 43 indexes, and 7 triggers, with no business rows or fixed tenant default.

- [ ] Create the machine-readable fixture first with exact base object names, column types/nullability/non-tenant defaults, constraint definitions, index definitions, and trigger definitions derived from the approved spec and sanitized snapshot. Mark the completion RPC body as separately tested in Task 7.
- [ ] Extend `test_staging_migration_chain.py` to load the fixture and require every named table/column/constraint/index/trigger in the baseline; require exactly the six legacy nullable `company_id` columns to omit defaults; require settings tables and `application_sessions.company_id` to remain NOT NULL without a tenant default; require `contacts` to have no `company_id`; reject top-level business DML.
- [ ] Run `python -m unittest tests.test_staging_migration_chain -v`. Expected RED: the minimal baseline from Task 5 lacks the structural inventory.
- [ ] Add only the approved structural DDL to the locked baseline path. Use schema-qualified public objects. Create every trigger against its explicit `public` table name and execute `public.set_updated_at()`.
- [ ] Do not copy the incomplete body from `supabase/baselines/2026-07-24-public-schema-baseline.sql`; Task 7 owns the completion function.
- [ ] Run the focused test. Expected GREEN: base object contract is complete and fixed tenant defaults/business rows are absent.
- [ ] Run `python -m unittest tests.test_staging_migration_chain tests.test_inquiry_migrations -v` to prove the existing inquiry prerequisites remain compatible.
- [ ] Run `git diff --check` and commit: `git add backend/tests/test_staging_migration_chain.py supabase/tests/fixtures/production-public-schema-contract.json supabase/migrations && git commit -m "feat: add current-state structural baseline"`.

### Task 7: Strengthen `complete_application_session()` inside the baseline

**Files:**
- Modify: path equal to `baseline_path` in `supabase/migration-chain.lock.json`
- Modify: `backend/tests/test_staging_migration_chain.py`
- Create: `backend/tests/test_local_application_session_rpc.py`
- Create: `supabase/tests/database/0001_application_session_functions.test.sql`

**Interfaces:**
- Consumes: existing RPC signature and JSON contract, `public.application_sessions`, `public.applicants`.
- Produces: `SECURITY INVOKER` RPC with fixed search path, tenant predicates, row locking, idempotency, and unchanged Backend-visible result contract.

- [ ] Add static tests first requiring: `SECURITY INVOKER`; `SET search_path = pg_catalog`; only `public.application_sessions` and `public.applicants` table references; initial session predicate `id + company_id + line_user_id`; `FOR UPDATE`; applicant lookup predicate `application_session_id + company_id + line_user_id`; explicit `company_id` insert; scoped session update with affected-row verification; idempotent completed branch; rejection of cancelled/non-active state.
- [ ] Add pgTAP scenarios in `0001_application_session_functions.test.sql` for first completion, exact replay, cancelled session rejection, cross-company session rejection, cross-user rejection, and stale duplicate applicant prevention. Wrap all cases in transactions and rollback synthetic rows.
- [ ] Add `test_local_application_session_rpc.py` for the concurrency contract. Default it to skipped unless `RUN_LOCAL_DB_TESTS=1`; in `setUpClass`, invoke `supabase status -o json`, parse the local API URL/server key in memory without printing them, and reject both remote project refs before any request. Use two `ThreadPoolExecutor` callers with the same session/company/user; assert both calls complete according to the idempotency contract and a scoped applicant count is exactly one.
- [ ] Run the static focused test before editing the migration. Expected RED: `complete_application_session()` is absent.
- [ ] Add the minimal reviewed function body to the locked baseline path without changing the Fixed Existing Interfaces signature or response keys.
- [ ] Run the static test. Expected GREEN: all security/contract clauses are present.
- [ ] Defer execution of pgTAP until Task 10 local stack exists; at this point run a syntax-oriented review that rejects `SECURITY DEFINER`, unqualified business tables, unscoped update, and dynamic SQL.
- [ ] Run `git diff --check` and commit: `git add backend/tests/test_staging_migration_chain.py backend/tests/test_local_application_session_rpc.py supabase/tests/database/0001_application_session_functions.test.sql supabase/migrations && git commit -m "feat: harden application completion rpc"`.

### Task 8: Implement the fail-closed privilege migration

**Files:**
- Modify: `backend/tests/test_staging_migration_chain.py`
- Create: path equal to `security_path` in `supabase/migration-chain.lock.json`
- Create: `supabase/tests/database/0002_fail_closed_security.test.sql`

**Interfaces:**
- Consumes: 12 base tables, two application functions, database role `service_role`, Supabase-managed roles that must remain intact.
- Produces: RLS-enabled/policy-zero base tables, least-privilege object ACLs, restricted function execution, safe schema/default ACLs.

- [ ] Add static tests first requiring explicit RLS enablement for `public.app_settings`, `public.applicant_status_settings`, `public.applicants`, `public.application_sessions`, `public.contacts`, `public.faq_categories`, `public.faq_settings`, `public.faqs`, `public.inquiries`, `public.interview_slots`, `public.line_message_logs`, and `public.question_tree_settings`, while rejecting FORCE RLS/policy creation. Require explicit revoke from PUBLIC, anon, authenticated for business tables and both functions; explicit server-role grants only; public schema CREATE revocation from client roles; and default privilege revocation for tables, functions, and sequences from client roles.
- [ ] Require the test to reject role alteration, Supabase-managed schema changes, broad `GRANT ALL`, grants to browser roles, owner changes, and any policy creation.
- [ ] Write `0002_fail_closed_security.test.sql` first. It must assert policy count 0, RLS enabled/FORCE disabled, no table CRUD/SELECT privilege for anon/authenticated, no RPC execute for PUBLIC/anon/authenticated, required service-role access, and no automatic client grant on a transaction-local test table/function/sequence created by the migration owner.
- [ ] Run `python -m unittest tests.test_staging_migration_chain -v`. Expected RED: locked security path is absent.
- [ ] Create the locked security migration with explicit object lists and approved roles. Do not use wildcard grants that could affect Supabase-managed objects. Do not create tenant policies.
- [ ] Run the focused static test. Expected GREEN: fail-closed contract is exact.
- [ ] Defer pgTAP execution to Task 10, run `git diff --check`, and commit: `git add backend/tests/test_staging_migration_chain.py supabase/tests/database/0002_fail_closed_security.test.sql supabase/migrations && git commit -m "security: fail close staging database privileges"`.

### Task 9: Protect the existing inquiry migrations and full dependency chain

**Files:**
- Modify: `backend/tests/test_staging_migration_chain.py`
- Modify: `backend/tests/test_inquiry_migrations.py` only when an ordering assertion is absent
- Read without modification:
  - `supabase/migrations/202608070001_inquiry_workflow_columns.sql`
  - `supabase/migrations/202608070002_inquiry_replies.sql`
  - `supabase/migrations/202608070003_line_message_log_inquiry_reply.sql`
  - `supabase/migrations/202608070004_finalize_inquiry_reply.sql`

**Interfaces:**
- Consumes: Task 2 inquiry hashes and locked six-file order.
- Produces: regression guard proving inquiry files are unchanged and each dependency is provided by the preceding migration state.

- [ ] Add tests that recompute all four SHA-256 values, require filenames/versions unchanged, and assert the active directory contains only the two locked new migrations plus the four inquiry migrations.
- [ ] Add dependency assertions: baseline provides `inquiries`, `line_message_logs`, `set_updated_at`, and UUID generation; migration 1 provides inquiry composite unique; migration 2 provides `inquiry_replies`; migration 3 provides correlation; migration 4 provides `finalize_inquiry_reply`.
- [ ] Temporarily alter an in-memory SQL string in the test, not a repository migration, to prove hash/order checks fail on renamed, reordered, or modified inquiry content. Expected RED is the deliberate in-memory mutation being rejected.
- [ ] Run `python -m unittest tests.test_staging_migration_chain tests.test_inquiry_migrations -v`. Expected GREEN on repository files.
- [ ] Run `git diff --exit-code -- supabase/migrations/202608070001_inquiry_workflow_columns.sql supabase/migrations/202608070002_inquiry_replies.sql supabase/migrations/202608070003_line_message_log_inquiry_reply.sql supabase/migrations/202608070004_finalize_inquiry_reply.sql`; expect no output.
- [ ] Run `git diff --check` and commit test changes: `git add backend/tests/test_staging_migration_chain.py backend/tests/test_inquiry_migrations.py && git commit -m "test: protect canonical inquiry migration chain"`.

### Task 10: Replay the full chain from an empty local database

**Files:**
- Create: `supabase/config.toml`
- Create: `supabase/tests/database/0003_baseline_structure.test.sql`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`

**Interfaces:**
- Consumes: locked six-file chain, approved CLI/Docker versions.
- Produces: two clean local replays, six-version local history, passing pgTAP/function tests, and lint evidence.

- [ ] Run `supabase init` only if `supabase/config.toml` is absent. Review the generated config and remove generated example/seed entries that would insert data; keep only local project configuration needed by CLI.
- [ ] Write `0003_baseline_structure.test.sql` before replay. Assert the 12 base tables, base columns/nullability/default rules, 19 base constraints, 43 named base indexes, 7 named base triggers, and two functions. Assert inquiry objects separately so they do not change the base inventory count.
- [ ] Run `supabase start`. If Docker is unavailable, memory/disk is insufficient, or CLI version differs from the lock file, record `NO-GO: Task 10` and stop.
- [ ] Run `supabase db reset --local --no-seed`. Expected first GREEN: all six migrations apply in the locked order from an empty DB.
- [ ] Run `supabase migration list --local`; expect exactly the two locked versions followed by `202608070001`, `202608070002`, `202608070003`, `202608070004`.
- [ ] Run `supabase db lint --local --level error` and `supabase test db`; expected GREEN includes `0001_application_session_functions`, `0002_fail_closed_security`, and `0003_baseline_structure`.
- [ ] Set `RUN_LOCAL_DB_TESTS=1`, then from `backend/` run `python -m unittest tests.test_local_application_session_rpc -v`. The test module itself obtains local-only credentials from `supabase status -o json` without printing them; expect two successful/idempotent calls and one scoped applicant.
- [ ] Destroy/recreate only the local database with `supabase db reset --local --no-seed` and rerun `supabase test db`. Expect identical object assertions on the second replay.
- [ ] Record command, CLI version, test count, and outcome only; do not commit local connection strings or `.temp` content.
- [ ] Run `git diff --check` and commit: `git add supabase/config.toml supabase/tests/database/0003_baseline_structure.test.sql docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "test: replay staging schema from empty database"`.

### Task 11: Prove structural equivalence and intentional security differences

**Files:**
- Create: `backend/tests/test_schema_contract_fixture.py`
- Create: `scripts/render_schema_contract_test.py`
- Modify: `supabase/tests/fixtures/production-public-schema-contract.json`
- Create: `supabase/tests/database/0004_schema_equivalence.test.sql`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`

**Interfaces:**
- Consumes: approved production structural reference, local post-chain catalog, intentional-difference rules.
- Produces: separate structural and security fingerprints with zero unexplained structural differences.

- [ ] Write `test_schema_contract_fixture.py` first. Require exact inventory totals, unique object keys, no row values/tenant literals/secrets, and explicit intentional differences: six removed tenant defaults, hardened function definitions, fail-closed ACL/RLS.
- [ ] Run `python -m unittest tests.test_schema_contract_fixture -v`. Expected RED until the fixture contains normalized definitions and intentional-difference classifications for every approved difference.
- [ ] Complete the fixture from `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql` and the approved design; do not query production business tables.
- [ ] Create `scripts/render_schema_contract_test.py` using only the Python standard library. It must read the JSON fixture, deterministically render `0004_schema_equivalence.test.sql`, and support `--check` to fail when the committed SQL differs. The generated pgTAP must compare the local catalog against fixture object sets for tables, columns, types, nullability, non-tenant defaults, constraints, indexes, triggers, and function signatures, reporting unexpected and missing names separately.
- [ ] Run `python scripts/render_schema_contract_test.py --check` before generating the SQL. Expected RED: `0004_schema_equivalence.test.sql` is absent or differs.
- [ ] Run `python scripts/render_schema_contract_test.py`, then rerun with `--check`. Expected GREEN: deterministic output matches the committed SQL.
- [ ] Run `supabase test db`. Expected GREEN: structural reference matches except the explicitly approved company-default/function-security/ACL/RLS differences.
- [ ] Store only object counts, normalized hashes, and named differences in the report. Do not store database URLs or row data.
- [ ] Run `git diff --check` and commit: `git add backend/tests/test_schema_contract_fixture.py scripts/render_schema_contract_test.py supabase/tests/fixtures/production-public-schema-contract.json supabase/tests/database/0004_schema_equivalence.test.sql docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "test: prove baseline schema equivalence"`.

### Task 12: Execute fail-closed negative tests with the backend role positive control

**Files:**
- Modify: `supabase/tests/database/0002_fail_closed_security.test.sql`
- Create: `supabase/tests/database/0005_default_privileges.test.sql`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`

**Interfaces:**
- Consumes: local post-chain roles/ACL/RLS and `backend_database_role` from the lock file.
- Produces: executable evidence that browser roles are denied and the approved server role can perform required operations.

- [ ] Add negative pgTAP cases for anon and authenticated SELECT/INSERT/UPDATE/DELETE against each base business table and `inquiry_replies`; add execute-denied cases for `set_updated_at`, `complete_application_session`, and `finalize_inquiry_reply` where callable signatures permit catalog privilege checks.
- [ ] Add the positive control using `SET LOCAL ROLE service_role`: schema usage, required table operations, and RPC execute privilege must be present. Keep test rows synthetic and wrap them in rollback.
- [ ] In `0005_default_privileges.test.sql`, create transaction-local objects as the same owner used by migrations; assert anon/authenticated receive no table, sequence, or function privilege, then rollback.
- [ ] Before any security SQL adjustment, run `supabase test db`. Expected RED must identify the exact missing revoke/grant/default ACL assertion; unrelated test failure stops the Task.
- [ ] Make the minimum change only in the locked security migration, reset local DB from empty, and rerun `supabase test db`.
- [ ] Expected GREEN: anon/authenticated have no business access or RPC execute; service_role has only required access; policy count remains 0; RLS remains enabled and FORCE disabled.
- [ ] Run `supabase db lint --local --level error`, `git diff --check`, and commit: `git add supabase/tests/database/0002_fail_closed_security.test.sql supabase/tests/database/0005_default_privileges.test.sql supabase/migrations docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "test: verify fail-closed database access"`.

### Task 13: Run application regression and inquiry workflow contracts

**Files:**
- Modify only for regression evidence: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- Test: `backend/tests/test_application_session_rpc_contract.py`
- Test: `backend/tests/test_inquiry_migrations.py`
- Test: `backend/tests/test_inquiry_response_api.py`
- Test: `backend/tests/test_inquiry_response_delivery.py`
- Test: `backend/tests/test_inquiry_response_policy.py`
- Test: `backend/tests/test_inquiry_rollout_docs.py`

**Interfaces:**
- Consumes: full local schema and unchanged application source.
- Produces: full Backend/Frontend regression evidence and a NO-GO on any contract regression.

- [ ] Run focused Backend tests first from `backend/`: `python -m unittest tests.test_application_session_rpc_contract tests.test_inquiry_migrations tests.test_inquiry_response_api tests.test_inquiry_response_delivery tests.test_inquiry_response_policy tests.test_inquiry_rollout_docs -v`.
- [ ] Expected RED handling: any RPC JSON mismatch, company-scope regression, idempotency failure, delivery_unknown regression, or migration-contract failure stops the rollout. Fix only the migration responsible; do not weaken existing tests.
- [ ] Run `python -m pip check` and `python -m compileall backend`.
- [ ] Run the full Backend suite from `backend/`: `python -m unittest discover -s tests -p "test_*.py" -v`.
- [ ] From `frontend/`, run `npm ci`, `npm run typecheck`, and `npm run build`.
- [ ] Expected GREEN: all existing tests pass; no Backend/Frontend source change is needed solely for the baseline.
- [ ] Record exact test counts and build result, run `git diff --check`, and commit report-only evidence: `git add docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "docs: record baseline regression evidence"`.

### Task 14: Pass staging credential classification and read-only preflight Gates

**Files:**
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- Read: `backend/main.py`
- Read: `docs/STAGING_SUPABASE_BOOTSTRAP.md`
- Read: `docs/INQUIRY_RESPONSE_RUNBOOK.md`

**Interfaces:**
- Consumes: staging environment variable names and key metadata without values, `supabase-staging` read-only MCP, locked migration chain.
- Produces: credential classification, project identity, empty-schema/history proof, dry-run list, and explicit apply approval request.

- [ ] Confirm the deployed staging Backend, if one exists, uses only server-side `SUPABASE_URL` and `SUPABASE_KEY`; confirm neither value is in a `NEXT_PUBLIC_*` variable or browser bundle. Record only SET/UNSET and key category: service_role, secret, publishable, anon, or unknown.
- [ ] Accept only `service_role` or a Supabase secret key verified to execute as the database `service_role` while remaining server-only. If category/role cannot be proven, record `NO-GO: Task 14 credential` and stop.
- [ ] Run `codex mcp list`; require `supabase-staging`, project ref `eygotkbexkjzzvcxqfea`, `read_only=true`, enabled OAuth. Use that MCP for catalog/history read-only checks only. OAuth refresh failure, wrong project, non-empty business schema, non-zero business row count, or non-zero remote migration history is `NO-GO`.
- [ ] Verify staging remains disconnected from Backend, Frontend, Render, and LINE webhook. Confirm no production secret/data is present.
- [ ] Re-link the dedicated CLI worktree only to `eygotkbexkjzzvcxqfea`; run `supabase migration list --linked` and `supabase db push --dry-run --linked`.
- [ ] Expected dry-run: exactly six migrations in lock order and no seed/role file. Any additional, missing, or reordered version is `NO-GO`.
- [ ] Have a second reviewer compare the linked ref, project name, migration list, lock file, credential category, and dry-run output. Obtain explicit user approval for Task 15. Without that approval stop, even when all read-only checks are GREEN.
- [ ] Commit sanitized preflight evidence: `git add docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "docs: record staging baseline preflight"`.

### Task 15: Apply the canonical chain to empty staging through the approved path

**Files:**
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- No migration file modification is allowed during this Task.

**Interfaces:**
- Consumes: explicit user approval, Task 14 GREEN evidence, exact six-file chain.
- Produces: six remote history entries and verified fail-closed staging post-state.

- [ ] Immediately before apply, rerun `git status --short`, `git rev-parse HEAD`, `codex mcp list`, `supabase migration list --linked`, and `supabase db push --dry-run --linked`. Require a clean tree, approved commit, staging ref, remote history 0, and exactly six pending files.
- [ ] Confirm Backend/Frontend/Render/LINE remain disconnected from staging and no synthetic rows exist.
- [ ] Run exactly one approved write command: `supabase db push --linked`. This is the formal migration deployment path; do not use MCP, Dashboard SQL Editor, `db pull`, `migration repair`, or `db reset --linked`.
- [ ] Treat non-zero exit, partial remote history, missing security version, or any SQL error as immediate stop. Do not retry blindly and do not repair. Keep applications disconnected and request approval to delete/recreate disposable staging from empty.
- [ ] On success, run read-only `supabase migration list --linked`; require all six versions in order. Verify catalog counts, function signatures, RLS/policy state, table/routine/schema grants, and default ACL against Tasks 11–12.
- [ ] Baseline and security are considered successful only when both remote history entries and all security assertions pass. Inquiry migrations are considered successful only when all four subsequent history entries and catalog assertions pass.
- [ ] Record only project ref, versions, normalized structural/security hashes, counts, timestamps, and pass/fail. Do not record credentials or rows.
- [ ] Commit sanitized apply evidence: `git add docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "docs: record staging baseline deployment"`.

### Task 16: Validate workflows using synthetic data only

**Files:**
- Create: `supabase/tests/database/0006_synthetic_workflows.test.sql`
- Create: `backend/tests/test_staging_synthetic_workflows.py`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`

**Interfaces:**
- Consumes: migrated staging schema, dedicated synthetic company/session/inquiry identifiers, server-only staging credential.
- Produces: DB behavior evidence for applicant, session, inquiry, LINE log, and inquiry reply without production data or real LINE delivery.

- [ ] Write local tests first. `0006_synthetic_workflows.test.sql` must cover session creation/resume/cancel/complete/replay, applicant creation, inquiry lifecycle, message-log correlation, inquiry reply finalization, cross-company rejection, and cleanup in a transaction.
- [ ] `test_staging_synthetic_workflows.py` must default to skipped unless `RUN_STAGING_DB_TESTS=1`, reject the production ref, require staging ref `eygotkbexkjzzvcxqfea`, generate synthetic UUIDs/text, and never print rows or credentials.
- [ ] Separate transport classes: DB-only/RPC checks run against staging; LINE transport checks run locally with the existing fake transport from inquiry response tests. No staging test calls the LINE API.
- [ ] Run local RED before adding test support; expected failure is missing synthetic fixture helper, not external connectivity.
- [ ] Add the minimal synthetic fixture/helper and run `supabase db reset --local --no-seed`, `supabase test db`, and the focused Python synthetic test in local/mock mode. Expect GREEN.
- [ ] After a separate user approval for synthetic writes, run the staging test with a server-only staging credential. Require cleanup in `finally`; then verify non-PII counts return to their pre-test values.
- [ ] Tests that would require actual LINE delivery are explicitly excluded from schema acceptance and remain unexecuted until a separate LINE sandbox design/approval. Existing mocked transport tests are the required transport proof here.
- [ ] Any cross-company visibility, duplicate applicant/reply/log, cleanup failure, or unknown external call is `NO-GO`; disable staging connection and stop.
- [ ] Run Backend full regression and `git diff --check`; commit: `git add supabase/tests/database/0006_synthetic_workflows.test.sql backend/tests/test_staging_synthetic_workflows.py docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "test: validate synthetic staging workflows"`.

### Task 17: Final verification, runbook alignment, and production protection

**Files:**
- Modify: `docs/STAGING_SUPABASE_BOOTSTRAP.md`
- Modify: `docs/SUPABASE_SCHEMA_RECONCILIATION.md`
- Modify: `docs/INQUIRY_RESPONSE_RUNBOOK.md`
- Modify: `docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md`
- Test: all files added or modified in Tasks 1–16.

**Interfaces:**
- Consumes: all local/staging evidence and final Git diff.
- Produces: implementation-complete branch with explicit production prohibition and reproducible runbook.

- [ ] Update the three runbooks to name the canonical six-file chain, legacy archive, exact approved versions from the lock file, local replay commands, staging deployment path, credential Gate, and disposable-staging rollback.
- [ ] Add a prominent production protection section: because production remote history is 0, production `db push`, migration apply, `migration repair`, and all schema/history changes remain prohibited until an independently approved production history-repair/cutover plan proves backup, equivalence, dry-run, and versions.
- [ ] Run the no-secret/data scan against changed files: reject key/token/JWT patterns, production project ref in executable CLI commands, LINE IDs, email/phone fixtures, and any INSERT outside transaction-rolled-back synthetic test files or function bodies.
- [ ] Run `python -m pip check`, `python -m compileall backend`, and from `backend/`, `python -m unittest discover -s tests -p "test_*.py" -v`.
- [ ] Run `supabase db reset --local --no-seed`, `supabase migration list --local`, `supabase db lint --local --level error`, and `supabase test db`.
- [ ] From `frontend/`, run `npm ci`, `npm run typecheck`, and `npm run build`.
- [ ] Verify all four archived hashes, all four inquiry hashes, exact active six-file order, structural equivalence, fail-closed ACL/RLS, RPC contracts, and no production/staging links or credentials committed.
- [ ] Run `git diff --check`, `git status --short`, and `git log --oneline 691a3aa90ec45ed1ba8a2715af06641cff6f5c68..HEAD`.
- [ ] Use `verification-before-completion`, then `requesting-code-review`. Resolve only evidence-backed findings and rerun every affected check.
- [ ] Commit runbook/report changes: `git add docs/STAGING_SUPABASE_BOOTSTRAP.md docs/SUPABASE_SCHEMA_RECONCILIATION.md docs/INQUIRY_RESPONSE_RUNBOOK.md docs/superpowers/reports/2026-08-11-staging-supabase-baseline-verification.md && git commit -m "docs: finalize staging baseline runbook"`.
- [ ] Use `finishing-a-development-branch`. Do not merge or apply anything to production automatically; present branch, commits, local/staging evidence, and remaining production NO-GO to the user.

## Task Dependency Map

```text
Task 1 tool/worktree Gate
  -> Task 2 version/history Gate
  -> Task 3 legacy archive
  -> Task 4 application characterization Gate
  -> Task 5 secure timestamp function
  -> Task 6 structural baseline
  -> Task 7 completion RPC
  -> Task 8 fail-closed security
  -> Task 9 inquiry-chain integrity
  -> Task 10 empty local replay
  -> Task 11 structural equivalence
  -> Task 12 security negative tests
  -> Task 13 application regression
  -> Task 14 staging credential/OAuth/read-only preflight Gate
  -> Task 15 approved staging apply
  -> Task 16 synthetic-only validation
  -> Task 17 final verification/runbooks
```

## Stop and Rollback Rules

1. **Before Task 2:** missing approved CLI/Docker, dirty base, or failing current regression stops without migration files.
2. **Task 2:** staging ref mismatch, OAuth/connection failure, remote history not 0, version collision, or unapproved version pair stops before the chain lock and migrations.
3. **Task 4:** any legacy-table insert depending on a database default stops baseline work for a separate application fix.
4. **Tasks 5–13:** local replay, catalog, security, function, Backend, typecheck, or build failure blocks staging preflight.
5. **Task 14:** unknown/browser-exposed credential, non-service server role, non-empty staging, unexpected dry-run, or absent user approval blocks all staging writes.
6. **Task 15:** partial apply or post-state mismatch keeps every application disconnected. No repair is attempted; disposable staging recreation requires separate approval.
7. **Task 16:** production-like data, actual LINE call, tenant leak, duplicate side effect, or cleanup failure stops validation and disconnects staging.
8. **Production:** no Task authorizes production mutation. Production remains NO-GO after successful staging validation.

## Acceptance Checklist

- [ ] Active migration directory contains exactly the locked baseline, locked security migration, and unchanged inquiry migrations 1–4.
- [ ] Legacy July files are byte-identical in the archive and verifiable by SHA-256/original commit.
- [ ] Empty local DB reaches the same result on two replays.
- [ ] Base inventory is 12 tables, 19 constraints, 43 indexes, 7 triggers, and 2 functions.
- [ ] Six legacy company columns have no fixed default; settings/session tenant columns retain approved NOT NULL behavior; contacts remains without company ID.
- [ ] `set_updated_at()` and `complete_application_session()` meet the fixed-search-path and privilege contracts.
- [ ] Browser roles cannot access business tables or application RPCs; service_role positive controls pass.
- [ ] Inquiry migrations remain byte-identical and execute after baseline/security.
- [ ] Backend full tests, Python compile, TypeScript typecheck, Next.js build, local lint, pgTAP, and synthetic checks pass.
- [ ] Staging apply has explicit approval/evidence, or the implementation stops before Task 15 and reports NO-GO.
- [ ] Production has received no schema, data, grant, RLS, or migration-history change.

## Official Command References

- Supabase migrations and remote history: <https://supabase.com/docs/guides/deployment/database-migrations>
- Supabase CLI `db push --dry-run`, `migration list`, `db reset`: <https://supabase.com/docs/reference/cli/supabase-projects-create>
- Database pgTAP tests and `supabase test db`: <https://supabase.com/docs/guides/local-development/testing/overview>
