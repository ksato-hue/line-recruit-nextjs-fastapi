import { utf16CodeUnitLength } from "../../lib/send-confirmation";
import type {
  InquiryReply,
  InquiryReplyResponse,
  InquiryStatus,
  InquirySummary
} from "../../types";
import type {
  InquiryReplyAction,
  InquiryReplyDraft,
  InquiryReplyDraftErrors,
  InquiryReplySnapshot,
  InquiryReplyState,
  InquiryWorkspaceCopyState,
  InquiryWorkspaceState,
  SerializedInquiryReplyRequest
} from "./types";

export function createInitialInquiryWorkspaceState(options: {
  initialInquiryId?: string;
  initialStatus?: InquiryStatus;
} = {}): InquiryWorkspaceState {
  return {
    query: {
      status: options.initialStatus || null,
      sort: "newest"
    },
    selectedInquiryId: options.initialInquiryId || null
  };
}

export function selectInquiryAfterRefresh(
  selectedInquiryId: string | null,
  inquiries: readonly InquirySummary[],
  suppliedInquiryId?: string
) {
  if (selectedInquiryId === suppliedInquiryId) return selectedInquiryId;
  if (selectedInquiryId && inquiries.some((inquiry) => inquiry.id === selectedInquiryId)) {
    return selectedInquiryId;
  }
  return inquiries[0]?.id || null;
}

export function resetInquiryWorkspaceFilter(
  state: InquiryWorkspaceState
): InquiryWorkspaceState {
  return {
    ...state,
    query: { ...state.query, status: null }
  };
}

export function sortInquiryRepliesChronologically(
  replies: readonly InquiryReply[]
) {
  return [...replies].sort((left, right) => {
    const leftTime = Date.parse(left.created_at);
    const rightTime = Date.parse(right.created_at);
    const timeDifference = leftTime - rightTime;
    return timeDifference || left.id.localeCompare(right.id);
  });
}

export function getInquiryWorkspaceCopy(
  state: InquiryWorkspaceCopyState,
  options: { isFiltered?: boolean; errorMessage?: string } = {}
) {
  switch (state) {
    case "loading":
      return "お問い合わせを取得中...";
    case "empty":
      return options.isFiltered
        ? "選択した条件に一致するお問い合わせはありません。"
        : "まだお問い合わせはありません。";
    case "error":
      return options.errorMessage || "お問い合わせの取得に失敗しました。";
    case "read-only":
      return "返信機能は現在利用できません。内容と履歴のみ確認できます。";
  }
}

const EMPTY_DRAFT: InquiryReplyDraft = Object.freeze({
  assigneeName: "",
  message: ""
});

export function createInitialInquiryReplyState(options?: {
  storedAssigneeName: string | null;
  defaultAssigneeName: string;
}): InquiryReplyState {
  if (options) {
    return {
      status: "editing",
      draft: {
        assigneeName: options.storedAssigneeName || options.defaultAssigneeName,
        message: ""
      },
      snapshot: null,
      errorMessage: null
    };
  }
  return {
    status: "idle",
    draft: EMPTY_DRAFT,
    snapshot: null,
    errorMessage: null
  };
}

function createBrowserUuid() {
  if (!globalThis.crypto?.randomUUID) {
    throw new Error("UUID generation is unavailable");
  }
  return globalThis.crypto.randomUUID();
}

function createSnapshot(
  state: InquiryReplyState,
  action: Extract<InquiryReplyAction, { type: "open_confirmation" }>
): InquiryReplySnapshot {
  return Object.freeze({
    inquiryId: action.inquiryId,
    assigneeName: state.draft.assigneeName.trim(),
    message: state.draft.message,
    messageCodeUnits: utf16CodeUnitLength(state.draft.message),
    idempotencyKey: (action.createId || createBrowserUuid)(),
    expectedUpdatedAt: action.expectedUpdatedAt,
    maskedDestination: action.maskedDestination
  });
}

export function inquiryReplyReducer(
  state: InquiryReplyState,
  action: InquiryReplyAction
): InquiryReplyState {
  switch (action.type) {
    case "edit":
      if (state.status === "submitting") return state;
      return {
        status: "editing",
        draft: {
          assigneeName: action.assigneeName ?? state.draft.assigneeName,
          message: action.message ?? state.draft.message
        },
        snapshot: null,
        errorMessage: null
      };
    case "open_confirmation":
      if (state.status !== "idle" && state.status !== "editing") return state;
      return {
        ...state,
        status: "confirming",
        snapshot: createSnapshot(state, action),
        errorMessage: null
      };
    case "cancel_confirmation":
      if (state.status !== "confirming") return state;
      return {
        ...state,
        status: "editing",
        snapshot: null,
        errorMessage: null
      };
    case "submit":
      if (state.status !== "confirming" || state.snapshot === null) return state;
      return { ...state, status: "submitting", errorMessage: null };
    case "send_succeeded":
      if (state.status !== "submitting" || state.snapshot === null) return state;
      return {
        status: "sent",
        draft: EMPTY_DRAFT,
        snapshot: null,
        errorMessage: null,
        sentResult: {
          assigneeName: state.snapshot.assigneeName,
          inquiryStatus: action.inquiryStatus,
          sentAt: action.sentAt
        }
      };
    case "send_failed":
      if (state.status !== "submitting") return state;
      return {
        ...state,
        status: "failed",
        errorMessage: action.errorMessage || null,
        ...(action.failureKind ? { failureKind: action.failureKind } : {})
      };
    case "delivery_unknown":
      if (state.status !== "submitting") return state;
      return {
        ...state,
        status: "delivery_unknown",
        errorMessage: action.errorMessage || null
      };
    case "retry":
      if (state.status !== "delivery_unknown" || state.snapshot === null) {
        return state;
      }
      return { ...state, status: "submitting", errorMessage: null };
    case "detail_refreshed":
      if (state.status !== "failed" || state.failureKind !== "conflict") {
        return state;
      }
      return {
        status: "editing",
        draft: state.draft,
        snapshot: null,
        errorMessage: null
      };
    case "inquiry_reopened":
      if (state.status !== "failed" || state.failureKind !== "reopen_required") {
        return state;
      }
      return {
        status: "editing",
        draft: state.draft,
        snapshot: null,
        errorMessage: null
      };
    case "resume_editing":
      if (state.status !== "failed") return state;
      return {
        status: "editing",
        draft: state.draft,
        snapshot: null,
        errorMessage: null
      };
    case "timeline_refreshed":
      return state;
  }
}

export function validateInquiryReplyDraft(
  draft: InquiryReplyDraft
): InquiryReplyDraftErrors {
  const errors: InquiryReplyDraftErrors = {};
  const assigneeName = draft.assigneeName.trim();

  if (!assigneeName) {
    errors.assigneeName = "担当者名を入力してください。";
  } else if (assigneeName.length > 80) {
    errors.assigneeName = "担当者名は80文字以内で入力してください。";
  }

  if (!draft.message.trim()) {
    errors.message = "返信を入力してください。";
  } else if (utf16CodeUnitLength(draft.message) > 5_000) {
    errors.message = "返信は5,000文字以内で入力してください。";
  }

  return errors;
}

export function createInquiryReplyCoordinator(dependencies: {
  sendReply: (
    inquiryId: string,
    request: SerializedInquiryReplyRequest
  ) => Promise<InquiryReplyResponse>;
  scheduleFocus: (focus: () => void) => void;
}) {
  let submitting = false;

  return {
    validateForConfirmation(
      draft: InquiryReplyDraft,
      focusTargets: Readonly<{
        assignee: () => void;
        message: () => void;
      }>
    ) {
      const errors = validateInquiryReplyDraft(draft);
      if (errors.assigneeName) {
        dependencies.scheduleFocus(focusTargets.assignee);
      } else if (errors.message) {
        dependencies.scheduleFocus(focusTargets.message);
      }
      return errors;
    },

    cancelConfirmation(dispatch: (action: InquiryReplyAction) => void) {
      dispatch({ type: "cancel_confirmation" });
    },

    async submitReply(snapshot: InquiryReplySnapshot) {
      if (submitting) return null;
      submitting = true;
      try {
        return await dependencies.sendReply(
          snapshot.inquiryId,
          serializeInquiryReplyRequest(snapshot)
        );
      } finally {
        submitting = false;
      }
    },

    async reopenForReply(options: Readonly<{
      expectedUpdatedAt: string;
      reopen: (expectedUpdatedAt: string) => Promise<void>;
      onReopened: () => void;
      refreshRelatedViews: () => Promise<void>;
    }>) {
      await options.reopen(options.expectedUpdatedAt);
      options.onReopened();
      try {
        await options.refreshRelatedViews();
        return "refreshed" as const;
      } catch {
        return "refresh_failed" as const;
      }
    }
  };
}

export function serializeInquiryReplyRequest(
  snapshot: InquiryReplySnapshot
): SerializedInquiryReplyRequest {
  return {
    assignee_name: snapshot.assigneeName,
    message: snapshot.message,
    idempotency_key: snapshot.idempotencyKey,
    expected_updated_at: snapshot.expectedUpdatedAt
  };
}
