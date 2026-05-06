import { create } from "zustand";
import { persist } from "zustand/middleware";
import { FieldDefinition } from "@/types/api";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;
  // Field list from upload response — survives Vercel cold starts via localStorage
  fields: FieldDefinition[];
  answeredKeys: string[];
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  setFields: (fields: FieldDefinition[]) => void;
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
      answeredKeys: [],
      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      setFields: (fields) => set({ fields, answeredKeys: [] }),
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
      reset: () => set({ sessionToken: null, caseId: null, pdfId: null, fields: [], answeredKeys: [] }),
    }),
    {
      name: "bh-store",
      // Safely merge old persisted state that may lack fields/answeredKeys
      merge: (persisted: unknown, current) => ({
        ...current,
        ...(persisted as object),
        fields: (persisted as any)?.fields ?? [],
        answeredKeys: (persisted as any)?.answeredKeys ?? [],
      }),
    }
  )
);
