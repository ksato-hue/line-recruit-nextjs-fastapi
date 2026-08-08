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
  appendInquiryWorkspacePage,
  closeInquiryMobileDetail,
  createDashboardInquiryNavigation,
  createDashboardInquiryPreview,
  createInquiryListCoordinator,
  createInquiryReplyCoordinator,
  createInitialInquiryWorkspaceState,
  createInitialInquiryReplyState,
  formatInquiryUnansweredAge,
  getDashboardUnansweredCopy,
  getInquiryWorkspaceCopy,
  inquiryReplyReducer,
  replaceInquiryWorkspacePage,
  resetInquiryWorkspaceFilter,
  resetInquiryWorkspaceQuery,
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
type DashboardRecentInquiries = import("../types").Dashboard["recent_inquiries"];
type ExpectedDashboardRecentInquiries = import("../types").InquirySummary[];
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
const dashboardRecentInquiriesTypeIsExact: Equal<
  DashboardRecentInquiries,
  ExpectedDashboardRecentInquiries
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

test("reply editing prefers the stored assignee over the Backend default", () => {
  const state = createInitialInquiryReplyState({
    storedAssigneeName: "高橋",
    defaultAssigneeName: "佐藤"
  });

  assert.equal(state.status, "editing");
  assert.deepEqual(state.draft, { assigneeName: "高橋", message: "" });
});

test("reply editing uses Backend-normalized half, full and multiple-space surnames unchanged", () => {
  const backendCases = [
    { recruiterSetting: "佐藤 太郎", backendDefault: "佐藤" },
    { recruiterSetting: "佐藤　太郎", backendDefault: "佐藤" },
    { recruiterSetting: "佐藤   太郎", backendDefault: "佐藤" }
  ] as const;

  for (const { recruiterSetting, backendDefault } of backendCases) {
    const state = createInitialInquiryReplyState({
      storedAssigneeName: null,
      defaultAssigneeName: backendDefault
    });

    assert.equal(state.draft.assigneeName, backendDefault, recruiterSetting);
  }
});

test("an empty Backend recruiter default leaves assignee editing manual and invalid", () => {
  const state = createInitialInquiryReplyState({
    storedAssigneeName: null,
    defaultAssigneeName: ""
  });

  assert.equal(state.status, "editing");
  assert.equal(state.draft.assigneeName, "");
  assert.equal(
    validateInquiryReplyDraft({ ...state.draft, message: "返信本文" }).assigneeName,
    "担当者名を入力してください。"
  );
});

test("workspace query state initializes with a supplied Dashboard filter and inquiry", () => {
  assert.deepEqual(
    createInitialInquiryWorkspaceState({
      initialInquiryId: inquiryId,
      initialStatus: "未対応",
      initialSort: "oldest"
    }),
    {
      query: { status: "未対応", sort: "oldest" },
      selectedInquiryId: inquiryId,
      items: [],
      nextCursor: null,
      loadingMore: false
    }
  );
  assert.deepEqual(createInitialInquiryWorkspaceState(), {
    query: { status: null, sort: "newest" },
    selectedInquiryId: null,
    items: [],
    nextCursor: null,
    loadingMore: false
  });
});

test("workspace retains the cursor and appends server pages without duplicate inquiry IDs", () => {
  const initial = createInitialInquiryWorkspaceState();
  const firstPage = replaceInquiryWorkspacePage(initial, {
    items: inquirySummaries,
    next_cursor: "cursor-page-2"
  });
  const thirdInquiry: import("../types").InquirySummary = {
    ...inquirySummaries[0],
    id: "10000000-0000-0000-0000-000000000003",
    message_preview: "最古のお問い合わせ"
  };
  const complete = appendInquiryWorkspacePage(firstPage, {
    items: [inquirySummaries[1], thirdInquiry],
    next_cursor: null
  });

  assert.equal(firstPage.nextCursor, "cursor-page-2");
  assert.deepEqual(
    complete.items.map((inquiry) => inquiry.id),
    [inquirySummaries[0].id, inquirySummaries[1].id, thirdInquiry.id]
  );
  assert.equal(complete.nextCursor, null);
  assert.equal(complete.loadingMore, false);
});

test("filter and sort changes reset items and cursor in the same state transition", () => {
  const loaded = replaceInquiryWorkspacePage(
    createInitialInquiryWorkspaceState({ initialInquiryId: inquiryId }),
    { items: inquirySummaries, next_cursor: "cursor-page-2" }
  );

  const reset = resetInquiryWorkspaceQuery(loaded, {
    status: "対応中",
    sort: "oldest"
  });

  assert.deepEqual(reset, {
    query: { status: "対応中", sort: "oldest" },
    selectedInquiryId: inquiryId,
    items: [],
    nextCursor: null,
    loadingMore: false
  });
});

test("the load-more coordinator ignores a concurrent request and releases its guard", async () => {
  type InquiryListResponse = import("../types").InquiryListResponse;
  const calls: import("../lib/api").InquiryListParams[] = [];
  let finishFirst!: (page: InquiryListResponse) => void;
  const firstPage = new Promise<InquiryListResponse>((resolve) => {
    finishFirst = resolve;
  });
  const coordinator = createInquiryListCoordinator({
    loadPage: async (params) => {
      calls.push(params);
      if (calls.length === 1) return firstPage;
      return { items: [], next_cursor: null };
    }
  });

  const first = coordinator.loadMore(
    { status: "未対応", sort: "oldest" },
    "cursor-page-2"
  );
  const duplicate = coordinator.loadMore(
    { status: "未対応", sort: "oldest" },
    "cursor-page-2"
  );

  assert.equal(duplicate, null);
  assert.deepEqual(calls, [{
    status: "未対応",
    sort: "oldest",
    limit: 100,
    cursor: "cursor-page-2"
  }]);
  finishFirst({ items: [], next_cursor: "cursor-page-3" });
  await first;
  await coordinator.loadMore(
    { status: "未対応", sort: "oldest" },
    "cursor-page-3"
  );
  assert.equal(calls.length, 2);
});

test("unanswered age copy is bounded and safe for invalid values", () => {
  assert.equal(formatInquiryUnansweredAge(30), "未対応: 1分未満");
  assert.equal(formatInquiryUnansweredAge(120), "未対応: 2分");
  assert.equal(formatInquiryUnansweredAge(3_660), "未対応: 1時間");
  assert.equal(formatInquiryUnansweredAge(172_800), "未対応: 2日");
  assert.equal(formatInquiryUnansweredAge(Number.NaN), "未対応時間不明");
  assert.equal(formatInquiryUnansweredAge(-1), "未対応時間不明");
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
    selectedInquiryId: inquiryId,
    items: [],
    nextCursor: null,
    loadingMore: false
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

test("Dashboard recent inquiry navigation hands off the exact inquiry ID", () => {
  assert.deepEqual(
    createDashboardInquiryNavigation({ type: "recent", inquiryId }),
    { activeMenu: "お問い合わせ", initialInquiryId: inquiryId }
  );
});

test("Dashboard unanswered navigation hands off the unanswered status filter", () => {
  assert.deepEqual(
    createDashboardInquiryNavigation({ type: "unanswered" }),
    { activeMenu: "お問い合わせ", initialStatus: "未対応", initialSort: "oldest" }
  );
});

test("Dashboard unanswered zero state uses the dedicated copy", () => {
  assert.equal(
    getDashboardUnansweredCopy(0),
    "未対応のお問い合わせはありません"
  );
  assert.equal(getDashboardUnansweredCopy(1), null);
});

test("Dashboard inquiry preview preserves the message and limits it to two lines", () => {
  assert.deepEqual(
    createDashboardInquiryPreview("1行目\n2行目\n3行目"),
    { text: "1行目\n2行目\n3行目", lineClamp: 2 }
  );
  assert.deepEqual(createDashboardInquiryPreview(""), {
    text: "内容未入力",
    lineClamp: 2
  });
});

test("mobile Back closes detail and clears the selection in one transition", () => {
  const state = {
    ...createInitialInquiryWorkspaceState({ initialInquiryId: inquiryId }),
    mobileDetailOpen: true
  };

  assert.deepEqual(closeInquiryMobileDetail(state), {
    query: { status: null, sort: "newest" },
    selectedInquiryId: null,
    items: [],
    nextCursor: null,
    loadingMore: false,
    mobileDetailOpen: false
  });
});

test("confirmation trims only the assignee while preserving the exact reply text", () => {
  const editing = inquiryReplyReducer(createInitialInquiryReplyState(), {
    type: "edit",
    assigneeName: "  佐藤　",
    message: " 1行目\n2行目 \n"
  });
  const opened = inquiryReplyReducer(editing, {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt,
    maskedDestination: "U1234…7890",
    createId: () => firstKey
  });

  assert.equal(opened.snapshot?.assigneeName, "佐藤");
  assert.equal(opened.snapshot?.message, " 1行目\n2行目 \n");
  assert.deepEqual(serializeInquiryReplyRequest(opened.snapshot!), {
    assignee_name: "佐藤",
    message: " 1行目\n2行目 \n",
    idempotency_key: firstKey,
    expected_updated_at: expectedUpdatedAt
  });
});

test("cancelling confirmation keeps the draft and discards the snapshot", () => {
  const confirming = confirmingState();
  const cancelled = inquiryReplyReducer(confirming, { type: "cancel_confirmation" });

  assert.equal(cancelled.status, "editing");
  assert.deepEqual(cancelled.draft, confirming.draft);
  assert.equal(cancelled.snapshot, null);
});

test("a second cancel event such as Escape after button cancel is a no-op", () => {
  const cancelled = inquiryReplyReducer(confirmingState(), {
    type: "cancel_confirmation"
  });

  assert.strictEqual(
    inquiryReplyReducer(cancelled, { type: "cancel_confirmation" }),
    cancelled
  );
});

test("a second submit dispatch while submitting is a no-op", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const duplicate = inquiryReplyReducer(submitting, { type: "submit" });

  assert.equal(submitting.status, "submitting");
  assert.strictEqual(duplicate, submitting);
});

test("reply validation focuses the assignee first without calling the send API", () => {
  let sendCalls = 0;
  const focused: string[] = [];
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async () => {
      sendCalls += 1;
      throw new Error("send must not run during validation");
    },
    scheduleFocus: (focus) => focus()
  });

  const errors = coordinator.validateForConfirmation(
    { assigneeName: " 　", message: "" },
    {
      assignee: () => focused.push("assignee"),
      message: () => focused.push("message")
    }
  );

  assert.deepEqual(errors, {
    assigneeName: "担当者名を入力してください。",
    message: "返信を入力してください。"
  });
  assert.deepEqual(focused, ["assignee"]);
  assert.equal(sendCalls, 0);
});

test("reply validation focuses the message when the assignee is valid", () => {
  const focused: string[] = [];
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async () => {
      throw new Error("send must not run during validation");
    },
    scheduleFocus: (focus) => focus()
  });

  const errors = coordinator.validateForConfirmation(
    { assigneeName: "佐藤", message: "\n　" },
    {
      assignee: () => focused.push("assignee"),
      message: () => focused.push("message")
    }
  );

  assert.deepEqual(errors, { message: "返信を入力してください。" });
  assert.deepEqual(focused, ["message"]);
});

test("the dialog onCancel boundary, including Escape, retains the draft with zero sends", () => {
  let sendCalls = 0;
  let state = confirmingState();
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async () => {
      sendCalls += 1;
      throw new Error("send must not run during cancellation");
    },
    scheduleFocus: (focus) => focus()
  });

  coordinator.cancelConfirmation((action) => {
    state = inquiryReplyReducer(state, action);
  });

  assert.equal(state.status, "editing");
  assert.deepEqual(state.draft, {
    assigneeName: "佐藤",
    message: "お問い合わせありがとうございます。"
  });
  assert.equal(state.snapshot, null);
  assert.equal(sendCalls, 0);
});

test("confirm submits the exact immutable snapshot through the dedicated reply API", async () => {
  const calls: Array<{
    id: string;
    request: import("../types").InquiryReplyRequest;
  }> = [];
  const response: import("../types").InquiryReplyResponse = {
    outcome: "sent",
    reply_id: "reply-1",
    delivery_status: "sent",
    inquiry_status: "対応済み",
    sent_at: "2026-08-07T03:00:00+00:00",
    idempotent_replay: false
  };
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async (id, request) => {
      calls.push({ id, request });
      return response;
    },
    scheduleFocus: (focus) => focus()
  });
  const snapshot = confirmingState().snapshot;
  assert.ok(snapshot);

  const result = await coordinator.submitReply(snapshot);

  assert.strictEqual(result, response);
  assert.deepEqual(calls, [{
    id: inquiryId,
    request: {
      assignee_name: "佐藤",
      message: "お問い合わせありがとうございます。",
      idempotency_key: firstKey,
      expected_updated_at: expectedUpdatedAt
    }
  }]);
});

test("concurrent confirm clicks make exactly one reply API call", async () => {
  let sendCalls = 0;
  let finishSend!: (response: import("../types").InquiryReplyResponse) => void;
  const pendingSend = new Promise<import("../types").InquiryReplyResponse>((resolve) => {
    finishSend = resolve;
  });
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async () => {
      sendCalls += 1;
      return pendingSend;
    },
    scheduleFocus: (focus) => focus()
  });
  const snapshot = confirmingState().snapshot;
  assert.ok(snapshot);

  const first = coordinator.submitReply(snapshot);
  const duplicate = coordinator.submitReply(snapshot);

  assert.equal(await duplicate, null);
  assert.equal(sendCalls, 1);
  finishSend({
    outcome: "delivery_unknown",
    reply_id: "reply-1",
    delivery_status: "delivery_unknown",
    reason_code: "DELIVERY_RESULT_UNKNOWN"
  });
  assert.equal((await first)?.outcome, "delivery_unknown");
  assert.equal(sendCalls, 1);
});

test("successful reopen enables editing before a related-view refresh failure", async () => {
  const events: string[] = [];
  const coordinator = createInquiryReplyCoordinator({
    sendReply: async () => {
      throw new Error("send is unrelated to reopen");
    },
    scheduleFocus: (focus) => focus()
  });

  const result = await coordinator.reopenForReply({
    expectedUpdatedAt,
    reopen: async (timestamp) => {
      assert.equal(timestamp, expectedUpdatedAt);
      events.push("patch");
    },
    onReopened: () => events.push("editing"),
    refreshRelatedViews: async () => {
      events.push("refresh");
      throw new Error("dashboard unavailable");
    }
  });

  assert.equal(result, "refresh_failed");
  assert.deepEqual(events, ["patch", "editing", "refresh"]);
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
  const sent = inquiryReplyReducer(submitting, {
    type: "send_succeeded",
    inquiryStatus: "対応済み",
    sentAt: "2026-08-07T03:00:00+00:00"
  });

  assert.deepEqual(sent, {
    status: "sent",
    draft: { assigneeName: "", message: "" },
    snapshot: null,
    errorMessage: null,
    sentResult: {
      assigneeName: "佐藤",
      inquiryStatus: "対応済み",
      sentAt: "2026-08-07T03:00:00+00:00"
    }
  });
});

test("a 409 stale conflict retains the operation until an explicit detail refresh", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const conflicted = inquiryReplyReducer(submitting, {
    type: "send_failed",
    failureKind: "conflict",
    errorMessage: "別の更新がありました。最新の内容を確認してください。"
  });

  assert.equal(conflicted.status, "failed");
  assert.equal(conflicted.failureKind, "conflict");
  assert.deepEqual(conflicted.draft, submitting.draft);
  assert.strictEqual(conflicted.snapshot, submitting.snapshot);

  const refreshed = inquiryReplyReducer(conflicted, { type: "detail_refreshed" });
  assert.equal(refreshed.status, "editing");
  assert.deepEqual(refreshed.draft, submitting.draft);
  assert.equal(refreshed.snapshot, null);

  const reconfirmed = inquiryReplyReducer(refreshed, {
    type: "open_confirmation",
    inquiryId,
    expectedUpdatedAt: "2026-08-07T04:00:00+00:00",
    maskedDestination: "U1234…7890",
    createId: () => secondKey
  });
  assert.equal(reconfirmed.snapshot?.idempotencyKey, secondKey);
});

test("a completed inquiry requires an explicit successful reopen before reconfirmation", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const blocked = inquiryReplyReducer(submitting, {
    type: "send_failed",
    failureKind: "reopen_required",
    errorMessage: "返信するには、先に再対応を開始してください。"
  });

  assert.equal(blocked.failureKind, "reopen_required");
  assert.strictEqual(
    inquiryReplyReducer(blocked, {
      type: "open_confirmation",
      inquiryId,
      expectedUpdatedAt,
      maskedDestination: "U1234…7890"
    }),
    blocked
  );

  const reopened = inquiryReplyReducer(blocked, { type: "inquiry_reopened" });
  assert.equal(reopened.status, "editing");
  assert.deepEqual(reopened.draft, submitting.draft);
  assert.equal(reopened.snapshot, null);
});

test("a 502 known LINE rejection retains the snapshot until explicit editing", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const rejected = inquiryReplyReducer(submitting, {
    type: "send_failed",
    failureKind: "rejected",
    errorMessage: "LINEへ返信できませんでした。"
  });

  assert.equal(rejected.failureKind, "rejected");
  assert.strictEqual(rejected.snapshot, submitting.snapshot);
  assert.strictEqual(inquiryReplyReducer(rejected, { type: "submit" }), rejected);

  const editing = inquiryReplyReducer(rejected, { type: "resume_editing" });
  assert.equal(editing.status, "editing");
  assert.deepEqual(editing.draft, submitting.draft);
  assert.equal(editing.snapshot, null);
});

test("a 202 unknown outcome retains the same operation for timeline refresh and retry", () => {
  const submitting = inquiryReplyReducer(confirmingState(), { type: "submit" });
  const unknown = inquiryReplyReducer(submitting, {
    type: "delivery_unknown",
    errorMessage: "送信結果を確認しています。"
  });
  const timelineRefreshed = inquiryReplyReducer(unknown, {
    type: "timeline_refreshed"
  });

  assert.strictEqual(timelineRefreshed, unknown);
  const retried = inquiryReplyReducer(unknown, { type: "retry" });
  assert.strictEqual(retried.snapshot, unknown.snapshot);
  assert.equal(retried.snapshot?.idempotencyKey, firstKey);
  assert.equal(retried.status, "submitting");
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
