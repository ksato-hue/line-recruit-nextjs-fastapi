import type { AppSettings, Applicant, ApplicantStatusSetting, Dashboard, FAQ, FAQCategory, FAQPayload, FAQSetting, FAQSettingUpdatePayload, FAQUpdatePayload, Inquiry, InterviewSlot, InterviewSlotCreateRequest, InterviewSlotCreateResponse, LineMessageLog, LineSendRequest, LineSendResponse, QuestionTree } from "../types";

// 管理APIは同一オリジンのNext.jsプロキシ(/api/admin/*)経由で呼びます。
// 管理キーはサーバー側でのみ付与されるため、ブラウザには露出しません。
async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/admin${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    let detail = "";
    try {
      detail = String((JSON.parse(text) as { detail?: unknown }).detail || "");
    } catch {
      detail = "";
    }
    if (response.status === 503 && detail.includes("管理API")) {
      throw new Error("管理APIの接続設定が完了していません。環境変数を確認してください。");
    }
    throw new Error(detail || `処理に失敗しました（${response.status}）`);
  }

  return response.json();
}

export function getDashboard() {
  return adminRequest<Dashboard>("/dashboard");
}

export function getApplicants() {
  return adminRequest<Applicant[]>("/applicants");
}

export function getInquiries() {
  return adminRequest<Inquiry[]>("/inquiries");
}

export function getInquiry(id: Inquiry["id"]) {
  return adminRequest<Inquiry>(`/inquiries/${id}`);
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
