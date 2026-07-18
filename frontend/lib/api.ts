import type { AppSettings, Applicant, Dashboard, FAQ, FAQCategory, FAQPayload, FAQSetting, FAQSettingUpdatePayload, FAQUpdatePayload, Inquiry, InterviewSlot, InterviewSlotCreateRequest, InterviewSlotCreateResponse, LineMessageLog, LineSendRequest, LineSendResponse, QuestionTree } from "../types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `API error: ${response.status}`);
  }

  return response.json();
}

// 管理系の更新APIは同一オリジンのNext.jsプロキシ(/api/admin/*)経由で呼びます。
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
    throw new Error(text || `API error: ${response.status}`);
  }

  return response.json();
}

export function getDashboard() {
  return request<Dashboard>("/api/dashboard");
}

export function getApplicants() {
  return request<Applicant[]>("/api/applicants");
}

export function getInquiries() {
  return request<Inquiry[]>("/api/inquiries");
}

export function updateApplicant(id: Applicant["id"], data: Partial<Applicant>) {
  return request<Applicant>(`/api/applicants/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getInterviewSlots(applicantId: Applicant["id"]) {
  return request<InterviewSlot[]>(`/api/applicants/${applicantId}/interview-slots`);
}

export function createInterviewSlots(applicantId: Applicant["id"], data: InterviewSlotCreateRequest) {
  return request<InterviewSlotCreateResponse>(`/api/applicants/${applicantId}/interview-slots`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function sendLineMessage(data: LineSendRequest) {
  return request<LineSendResponse>("/api/line/send", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function getLineMessages(lineUserId?: string, limit = 100) {
  const params = new URLSearchParams();
  if (lineUserId) params.set("line_user_id", lineUserId);
  params.set("limit", String(limit));
  return request<LineMessageLog[]>(`/api/line-messages?${params.toString()}`);
}

export function getFAQCategories() {
  return request<FAQCategory[]>("/api/faq-categories");
}

export function getFAQs() {
  return request<FAQCategory[]>("/api/faqs");
}

export function createFAQ(data: FAQPayload) {
  return request<FAQ>("/api/faqs", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export function updateFAQ(id: FAQ["id"], data: FAQUpdatePayload) {
  return request<FAQ>(`/api/faqs/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getFAQSettings() {
  return request<FAQSetting[]>("/api/faq-settings");
}

export function updateFAQSetting(faqKey: string, data: FAQSettingUpdatePayload) {
  return adminRequest<FAQSetting>(`/faq-settings/${faqKey}`, {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getSettings() {
  return request<AppSettings>("/api/settings");
}

export function updateSettings(data: Partial<AppSettings>) {
  return adminRequest<AppSettings>("/settings", {
    method: "PATCH",
    body: JSON.stringify(data)
  });
}

export function getQuestionTree() {
  return request<QuestionTree>("/api/question-tree");
}

export function updateQuestionTree(tree: QuestionTree) {
  return adminRequest<QuestionTree>("/question-tree", {
    method: "PATCH",
    body: JSON.stringify(tree)
  });
}
