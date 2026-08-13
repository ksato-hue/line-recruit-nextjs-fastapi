# Task 1: Staging Supabase baseline implementation preflight

## Current status (2026-08-13 Asia/Tokyo)

**DONE_WITH_CONCERNS: Task 1**

The approved implementation worktree passed the toolchain gate and all required starting regressions. Task 2 was not started; no database/MCP connection or migration change was made.

## Current isolation evidence

- Worktree: `C:\Users\kouta\マイドライブ\github\line-recruit-staging-supabase-baseline`
- Branch: `agent/staging-supabase-baseline-implementation`
- Initial isolation/base HEAD: `dd62664b87a7236c63934adb88df1d6dc2dc48b4`
- Last committed HEAD reviewed before this report-only clarification: `6ded8203127058edcb763f300c68f36d57b6cf91`
- Intended Task 1 deliverables: root `package.json`, root `package-lock.json`, and this verification report.
- Root dependency diff: direct dev dependency `supabase: 2.113.0`; lockfile contains the Supabase CLI package and its platform/transitive packages only.
- No migration SQL/files were added or modified.

## Current toolchain gate

Each shell reconstructed process PATH from current Machine and User PATH values and appended the PostgreSQL 16 bin directory.

- `npx.cmd --no-install supabase --version`: `2.113.0` (exit 0)
- `docker --version`: Docker client `29.7.2` (exit 0)
- `docker version`: exit 0; Docker Desktop server `4.86.0 (236216)`, Engine `29.7.2` (accepted GO evidence; usable daemon confirmed)
- `psql --version`: PostgreSQL `16.14` (exit 0)
- `python --version`: `Python 3.12.10`
- `node --version`: `v24.18.0`
- `npm --version`: `11.16.0`

## PostgreSQL client-only host evidence

These checks were read-only and did not invoke `psql` against any database.

- `Get-Service -Name 'postgresql*'`: `(none)`.
- `Get-Process -Name postgres`: `(none)`.
- `Get-NetTCPConnection -LocalPort 5432`: `(none)`.
- `C:\Program Files\PostgreSQL\16` top-level footprint: `bin`, `installer`, `lib`, `scripts`, `commandlinetools_3rd_party_licenses.txt`, `installation_summary.log`, `uninstall-postgresql.dat`, and `uninstall-postgresql.exe`; `data_directory_present=False`.
- `installation_summary.log`: records a `Command Line Tools Installation Directory` and no populated data directory.
- PostgreSQL installation registry key: `Branding: PostgreSQL 16`, `CLT_Version: 16.14.2`; no server version or data-directory property was present.
- No matching PostgreSQL uninstall metadata record with a separate server component was returned.

These observations support the approved client-only installation and show no matching PostgreSQL service, `postgres` process, or listener on port 5432 at check time. They do not prove that no server binary exists anywhere under arbitrary names or that no external database exists; no database connection was attempted.
## Current regression evidence

- `python -m pip check`: exit 0; `No broken requirements found.`
- `python -m compileall backend`: exit 0; all 22 backend Python files compiled.
- From `backend/`, `python -m unittest discover -s tests -p "test_*.py" -v`: exit 0; 424 tests ran, all passed (`OK`) across 15 test modules.
- From `frontend/`, first exact `npm.cmd ci` attempt timed out at 184 seconds before completion.
- From `frontend/`, the same `npm.cmd ci` was rerun with verbose diagnostics: exit 0; 30 packages added, 31 audited, 3 high-severity npm audit findings reported.
- From `frontend/`, `npm.cmd run typecheck`: exit 0.
- From `frontend/`, `npm.cmd run build`: exit 0; Next.js 14.2.35 production build completed successfully.

## Current concerns

- The first frontend `npm ci` timed out; the repeated exact install completed successfully.
- `npm ci` reported 3 high-severity audit findings; no audit remediation was requested in Task 1.

## Verification scope

`git diff --check` passed before this follow-up commit. Only this tracked verification report is to be staged for the follow-up evidence clarification commit. No credentials, tokens, database URLs, or Docker environment details beyond versions are recorded.

## Historical attempt history
## Isolation evidence

- Worktree: `C:\Users\kouta\マイドライブ\github\line-recruit-staging-supabase-baseline`
- Branch: `agent/staging-supabase-baseline-implementation`
- HEAD: `dd62664b87a7236c63934adb88df1d6dc2dc48b4`
- `git status --short`: empty
- `git diff --check`: passed
- Existing `supabase/migrations/` files were inspected but not modified or added.

## Tool availability

`Get-Command supabase,docker,psql -ErrorAction SilentlyContinue` returned no commands. Required tools are therefore missing:

| Tool | Required role | Observed state |
| --- | --- | --- |
| Supabase CLI | local migration/reset/replay | absent |
| Docker-compatible runtime | Supabase local stack | absent |
| `psql` | catalog and verification queries | absent |

Read-only runtime versions already available:

- Python `3.12.10`
- Node `v24.18.0`
- npm `11.16.0`

## Recommended installation policy (approval required)

These are documented recommendations only; no installer, package manager, or network installation was run.

1. Pin Supabase CLI stable `v2.113.0`. The official release tag identifies `v2.113.0` as **Latest**, released 2026-08-08; this exact stable tag is verified. Official Windows/npm command:

   `npm install supabase@2.113.0 --save-dev`

   Supabase's official guide requires Node.js 20+ and recommends pinning the CLI version in `package.json`.

2. Install Docker Desktop for Windows `4.84.0` (official Docker release notes, 2026-07-27), which supersedes the previously listed 4.83.0 (released 2026-07-20). No compatibility reason was found to retain 4.83.0. After downloading the official 4.84.0 installer, the documented per-user PowerShell command is:

   `Start-Process 'Docker Desktop Installer.exe' -Wait -ArgumentList 'install', '--user'`

   Docker documents WSL 2 as the default backend and requires WSL 2.1.5+ plus supported Windows 10/11 builds. Enabling/updating WSL may require administrator approval and a restart.

3. `psql` is required, but the previously suggested command is not client-only: the official EDB development guide's `winget install PostgreSQL.PostgreSQL.16` installs the full PostgreSQL 16 server package (including pgAdmin/StackBuilder and command-line tools). It is therefore **not an appropriate client-only recommendation** for this gate. The official EDB Windows installer permits selecting **Command Line Tools** without selecting PostgreSQL Server; use that GUI path after explicit approval. No official one-line client-only install command was established here, so do not run the winget command under the client-only policy:

   If a full local PostgreSQL server is explicitly approved as an intentional choice, the documented command is `winget install PostgreSQL.PostgreSQL.16`; that is a different policy and remains out of scope here.

   This installs PostgreSQL 16 and includes the `psql` command-line tool. The EDB guide documents the exact package command and PATH location; use only the Command Line Tools component if the installer offers component selection.

Primary official references:

- [Supabase CLI installation guide](https://supabase.com/docs/guides/local-development/cli/getting-started)
- [Supabase CLI stable releases](https://github.com/supabase/cli/releases)
- [Supabase CLI v2.113.0 release tag](https://github.com/supabase/cli/releases/tag/v2.113.0)
- [Docker Desktop Windows installation](https://docs.docker.com/desktop/setup/install/windows-install/)
- [Docker Desktop release notes](https://docs.docker.com/desktop/release-notes/)
- [EDB PostgreSQL Windows development installation](https://www.enterprisedb.com/docs/dev-guides/deploy/windows/)
- [EDB PostgreSQL Windows installer component selection](https://www.enterprisedb.com/docs/supported-open-source/postgresql/installing/windows/)

Installation requires explicit approval because it changes the host, may require administrator privileges/restart, adds a container runtime, and can consume substantial disk/network resources. The task explicitly prohibits installing these tools without approval.

## Regression gate

Not run. The brief requires stopping immediately when Supabase CLI or Docker is absent; therefore `pip check`, Python compile/tests, `npm ci`, TypeScript typecheck, and frontend build remain pending until the toolchain gate is approved and satisfied.

## Historical stopping reason

**Historical blocker: do not proceed to Task 2 or create migration SQL until explicit approval is provided and all three missing tools are installed and version-verified.**

## Retry evidence (2026-08-12 Asia/Tokyo)

The required preflight was rerun in the isolated worktree without contacting any database/MCP and without installing anything.

- `git status --short`: `?? docs/superpowers/reports/` (the existing Task 1 report artifact; no source or migration changes)
- `git branch --show-current`: `agent/staging-supabase-baseline-implementation`
- `git rev-parse HEAD`: `dd62664b87a7236c63934adb88df1d6dc2dc48b4`
- `Get-Command supabase,docker,psql -ErrorAction SilentlyContinue`: no commands returned
- `supabase --version`: unavailable (command not found)
- `docker version --format '{{.Server.Version}}'`: unavailable (docker command not found; Docker server availability unconfirmed)
- `psql --version`: unavailable (command not found)
- `python --version`: `Python 3.12.10`
- `node --version`: `v24.18.0`
- `npm --version`: `11.16.0`

**NO-GO: Task 1 (RETRY BLOCKED).** The missing Supabase CLI, Docker-compatible runtime/server, and `psql` keep the toolchain gate unsatisfied. Per the brief, no regression commands were run and Task 2 was not started. No migration SQL/files were created or modified. Explicit approval and a usable, version-verified toolchain remain required.

## Bounded standard-path retry (2026-08-12 Asia/Tokyo)

A read-only PATH/standard-location check was performed; no installation, database/MCP connection, or process launch was performed.

- `where.exe supabase/docker/psql`: no results.
- Repo `node_modules/.bin` and `frontend/node_modules/.bin`: no `supabase*` binaries.
- Root/frontend `package.json` and lockfiles: no direct Supabase CLI dependency found.
- `npm root -g`: `C:\Users\kouta\AppData\Roaming\npm\node_modules`; no `supabase*` package/version present.
- `C:\Program Files\Docker\Docker\resources\bin\docker.exe`: absent; Docker Desktop executable, Docker service, and Docker processes: absent.
- `C:\Program Files\PostgreSQL\*\bin\psql.exe`: no matches.
- User and machine PATH: no Supabase, Docker resources/bin, or PostgreSQL bin entry; this is not a PATH-only issue.
- No absolute-path binary was found, so no version or daemon check could be run.

**NO-GO remains confirmed absent**, with exact remediation: obtain explicit approval to install the required pinned tools, then refresh PATH/restart the shell and rerun absolute-path/version checks. No commit was made.

## Docker prerequisite gate (2026-08-12 Asia/Tokyo)

Per the newly approved Docker-install scope, official Docker documentation and the 4.84.0 release-notes page were reviewed. The official Windows guide requires WSL 2 (version 2.1.5+), WSL 2 feature enablement, 8 GB RAM, hardware virtualization, and LanmanServer enabled/Automatic; it documents that first-time WSL 2 enablement requires administrator privileges and may require restart. Sources: https://docs.docker.com/desktop/setup/install/windows-install/ and https://docs.docker.com/desktop/release-notes/.

Read-only host checks (no installer download, GUI, elevation, reboot, license acceptance, DB/MCP connection, or migration work):

- OS: Windows 11 Home, build 26200, 64-bit.
- Physical RAM: 15.8 GB.
- LanmanServer: Running; StartType Automatic.
- Current token: non-elevated (`Elevated=False`).
- `wsl.exe`: present at `C:\WINDOWS\system32\wsl.exe`, but `wsl --version` did not yield usable version details.
- Read-only DISM checks for `Microsoft-Windows-Subsystem-Linux` and `VirtualMachinePlatform`: both returned `Error: 740` (elevation required), so feature state cannot be verified without administrator access.
- Virtualization query returned `VirtualizationFirmwareEnabled=False; SLAT=False`; hardware virtualization cannot be treated as available.

**NO-GO: Docker prerequisite blocked.** The first required WSL feature verification/enablement requires an elevated token (and may require restart), which is explicitly outside the allowed actions. Docker 4.84.0 was not downloaded or installed. Do not proceed to psql or regressions. Manual action required: an administrator must verify/enable WSL 2 and hardware virtualization, then rerun this gate; only after prerequisites are satisfied may the approved per-user installer be considered.

## Task 2 approved migration-chain gate (2026-08-13)

Human review approved the non-final ordering values `202608060001_public_schema_current_state_baseline.sql` and `202608060002_fail_closed_security_privileges.sql`, ahead of `202608070001`. The exact tracked local CLI `2.113.0` listed the required ten-version order in an isolated temporary project with Vector excluded. The approved lock records the two paths, server role `service_role`, six final active paths in order, and SHA-256 checksums for all four active inquiry migrations.

This gate deliberately does not create the two approved migration SQL files; they remain future work. No production or staging database/MCP access, migration application, legacy move, or Task 3 work occurred.
