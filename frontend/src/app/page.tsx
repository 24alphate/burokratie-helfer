"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useCaseStore } from "@/store/caseStore";

const LANGUAGES = [
  { code: "ar", label: "العربية", dir: "rtl" },
  { code: "tr", label: "Türkçe", dir: "ltr" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "de", label: "Deutsch", dir: "ltr" },
  { code: "fa", label: "فارسی", dir: "rtl" },
  { code: "ru", label: "Русский", dir: "ltr" },
  { code: "uk", label: "Українська", dir: "ltr" },
];

export default function LandingPage() {
  const router = useRouter();
  const { setSessionToken, setCaseId, setLocale, reset } = useCaseStore();
  const [selectedLocale, setSelectedLocale] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    if (!selectedLocale) return;
    setLoading(true);
    setError(null);
    try {
      // Clear ALL stale state from previous sessions before creating a new one.
      // Without this, old fields from a previous upload stay in localStorage and
      // the questions page shows them for a completely different PDF.
      reset();

      const session = await api.sessions.create(selectedLocale);
      setSessionToken(session.session_token);
      setLocale(selectedLocale);
      const newCase = await api.cases.create(session.session_token);
      setCaseId(newCase.id);
      router.push(`/${selectedLocale}/upload`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to start. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-brand-700 mb-2">Bürokratie-Helfer</h1>
          <p className="text-gray-500 text-sm">Form assistance · مساعدة استمارات · Form yardımı</p>
        </div>

        <div className="bg-white rounded-2xl shadow-md p-8">
          <p className="text-center text-gray-700 font-medium mb-6 text-lg">
            Select your language / اختر لغتك / Dilinizi seçin
          </p>

          <div className="grid grid-cols-2 gap-3 mb-8">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => setSelectedLocale(lang.code)}
                dir={lang.dir}
                className={`py-3 px-4 rounded-xl border-2 text-base font-medium transition-all ${
                  selectedLocale === lang.code
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 bg-white text-gray-700 hover:border-brand-300"
                }`}
              >
                {lang.label}
              </button>
            ))}
          </div>

          {error && (
            <p className="text-red-600 text-sm text-center mb-4">{error}</p>
          )}

          <button
            onClick={handleStart}
            disabled={!selectedLocale || loading}
            className="w-full py-3 px-6 bg-brand-600 text-white rounded-xl font-semibold text-lg hover:bg-brand-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? "..." : "Start →"}
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6 px-4">
          This is a form completion tool. We provide no legal advice.
        </p>
      </div>
    </main>
  );
}
