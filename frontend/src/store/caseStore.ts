import { create } from "zustand";
import { persist } from "zustand/middleware";
import { FieldDefinition } from "@/types/api";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;

  // ── Stateless pipeline fields ─────────────────────────────────────────────
  // pdfToken: signed JWT from /process-pdf — contains the original PDF bytes.
  // answeredValues: field_key → raw_answer, stored here so the review page can
  //   build the answers map for /fill-pdf without a DB lookup.
  pdfToken: string | null;
  answeredValues: Record<string, string>;

  // ── Grounding fields ──────────────────────────────────────────────────────
  // RULE: never show questions unless pdfToken is set AND extractedFieldIds is
  //   non-empty AND fieldsForCaseId === caseId (for the legacy flow).
  fields: FieldDefinition[];
  fieldsForCaseId: string | null;
  documentId: string | null;
  extractedFieldIds: string[];
  answeredKeys: string[];

  // ── Actions ───────────────────────────────────────────────────────────────
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  setPdfToken: (token: string) => void;
  setFields: (
    fields: FieldDefinition[],
    caseId: string,
    documentId: string,
    extractedFieldIds: string[],
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
      pdfToken: null,
      answeredValues: {},
      fields: [],
      fieldsForCaseId: null,
      documentId: null,
      extractedFieldIds: [],
      answeredKeys: [],

      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      setPdfToken: (token) => set({ pdfToken: token }),

      setFields: (fields, caseId, documentId, extractedFieldIds) =>
        set({
          fields,
          fieldsForCaseId: caseId,
          documentId,
          extractedFieldIds,
          answeredKeys: [],
          answeredValues: {},
        }),

      // Store both the key (for progress tracking) and the value (for PDF filling).
      addAnswer: (key, value) =>
        set((s) => ({
          answeredKeys: s.answeredKeys.includes(key)
            ? s.answeredKeys
            : [...s.answeredKeys, key],
          answeredValues: { ...s.answeredValues, [key]: value },
        })),

      // Legacy: used by old flow where values came from DB.
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

      reset: () =>
        set({
          sessionToken: null,
          caseId: null,
          pdfId: null,
          pdfToken: null,
          answeredValues: {},
          fields: [],
          fieldsForCaseId: null,
          documentId: null,
          extractedFieldIds: [],
          answeredKeys: [],
        }),
    }),
    {
      name: "bh-store",
      merge: (persisted: unknown, current) => ({
        ...current,
        ...(persisted as object),
        fields: (persisted as any)?.fields ?? [],
        fieldsForCaseId: (persisted as any)?.fieldsForCaseId ?? null,
        documentId: (persisted as any)?.documentId ?? null,
        extractedFieldIds: (persisted as any)?.extractedFieldIds ?? [],
        answeredKeys: (persisted as any)?.answeredKeys ?? [],
        pdfToken: (persisted as any)?.pdfToken ?? null,
        answeredValues: (persisted as any)?.answeredValues ?? {},
      }),
    }
  )
);
