import type {
  AppSettings,
  Applicant,
  ApplicantStatusSetting,
  Dashboard,
  FAQ,
  FAQCategory,
  FAQPayload,
  FAQSetting,
  FAQSettingUpdatePayload,
  FAQUpdatePayload,
  Inquiry,
  InquiryDetailResponse,
  InquiryListResponse,
  InquiryReplyRequest,
  InquiryReplyResponse,
  InquiryStatus,
  InquiryUpdateRequest,
  InquiryRecord,
  InterviewSlot,
  InterviewSlotCreateRequest,
  InterviewSlotCreateResponse,
  LineMessageLog,
  LineSendRequest,
  LineSendResponse,
  QuestionTree
} from "../types";

export type InquiryListParams = {
  status?: InquiryStatus;
  sort?: "oldest" | "newest";
  limit?: number;
  cursor?: string;
};

const ADMIN_API_REASON_MESSAGES: Readonly<Record<string, string>> = {
  INQUIRY_CONFLICT: "問い合わせが更新されています。最新の内容を確認してください。",
  INVALID_STATUS_TRANSITION: "この状態には変更できません。最新の内容を確認してください。",
  INQUIRY_REOPEN_REQUIRED: "返信するには、先に再対応を開始してください。",
  IDEMPOTENCY_CONFLICT: "送信内容が変更されています。内容を確認してもう一度操作してください。",
  REPLY_IN_PROGRESS: "この返信は処理中です。しばらくしてから履歴を確認してください。",
  RETRY_WINDOW_EXPIRED: "再送可能な時間を過ぎています。送信履歴を確認してください。",
  DELIVERY_RESULT_UNKNOWN: "送信結果を確認できません。再送せず、履歴を確認してください。",
  LINE_REJECTED: "LINEへの送信が拒否されました。内容を確認して、もう一度お試しください。",
  INQUIRY_REPLY_WORKFLOW_DISABLED: "問い合わせ返信は現在利用できません。",
  LINE_CONFIGURATION_UNAVAILABLE: "LINE送信の設定を確認できません。管理者に連絡してください。",
  INQUIRY_REPLY_UNAVAILABLE: "問い合わせ返信を処理できません。時間をおいてお試しください。"
};

const ADMIN_API_STATUS_MESSAGES: Readonly<Record<number, string>> = {
  0: "サーバーに接続できません。通信環境を確認してください。",
  401: "認証が必要です。ページを再読み込みしてください。",
  403: "この操作を実行する権限がありません。",
  404: "対象のデータが見つかりません。",
  409: "最新の内容と競合しました。内容を確認してください。",
  422: "入力内容を確認してください。",
  502: "LINEへの送信に失敗しました。時間をおいてもう一度お試しください。",
  503: "サービスを利用できません。時間をおいてもう一度お試しください。"
};

function safeAdminApiMessage(status: number, reasonCode: string | null) {
  if (reasonCode && ADMIN_API_REASON_MESSAGES[reasonCode]) {
    return ADMIN_API_REASON_MESSAGES[reasonCode];
  }
  return ADMIN_API_STATUS_MESSAGES[status]
    || "処理に失敗しました。時間をおいてもう一度お試しください。";
}

export class AdminApiError extends Error {
  readonly status: number;
  readonly reasonCode: string | null;

  constructor(status: number, reasonCode: string | null = null) {
    super(safeAdminApiMessage(status, reasonCode));
    this.name = "AdminApiError";
    this.status = status;
    this.reasonCode = reasonCode;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

function parseSafeReasonCode(body: string) {
  try {
    const detail = (JSON.parse(body) as { detail?: unknown }).detail;
    return typeof detail === "string" && /^[A-Z][A-Z0-9_]{0,79}$/.test(detail)
      ? detail
      : null;
  } catch {
    return null;
  }
}

// 管理APIは同一オリジンのNext.jsプロキシ(/api/admin/*)経由で呼びます。
// 管理キーはサーバー側でのみ付与されるため、ブラウザには露出しません。
async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/admin${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers || {})
      },
      cache: "no-store"
    });
  } catch {
    throw new AdminApiError(0);
  }

  if (!response.ok) {
    const reasonCode = parseSafeReasonCode(await response.text());
    throw new AdminApiError(response.status, reasonCode);
  }

  return response.json();
}

export function getDashboard() {
  return adminRequest<Dashboard>("/dashboard");
}

export function getApplicants() {
  return adminRequest<Applicant[]>("/applicants");
}

export function getInquiries(): Promise<Inquiry[]>;
export function getInquiries(params: InquiryListParams): Promise<InquiryListResponse>;
export async function getInquiries(params?: InquiryListParams) {
  const search = new URLSearchParams();
  if (params?.status) search.set("status", params.status);
  if (params?.sort) search.set("sort", params.sort);
  if (params?.limit !== undefined) search.set("limit", String(params.limit));
  if (params?.cursor) search.set("cursor", params.cursor);
  const suffix = search.size > 0 ? `?${search.toString()}` : "";
  const response = await adminRequest<InquiryListResponse>(`/inquiries${suffix}`);

  if (params === undefined) {
    return response.items.map((item): Inquiry => ({
      id: item.id,
      created_at: item.created_at,
      message: item.message_preview,
      status: item.status
    }));
  }
  return response;
}

export function getInquiry(id: string) {
  return adminRequest<InquiryDetailResponse>(`/inquiries/${encodeURIComponent(id)}`);
}

export function updateInquiry(id: string, data: InquiryUpdateRequest) {
  return adminRequest<InquiryRecord>(`/inquiries/${encodeURIComponent(id)}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function sendInquiryReply(id: string, data: InquiryReplyRequest) {
  return adminRequest<InquiryReplyResponse>(`/inquiries/${encodeURIComponent(id)}/replies`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateApplicant(id: Applicant["id"], data: Partial<Applicant>) {
  return adminRequest<Applicant>(`/applicants/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getInterviewSlots(applicantId: Applicant["id"]) {
  return adminRequest<InterviewSlot[]>(`/applicants/${applicantId}/interview-slots`);
}

export function createInterviewSlots(applicantId: Applicant["id"], data: InterviewSlotCreateRequest) {
  return adminRequest<InterviewSlotCreateResponse>(`/applicants/${applicantId}/interview-slots`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function sendLineMessage(data: LineSendRequest) {
  return adminRequest<LineSendResponse>("/line/send", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function getLineMessages(lineUserId?: string, limit = 100) {
  const params = new URLSearchParams();
  if (lineUserId) params.set("line_user_id", lineUserId);
  params.set("limit", String(limit));
  return adminRequest<LineMessageLog[]>(`/line-messages?${params.toString()}`);
}

export function getFAQCategories() {
  return adminRequest<FAQCategory[]>("/faq-categories");
}

export function getFAQs() {
  return adminRequest<FAQCategory[]>("/faqs");
}

export function createFAQ(data: FAQPayload) {
  return adminRequest<FAQ>("/faqs", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateFAQ(id: FAQ["id"], data: FAQUpdatePayload) {
  return adminRequest<FAQ>(`/faqs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getFAQSettings() {
  return adminRequest<FAQSetting[]>("/faq-settings");
}

export function updateFAQSetting(faqKey: string, data: FAQSettingUpdatePayload) {
  return adminRequest<FAQSetting>(`/faq-settings/${faqKey}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getSettings() {
  return adminRequest<AppSettings>("/settings");
}

export function updateSettings(data: Partial<AppSettings>) {
  return adminRequest<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getQuestionTree() {
  return adminRequest<QuestionTree>("/question-tree");
}

export function updateQuestionTree(tree: QuestionTree) {
  return adminRequest<QuestionTree>("/question-tree", {
    method: "PATCH",
    body: JSON.stringify(tree)
  });
}

export function getStatusSettings() {
  return adminRequest<ApplicantStatusSetting[]>("/status-settings");
}

export function updateStatusSettings(statuses: ApplicantStatusSetting[]) {
  return adminRequest<ApplicantStatusSetting[]>("/status-settings", {
    method: "PATCH",
    body: JSON.stringify({ statuses })
  });
}
