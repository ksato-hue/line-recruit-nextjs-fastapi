import type { Applicant, Dashboard, FAQ, FAQCategory, FAQPayload, FAQUpdatePayload, Inquiry, InterviewSlot, InterviewSlotCreateRequest, InterviewSlotCreateResponse, LineMessageLog, LineSendRequest, LineSendResponse } from "../types";

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
