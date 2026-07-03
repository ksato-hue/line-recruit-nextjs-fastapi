import type { Applicant, Dashboard, Inquiry } from "../types";

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
