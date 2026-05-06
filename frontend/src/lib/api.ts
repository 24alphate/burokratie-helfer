import {
  ApiError,
  AnswerRead,
  CaseRead,
  CompletedSignal,
  FormTemplateSummary,
  PDFGenerateResponse,
  QuestionRead,
  SessionRead,
  UploadResponse,
} from "@/types/api";

// In dev: uses Next.js proxy rewrite (/api → localhost:8000)
// In production: NEXT_PUBLIC_API_URL points directly to the Railway backend
const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : "/api/v1";

async function request<T>(
  path: string,
  options: RequestInit & { token?: string } = {}
): Promise<T> {
  const { token, ...fetchOptions } = options;
  const headers: Record<string, string> = {
    ...(fetchOptions.headers as Record<string, string>),
  };
  if (token) headers["X-Session-Token"] = token;
  if (fetchOptions.body && typeof fetchOptions.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${BASE}${path}`, { ...fetchOptions, headers });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(detail.detail ?? "Request failed", res.status);
  }
  return res.json();
}

export const api = {
  sessions: {
    create: (preferred_language: string): Promise<SessionRead> =>
      request("/sessions", {
        method: "POST",
        body: JSON.stringify({ preferred_language }),
      }),

    me: (token: string): Promise<SessionRead> =>
      request("/sessions/me", { token }),
  },

  cases: {
    create: (token: string, form_template_id?: string): Promise<CaseRead> =>
      request("/cases", {
        method: "POST",
        token,
        body: JSON.stringify({ form_template_id: form_template_id ?? null }),
      }),

    get: (token: string, caseId: string): Promise<CaseRead> =>
      request(`/cases/${caseId}`, { token }),

    setFormType: (token: string, caseId: string, template_id: string): Promise<CaseRead> =>
      request(`/cases/${caseId}/form-type`, {
        method: "PATCH",
        token,
        body: JSON.stringify({ form_template_id: template_id }),
      }),
  },

  documents: {
    translateFields: async (
      token: string,
      caseId: string,
      userLanguage: string,
      fields: Array<{ field_name: string; field_type: string; options?: string[] }>,
      documentLanguage = "de",
    ): Promise<Record<string, { question: string; explanation: string; translated_options: Record<string, string> }>> =>
      request(`/cases/${caseId}/translate-fields?user_language=${userLanguage}&document_language=${documentLanguage}`, {
        method: "POST",
        token,
        body: JSON.stringify({ fields }),
      }),

    upload: async (token: string, caseId: string, file: File, userLanguage = "en", documentLanguage = "de"): Promise<UploadResponse> => {
      const form = new FormData();
      form.append("file", file);
      const params = new URLSearchParams({ user_language: userLanguage, document_language: documentLanguage });
      const res = await fetch(`${BASE}/cases/${caseId}/upload?${params}`, {
        method: "POST",
        headers: { "X-Session-Token": token },
        body: form,
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: res.statusText }));
        throw new ApiError(detail.detail ?? "Upload failed", res.status);
      }
      return res.json();
    },
  },

  questions: {
    getNext: (token: string, caseId: string): Promise<QuestionRead | CompletedSignal> =>
      request(`/cases/${caseId}/next-question`, { token }),

    submitAnswer: (
      token: string,
      caseId: string,
      field_key: string,
      raw_answer: string
    ): Promise<AnswerRead> =>
      request(`/cases/${caseId}/answers`, {
        method: "POST",
        token,
        body: JSON.stringify({ field_key, raw_answer }),
      }),

    getAll: (token: string, caseId: string): Promise<AnswerRead[]> =>
      request(`/cases/${caseId}/answers`, { token }),
  },

  templates: {
    list: (): Promise<FormTemplateSummary[]> => request("/templates"),
  },

  pdf: {
    generate: (token: string, caseId: string): Promise<PDFGenerateResponse> =>
      request(`/cases/${caseId}/generate-pdf`, { method: "POST", token }),

    downloadUrl: (caseId: string, pdfId: string): string =>
      `${BASE}/cases/${caseId}/pdf/${pdfId}/download`,
  },
};
