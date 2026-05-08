import { create } from "zustand";
import { persist } from "zustand/middleware";
import { FieldDefinition } from "@/types/api";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;

  // ── Upload attempt tracking ───────────────────────────────────────────────
  // uploadAttemptId: a new UUID is generated at the START of every upload
  // attempt, before the fetch begins. It is cleared immediately along with all
  // document state.
  //
  // fieldsForUploadAttemptId: the uploadAttemptId that produced the current
  // fields. The questions page requires this to equal uploadAttemptId before
  // showing any question.
  //
  // This prevents stale fields from a previous PDF leaking into a new upload:
  //   - PDF A uploaded → fields set, fieldsForUploadAttemptId = "attempt-A"
  //   - PDF B upload starts → uploadAttemptId = "attempt-B", fields cleared
  //   - PDF B fails → fields stay empty, fieldsForUploadAttemptId = null
  //   - questions page: "attempt-B" !== null → blocked → redirect to upload
  uploadAttemptId: string | null;
  fieldsForUploadAttemptId: string | null;

  // File metadata stored at the START of every upload (before the fetch).
  // The questions page can show these in the debug panel as identity proof.
  currentFilename: string | null;
  currentFileSize: number | null;
  currentFileLastModified: number | null;

  // ── Stateless pipeline fields ─────────────────────────────────────────────
  pdfToken: string | null;
  answeredValues: Record<string, string>;

  // ── Grounding fields ──────────────────────────────────────────────────────
  fields: FieldDefinition[];
  fieldsForCaseId: string | null;
  documentId: string | null;
  extractedFieldIds: string[];
  answeredKeys: string[];

  // ── Routing metadata ──────────────────────────────────────────────────────
  // Mirrors AnalysisReport.support_level / template_id from /process-pdf.
  // The questions page reads these to render the support-level banner.
  supportLevel: number | null;        // 1 | 2 | 3 | 4
  templateId: string | null;          // verified template ID, when matched

  // ── Timestamps ───────────────────────────────────────────────────────────
  /** Unix ms when the current pdf_token was signed (set alongside pdfToken). */
  pdfUploadedAt: number | null;
  /** Unix ms when the user last explicitly clicked "Save for later". */
  lastSavedAt: number | null;

  // ── Actions ───────────────────────────────────────────────────────────────
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  setPdfToken: (token: string) => void;

  /** Mark the current session as deliberately saved (updates lastSavedAt). */
  markSaved: () => void;

  /**
   * Clear all document state (fields, answers, token) while keeping the
   * session (locale, sessionToken, caseId).  Call this when the user chooses
   * to start a new document without doing a full language-selection reset.
   */
  clearCurrentDocument: () => void;

  /**
   * Call this BEFORE the /process-pdf fetch starts.
   * Clears all document state so stale fields from a previous PDF cannot leak.
   * Stores file metadata for identity verification.
   * Returns the new uploadAttemptId — capture it in a local variable
   * and check it after the fetch to detect race conditions (if the user
   * uploaded another file while this one was in flight).
   */
  beginNewUpload: (params: {
    filename: string;
    fileSize: number;
    fileLastModified: number;
  }) => string;

  setFields: (
    fields: FieldDefinition[],
    caseId: string,
    documentId: string,
    extractedFieldIds: string[],
    uploadAttemptId: string,
    routing?: { supportLevel: number | null; templateId: string | null },
  ) => void;

  addAnswer: (key: string, value: string) => void;
  addAnsweredKey: (key: string) => void;
  mergeTranslations: (
    translations: Record<string, { question: string; explanation: string; translated_options: Record<string, string> }>,
    userLanguage: string,
  ) => void;
  reset: () => void;
}

export const useCaseStore = create<CaseStore>()(
  persist(
    (set) => ({
      sessionToken: null,
      caseId: null,
      locale: "en",
      pdfId: null,
      uploadAttemptId: null,
      fieldsForUploadAttemptId: null,
      currentFilename: null,
      currentFileSize: null,
      currentFileLastModified: null,
      pdfToken: null,
      pdfUploadedAt: null,
      lastSavedAt: null,
      answeredValues: {},
      fields: [],
      fieldsForCaseId: null,
      documentId: null,
      extractedFieldIds: [],
      answeredKeys: [],
      supportLevel: null,
      templateId: null,

      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      setPdfToken: (token) => set({ pdfToken: token, pdfUploadedAt: Date.now() }),

      markSaved: () => set({ lastSavedAt: Date.now() }),

      clearCurrentDocument: () => set({
        // Keep: sessionToken, caseId, locale — session + language remain intact
        uploadAttemptId: null,
        fieldsForUploadAttemptId: null,
        currentFilename: null,
        currentFileSize: null,
        currentFileLastModified: null,
        pdfToken: null,
        pdfUploadedAt: null,
        lastSavedAt: null,
        answeredValues: {},
        fields: [],
        fieldsForCaseId: null,
        documentId: null,
        extractedFieldIds: [],
        answeredKeys: [],
        supportLevel: null,
        templateId: null,
      }),

      beginNewUpload: ({ filename, fileSize, fileLastModified }) => {
        const id = crypto.randomUUID();
        set({
          // New attempt identity
          uploadAttemptId: id,
          fieldsForUploadAttemptId: null,
          currentFilename: filename,
          currentFileSize: fileSize,
          currentFileLastModified: fileLastModified,
          // Clear ALL previous document state — this is the core fix
          fields: [],
          fieldsForCaseId: null,
          documentId: null,
          extractedFieldIds: [],
          pdfToken: null,
          pdfUploadedAt: null,
          lastSavedAt: null,
          answeredValues: {},
          answeredKeys: [],
          supportLevel: null,
          templateId: null,
        });
        return id;
      },

      setFields: (fields, caseId, documentId, extractedFieldIds, uploadAttemptId, routing) =>
        set({
          fields,
          fieldsForCaseId: caseId,
          documentId,
          extractedFieldIds,
          fieldsForUploadAttemptId: uploadAttemptId,
          answeredKeys: [],
          answeredValues: {},
          supportLevel: routing?.supportLevel ?? null,
          templateId: routing?.templateId ?? null,
        }),

      addAnswer: (key, value) =>
        set((s) => ({
          answeredKeys: s.answeredKeys.includes(key)
            ? s.answeredKeys
            : [...s.answeredKeys, key],
          answeredValues: { ...s.answeredValues, [key]: value },
        })),

      addAnsweredKey: (key) =>
        set((s) => ({
          answeredKeys: s.answeredKeys.includes(key)
            ? s.answeredKeys
            : [...s.answeredKeys, key],
        })),

      mergeTranslations: (translations, userLanguage) =>
        set((s) => ({
          fields: (s.fields ?? []).map((f) => {
            const tr = translations[f.key];
            if (!tr) return f;
            return {
              ...f,
              question: { ...f.question, [userLanguage]: tr.question },
              explanation: { ...f.explanation, [userLanguage]: tr.explanation },
              options: f.options.map((o) => ({
                ...o,
                label: tr.translated_options?.[o.value] ?? o.label,
              })),
            };
          }),
        })),

      // Phase E/E4 — `reset` is the action behind the user-visible
      // "Delete my saved data" button. It MUST wipe every field that holds
      // PDF or answer state so a shared-device user can confidently clear
      // their data. `locale` is intentionally kept (it's a UI preference,
      // not user data) so the page doesn't suddenly switch language under
      // the user.
      reset: () =>
        set({
          sessionToken: null,
          caseId: null,
          pdfId: null,
          uploadAttemptId: null,
          fieldsForUploadAttemptId: null,
          currentFilename: null,
          currentFileSize: null,
          currentFileLastModified: null,
          pdfToken: null,
          pdfUploadedAt: null,
          lastSavedAt: null,
          answeredValues: {},
          fields: [],
          fieldsForCaseId: null,
          documentId: null,
          extractedFieldIds: [],
          answeredKeys: [],
          supportLevel: null,
          templateId: null,
        }),
    }),
    {
      name: "bh-store",
      merge: (persisted: unknown, current) => ({
        ...current,
        ...(persisted as object),
        fields:                    (persisted as any)?.fields ?? [],
        fieldsForCaseId:           (persisted as any)?.fieldsForCaseId ?? null,
        documentId:                (persisted as any)?.documentId ?? null,
        extractedFieldIds:         (persisted as any)?.extractedFieldIds ?? [],
        answeredKeys:              (persisted as any)?.answeredKeys ?? [],
        pdfToken:                  (persisted as any)?.pdfToken ?? null,
        answeredValues:            (persisted as any)?.answeredValues ?? {},
        // Both IDs are persisted so a page refresh doesn't force a re-upload.
        // After a successful upload: both = "attempt-A" → questions page shows ✓
        // After a failed upload: uploadAttemptId = "attempt-B", fieldsFor... = null → blocked ✓
        uploadAttemptId:           (persisted as any)?.uploadAttemptId ?? null,
        fieldsForUploadAttemptId:  (persisted as any)?.fieldsForUploadAttemptId ?? null,
        currentFilename:           (persisted as any)?.currentFilename ?? null,
        currentFileSize:           (persisted as any)?.currentFileSize ?? null,
        currentFileLastModified:   (persisted as any)?.currentFileLastModified ?? null,
        pdfUploadedAt:             (persisted as any)?.pdfUploadedAt ?? null,
        lastSavedAt:               (persisted as any)?.lastSavedAt ?? null,
      }),
    }
  )
);
