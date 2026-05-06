import {
  ApiError,
  AnswerRead,
  CaseRead,
  CompletedSignal,
  FormTemplateSummary,
  PDFGenerateResponse,
  ProcessPdfResponse,
  QuestionRead,
  SessionRead,
  UploadResponse,
} from "@/types/api";

// In dev (no NEXT_PUBLIC_API_URL): relative /api/v1 + Next.js rewrite → localhost:8000
// In production: NEXT_PUBLIC_API_URL must be set to the backend Vercel URL
//   → Go to Vercel → frontend project → Settings → Environment Variables
//   → Add: NEXT_PUBLIC_API_URL = https://<your-backend-project>.vercel.app
const BASE = process.env.NEXT_PUBLIC_API_URL
  ? `${process.env.NEXT_PUBLIC_API_URL}/api/v1`
  : "/api/v1";

// Exported so other modules can show the resolved URL in diagnostics
export const API_BASE = BASE;

/**
 * Returns true when the JS environment is a browser AND the current hostname
 * is NOT localhost — i.e. we're in deployed production.
 * Used to detect the "NEXT_PUBLIC_API_URL not set" misconfiguration early.
 */
export function isProductionWithoutApiUrl(): boolean {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1";
  const hasApiUrl = Boolean(process.env.NEXT_PUBLIC_API_URL);
  return !isLocal && !hasApiUrl;
}

/** Classify a fetch() rejection or HTTP error into a human-readable stage. */
function classifyError(err: unknown, status?: number): ApiError {
  // Network-level failure (server unreachable, CORS, no internet)
  if (err instanceof TypeError && /failed to fetch|network/i.test(err.message)) {
    const configured = process.env.NEXT_PUBLIC_API_URL;
    if (!configured) {
      return new ApiError(
        "Cannot reach the backend API. " +
        "Set NEXT_PUBLIC_API_URL in your Vercel frontend environment variables " +
        "and redeploy.",
        0
      );
    }
    return new ApiError(
      `Cannot reach API at ${configured}. ` +
        "Check that the backend is deployed and CORS allows this origin.",
      0
    );
  }

  // HTTP errors with known status codes
  if (status === 413) return new ApiError("File is too large. Max 10 MB.", 413);
  if (status === 404) return new ApiError("Upload endpoint not found (404). Check backend deployment.", 404);
  if (status === 401 || status === 403) return new ApiError("Session expired. Please refresh and start again.", status);
  if (status === 422) return new ApiError("PDF has no detectable fillable fields — you can still answer questions manually.", 422);
  if (status && status >= 500)
    return new ApiError(
      "The backend encountered an error while processing the file. " +
        "Check backend logs for details.",
      status
    );

  if (err instanceof ApiError) return err;
  return new ApiError(String(err), status ?? 0);
}

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

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...fetchOptions, headers });
  } catch (err) {
    console.error("[api] Network error on", path, err);
    throw classifyError(err);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    const msg = body?.detail ?? body?.message ?? "Request failed";
    console.error("[api] HTTP", res.status, path, msg);
    throw classifyError(new ApiError(msg, res.status), res.status);
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

    extractPdfFields: (
      token: string,
      caseId: string,
      userLanguage: string,
      documentLanguage = "de",
    ): Promise<UploadResponse> =>
      request(`/cases/${caseId}/extract-pdf-fields?user_language=${userLanguage}&document_language=${documentLanguage}`, {
        method: "POST",
        token,
        body: JSON.stringify({}),
      }),

    upload: async (
      token: string,
      caseId: string,
      file: File,
      userLanguage = "en",
      documentLanguage = "de",
    ): Promise<UploadResponse> => {
      // IMPORTANT: Do NOT set Content-Type manually for FormData.
      // The browser must set it so that the multipart boundary is included.
      const form = new FormData();
      form.append("file", file);   // backend expects field named "file"
      const params = new URLSearchParams({ user_language: userLanguage, document_language: documentLanguage });
      const url = `${BASE}/cases/${caseId}/upload?${params}`;

      console.log("[upload] POST", url, "file:", file.name, file.size, "bytes");

      let res: Response;
      try {
        res = await fetch(url, {
          method: "POST",
          headers: { "X-Session-Token": token },
          body: form,
        });
      } catch (err) {
        console.error("[upload] Network error:", err);
        throw classifyError(err);
      }

      if (!res.ok) {
        const body = await res.json().catch(() => ({ detail: res.statusText }));
        const msg = body?.detail ?? body?.message ?? "Upload failed";
        console.error("[upload] HTTP", res.status, msg, "body:", body);
        throw classifyError(new ApiError(msg, res.status), res.status);
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

  // ── Stateless pipeline ────────────────────────────────────────────────────

  /**
   * Upload a PDF and receive grounded questions + a signed PDF token.
   * Single call — replaces the old upload → extract-pdf-fields two-step.
   * No caseId or session token required (stateless).
   */
  processPdf: async (
    file: File,
    userLanguage: string,
    documentLanguage = "de",
    noAi = false,
  ): Promise<ProcessPdfResponse> => {
    const form = new FormData();
    form.append("file", file);
    const params = new URLSearchParams({ user_language: userLanguage, document_language: documentLanguage });
    if (noAi) params.set("no_ai", "true");
    const url = `${BASE}/process-pdf?${params}`;

    console.log("[processPdf] POST", url, "file:", file.name, file.size, "bytes");

    let res: Response;
    try {
      res = await fetch(url, { method: "POST", body: form });
    } catch (err) {
      console.error("[processPdf] Network error:", err);
      throw classifyError(err);
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      const msg = body?.detail ?? "PDF processing failed";
      console.error("[processPdf] HTTP", res.status, msg);
      throw classifyError(new ApiError(msg, res.status), res.status);
    }
    return res.json();
  },

  /**
   * Fill the PDF with the user's answers and return a downloadable Blob.
   * Decodes the signed pdf_token on the server — no DB or file lookup needed.
   */
  fillPdf: async (
    pdfToken: string,
    answers: Record<string, string>,
  ): Promise<Blob> => {
    const url = `${BASE}/fill-pdf`;
    console.log("[fillPdf] POST", url, "answer_count:", Object.keys(answers).length);

    let res: Response;
    try {
      res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pdf_token: pdfToken, answers }),
      });
    } catch (err) {
      console.error("[fillPdf] Network error:", err);
      throw classifyError(err);
    }

    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      const msg = body?.detail ?? "PDF generation failed";
      console.error("[fillPdf] HTTP", res.status, msg);
      throw classifyError(new ApiError(msg, res.status), res.status);
    }
    return res.blob();
  },
};
