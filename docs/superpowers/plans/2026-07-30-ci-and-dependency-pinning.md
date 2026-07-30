# CI and Dependency Pinning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 現在成功しているBackend 149件のunittest、Frontend型検査、Next.js buildを再現可能な依存versionとGitHub Actionsで毎回実行できるようにする。

**Architecture:** Backendはruntime直接依存を `requirements.txt`、FastAPI TestClientが直接必要とするtest依存を `requirements-dev.txt` に分離する。Frontendはpackage-lockに記録済みの直接依存versionへ厳密固定し、型関連packageをdevDependenciesへ移す。CIは秘密情報を使わない独立したBackend/Frontend jobで構成する。

**Tech Stack:** CPython 3.12.10、unittest、FastAPI、Node.js 24.18.0、npm 11.16.0、Next.js 14.2.35、GitHub Actions

## Global Constraints

- 既存機能、API仕様、UI、Basic認証、`ADMIN_API_KEY`、`COMPANY_ID`を変更しない。
- Supabase、migration、Render、production、stagingへ接続・変更しない。
- 依存packageをupgradeせず、確認済みの実環境またはpackage-lockのversionだけを使用する。
- pytest、pytest-cov、pip-tools、uv、pip-audit、ESLint関連packageを追加しない。
- BackendテストはPython標準ライブラリのunittestだけを使用する。
- CIへsecret参照やwrite permissionを追加しない。
- lockfileを再生成せず、直接依存の厳密固定とdependency区分変更に必要な差分だけを加える。

---

### Task 1: Backend直接依存とtest依存を固定する

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`

**Interfaces:**
- Consumes: 現在のCPython 3.12.10環境で成功した149件のunittestと、`importlib.metadata`で取得したinstalled package version
- Produces: CIとローカルが共用するruntime/test依存定義

- [ ] **Step 1: runtime直接依存を確認済みversionへ固定する**

`backend/requirements.txt`を次の内容にする。

```text
fastapi==0.139.2
uvicorn[standard]==0.51.0
supabase==2.31.0
requests==2.34.2
pydantic==2.13.4
```

- [ ] **Step 2: FastAPI TestClientの直接test依存だけを分離する**

`backend/requirements-dev.txt`を次の内容で作成する。

```text
-r requirements.txt
httpx==0.28.1
```

`backend/tests/test_legacy_routes_tenant_scope.py` が `fastapi.testclient.TestClient` をimportし、FastAPI TestClientがhttpx transportを使用するため、httpxをtest直接依存として明示する。unittestは標準ライブラリなので記載しない。

- [ ] **Step 3: 現在環境で依存整合とテストを確認する**

Run:

```powershell
python -m pip check
python -m compileall backend
cd backend
python -m unittest discover -s tests -p "test_*.py" -v
```

Expected: `pip check`成功、Python構文検査成功、149件以上のunittest成功。既存FastAPI TestClient非推奨警告は今回変更しない。

### Task 2: Frontend直接依存をlockfileのversionへ固定する

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

**Interfaces:**
- Consumes: package-lock v3の `node_modules/<package>.version`
- Produces: `npm ci`で再現できるruntime/dev依存区分と `typecheck` script

- [ ] **Step 1: package.jsonのruntime依存を厳密固定する**

```json
"dependencies": {
  "next": "14.2.35",
  "react": "18.3.1",
  "react-dom": "18.3.1"
}
```

- [ ] **Step 2: 型・コンパイラ依存を同じversionのままdevDependenciesへ移す**

```json
"devDependencies": {
  "@types/node": "20.19.43",
  "@types/react": "18.3.31",
  "@types/react-dom": "18.3.7",
  "typescript": "5.9.3"
}
```

- [ ] **Step 3: typecheck scriptを追加する**

既存scriptを保持し、次を追加する。

```json
"typecheck": "tsc --noEmit"
```

- [ ] **Step 4: package-lockのroot metadataとdev区分だけを同期する**

`packages[""]` のdependencies/devDependenciesをpackage.jsonと一致させる。対象直接packageと、そのdev専用transitive packageの `dev` metadataはnpmが期待する状態へ同期するが、resolved package version、integrity、lockfileVersionは変更しない。

- [ ] **Step 5: npm clean installとFrontend検証を実行する**

Run:

```powershell
cd frontend
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
```

Expected: install、型検査、production buildが成功する。buildが生成する `next-env.d.ts` の非本質的差分はcommitしない。

### Task 3: GitHub Actions CIを追加する

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `backend/requirements-dev.txt`、`frontend/package-lock.json`、`frontend/package.json` scripts
- Produces: pull requestとmain pushで動くread-only Backend/Frontend gates

- [ ] **Step 1: 最小権限、trigger、concurrencyを定義する**

```yaml
name: CI

on:
  pull_request:
  push:
    branches:
      - main

permissions:
  contents: read

concurrency:
  group: ci-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true
```

- [ ] **Step 2: Backend jobを定義する**

GitHub公式 `actions/checkout@v6` と `actions/setup-python@v6` を使用し、Python `3.12.10`、pip cache dependency path `backend/requirements-dev.txt` を指定する。

```yaml
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12.10"
          cache: pip
          cache-dependency-path: backend/requirements-dev.txt
      - run: python -m pip install --upgrade pip
      - run: python -m pip install -r backend/requirements-dev.txt
      - run: python -m pip check
      - run: python -m compileall backend
      - run: python -m unittest discover -s tests -p "test_*.py" -v
        working-directory: backend
```

- [ ] **Step 3: Frontend jobを定義する**

GitHub公式 `actions/checkout@v6` と `actions/setup-node@v6` を使用する。Node.js `24.18.0`にはnpm `11.16.0`が同梱されるため、追加のnpm upgradeは行わない。

```yaml
  frontend:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: "24.18.0"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: npm ci
      - run: npm run typecheck
      - run: npm run build
```

- [ ] **Step 4: workflowを静的検証する**

YAML parserで構文を確認し、trigger、2 job、working-directory、cache path、requirements path、script名を検査する。`${{ secrets.* }}`、write permission、外部API接続コマンドが0件であることを確認する。

### Task 4: 利用手順と監査記録を更新する

**Files:**
- Modify: `README.md`
- Modify: `docs/CODEBASE_AUDIT.md`
- Modify: `docs/superpowers/plans/2026-07-30-ci-and-dependency-pinning.md`

**Interfaces:**
- Consumes: Task 1-3の確定コマンドとversion
- Produces: ローカル/CIで同じ検証を再実行する手順と監査証跡

- [ ] **Step 1: READMEへローカル検証とCIを記載する**

Backendは `requirements-dev.txt`、`pip check`、`compileall`、149件以上のunittestを使用する。Frontendは `npm ci`、`npm run typecheck`、`npm run build` を使用する。CIはpull requestとmain pushでBackend/Frontendを独立実行し、production secretを使用しないと明記する。

- [ ] **Step 2: unittestとlint方針を記載する**

pytestは現在採用せず、pytest固有機能が必要になった場合だけ別タスクで検討する。ESLint package・設定・既存lint修正はCI導入へ混ぜず、typecheck/buildを最初の必須gateとする。

- [ ] **Step 3: CODEBASE_AUDITへ事実と制約を追記する**

固定version、取得根拠、CI job、secret非使用、clean install結果、既存TestClient警告、lint未導入を事実・未確認事項として記録する。

### Task 5: Clean環境と最終差分を検証する

**Files:**
- Verify: `backend/requirements.txt`
- Verify: `backend/requirements-dev.txt`
- Verify: `frontend/package.json`
- Verify: `frontend/package-lock.json`
- Verify: `.github/workflows/ci.yml`
- Verify: `README.md`
- Verify: `docs/CODEBASE_AUDIT.md`

**Interfaces:**
- Consumes: Task 1-4の全成果物
- Produces: 2コミットへ進める検証証跡

- [ ] **Step 1: リポジトリ外の一時venvでBackendをclean installする**

```powershell
python -m venv $env:TEMP\line-recruit-ci-venv
$env:TEMP\line-recruit-ci-venv\Scripts\python.exe -m pip install --upgrade pip
$env:TEMP\line-recruit-ci-venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
$env:TEMP\line-recruit-ci-venv\Scripts\python.exe -m pip check
$env:TEMP\line-recruit-ci-venv\Scripts\python.exe -m compileall backend
cd backend
$env:TEMP\line-recruit-ci-venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```

- [ ] **Step 2: Frontendをlockfileから再検証する**

```powershell
cd frontend
npm.cmd ci
npm.cmd run typecheck
npm.cmd run build
```

- [ ] **Step 3: repository静的検証を実行する**

```powershell
git diff --check
git status --short
```

加えてworkflow YAML、secret参照、write permission、文書パス、直接依存version、package-lock内version不変を機械検査する。

### Task 6: 2コミットへ分割してpushする

**Files:**
- Commit 1: `backend/requirements.txt`, `backend/requirements-dev.txt`, `frontend/package.json`, `frontend/package-lock.json`, `README.md`
- Commit 2: `.github/workflows/ci.yml`, `docs/CODEBASE_AUDIT.md`, `docs/superpowers/plans/2026-07-30-ci-and-dependency-pinning.md`

**Interfaces:**
- Consumes: Task 5の全検証成功
- Produces: `origin/agent/ci-dependency-pinning` の2コミット

- [ ] **Step 1: dependency commitを作成する**

```powershell
git add -- backend/requirements.txt backend/requirements-dev.txt frontend/package.json frontend/package-lock.json README.md
git commit -m "chore: pin project dependencies"
```

- [ ] **Step 2: CI commitを作成する**

```powershell
git add -- .github/workflows/ci.yml docs/CODEBASE_AUDIT.md docs/superpowers/plans/2026-07-30-ci-and-dependency-pinning.md
git commit -m "ci: add automated backend and frontend checks"
```

- [ ] **Step 3: 指定branchへpushし同期を確認する**

```powershell
git push -u origin agent/ci-dependency-pinning
git rev-list --left-right --count origin/agent/ci-dependency-pinning...HEAD
git rev-list --left-right --count origin/main...HEAD
git status -sb
```

PR作成とmergeは行わない。push後にGitHub Actions runをread-onlyで取得できる場合だけ結果を確認し、取得できなければremote CI未確認と報告する。

## Version Evidence

| Item | Fixed version | Evidence |
|---|---:|---|
| Python | 3.12.10 | `python --version` / `platform.python_version()` |
| fastapi | 0.139.2 | `importlib.metadata.version("fastapi")` |
| uvicorn | 0.51.0 | `importlib.metadata.version("uvicorn")` |
| supabase | 2.31.0 | `importlib.metadata.version("supabase")` |
| requests | 2.34.2 | `importlib.metadata.version("requests")` |
| pydantic | 2.13.4 | `importlib.metadata.version("pydantic")` |
| httpx | 0.28.1 | `importlib.metadata.version("httpx")` とTestClient import |
| Node.js | 24.18.0 | `node --version`、Node.js公式LTS release |
| npm | 11.16.0 | `npm --version`、Node.js 24.18.0公式同梱version |
| next | 14.2.35 | `frontend/package-lock.json` |
| react | 18.3.1 | `frontend/package-lock.json` |
| react-dom | 18.3.1 | `frontend/package-lock.json` |
| typescript | 5.9.3 | `frontend/package-lock.json` |
| @types/node | 20.19.43 | `frontend/package-lock.json` |
| @types/react | 18.3.31 | `frontend/package-lock.json` |
| @types/react-dom | 18.3.7 | `frontend/package-lock.json` |

## Rollback

- 2コミットを逆順に通常のrevertで戻す。
- CI commitのrevertでworkflowと監査追記を除去し、dependency commitのrevertでrequirements/package metadata/READMEを元へ戻す。
- DB、Supabase、Render、環境変数、外部設定を変更しないため、外部環境のrollbackは不要。
