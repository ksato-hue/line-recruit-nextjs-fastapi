# Supabase Schema Reconciliation Implementation Plan

> **Status:** investigation completed on 2026-07-24; production execution is not authorized by this plan.

**Goal:** Establish a reproducible, reviewable migration chain for the current live `public` schema before any Supabase Auth/RBAC/MFA migration is created.

**Strategy:** Preserve the live evidence as a non-applicable sanitized snapshot, build a separate executable baseline in a new staging project, prove schema equivalence, then reconcile production migration history only through a separately approved change.

**Current evidence:** `docs/SUPABASE_SCHEMA_RECONCILIATION.md` and `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`.

## 1. Dependency graph

```text
P0 live read-only inventory (complete)
  └─ P1 approve canonical schema decisions
       ├─ P2 prepare isolated Supabase tooling
       └─ P3 author executable baseline
            └─ P4 clean staging replay
                 ├─ P5 schema equivalence proof
                 └─ P6 application/RLS rehearsal
                      └─ P7 approve production history strategy
                           ├─ P8 history-only reconciliation
                           └─ P9 first Auth foundation migration
```

P7-P9 must not begin if P5 or P6 fails.

## 2. Phase P0: read-only evidence capture — complete

**Files**

- Create: `docs/SUPABASE_SCHEMA_RECONCILIATION.md`
- Create: `docs/schema/REMOTE_PUBLIC_SCHEMA_SANITIZED.sql`
- Create: `docs/superpowers/plans/2026-07-24-supabase-schema-reconciliation.md`
- Update: `docs/AUTH_ENVIRONMENT_PREFLIGHT.md`
- Update: `docs/CODEBASE_AUDIT.md`

**Evidence**

- 12 public base tables, 2 functions, 7 triggers, 42 indexes
- no public view/materialized view/sequence/foreign table
- no `supabase_migrations.schema_migrations`
- 12 tables with RLS/FORCE RLS disabled and no policies
- table/function/schema/default ACL inventory
- aggregate-only company identifier counts
- four checked-in migration postconditions

**Verification**

```powershell
Push-Location backend
python -m unittest discover -s tests -v
Pop-Location
$env:PYTHONDONTWRITEBYTECODE='1'
python -c "import ast, pathlib; ast.parse(pathlib.Path('backend/main.py').read_text(encoding='utf-8')); print('Python AST: OK')"
Push-Location frontend
npm exec tsc -- --noEmit --incremental false
Pop-Location
git diff --check
git status --short
```

## 3. Phase P1: canonical schema decisions

**Purpose:** Decide what the baseline must reproduce exactly and what must be corrected by an immediate forward migration.

**Files**

- Update: `docs/SUPABASE_SCHEMA_RECONCILIATION.md`
- Update: `docs/superpowers/plans/2026-07-23-supabase-auth-rbac-mfa-implementation.md`
- Create: `docs/schema/SCHEMA_DECISIONS.md`

**Decisions requiring human approval**

1. Whether `contacts` remains, gains company scope, or is retired.
2. Whether the six nullable legacy `company_id` columns remain nullable in baseline.
3. Whether the constant company defaults are preserved only for live equivalence or removed immediately afterward.
4. Whether `faq_categories.name` remains globally unique or becomes `(company_id, name)`.
5. Whether `faqs(category_id, question)` is sufficient after category ownership enforcement.
6. FK policy for `interview_slots.applicant_id` and `applicants.application_session_id`.
7. Whether redundant unique indexes are retained for exact equivalence or removed in a later migration.
8. Function ownership, search path, `EXECUTE` grants, and company predicate changes for `complete_application_session`.
9. Exact mapping from legacy text company identifiers to future `companies.id uuid`.

**Failing tests first**

No production SQL is written in this phase. Add a documentation check that fails if any decision remains marked approved without an approver/date/evidence link.

**Stop condition**

Do not author executable SQL while any item above lacks an explicit decision.

## 4. Phase P2: isolated tooling and staging

**External setup**

- Create a separate Supabase staging project.
- Record plan/region/project owner without committing project secrets.
- Install an approved, version-pinned Supabase CLI and Docker Desktop/Engine.
- Run `supabase init` only in a reviewed branch.
- Link only to staging during baseline work.
- Store DB credentials in the OS/CI secret store, never repository files.

**Files**

- Create: `supabase/config.toml`
- Update: `.gitignore` only if generated local credential/cache paths are not already ignored
- Create: `docs/runbooks/SUPABASE_STAGING_REPLAY.md`

**Failing checks first**

```powershell
supabase --version
docker version
supabase status
supabase migration list --linked
```

The linked project ref must be compared to the approved staging ref before every command capable of changing schema.

**Rollback**

Unlink local staging config and delete the disposable staging project. No production state is touched.

**Cost**

The extra Supabase project, compute, backups, egress, email, and retained logs may incur plan/usage charges. Obtain approval before project creation.

## 5. Phase P3: executable baseline

**Files**

- Create: `supabase/migrations/<CLI_TIMESTAMP>_public_schema_baseline.sql`
- Create: `supabase/tests/schema_baseline.test.sql`
- Create: `scripts/schema_fingerprint.sql`
- Update: `README.md`

Do not invent `<CLI_TIMESTAMP>` in advance. Generate it with `supabase migration new public_schema_baseline` after tooling approval.

**SQL scope**

- Create the 12 approved public tables in dependency order.
- Create reviewed PK, FK, UNIQUE, CHECK, and index definitions.
- Create `set_updated_at` and approved triggers.
- Create the reviewed version of `complete_application_session`.
- Reproduce only approved defaults; never copy the redacted live company default blindly.
- Make grants explicit.
- Enable RLS in the same transaction for tables intended for Data API exposure.
- If exact-equivalence baseline must preserve unsafe live ACL/RLS temporarily, keep it staging-only and add an immediate next migration that closes exposure before application access.
- Do not include production row data.

**Failing tests first**

`supabase/tests/schema_baseline.test.sql` must initially fail for:

- missing table/column/type/nullability/default
- missing PK/FK/UNIQUE/CHECK/index
- unexpected nullable company column
- missing company FK decision
- RLS not enabled on approved tables
- anon/authenticated over-grant
- PUBLIC execute on data-changing RPC
- function update predicate missing company scope

**Verification**

```powershell
supabase db reset --local
supabase test db
supabase db lint --local
```

`db reset --linked` is prohibited for production and should not appear in the runbook.

**Rollback**

Before external use, replace or delete the staging baseline and recreate the disposable staging database. Never reverse a partially adopted production baseline with destructive reset.

## 6. Phase P4: clean staging replay

**Files**

- Update: `docs/runbooks/SUPABASE_STAGING_REPLAY.md`
- Create: `docs/schema/STAGING_REPLAY_RESULT.md`

**Steps**

1. Confirm linked ref is staging.
2. Capture `supabase migration list --linked`.
3. Apply the clean chain to an empty staging project.
4. Confirm migration history versions and checksums.
5. Restart the replay from a second empty staging project or a disposable local stack.
6. Confirm both runs produce the same fingerprint.

**Failing checks first**

- replay must fail if any base table is missing before the four historical deltas
- replay must fail if order differs
- replay must fail if generated fingerprint differs between clean runs

**Rollback**

Delete and recreate staging. Production remains untouched.

## 7. Phase P5: schema equivalence proof

**Files**

- Use: `scripts/schema_fingerprint.sql`
- Create: `docs/schema/LIVE_STAGING_EQUIVALENCE.md`

**Compare**

- schemas, tables, partitions, columns, types, defaults, nullability
- PK, FK including actions, UNIQUE, CHECK and validation state
- all indexes including predicates and sort direction
- views/materialized views/sequences/foreign tables
- functions by signature, attributes, owner and normalized definition hash
- triggers and enable state
- RLS/FORCE RLS/policy
- schema/table/sequence/function/default privileges
- required extensions

**Allowed differences**

Every allowed difference must be named and justified before comparison. Production data, generated OIDs, statistics, and owner differences caused only by managed staging roles are not schema failures if explicitly normalized.

**Pass criteria**

- exact equality for baseline-reproduced objects
- only approved security-forward differences
- no production company identifier value in evidence files

## 8. Phase P6: application and security rehearsal

**Files**

- Create: `backend/tests/integration/test_staging_schema_contract.py`
- Create: `supabase/tests/rls_baseline.test.sql`
- Update: `docs/SUPABASE_COMPANY_SCOPE.md`

**Failing tests first**

- application cannot start when a required table/function is absent
- same identifier in two companies never crosses tenant boundary
- anon/authenticated cannot read or write without an approved policy
- service-only RPC cannot be executed by PUBLIC
- `complete_application_session` cannot mutate another company session
- nullable/default legacy behavior matches the approved bridge plan

**Commands**

```powershell
Push-Location backend
python -m unittest discover -s tests -v
Pop-Location
supabase test db
supabase db lint --linked
```

Staging integration credentials must be ephemeral and excluded from logs.

## 9. Phase P7: choose production history strategy

**Options**

- One current-state baseline version
- Reconstructed base migration plus retained four versions
- A reviewed hybrid in which historical DML is separated from schema

**Required evidence**

- P5 equivalence report
- P6 green tests
- restore rehearsal
- approved version list
- exact statement of which SQL has already taken effect in production

**Decision record**

- Create: `docs/decisions/ADR_SUPABASE_MIGRATION_BASELINE.md`

No version may be marked applied until this ADR is approved.

## 10. Phase P8: production history-only reconciliation

This is a separate production change window.

**Preconditions**

- current backup and tested restore
- no concurrent schema changes
- schema fingerprint unchanged since approval
- exact applied-version list approved
- Supabase project ref verbally and programmatically verified

**Commands, in order**

```powershell
supabase migration list --linked
supabase migration repair <APPROVED_VERSION> --status applied --linked
supabase migration list --linked
supabase db push --dry-run --linked
```

Repeat the repair command only for explicitly approved versions. Do not use a placeholder or guessed timestamp.

**Pass criteria**

- local/remote migration list matches the ADR
- dry-run contains exactly the approved pending set, or no pending migration when zero is expected
- live schema fingerprint remains unchanged by history-only repair

**Rollback**

If only history metadata was changed and the schema was not changed:

```powershell
supabase migration repair <APPROVED_VERSION> --status reverted --linked
```

Re-run migration list and schema fingerprint. If schema was also changed, use the tested restore or an approved forward migration; never use remote reset.

## 11. Phase P9: Auth foundation gate

Only after P8 is complete may the first Auth migration in
`docs/superpowers/plans/2026-07-23-supabase-auth-rbac-mfa-implementation.md`
be created.

Before creation, update that plan so its first migration depends on the approved baseline version and current grants/RLS facts. Existing 62 Backend tests remain unchanged and must stay green.

## 12. Global stop conditions

Stop before any external change if:

- linked project identity is ambiguous
- backup or restore rehearsal is unavailable
- live fingerprint changed after evidence capture
- a company identifier mapping is not approved
- a migration contains row data or a production identifier
- an exposed table would exist with RLS disabled
- anon/authenticated retain an unreviewed all-table grant
- a data-changing function remains executable by PUBLIC
- clean replay or equivalence checks fail
- `db push --dry-run` reports an unexpected migration
