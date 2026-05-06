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
      reset: () => set({ sessionToken: null, caseId: null, pdfId: null, fields: [], answeredKeys: [] }),
    }),
    { name: "bh-store" }
  )
);
