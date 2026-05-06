import { create } from "zustand";
import { persist } from "zustand/middleware";
import { FieldDefinition } from "@/types/api";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;
  // Field list from the extracted PDF — survives Vercel cold starts via localStorage.
  // CRITICAL: always check fieldsForCaseId === caseId before using these fields.
  // If they differ, the fields belong to a different upload and must not be shown.
  fields: FieldDefinition[];
  fieldsForCaseId: string | null;   // which caseId produced the current fields
  answeredKeys: string[];
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  setFields: (fields: FieldDefinition[], caseId: string) => void;
  addAnsweredKey: (key: string) => void;
  mergeTranslations: (translations: Record<string, { question: string; explanation: string; translated_options: Record<string, string> }>, userLanguage: string) => void;
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
      answeredKeys: [],
      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      // setFields now requires the caseId so the questions page can verify ownership.
      // answeredKeys resets to [] so the user starts fresh on the new PDF.
      setFields: (fields, caseId) => set({ fields, fieldsForCaseId: caseId, answeredKeys: [] }),
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
        answeredKeys: [],
      }),
    }),
    {
      name: "bh-store",
      // Safely merge old persisted state that may lack newer fields.
      // fieldsForCaseId defaults to null so stale fields are rejected by the questions page.
      merge: (persisted: unknown, current) => ({
        ...current,
        ...(persisted as object),
        fields: (persisted as any)?.fields ?? [],
        fieldsForCaseId: (persisted as any)?.fieldsForCaseId ?? null,
        answeredKeys: (persisted as any)?.answeredKeys ?? [],
      }),
    }
  )
);
