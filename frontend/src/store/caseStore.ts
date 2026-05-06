import { create } from "zustand";
import { persist } from "zustand/middleware";
import { FieldDefinition } from "@/types/api";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;
  // Fields from the extracted PDF.
  // RULE: never read `fields` without first checking that
  //   (a) fieldsForCaseId === caseId, AND
  //   (b) extractedFieldIds.length > 0
  // If either check fails, the fields are stale / ungrounded.
  fields: FieldDefinition[];
  fieldsForCaseId: string | null;  // which caseId produced the current fields
  documentId: string | null;       // document_id from the extract-pdf-fields response
  extractedFieldIds: string[];     // authoritative field_id list from the backend PDF extraction
                                   // stored SEPARATELY from `fields` so the guard is meaningful
  answeredKeys: string[];
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  setFields: (
    fields: FieldDefinition[],
    caseId: string,
    documentId: string,
    extractedFieldIds: string[],
  ) => void;
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
      fields: [],
      fieldsForCaseId: null,
      documentId: null,
      extractedFieldIds: [],
      answeredKeys: [],
      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      setFields: (fields, caseId, documentId, extractedFieldIds) =>
        set({ fields, fieldsForCaseId: caseId, documentId, extractedFieldIds, answeredKeys: [] }),
      addAnsweredKey: (key) => set((s) => ({ answeredKeys: [...s.answeredKeys, key] })),
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
      reset: () => set({
        sessionToken: null,
        caseId: null,
        pdfId: null,
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
        // If extractedFieldIds is missing from old localStorage (pre-this fix),
        // default to [] so the grounding gate blocks everything until re-upload.
        extractedFieldIds: (persisted as any)?.extractedFieldIds ?? [],
        answeredKeys: (persisted as any)?.answeredKeys ?? [],
      }),
    }
  )
);
