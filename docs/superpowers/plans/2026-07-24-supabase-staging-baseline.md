# Supabase Staging Baseline Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a non-production Supabase public-schema baseline candidate and a safe staging bootstrap runbook without changing any database, migration history, external setting, or application source.

**Architecture:** Treat browser key exposure as a hard gate. If the gate passes, keep the candidate outside `supabase/migrations/`, preserve unresolved live defaults and the data-changing RPC as fail-closed, and adopt a new staging chain consisting of one approved baseline followed only by future migrations.

**Tech Stack:** FastAPI/Python, Next.js/TypeScript, PostgreSQL DDL, Supabase CLI/Docker as documented future prerequisites, Git.

## Global Constraints

- Do not expose or record any key, token, password, production URL, company identifier, applicant data, LINE identifier, or message body.
- Do not connect a browser Supabase client while live RLS is disabled.
- Do not change `backend/`, `frontend/`, the four existing files in `supabase/migrations/`, production schema, migration history, Auth, Storage, Render, or environment variables.
- Do not install Supabase CLI or Docker in this task.
- Do not apply the baseline candidate to any database.
- Commit and push only after all required verification succeeds.

---

### Task 1: Establish the clean branch and regression baseline

**Files:**

- Read: `AGENTS.md`
- Read: `backend/tests/`

**Interfaces:**

- Consumes: `origin/main`
- Produces: clean branch `agent/supabase-staging-baseline` and a recorded Backend test count

- [x] **Step 1: Fast-forward from main**

```powershell
git switch main
git fetch origin main
git merge --ff-only origin/main
git switch -c agent/supabase-staging-baseline
```

Expected: branch points at the current `origin/main`.

- [x] **Step 2: Run the starting Backend suite**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
Push-Location backend
python -m unittest discover -s tests
Pop-Location
git status --short
```

Expected: 62 tests pass and the working tree is clean.

### Task 2: Enforce the public-key exposure gate

**Files:**

- Read: `frontend/package.json`
- Read: `frontend/.env.local.example`
- Read: `frontend/app/page.tsx`
- Read: `frontend/lib/api.ts`
- Read: `frontend/app/api/admin/[...path]/route.ts`
- Read: `frontend/middleware.ts`
- Read: `frontend/next.config.mjs`
- Read: `backend/main.py`
- Read: `backend/.env.example`
- Update: `docs/AUTH_ENVIRONMENT_PREFLIGHT.md`
- Update: `docs/CODEBASE_AUDIT.md`

**Interfaces:**

- Consumes: current source, tracked env examples, process/user/machine environment presence, local build artifacts
- Produces: a Fact/Unverified classification and a hard GO/NO-GO gate

- [x] **Step 1: Search source and dependencies**

```powershell
rg -n -i "supabase|NEXT_PUBLIC_|SUPABASE_KEY|SUPABASE_URL" frontend backend
rg -n "fetch\\(|createClient\\(|process\\.env" frontend/app frontend/lib frontend/middleware.ts
git ls-files "*env*"
```

Expected: no current frontend Supabase client/dependency or direct browser connection; browser fetches only `/api/admin/*`.

- [x] **Step 2: Inspect generated JavaScript without printing values**

```powershell
rg -l -i "supabase|NEXT_PUBLIC_|SUPABASE_KEY|SUPABASE_URL" frontend/.next -g "*.js" -g "*.json" -g "*.html"
```

Expected: no matching build artifact. If a match exists, stop before Task 3 and record a critical blocker.

- [x] **Step 3: Classify available Backend key material**

Use only prefix classification or the JWT `role` claim and print one of:
`publishable`, `anon`, `secret`, `service_role`, `不明`.

Expected for this checkout: no local/process value is available, so classification is `不明`. Never print the value.

### Task 3: Create the non-migration baseline candidate

**Files:**

- Read: `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`
- Create: `supabase/baselines/2026-07-24-public-schema-baseline.sql`
- Do not modify: `supabase/migrations/202607190001_mvp_security_foundation.sql`
- Do not modify: `supabase/migrations/202607190002_admin_configuration.sql`
- Do not modify: `supabase/migrations/202607200001_application_sessions.sql`
- Do not modify: `supabase/migrations/202607210001_applicant_tags.sql`

**Interfaces:**

- Consumes: sanitized live catalog evidence
- Produces: a non-active baseline candidate with 12 tables, 2 function signatures, 7 triggers, and 43 indexes

- [x] **Step 1: Reconfirm the index count**

Run a project-scoped, read-only catalog query:

```sql
select count(*) as public_index_count
from pg_catalog.pg_indexes
where schemaname = 'public';
```

Expected: `43`. Correct prior documentation that stated `42`.

- [x] **Step 2: Write the candidate**

The file must:

- start with `STAGING BASELINE CANDIDATE ONLY. DO NOT APPLY TO PRODUCTION`
- omit all row data and row-changing statements
- omit the six live constant company defaults and label them `REDACTED`
- define `set_updated_at`
- preserve the signature of `complete_application_session` with a fail-closed exception
- include all table, constraint, explicit-index, and trigger DDL
- document, but not recreate, the unsafe live ACL/RLS state

- [ ] **Step 3: Validate structural counts**

```powershell
$sql = Get-Content supabase/baselines/2026-07-24-public-schema-baseline.sql -Raw
([regex]::Matches($sql, '(?im)^CREATE TABLE public\\.')).Count
([regex]::Matches($sql, '(?im)^CREATE OR REPLACE FUNCTION public\\.')).Count
([regex]::Matches($sql, '(?im)^CREATE TRIGGER ')).Count
([regex]::Matches($sql, '(?im)^CREATE (?:UNIQUE )?INDEX ')).Count
```

Expected: 12 tables, 2 functions, 7 triggers, 28 explicit indexes. Together with 15 constraint-backed indexes, the candidate represents 43 indexes.

### Task 4: Document the staging chain and manual bootstrap

**Files:**

- Create: `docs/STAGING_SUPABASE_BOOTSTRAP.md`
- Update: `docs/SUPABASE_SCHEMA_RECONCILIATION.md`
- Update: `docs/AUTH_ENVIRONMENT_PREFLIGHT.md`
- Update: `docs/CODEBASE_AUDIT.md`
- Create: `docs/superpowers/plans/2026-07-24-supabase-staging-baseline.md`

**Interfaces:**

- Consumes: exposure-gate result, baseline unresolved items, official Supabase CLI/current pricing documentation
- Produces: one selected migration-chain design and a production-isolated human runbook

- [x] **Step 1: Compare the three chain designs**

Compare:

1. one exact live-state baseline
2. reverse-engineered pre-four-migration base
3. approved baseline followed only by future migrations

Select option 3 because it avoids guessing historical base DDL and keeps future history reproducible.

- [x] **Step 2: Write manual staging steps**

Document:

- Dashboard project creation and cost approval
- CLI/Docker prerequisites and install gates
- local empty-DB replay
- staging-only link verification
- `migration list`, `db push --dry-run`, and `db push`
- schema fingerprint/equivalence
- project recreation and destructive-reset restrictions
- explicit production project protections

- [ ] **Step 3: Update the evidence documents**

Record exact source paths/lines for the browser proxy boundary, key classification limits, corrected 43-index count, candidate unresolved DDL, and the selected option-3 chain.

### Task 5: Verify and publish the documentation-only change

**Files:**

- Verify all files above
- Commit only the allowed baseline and documentation files

**Interfaces:**

- Consumes: Tasks 1-4
- Produces: one clean commit and synchronized remote feature branch

- [ ] **Step 1: Run Backend and language checks**

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
Push-Location backend
python -m unittest discover -s tests
Pop-Location
python -c "import ast, pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8'))"
Push-Location frontend
& 'C:\Program Files\nodejs\npm.cmd' exec tsc -- --noEmit --incremental false
Pop-Location
```

Expected: 62 Backend tests, Python parse, and TypeScript type check pass.

- [ ] **Step 2: Check baseline safety and migration integrity**

```powershell
rg -n -i '^\s*(insert\s+into|update\s+|delete\s+from|copy\s+)' supabase/baselines/2026-07-24-public-schema-baseline.sql
rg -n -i '(https?://|service_role\s*[=:]|api[_-]?key\s*[=:]|access[_-]?token\s*[=:]|refresh[_-]?token\s*[=:]|@[A-Za-z0-9.-]+\.[A-Za-z]{2,})' supabase/baselines/2026-07-24-public-schema-baseline.sql
git diff --exit-code origin/main -- supabase/migrations
```

Expected: the first two searches return no match and all four active migration files are unchanged.

- [ ] **Step 3: Check paths and diff**

```powershell
git diff --check
git status --short
```

Expected: only the baseline candidate and requested documentation files differ.

- [ ] **Step 4: Commit and push**

```powershell
git add -- `
  supabase/baselines/2026-07-24-public-schema-baseline.sql `
  docs/STAGING_SUPABASE_BOOTSTRAP.md `
  docs/SUPABASE_SCHEMA_RECONCILIATION.md `
  docs/AUTH_ENVIRONMENT_PREFLIGHT.md `
  docs/CODEBASE_AUDIT.md `
  docs/superpowers/plans/2026-07-24-supabase-staging-baseline.md
git commit -m "docs: prepare Supabase staging baseline"
git push -u origin agent/supabase-staging-baseline
```

Expected: local and remote feature branches are synchronized and the working tree is clean.
