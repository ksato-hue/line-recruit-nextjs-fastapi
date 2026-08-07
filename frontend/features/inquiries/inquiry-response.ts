import { utf16CodeUnitLength } from "../../lib/send-confirmation";
import type {
  InquiryReplyAction,
  InquiryReplyDraft,
  InquiryReplyDraftErrors,
  InquiryReplySnapshot,
  InquiryReplyState,
  SerializedInquiryReplyRequest
} from "./types";

const EMPTY_DRAFT: InquiryReplyDraft = Object.freeze({
  assigneeName: "",
  message: ""
});

export function createInitialInquiryReplyState(): InquiryReplyState {
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
    assigneeName: state.draft.assigneeName,
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
      if (state.status !== "submitting") return state;
      return {
        status: "sent",
        draft: EMPTY_DRAFT,
        snapshot: null,
        errorMessage: null
      };
    case "send_failed":
      if (state.status !== "submitting") return state;
      return {
        ...state,
        status: "failed",
        errorMessage: action.errorMessage || null
      };
    case "delivery_unknown":
      if (state.status !== "submitting") return state;
      return {
        ...state,
        status: "delivery_unknown",
        errorMessage: action.errorMessage || null
      };
    case "retry":
      if (
        (state.status !== "failed" && state.status !== "delivery_unknown")
        || state.snapshot === null
      ) {
        return state;
      }
      return { ...state, status: "submitting", errorMessage: null };
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
