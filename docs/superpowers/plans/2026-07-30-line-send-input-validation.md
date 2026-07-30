# Manual LINE send input validation implementation plan

> Date: 2026-07-30
>
> Scope: Add strict request-boundary validation to `POST /api/line/send`. Do not connect to Supabase or LINE, change frontend payloads, alter authentication, or add dependencies.

## Verified current contract

- `frontend/types/index.ts` defines the request as exactly `line_user_id` and `message`, and the response as `status`, `line_user_id`, and `message`.
- `frontend/lib/api.ts` sends those two request fields through `POST /api/admin/line/send`.
- `frontend/app/api/admin/[...path]/route.ts` forwards the request to `POST /api/line/send` and supplies `X-Admin-Key` on the server.
- `backend/main.py` currently accepts an untyped dictionary, calls `push_line_message`, then calls `try_insert_line_message_log`, and returns the existing response fields.
- Existing tests replace the import-time Supabase client and patch outbound functions, so endpoint tests can run without external connections.

## Design

Create `backend/line_send_validation.py` with:

- `utf16_code_unit_length(value: str) -> int`, counting `utf-16-le` bytes without a BOM and rejecting malformed isolated surrogates.
- `LineSendRequest`, a strict Pydantic model that forbids unknown fields.
- Exact LINE user ID validation using `U[0-9a-f]{32}` without trimming or case conversion.
- Message validation that requires a string with at least one non-whitespace character, preserves valid content unchanged, and permits at most 5,000 UTF-16 code units.

Update only the body type of `backend/main.py::api_line_send` and read validated model attributes. Preserve the route, authentication dependency, outbound call, log call, error propagation, call order, and response.

## TDD tasks

1. Add `backend/tests/test_line_send_validation.py` before production code.
2. Cover helper and model boundaries: strict field types, exact ID syntax, missing/null/extra fields, whitespace behavior, ASCII/Japanese/emoji limits, and isolated surrogates.
3. Cover endpoint behavior: valid request and unchanged response, 422 boundaries, no send/log side effects on invalid input, and existing authentication failures.
4. Run the focused tests and record RED caused by the missing validation module or unvalidated endpoint.
5. Add the pure validation module and minimal endpoint integration.
6. Run focused tests, then all Backend tests.

## Documentation tasks

- Add `docs/LINE_SEND_INPUT_VALIDATION.md` as the request contract and security rationale.
- Update `docs/CODEBASE_AUDIT.md` and `docs/requirements.md` only where the implemented validation state belongs.
- Do not change README unless an existing manual-send contract requires correction.

## Verification

Run from the repository root unless noted:

```text
python -m pip check
python -m compileall backend
cd backend
python -m unittest tests.test_line_send_validation -v
python -m unittest discover -s tests -p "test_*.py" -v
cd ../frontend
npm ci
npm run typecheck
npm run build
```

Also inspect FastAPI route/model metadata, imports in the new module, secret/PII logging changes, `git diff --check`, and `git status`.

## Rollback

Revert the single feature commit. This removes the model, tests, documentation, and endpoint type change together, restoring the former dictionary body without changing database state, external services, environment variables, or migrations.
