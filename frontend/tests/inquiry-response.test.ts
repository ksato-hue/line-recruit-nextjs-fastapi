const assert: typeof import("node:assert/strict") = require("node:assert/strict");
const test: typeof import("node:test") = require("node:test");

type ResolveNext = (specifier: string, context?: unknown) => unknown;
type RegisterHooks = (hooks: {
  resolve: (specifier: string, context: unknown, nextResolve: ResolveNext) => unknown;
}) => void;

const { registerHooks } = require("node:module") as { registerHooks: RegisterHooks };

registerHooks({
  resolve(specifier, context, nextResolve) {
    try {
      return nextResolve(specifier, context);
    } catch (error) {
      const isRelative = specifier.startsWith("./") || specifier.startsWith("../");
      if (isRelative && !specifier.endsWith(".ts")) {
        return nextResolve(`${specifier}.ts`, context);
      }
      throw error;
    }
  }
});

const { AdminApiError } = require("../lib/api.ts") as typeof import("../lib/api");
const {
  createInitialInquiryReplyState,
  inquiryReplyReducer,
  serializeInquiryReplyRequest,
  validateInquiryReplyDraft
} = require("../features/inquiries/inquiry-response.ts") as typeof import(
  "../features/inquiries/inquiry-response"
);

const inquiryId = "10000000-0000-0000-0000-000000000001";
const firstKey = "20000000-0000-0000-0000-000000000001";
const secondKey = "20000000-0000-0000-0000-000000000002";
const expectedUpdatedAt = "2026-08-07T00:00:00+00:00";

function editingState() {
  return inquiryReplyReducer(createInitialInquiryReplyState(), {
    type: "edit",
    assigneeName: "佐藤",
    message: "お問い合わせありがとうございます。"
  });
}

function confirmingState(createId = () => firstKey) {
  return inquiryReplyReducer(editingState(), {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt,
    maskedDestination: "U1234…7890",
    createId
  });
}

test("the initial reply draft is idle and empty", () => {
  assert.deepEqual(createInitialInquiryReplyState(), {
    status: "idle",
    draft: { assigneeName: "", message: "" },
    snapshot: null,
    errorMessage: null
  });
});

test("opening confirmation freezes an exact snapshot and generates one key", () => {
  let calls = 0;
  const createId = () => {
    calls += 1;
    return calls === 1 ? firstKey : secondKey;
  };
  const draft = editingState();
  const opened = inquiryReplyReducer(draft, {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt,
    maskedDestination: "U1234…7890",
    createId
  });
  const openedAgain = inquiryReplyReducer(opened, {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt: "2099-01-01T00:00:00Z",
    maskedDestination: "changed",
    createId
  });

  assert.equal(calls, 1);
  assert.strictEqual(openedAgain, opened);
  assert.equal(Object.isFrozen(opened.snapshot), true);
  assert.deepEqual(opened.snapshot, {
    inquiryId,
    assigneeName: "佐藤",
    message: "お問い合わせありがとうございます。",
    messageCodeUnits: 17,
    idempotencyKey: firstKey,
    expectedUpdatedAt,
    maskedDestination: "U1234…7890"
  });
});

test("cancelling confirmation keeps the draft and discards the snapshot", () => {
  const confirming = confirmingState();
  const cancelled = inquiryReplyReducer(confirming, { type: "cancel_confirmation" });

  assert.equal(cancelled.status, "editing");
  assert.deepEqual(cancelled.draft, confirming.draft);
  assert.equal(cancelled.snapshot, null);
});

test("a second submit dispatch while submitting is a no-op", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const duplicate = inquiryReplyReducer(submitting, { type: "submit" });

  assert.equal(submitting.status, "submitting");
  assert.strictEqual(duplicate, submitting);
});

test("reply validation counts UTF-16 code units at the 5,000-unit boundary", () => {
  assert.deepEqual(
    validateInquiryReplyDraft({ assigneeName: "佐藤", message: "a".repeat(5_000) }),
    {}
  );
  assert.equal(
    validateInquiryReplyDraft({ assigneeName: "佐藤", message: "a".repeat(5_001) }).message,
    "返信は5,000文字以内で入力してください。"
  );
  assert.deepEqual(
    validateInquiryReplyDraft({ assigneeName: "佐藤", message: "😀".repeat(2_500) }),
    {}
  );
  assert.equal(
    validateInquiryReplyDraft({ assigneeName: "佐藤", message: `${"😀".repeat(2_500)}a` }).message,
    "返信は5,000文字以内で入力してください。"
  );
});

test("reply validation rejects a blank message", () => {
  assert.equal(
    validateInquiryReplyDraft({ assigneeName: "佐藤", message: " \n　" }).message,
    "返信を入力してください。"
  );
});

test("success is the only outcome that clears the draft and snapshot", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const sent = inquiryReplyReducer(submitting, { type: "send_succeeded" });

  assert.deepEqual(sent, {
    status: "sent",
    draft: { assigneeName: "", message: "" },
    snapshot: null,
    errorMessage: null
  });
});

test("known failure and unknown delivery retain the draft and immutable snapshot", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const failed = inquiryReplyReducer(submitting, {
    type: "send_failed",
    errorMessage: "LINEへの送信が拒否されました。"
  });
  const unknown = inquiryReplyReducer(submitting, {
    type: "delivery_unknown",
    errorMessage: "送信結果を確認できません。"
  });

  for (const outcome of [failed, unknown]) {
    assert.deepEqual(outcome.draft, submitting.draft);
    assert.strictEqual(outcome.snapshot, submitting.snapshot);
  }
  assert.equal(failed.status, "failed");
  assert.equal(unknown.status, "delivery_unknown");
});

test("retry submits the same immutable operation and idempotency key", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const unknown = inquiryReplyReducer(submitting, { type: "delivery_unknown" });
  const retried = inquiryReplyReducer(unknown, { type: "retry" });

  assert.equal(retried.status, "submitting");
  assert.strictEqual(retried.snapshot, unknown.snapshot);
  assert.equal(retried.snapshot?.idempotencyKey, firstKey);
});

test("the browser reply serializer emits only the four allowed fields", () => {
  const snapshot = confirmingState().snapshot;
  assert.ok(snapshot);

  const request = serializeInquiryReplyRequest(snapshot);

  assert.deepEqual(Object.keys(request).sort(), [
    "assignee_name",
    "expected_updated_at",
    "idempotency_key",
    "message"
  ]);
  assert.deepEqual(request, {
    assignee_name: "佐藤",
    message: "お問い合わせありがとうございます。",
    idempotency_key: firstKey,
    expected_updated_at: expectedUpdatedAt
  });
  assert.equal("company_id" in request, false);
  assert.equal("line_user_id" in request, false);
});

test("admin API errors retain status and reason without exposing raw response text", () => {
  const known = new AdminApiError(409, "INQUIRY_CONFLICT");
  const unknown = new AdminApiError(500, "upstream secret response body");

  assert.equal(known.status, 409);
  assert.equal(known.reasonCode, "INQUIRY_CONFLICT");
  assert.equal(known.message, "問い合わせが更新されています。最新の内容を確認してください。");
  assert.equal(unknown.status, 500);
  assert.equal(unknown.reasonCode, "upstream secret response body");
  assert.equal(unknown.message, "処理に失敗しました。時間をおいてもう一度お試しください。");
  assert.equal(unknown.message.includes("secret"), false);
});
