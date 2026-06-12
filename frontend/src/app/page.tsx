"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useCaseStore } from "@/store/caseStore";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { PrivacyNote } from "@/components/layout/PrivacyNote";
import { LegalFooter } from "@/components/layout/LegalFooter";
import { t } from "@/lib/i18n";

// Only Tier-A locales are offered: these have complete human-verified
// questions + guidance on the verified templates (KG1/BuT) and full UI
// strings. es/fa/ru/uk were removed from the grid because verified KG1
// questions don't exist for them yet — users would silently get English
// questions, breaking the core promise. Re-add a locale only after its
// verified_questions coverage is complete (see backend locale_quality).
const LANGUAGES = [
  { code: "ar", label: "العربية", dir: "rtl" },
  { code: "tr", label: "Türkçe", dir: "ltr" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "de", label: "Deutsch", dir: "ltr" },
  { code: "fr", label: "Français", dir: "ltr" },
  { code: "sq", label: "Shqip", dir: "ltr" },
];

const TOKEN_TTL_MS = 4 * 60 * 60 * 1000; // 4 hours

export default function LandingPage() {
  const router = useRouter();
  const {
    setSessionToken, setCaseId, setLocale, reset, clearCurrentDocument,
    fields, pdfToken, pdfUploadedAt, lastSavedAt, currentFilename,
    answeredValues, extractedFieldIds, locale: savedLocale,
  } = useCaseStore();

  const [mounted, setMounted]             = useState(false);
  const [selectedLocale, setSelectedLocale] = useState<string | null>(null);
  const [loading, setLoading]             = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [showStartNewConfirm, setShowStartNewConfirm] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // ── Derived saved-form state (only meaningful after mount) ──────────────────
  const now             = mounted ? Date.now() : 0;
  const hasFields       = mounted && fields.length > 0;
  const tokenAge        = mounted && pdfUploadedAt ? now - pdfUploadedAt : null;
  const hasSavedForm    = hasFields && !!pdfToken && tokenAge !== null && tokenAge < TOKEN_TTL_MS;
  const isExpiredForm   = hasFields && tokenAge !== null && tokenAge >= TOKEN_TTL_MS;

  // The locale we use for the saved-form / expired card UI is the locale the
  // user picked in the previous session (savedLocale), NOT the new selection
  // since the user hasn't started a new flow yet. Modal copy uses the new
  // selectedLocale because the modal is part of the new flow.
  const cardLocale = savedLocale || "en";
  const modalLocale = selectedLocale || cardLocale;

  // Question counts for the saved-form card
  const groundedFields  = extractedFieldIds.length > 0
    ? fields.filter(f => extractedFieldIds.includes(f.key))
    : [];
  const questionFields  = groundedFields.filter(f => f.show_question !== false && !f.is_prefilled);
  const answeredCount   = questionFields.filter(f => answeredValues[f.key] !== undefined).length;
  const totalCount      = questionFields.length;
  const missingCount    = totalCount - answeredCount;
  const allAnswered     = totalCount > 0 && missingCount === 0;

  function formatSavedTime(ts: number | null): string {
    if (!ts) return "";
    return new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  async function doStart(locale: string) {
    setLoading(true);
    setError(null);
    // The active flow is fully stateless (/process-pdf + /fill-pdf need no
    // session). sessionToken/caseId are kept as local identifiers only, so
    // starting never depends on the backend DB being reachable.
    reset();
    setSessionToken(`local-${crypto.randomUUID()}`);
    setLocale(locale);
    setCaseId(`local-${crypto.randomUUID()}`);
    router.push(`/${locale}/upload`);
    setLoading(false);
  }

  async function handleStart() {
    if (!selectedLocale) return;
    if (hasSavedForm || isExpiredForm) {
      setShowStartNewConfirm(true);
      return;
    }
    await doStart(selectedLocale);
  }

  function handleContinue() {
    const dest = allAnswered ? "review" : "questions";
    router.push(`/${savedLocale}/${dest}`);
  }

  function handleDeleteSaved() {
    clearCurrentDocument();
  }

  function handleReupload() {
    clearCurrentDocument();
    router.push(`/${savedLocale}/upload`);
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-10">
          <h1 className="text-4xl font-bold text-brand-700 mb-2">Bürokratie-Helfer</h1>
          <p className="text-gray-500 text-sm">{t("landing.tagline", cardLocale)}</p>
        </div>

        {/* ── Continue saved form card ─────────────────────────────────────── */}
        {mounted && hasSavedForm && (
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-2xl p-5 shadow-sm">
            <div className="flex items-start gap-3 mb-3">
              <span className="text-2xl">📄</span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-blue-900 text-sm">
                  {t("saved.title", cardLocale)}
                </p>
                {currentFilename && (
                  <p className="text-xs text-blue-700 mt-0.5 truncate font-mono">{currentFilename}</p>
                )}
                {totalCount > 0 && (
                  <p className="text-xs text-blue-700 mt-1">
                    {answeredCount} / {totalCount} {t("saved.questions_answered", cardLocale)}
                    {missingCount > 0 && (
                      <span className="text-amber-600 ml-2">
                        · {missingCount} {t("saved.missing", cardLocale)}
                      </span>
                    )}
                  </p>
                )}
                {lastSavedAt && (
                  <p className="text-xs text-blue-500 mt-0.5">
                    {t("saved.saved_at", cardLocale)} {formatSavedTime(lastSavedAt)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <button
                onClick={handleContinue}
                className="w-full py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors"
              >
                {t("saved.continue", cardLocale)}
              </button>
              <button
                onClick={handleDeleteSaved}
                className="w-full py-2 text-red-600 text-xs font-medium hover:text-red-800 transition-colors"
              >
                {t("saved.delete", cardLocale)}
              </button>
            </div>

            <p className="text-xs text-blue-400 mt-3 text-center">
              {t("saved.local_only", cardLocale)}
            </p>
          </div>
        )}

        {/* ── Expired form warning ─────────────────────────────────────────── */}
        {mounted && isExpiredForm && (
          <div className="mb-6 bg-amber-50 border border-amber-300 rounded-2xl p-5">
            <p className="text-amber-900 text-sm font-semibold mb-1">
              {t("expired.title", cardLocale)}
            </p>
            <p className="text-amber-800 text-xs mb-4">
              {t("expired.body", cardLocale)}
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleReupload}
                className="flex-1 py-2 bg-amber-600 text-white text-sm font-semibold rounded-xl hover:bg-amber-700 transition-colors"
              >
                {t("expired.reupload", cardLocale)}
              </button>
              <button
                onClick={handleDeleteSaved}
                className="px-4 py-2 border-2 border-amber-300 text-amber-700 text-sm rounded-xl hover:bg-amber-100 transition-colors"
              >
                {t("expired.delete", cardLocale)}
              </button>
            </div>
          </div>
        )}

        {/* ── Language selection + Start ───────────────────────────────────── */}
        <div className="bg-white rounded-2xl shadow-md p-8">
          <p className="text-center text-gray-700 font-medium mb-6 text-lg">
            {t("landing.select_language", selectedLocale ?? "en")}
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
            {loading ? "..." : t("landing.start", selectedLocale ?? "en")}
          </button>
        </div>

        <p className="text-center text-xs text-gray-400 mt-6 px-4">
          {t("landing.disclaimer", selectedLocale ?? cardLocale)}
        </p>

        {/* Phase E/E5 — honest, locale-aware privacy statement */}
        <div className="mt-3 px-4">
          <PrivacyNote
            locale={selectedLocale ?? cardLocale}
            className="text-center text-xs text-gray-500 leading-relaxed"
          />
        </div>

        {/* German-law mandated Impressum + Datenschutz links */}
        <LegalFooter locale={selectedLocale ?? cardLocale} />
      </div>

      {/* Start-new confirmation when a saved form exists */}
      {showStartNewConfirm && (
        <ConfirmModal
          title={t("modal.start_new.title", modalLocale)}
          message={t("modal.start_new.body", modalLocale)}
          onDismiss={() => setShowStartNewConfirm(false)}
          actions={[
            {
              label: t("modal.start_new.confirm", modalLocale),
              variant: "danger",
              onClick: async () => {
                setShowStartNewConfirm(false);
                await doStart(selectedLocale!);
              },
            },
            {
              label: t("common.cancel", modalLocale),
              variant: "secondary",
              onClick: () => setShowStartNewConfirm(false),
            },
          ]}
        />
      )}
    </main>
  );
}
