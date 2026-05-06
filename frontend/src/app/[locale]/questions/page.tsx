"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { QuestionRead } from "@/types/api";

const LOADING: Record<string, string> = {
  en: "Reading your document…", ar: "جارٍ قراءة مستندك…",
  tr: "Belgeniz okunuyor…", de: "Dokument wird gelesen…",
};
const SUBMIT: Record<string, string> = {
  en: "Next →", ar: "التالي →", tr: "İleri →", de: "Weiter →",
};
const PREFILL_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `✓ ${n} field${n !== 1 ? "s" : ""} were read from your document and pre-filled.`,
  ar: (n) => `✓ تم قراءة ${n} حقل من مستندك وتعبئته تلقائياً.`,
  tr: (n) => `✓ ${n} alan belgenizden okunarak otomatik dolduruldu.`,
  de: (n) => `✓ ${n} Feld${n !== 1 ? "er" : ""} wurden aus Ihrem Dokument gelesen und vorausgefüllt.`,
};
const BLOCKED_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `ℹ ${n} field${n !== 1 ? "s" : ""} could not be verified (low confidence) and were excluded.`,
  ar: (n) => `ℹ ${n} حقل لم يمكن التحقق منه واستُبعد.`,
  tr: (n) => `ℹ ${n} alan doğrulanamadı ve dışlandı.`,
  de: (n) => `ℹ ${n} Feld${n !== 1 ? "er" : ""} konnten nicht verifiziert werden und wurden ausgeschlossen.`,
};

export default function QuestionsPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, fields, answeredKeys, addAnsweredKey } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ALL hooks before any conditional return
  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) router.replace("/");
  }, [mounted, sessionToken, caseId, router]);

  useEffect(() => {
    if (mounted && sessionToken && caseId && (fields ?? []).length === 0) {
      router.replace(`/${locale}/upload`);
    }
  }, [mounted, sessionToken, caseId, fields, locale, router]);

  // Derive question state — all fields already have show_question=true (filtered at upload)
  const safeFields      = fields ?? [];
  const safeAnswered    = answeredKeys ?? [];
  const questionFields  = safeFields.filter((f) => f.show_question !== false && !f.is_prefilled);
  const blockedFields   = safeFields.filter((f) => f.show_question === false);
  const unanswered      = questionFields.filter((f) => !safeAnswered.includes(f.key));
  const nextField       = unanswered[0] ?? null;
  const answeredCount   = questionFields.length - unanswered.length;
  const totalCount      = questionFields.length;
  const prefillCount    = safeFields.filter((f) => f.is_prefilled && f.show_question !== false).length;

  useEffect(() => {
    if (mounted && safeFields.length > 0 && unanswered.length === 0) {
      router.push(`/${locale}/review`);
    }
  }, [mounted, safeFields.length, unanswered.length, locale, router]);

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  async function handleAnswer(rawAnswer: string) {
    if (!nextField || !sessionToken || !caseId) return;
    setIsLoading(true);
    setSubmitError(null);
    try {
      const result = await api.questions.submitAnswer(
        sessionToken, caseId, nextField.key, rawAnswer
      );
      if (!result.is_validated && result.validation_errors.length > 0) {
        setSubmitError(result.validation_errors[0]);
        return;
      }
    } catch {
      // Backend may reject after cold start — still advance client-side
    } finally {
      setIsLoading(false);
    }
    addAnsweredKey(nextField.key);
  }

  if (safeFields.length === 0) {
    return (
      <>
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={1} />
          <div className="text-center py-16 text-gray-400 text-lg">
            {LOADING[locale] ?? "Loading…"}
          </div>
        </main>
      </>
    );
  }

  if (!nextField) return null;

  const question: QuestionRead = {
    id: nextField.key,
    field_key: nextField.key,
    order_index: nextField.order,
    input_type: nextField.input_type,
    question_text: nextField.question,
    explanation_text: nextField.explanation,
    options: null,
    answered_count: answeredCount,
    total_count: totalCount,
  };

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={1} />

        {/* Pre-fill banner */}
        {prefillCount > 0 && answeredCount === 0 && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {(PREFILL_BANNER[locale] ?? PREFILL_BANNER.en)(prefillCount)}
          </div>
        )}

        {/* Blocked-fields banner (informational only) */}
        {blockedFields.length > 0 && answeredCount === 0 && (
          <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-500 text-sm">
            {(BLOCKED_BANNER[locale] ?? BLOCKED_BANNER.en)(blockedFields.length)}
          </div>
        )}

        {/* Validation error */}
        {submitError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
            {submitError}
          </div>
        )}

        {/* Progress */}
        <div className="mb-3 flex items-center gap-3 text-sm text-gray-400">
          <span>
            {locale === "ar"
              ? `سؤال ${answeredCount + 1} من ${totalCount}`
              : `Question ${answeredCount + 1} of ${totalCount}`}
          </span>
          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-600 rounded-full transition-all duration-300"
              style={{ width: `${totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0}%` }}
            />
          </div>
        </div>

        <QuestionCard
          question={question}
          locale={locale}
          onSubmit={handleAnswer}
          isLoading={isLoading}
          validationErrors={submitError ? [submitError] : []}
          submitLabel={SUBMIT[locale] ?? "Next →"}
          options={nextField.options ?? []}
          needsReview={nextField.needs_review ?? false}
          originalLabel={nextField.original_label}
        />

        {/* Debug table — grounding metadata, visible only in development */}
        {process.env.NODE_ENV === "development" && (
          <details className="mt-8 text-xs">
            <summary className="cursor-pointer text-gray-400 hover:text-gray-600 font-mono">
              🔍 Debug: grounding metadata
            </summary>
            <div className="mt-2 overflow-x-auto">
              <table className="w-full border-collapse text-left font-mono text-xs">
                <thead>
                  <tr className="bg-gray-100">
                    {["show", "key", "label (PDF)", "type", "page", "conf", "source_text", "status"].map(h => (
                      <th key={h} className="border border-gray-200 px-2 py-1">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {safeFields.map((f) => (
                    <tr
                      key={f.key}
                      className={
                        f.key === nextField?.key
                          ? "bg-yellow-50"
                          : f.show_question === false
                          ? "bg-red-50 opacity-60"
                          : f.needs_review
                          ? "bg-amber-50"
                          : ""
                      }
                    >
                      <td className="border border-gray-200 px-2 py-1">
                        {f.show_question !== false ? "✅" : "🚫"}
                      </td>
                      <td className="border border-gray-200 px-2 py-1 max-w-[120px] truncate">
                        {f.key}
                      </td>
                      <td className="border border-gray-200 px-2 py-1 max-w-[120px] truncate">
                        {f.original_label}
                      </td>
                      <td className="border border-gray-200 px-2 py-1">{f.input_type}</td>
                      <td className="border border-gray-200 px-2 py-1">{f.source_page}</td>
                      <td className="border border-gray-200 px-2 py-1">{f.confidence.toFixed(2)}</td>
                      <td className="border border-gray-200 px-2 py-1 max-w-[200px] truncate" title={f.source_text}>
                        {f.source_text || "—"}
                      </td>
                      <td className="border border-gray-200 px-2 py-1">
                        {f.show_question === false
                          ? "blocked"
                          : f.needs_review
                          ? "needs_review"
                          : "valid"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        )}
      </main>
    </>
  );
}
