"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { getApplicableQuestionFields, getApplicableAnswers } from "@/lib/applicableFields";
import { resolveQuestionText } from "@/lib/labelUtils";
import { OutputGuarantee } from "@/components/questions/OutputGuarantee";
import { LegalFooter } from "@/components/layout/LegalFooter";
import { t } from "@/lib/i18n";

export default function ReviewPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { fields, answeredValues, pdfToken, extractedFieldIds, reset, markSaved, clearCurrentDocument, supportLevel } = useCaseStore();
  const [mounted, setMounted]             = useState(false);
  const [generating, setGenerating]       = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [done, setDone]                   = useState(false);
  const [notFillable, setNotFillable]     = useState<string[]>([]);
  const [fillStrategy, setFillStrategy]   = useState<string>("");
  const [showNewDocModal, setShowNewDocModal] = useState(false);
  const [saveMsg, setSaveMsg]             = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!fields || fields.length === 0)) {
      router.replace(`/${locale}/upload`);
    }
  }, [mounted, fields, locale, router]);

  if (!mounted) return null;

  const safeFields    = fields ?? [];
  const safeAnswers   = answeredValues ?? {};
  const safeExtracted = extractedFieldIds ?? [];

  // Phase v2 — only consider questions/answers that are currently applicable
  // given the conditional flow. applicableAnswers is also what we send to
  // /fill-pdf, so a stale answer (e.g. partner data after switching to "ledig")
  // is never written to the PDF.
  const questionFields    = getApplicableQuestionFields(safeFields, safeExtracted, safeAnswers);
  const applicableAnswers = getApplicableAnswers(safeFields, safeExtracted, safeAnswers);
  const unansweredFields  = questionFields.filter(f => applicableAnswers[f.key] === undefined);

  const answeredList = safeFields
    .filter((f) => applicableAnswers[f.key] !== undefined)
    .map((f) => ({
      key:       f.key,
      label:     resolveQuestionText(f.question, f.original_label, f.key, locale, { isLevel1: supportLevel === 1 }),
      origLabel: f.original_label,
      value:     applicableAnswers[f.key],
      inputType: f.input_type,
    }));

  function handleSave() {
    markSaved();
    setSaveMsg(`${t("q.saved_msg", locale)} ${t("q.saved_warn", locale)}`);
  }

  function handleStartNew() {
    clearCurrentDocument();
    router.push(`/${locale}/upload`);
  }

  async function handleGenerate() {
    if (!pdfToken) {
      setError(t("review.no_token", locale));
      return;
    }
    if (Object.keys(applicableAnswers).length === 0) {
      setError(t("review.no_answers", locale));
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const fieldLabels: Record<string, string> = {};
      safeFields.forEach((f) => { fieldLabels[f.key] = f.original_label || f.key; });

      // Send only currently-applicable answers — never stale conditional data.
      const { blob, notFillable: nf, strategy } = await api.fillPdf(pdfToken, applicableAnswers, fieldLabels);

      const nfLabels = nf.map((id) => {
        const field = safeFields.find((f) => f.key === id);
        return field?.original_label ?? id;
      });
      setNotFillable(nfLabels);
      setFillStrategy(strategy);

      const url  = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href  = url;
      link.download = "form_filled.pdf";
      link.click();
      URL.revokeObjectURL(url);
      setDone(true);
    } catch (e: unknown) {
      const { friendlyError } = await import("@/lib/errors");
      setError(friendlyError(e, locale));
    } finally {
      setGenerating(false);
    }
  }

  if (done) {
    const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
    const maxTouch = typeof navigator !== "undefined" ? (navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints ?? 0 : 0;
    const isIOS =
      /iPhone|iPad|iPod/i.test(ua) ||
      (/Macintosh/i.test(ua) && maxTouch > 1);

    return (
      <>
        <Header locale={locale} />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={3} locale={locale} />
          <div className="text-center py-8">
            <div className="text-6xl mb-4">✅</div>
            <p className="text-xl font-semibold text-gray-800 mb-2">
              {t("review.pdf_downloaded", locale)}
            </p>
            {fillStrategy === "fitz_overlay" && (
              <p className="text-xs font-mono text-green-600 mb-2">
                {t("review.fitz_overlay_note", locale)}
              </p>
            )}
            <p className="text-gray-500 text-sm mb-6">
              {t("review.submit_to_office", locale)}
            </p>
          </div>

          {isIOS && (
            <div
              data-testid="ios-save-instructions"
              className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3"
            >
              <span className="text-2xl leading-none mt-0.5" aria-hidden>📲</span>
              <div className="flex-1 min-w-0">
                <p className="text-blue-900 font-semibold text-sm mb-1">
                  {t("review.ios_title", locale)}
                </p>
                <p className="text-blue-800 text-sm leading-relaxed">
                  {t("review.ios_body", locale)}
                </p>
              </div>
            </div>
          )}

          {notFillable.length > 0 && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-300 rounded-xl">
              <p className="text-amber-800 text-sm font-semibold mb-2">
                ⚠ {t("review.manual_fields", locale)}
              </p>
              <ul className="list-disc list-inside space-y-1">
                {notFillable.map((label) => (
                  <li key={label} className="text-amber-700 text-sm">{label}</li>
                ))}
              </ul>
            </div>
          )}

          <button
            onClick={() => { reset(); router.push("/"); }}
            className="w-full py-3 border-2 border-gray-200 text-gray-600 rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            {t("review.start_new", locale)}
          </button>

          <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <p className="text-amber-800 text-sm leading-relaxed">{t("review.disclaimer", locale)}</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header locale={locale} />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={2} locale={locale} />

        {/* Action bar */}
        <div className="flex items-center justify-between gap-3 mb-5">
          <button
            onClick={() => setShowNewDocModal(true)}
            className="text-sm text-gray-500 hover:text-gray-800 font-medium transition-colors"
          >
            ← {t("q.new_doc_btn", locale)}
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-xl hover:bg-green-700 transition-colors"
          >
            {t("q.save_btn", locale)}
          </button>
        </div>

        {saveMsg && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-sm">
            {saveMsg}
          </div>
        )}

        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t("review.title", locale)}</h1>
        <p className="text-gray-500 mb-6">{t("review.instr", locale)}</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
            {error}
          </div>
        )}

        {!pdfToken && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">
            {t("review.no_token", locale)}
            <button
              onClick={() => router.push(`/${locale}/upload`)}
              className="ml-3 underline font-medium"
            >
              {t("review.reupload", locale)}
            </button>
          </div>
        )}

        {/* Answer list */}
        <div className="space-y-3 mb-8">
          {answeredList.length === 0 ? (
            <p className="text-gray-400 text-center py-8">{t("review.no_answers_yet", locale)}</p>
          ) : (
            answeredList.map(({ key, label, origLabel, value, inputType }) => (
              <div key={key} className="flex justify-between gap-4 p-4 bg-white border border-gray-100 rounded-xl shadow-sm">
                <div className="flex-shrink-0 max-w-[50%]">
                  <span className="text-gray-700 text-sm font-medium block">{label}</span>
                  {origLabel && origLabel !== label && (
                    <span className="text-gray-400 text-xs font-mono">{origLabel}</span>
                  )}
                </div>
                <span className="text-gray-800 font-medium text-sm text-right break-words">
                  {inputType === "checkbox"
                    ? (["yes","ja","true","1"].includes(String(value).toLowerCase())
                        ? `☑ ${t("yn.yes", locale)}`
                        : `☐ ${t("yn.no", locale)}`)
                    : value}
                </span>
              </div>
            ))
          )}
        </div>

        {/* Missing answers warning */}
        {unansweredFields.length > 0 && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-300 rounded-xl">
            <p className="text-amber-800 text-sm font-semibold mb-3">
              {t("review.unanswered_n", locale, { n: unansweredFields.length })}
            </p>
            <div className="space-y-2">
              {unansweredFields.map((f) => {
                const qText = resolveQuestionText(f.question, f.original_label, f.key, locale, { isLevel1: supportLevel === 1 });
                const globalIdx = questionFields.findIndex(q => q.key === f.key) + 1;
                return (
                  <div key={f.key} className="flex items-center justify-between gap-3 bg-white rounded-lg px-3 py-2 border border-amber-200">
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-amber-600 font-mono mr-2">{globalIdx}.</span>
                      <span className="text-sm text-gray-800">{qText}</span>
                      {f.original_label !== qText && (
                        <span className="block text-xs text-gray-400 mt-0.5 ml-5">{f.original_label}</span>
                      )}
                    </div>
                    <button
                      onClick={() => router.push(`/${locale}/questions?focus=${f.key}`)}
                      className="flex-shrink-0 px-3 py-1.5 bg-amber-600 text-white text-xs rounded-lg font-medium hover:bg-amber-700 transition-colors"
                    >
                      {t("q.answer", locale)}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <OutputGuarantee supportLevel={supportLevel} locale={locale} />

        <div className="flex flex-col gap-3">
          <button
            onClick={handleGenerate}
            disabled={generating || !pdfToken || answeredList.length === 0}
            className="w-full py-4 bg-brand-600 text-white rounded-xl font-bold text-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            {generating ? t("review.generating", locale) : t("review.generate", locale)}
          </button>
          <button
            onClick={() => router.push(`/${locale}/questions`)}
            className="w-full py-3 border-2 border-gray-200 text-gray-600 rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            {t("review.edit", locale)}
          </button>
        </div>

        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-amber-800 text-sm leading-relaxed">{t("review.disclaimer", locale)}</p>
        </div>

        <LegalFooter locale={locale} />
      </main>

      {showNewDocModal && (
        <ConfirmModal
          title={t("q.modal_title", locale)}
          message={t("q.modal_msg", locale)}
          onDismiss={() => setShowNewDocModal(false)}
          actions={[
            {
              label: t("q.save_first", locale),
              variant: "primary",
              onClick: () => { handleSave(); handleStartNew(); },
            },
            {
              label: t("q.start_new", locale),
              variant: "danger",
              onClick: handleStartNew,
            },
            {
              label: t("common.cancel", locale),
              variant: "secondary",
              onClick: () => setShowNewDocModal(false),
            },
          ]}
        />
      )}
    </>
  );
}
