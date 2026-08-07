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
  createInitialInquiryWorkspaceState,
  createInitialInquiryReplyState,
  getInquiryWorkspaceCopy,
  inquiryReplyReducer,
  resetInquiryWorkspaceFilter,
  selectInquiryAfterRefresh,
  serializeInquiryReplyRequest,
  sortInquiryRepliesChronologically,
  validateInquiryReplyDraft
} = require("../features/inquiries/inquiry-response.ts") as typeof import(
  "../features/inquiries/inquiry-response"
);

const inquiryId = "10000000-0000-0000-0000-000000000001";
const firstKey = "20000000-0000-0000-0000-000000000001";
const secondKey = "20000000-0000-0000-0000-000000000002";
const expectedUpdatedAt = "2026-08-07T00:00:00+00:00";

type InquiryRelatedApplicant = import("../types").InquiryRelatedApplicant;
type ExpectedRelatedApplicant = {
  id: string;
  name: string | null;
  job: string | null;
  status: string | null;
  interview_status: string | null;
  created_at: string | null;
};
type Equal<Left, Right> =
  (<Value>() => Value extends Left ? 1 : 2) extends
  (<Value>() => Value extends Right ? 1 : 2)
    ? (<Value>() => Value extends Right ? 1 : 2) extends
      (<Value>() => Value extends Left ? 1 : 2)
      ? true
      : false
    : false;

const relatedApplicantTypeIsExact: Equal<
  InquiryRelatedApplicant,
  ExpectedRelatedApplicant
> = true;

const relatedApplicantFixture: InquiryRelatedApplicant = {
  id: "30000000-0000-0000-0000-000000000001",
  name: null,
  job: null,
  status: null,
  interview_status: null,
  created_at: null
};

const inquirySummaries: import("../types").InquirySummary[] = [
  {
    id: inquiryId,
    message_preview: "最初のお問い合わせ",
    created_at: "2026-08-07T00:00:00+00:00",
    status: "未対応",
    assignee_name: null,
    last_replied_at: null,
    updated_at: "2026-08-07T00:00:00+00:00",
    related_applicant_exists: false,
    unanswered_age_seconds: 60
  },
  {
    id: "10000000-0000-0000-0000-000000000002",
    message_preview: "次のお問い合わせ",
    created_at: "2026-08-06T00:00:00+00:00",
    status: "対応中",
    assignee_name: "佐藤",
    last_replied_at: null,
    updated_at: "2026-08-06T00:00:00+00:00",
    related_applicant_exists: true,
    unanswered_age_seconds: null
  }
];

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

test("workspace query state initializes with a supplied Dashboard filter and inquiry", () => {
  assert.deepEqual(
    createInitialInquiryWorkspaceState({
      initialInquiryId: inquiryId,
      initialStatus: "未対応"
    }),
    {
      query: { status: "未対応", sort: "newest" },
      selectedInquiryId: inquiryId
    }
  );
  assert.deepEqual(createInitialInquiryWorkspaceState(), {
    query: { status: null, sort: "newest" },
    selectedInquiryId: null
  });
});

test("list refresh preserves a selected inquiry and otherwise selects the first result", () => {
  const selectedId = inquirySummaries[1].id;

  assert.equal(
    selectInquiryAfterRefresh(selectedId, inquirySummaries),
    selectedId
  );
  assert.equal(
    selectInquiryAfterRefresh("removed-inquiry", inquirySummaries),
    inquiryId
  );
  assert.equal(selectInquiryAfterRefresh(null, []), null);
});

test("a supplied Dashboard inquiry opens even when it is outside the current list", () => {
  const dashboardInquiryId = "10000000-0000-0000-0000-000000000099";

  assert.equal(
    selectInquiryAfterRefresh(dashboardInquiryId, inquirySummaries, dashboardInquiryId),
    dashboardInquiryId
  );
});

test("resetting the workspace filter keeps the current selection", () => {
  const state = createInitialInquiryWorkspaceState({
    initialInquiryId: inquiryId,
    initialStatus: "未対応"
  });

  assert.deepEqual(resetInquiryWorkspaceFilter(state), {
    query: { status: null, sort: "newest" },
    selectedInquiryId: inquiryId
  });
  assert.deepEqual(state.query, { status: "未対応", sort: "newest" });
});

test("reply history is copied and sorted from oldest to newest", () => {
  const newest: import("../types").InquiryReply = {
    id: "reply-newest",
    assignee_name: "佐藤",
    message: "後の返信",
    delivery_status: "sent",
    safe_error_code: null,
    created_at: "2026-08-07T02:00:00+00:00",
    updated_at: "2026-08-07T02:00:00+00:00",
    sent_at: "2026-08-07T02:00:00+00:00"
  };
  const oldest: import("../types").InquiryReply = {
    ...newest,
    id: "reply-oldest",
    message: "先の返信",
    created_at: "2026-08-07T01:00:00+00:00",
    updated_at: "2026-08-07T01:00:00+00:00",
    sent_at: "2026-08-07T01:00:00+00:00"
  };
  const replies = [newest, oldest];

  assert.deepEqual(
    sortInquiryRepliesChronologically(replies).map((reply) => reply.id),
    ["reply-oldest", "reply-newest"]
  );
  assert.deepEqual(replies.map((reply) => reply.id), ["reply-newest", "reply-oldest"]);
});

test("workspace state copy distinguishes loading, empty, filtered, error and read-only", () => {
  assert.equal(getInquiryWorkspaceCopy("loading"), "お問い合わせを取得中...");
  assert.equal(getInquiryWorkspaceCopy("empty"), "まだお問い合わせはありません。");
  assert.equal(
    getInquiryWorkspaceCopy("empty", { isFiltered: true }),
    "選択した条件に一致するお問い合わせはありません。"
  );
  assert.equal(
    getInquiryWorkspaceCopy("error", { errorMessage: "通信に失敗しました" }),
    "通信に失敗しました"
  );
  assert.equal(
    getInquiryWorkspaceCopy("read-only"),
    "返信機能は現在利用できません。内容と履歴のみ確認できます。"
  );
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

test("a known failure cannot retry until edit and reconfirm create a new key", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const failed = inquiryReplyReducer(submitting, { type: "send_failed" });
  const forbiddenRetry = inquiryReplyReducer(failed, { type: "retry" });

  assert.strictEqual(forbiddenRetry, failed);

  const edited = inquiryReplyReducer(failed, {
    type: "edit",
    message: "内容を確認して再送します。"
  });
  const reconfirmed = inquiryReplyReducer(edited, {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt,
    maskedDestination: "U1234…7890",
    createId: () => secondKey
  });

  assert.equal(reconfirmed.status, "confirming");
  assert.equal(reconfirmed.snapshot?.idempotencyKey, secondKey);
  assert.notEqual(reconfirmed.snapshot?.idempotencyKey, failed.snapshot?.idempotencyKey);
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
  const unknown = new AdminApiError(500, "INTERNAL_SECRET_TOKEN");

  assert.equal(known.status, 409);
  assert.equal(known.reasonCode, "INQUIRY_CONFLICT");
  assert.equal(known.message, "問い合わせが更新されています。最新の内容を確認してください。");
  assert.equal(unknown.status, 500);
  assert.equal(unknown.reasonCode, null);
  assert.equal(unknown.message, "処理に失敗しました。時間をおいてもう一度お試しください。");
  assert.equal(unknown.message.includes("SECRET"), false);
});

test("related applicant fixtures match the exact nullable Backend response", () => {
  assert.equal(relatedApplicantTypeIsExact, true);
  assert.deepEqual(relatedApplicantFixture, {
    id: "30000000-0000-0000-0000-000000000001",
    name: null,
    job: null,
    status: null,
    interview_status: null,
    created_at: null
  });
});
