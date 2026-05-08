"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useCaseStore } from "@/store/caseStore";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { PrivacyNote } from "@/components/layout/PrivacyNote";

const LANGUAGES = [
  { code: "ar", label: "العربية", dir: "rtl" },
  { code: "tr", label: "Türkçe", dir: "ltr" },
  { code: "en", label: "English", dir: "ltr" },
  { code: "de", label: "Deutsch", dir: "ltr" },
  { code: "fr", label: "Français", dir: "ltr" },
  { code: "es", label: "Español", dir: "ltr" },
  { code: "sq", label: "Shqip", dir: "ltr" },
  { code: "fa", label: "فارسی", dir: "rtl" },
  { code: "ru", label: "Русский", dir: "ltr" },
  { code: "uk", label: "Українська", dir: "ltr" },
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
    try {
      reset();
      const session = await api.sessions.create(locale);
      setSessionToken(session.session_token);
      setLocale(locale);
      const newCase = await api.cases.create(session.session_token);
      setCaseId(newCase.id);
      router.push(`/${locale}/upload`);
    } catch (e: unknown) {
      // Always render a localized, plain-language message.
      const { friendlyError } = await import("@/lib/errors");
      setError(friendlyError(e, locale));
    } finally {
      setLoading(false);
    }
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
          <p className="text-gray-500 text-sm">Form assistance · مساعدة استمارات · Form yardımı</p>
        </div>

        {/* ── Continue saved form card ─────────────────────────────────────── */}
        {mounted && hasSavedForm && (
          <div className="mb-6 bg-blue-50 border border-blue-200 rounded-2xl p-5 shadow-sm">
            <div className="flex items-start gap-3 mb-3">
              <span className="text-2xl">📄</span>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-blue-900 text-sm">
                  {savedLocale === "de" ? "Gespeichertes Formular" :
                   savedLocale === "ar" ? "نموذج محفوظ" :
                   savedLocale === "tr" ? "Kaydedilmiş form" :
                   "Saved form"}
                </p>
                {currentFilename && (
                  <p className="text-xs text-blue-700 mt-0.5 truncate font-mono">{currentFilename}</p>
                )}
                {totalCount > 0 && (
                  <p className="text-xs text-blue-700 mt-1">
                    {answeredCount} / {totalCount}{" "}
                    {savedLocale === "de" ? "Fragen beantwortet" :
                     savedLocale === "ar" ? "أسئلة تمت الإجابة عنها" :
                     savedLocale === "tr" ? "soru yanıtlandı" :
                     "questions answered"}
                    {missingCount > 0 && (
                      <span className="text-amber-600 ml-2">
                        · {missingCount}{" "}
                        {savedLocale === "de" ? "fehlen" :
                         savedLocale === "ar" ? "مفقودة" :
                         savedLocale === "tr" ? "eksik" :
                         "missing"}
                      </span>
                    )}
                  </p>
                )}
                {lastSavedAt && (
                  <p className="text-xs text-blue-500 mt-0.5">
                    {savedLocale === "de" ? "Gespeichert" :
                     savedLocale === "ar" ? "تم الحفظ" :
                     savedLocale === "tr" ? "Kaydedildi" :
                     "Saved"}{" "}
                    {formatSavedTime(lastSavedAt)}
                  </p>
                )}
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <button
                onClick={handleContinue}
                className="w-full py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors"
              >
                {savedLocale === "de" ? "Weiter ausfüllen →" :
                 savedLocale === "ar" ? "متابعة التعبئة ←" :
                 savedLocale === "tr" ? "Doldurmaya devam et →" :
                 "Continue filling in →"}
              </button>
              <button
                onClick={handleDeleteSaved}
                className="w-full py-2 text-red-600 text-xs font-medium hover:text-red-800 transition-colors"
              >
                {savedLocale === "de" ? "Gespeichertes Formular löschen" :
                 savedLocale === "ar" ? "حذف النموذج المحفوظ" :
                 savedLocale === "tr" ? "Kaydedilen formu sil" :
                 "Delete saved form"}
              </button>
            </div>

            <p className="text-xs text-blue-400 mt-3 text-center">
              {savedLocale === "de" ? "Nur auf diesem Gerät/Browser gespeichert." :
               savedLocale === "ar" ? "محفوظ فقط على هذا الجهاز/المتصفح." :
               savedLocale === "tr" ? "Yalnızca bu cihaz/tarayıcıda kaydedildi." :
               "Saved only on this device/browser."}
            </p>
          </div>
        )}

        {/* ── Expired form warning ─────────────────────────────────────────── */}
        {mounted && isExpiredForm && (
          <div className="mb-6 bg-amber-50 border border-amber-300 rounded-2xl p-5">
            <p className="text-amber-900 text-sm font-semibold mb-1">
              {savedLocale === "de" ? "Gespeichertes Formular abgelaufen" :
               savedLocale === "ar" ? "انتهت صلاحية النموذج المحفوظ" :
               savedLocale === "tr" ? "Kaydedilen form süresi doldu" :
               "Saved form expired"}
            </p>
            <p className="text-amber-800 text-xs mb-4">
              {savedLocale === "de"
                ? "Aus Datenschutzgründen laufen gespeicherte Formulare nach 4 Stunden ab. Bitte laden Sie das PDF erneut hoch."
                : savedLocale === "ar"
                ? "لأسباب تتعلق بالخصوصية، تنتهي صلاحية النماذج المحفوظة بعد 4 ساعات. يرجى إعادة رفع ملف PDF."
                : savedLocale === "tr"
                ? "Gizlilik nedeniyle kaydedilen formlar 4 saat sonra sona erer. Lütfen PDF'yi tekrar yükleyin."
                : "For privacy reasons, saved forms expire after 4 hours. Please re-upload the PDF."}
            </p>
            <div className="flex gap-2">
              <button
                onClick={handleReupload}
                className="flex-1 py-2 bg-amber-600 text-white text-sm font-semibold rounded-xl hover:bg-amber-700 transition-colors"
              >
                {savedLocale === "de" ? "Erneut hochladen" :
                 savedLocale === "ar" ? "إعادة الرفع" :
                 savedLocale === "tr" ? "Tekrar yükle" :
                 "Re-upload PDF"}
              </button>
              <button
                onClick={handleDeleteSaved}
                className="px-4 py-2 border-2 border-amber-300 text-amber-700 text-sm rounded-xl hover:bg-amber-100 transition-colors"
              >
                {savedLocale === "de" ? "Löschen" :
                 savedLocale === "ar" ? "حذف" :
                 savedLocale === "tr" ? "Sil" :
                 "Delete"}
              </button>
            </div>
          </div>
        )}

        {/* ── Language selection + Start ───────────────────────────────────── */}
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

        {/* Phase E/E5 — honest, locale-aware privacy statement */}
        <div className="mt-3 px-4">
          <PrivacyNote
            locale={selectedLocale ?? "en"}
            className="text-center text-xs text-gray-500 leading-relaxed"
          />
        </div>
      </div>

      {/* Start-new confirmation when a saved form exists */}
      {showStartNewConfirm && (
        <ConfirmModal
          title={
            selectedLocale === "de" ? "Neues Formular starten?" :
            selectedLocale === "ar" ? "بدء نموذج جديد؟" :
            selectedLocale === "tr" ? "Yeni form başlatılsın mı?" :
            "Start a new form?"
          }
          message={
            selectedLocale === "de"
              ? "Ein neues Formular zu starten löscht das gespeicherte Formular auf diesem Gerät."
              : selectedLocale === "ar"
              ? "سيؤدي بدء نموذج جديد إلى حذف النموذج المحفوظ على هذا الجهاز."
              : selectedLocale === "tr"
              ? "Yeni bir form başlatmak bu cihazdaki kaydedilmiş formu silecek."
              : "Starting a new form will delete the saved form on this device."
          }
          onDismiss={() => setShowStartNewConfirm(false)}
          actions={[
            {
              label: selectedLocale === "de" ? "Ja, neu starten" :
                     selectedLocale === "ar" ? "نعم، ابدأ من جديد" :
                     selectedLocale === "tr" ? "Evet, yeniden başlat" :
                     "Yes, start new",
              variant: "danger",
              onClick: async () => {
                setShowStartNewConfirm(false);
                await doStart(selectedLocale!);
              },
            },
            {
              label: selectedLocale === "de" ? "Abbrechen" :
                     selectedLocale === "ar" ? "إلغاء" :
                     selectedLocale === "tr" ? "İptal" :
                     "Cancel",
              variant: "secondary",
              onClick: () => setShowStartNewConfirm(false),
            },
          ]}
        />
      )}
    </main>
  );
}
