import type { InquiryReplyRequest } from "../../types";

export type InquiryReplyStatus =
  | "idle"
  | "editing"
  | "confirming"
  | "submitting"
  | "sent"
  | "failed"
  | "delivery_unknown";

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

export type InquiryReplyState = Readonly<{
  status: InquiryReplyStatus;
  draft: InquiryReplyDraft;
  snapshot: InquiryReplySnapshot | null;
  errorMessage: string | null;
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
  | Readonly<{ type: "send_succeeded" }>
  | Readonly<{ type: "send_failed"; errorMessage?: string }>
  | Readonly<{ type: "delivery_unknown"; errorMessage?: string }>
  | Readonly<{ type: "retry" }>;

export type SerializedInquiryReplyRequest = InquiryReplyRequest;
