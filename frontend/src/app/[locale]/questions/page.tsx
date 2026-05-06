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

export default function QuestionsPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, fields, answeredKeys, addAnsweredKey } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) {
      router.replace("/");
    }
  }, [mounted, sessionToken, caseId, router]);

  if (!mounted || !sessionToken || !caseId) return null;

  // ── Client-side question flow (primary path) ───────────────────────────────
  // Fields are stored in Zustand (localStorage) from the upload response.
  // This works across Vercel cold starts because localStorage persists.

  const safeFields = fields ?? [];
  const safeAnsweredKeys = answeredKeys ?? [];
  const questionFields = safeFields.filter((f) => !f.is_prefilled);
  const unanswered = questionFields.filter((f) => !safeAnsweredKeys.includes(f.key));
  const nextField = unanswered[0] ?? null;
  const answeredCount = questionFields.length - unanswered.length;
  const totalCount = questionFields.length;
  const prefillCount = safeFields.length - questionFields.length;

  // Redirect to upload if no fields stored (session without upload, or stale store)
  useEffect(() => {
    if (mounted && sessionToken && caseId && safeFields.length === 0) {
      router.replace(`/${locale}/upload`);
    }
  }, [mounted, sessionToken, caseId, safeFields.length, locale, router]);

  // Navigate to review when all questions answered
  useEffect(() => {
    if (mounted && safeFields.length > 0 && unanswered.length === 0) {
      router.push(`/${locale}/review`);
    }
  }, [mounted, safeFields.length, unanswered.length, locale, router]);

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
      addAnsweredKey(nextField.key);
    } catch (e: unknown) {
      // If backend rejects (e.g. template gone after cold start), still advance client-side
      addAnsweredKey(nextField.key);
    } finally {
      setIsLoading(false);
    }
  }

  if (!nextField && safeFields.length === 0) {
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

  if (!nextField) return null; // navigating to review

  // Convert FieldDefinition → QuestionRead shape for QuestionCard reuse
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

        {prefillCount > 0 && answeredCount === 0 && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {(PREFILL_BANNER[locale] ?? PREFILL_BANNER.en)(prefillCount)}
          </div>
        )}

        {submitError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
            {submitError}
          </div>
        )}

        <div className="mb-3 flex items-center gap-3 text-sm text-gray-400">
          <span>{locale === "ar" ? `سؤال ${answeredCount + 1} من ${totalCount}` : `Question ${answeredCount + 1} of ${totalCount}`}</span>
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
        />
      </main>
    </>
  );
}
