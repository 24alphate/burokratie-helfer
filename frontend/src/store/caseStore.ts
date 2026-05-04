import { create } from "zustand";
import { persist } from "zustand/middleware";

interface CaseStore {
  sessionToken: string | null;
  caseId: string | null;
  locale: string;
  pdfId: string | null;
  setSessionToken: (token: string) => void;
  setCaseId: (id: string) => void;
  setLocale: (locale: string) => void;
  setPdfId: (id: string) => void;
  reset: () => void;
}

export const useCaseStore = create<CaseStore>()(
  persist(
    (set) => ({
      sessionToken: null,
      caseId: null,
      locale: "en",
      pdfId: null,
      setSessionToken: (token) => set({ sessionToken: token }),
      setCaseId: (id) => set({ caseId: id }),
      setLocale: (locale) => set({ locale }),
      setPdfId: (id) => set({ pdfId: id }),
      reset: () => set({ sessionToken: null, caseId: null, pdfId: null }),
    }),
    { name: "bh-store" }
  )
);
