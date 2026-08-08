import type { InquiryReplyRequest, InquiryStatus, InquirySummary } from "../../types";

export type InquiryWorkspaceQuery = Readonly<{
  status: InquiryStatus | null;
  sort: "oldest" | "newest";
}>;

export type InquiryWorkspaceState = Readonly<{
  query: InquiryWorkspaceQuery;
  selectedInquiryId: string | null;
  items: readonly InquirySummary[];
  nextCursor: string | null;
  loadingMore: boolean;
}>;

export type InquiryWorkspaceCopyState =
  | "loading"
  | "empty"
  | "error"
  | "read-only";

export type InquiryReplyStatus =
  | "idle"
  | "editing"
  | "confirming"
  | "submitting"
  | "sent"
  | "failed"
  | "delivery_unknown";

export type InquiryReplyFailureKind =
  | "conflict"
  | "reopen_required"
  | "rejected"
  | "other";

export type InquiryReplyDraft = Readonly<{
  assigneeName: string;
  message: string;
}>;

export type InquiryReplySnapshot = Readonly<{
  inquiryId: string;
  assigneeName: string;
  message: string;
  messageCodeUnits: number;
  idempotencyKey: string;
  expectedUpdatedAt: string;
  maskedDestination: string;
}>;

export type InquiryReplySentResult = Readonly<{
  assigneeName: string;
  inquiryStatus: "対応済み";
  sentAt: string;
}>;

export type InquiryReplyState = Readonly<{
  status: InquiryReplyStatus;
  draft: InquiryReplyDraft;
  snapshot: InquiryReplySnapshot | null;
  errorMessage: string | null;
  failureKind?: InquiryReplyFailureKind;
  sentResult?: InquiryReplySentResult;
}>;

export type InquiryReplyDraftErrors = Partial<Record<keyof InquiryReplyDraft, string>>;

export type InquiryReplyAction =
  | Readonly<{ type: "edit"; assigneeName?: string; message?: string }>
  | Readonly<{
      type: "open_confirmation";
      inquiryId: string;
      expectedUpdatedAt: string;
      maskedDestination: string;
      createId?: () => string;
    }>
  | Readonly<{ type: "cancel_confirmation" }>
  | Readonly<{ type: "submit" }>
  | Readonly<{
      type: "send_succeeded";
      inquiryStatus: "対応済み";
      sentAt: string;
    }>
  | Readonly<{
      type: "send_failed";
      failureKind?: InquiryReplyFailureKind;
      errorMessage?: string;
    }>
  | Readonly<{ type: "delivery_unknown"; errorMessage?: string }>
  | Readonly<{ type: "retry" }>
  | Readonly<{ type: "detail_refreshed" }>
  | Readonly<{ type: "inquiry_reopened" }>
  | Readonly<{ type: "resume_editing" }>
  | Readonly<{ type: "timeline_refreshed" }>;

export type SerializedInquiryReplyRequest = InquiryReplyRequest;
