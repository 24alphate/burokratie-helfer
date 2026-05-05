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
  en: "Loading...", ar: "جارٍ التحميل...", tr: "Yükleniyor...", de: "Wird geladen...",
};
const SUBMIT: Record<string, string> = {
  en: "Next →", ar: "التالي →", tr: "İleri →", de: "Weiter →",
};
const PREFILL_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `✓ ${n} field${n !== 1 ? "s" : ""} were pre-filled from your document and skipped.`,
  ar: (n) => `✓ تم ملء ${n} حقل تلقائياً من مستندك وتم تخطيه.`,
  tr: (n) => `✓ ${n} alan belgenizden otomatik dolduruldu ve atlandı.`,
  de: (n) => `✓ ${n} Feld${n !== 1 ? "er" : ""} wurden aus Ihrem Dokument vorausgefüllt und übersprungen.`,
};

export default function QuestionsPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [question, setQuestion] = useState<QuestionRead | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [prefillCount, setPrefillCount] = useState<number | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!sessionToken || !caseId) { router.replace("/"); return; }
    fetchNext();
  }, [mounted]);

  async function fetchNext() {
    if (!sessionToken || !caseId) return;
    setFetchError(null);
    try {
      const result = await api.questions.getNext(sessionToken, caseId);
      if ("completed" in result) {
        router.push(`/${locale}/review`);
      } else {
        const q = result as QuestionRead;
        setQuestion(q);
        setValidationErrors([]);
        // On first load, detect pre-filled questions (answered_count > 0 before user answered anything)
        setPrefillCount((prev) => prev === null && q.answered_count > 0 ? q.answered_count : prev);
      }
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : "Failed to load question.");
    }
  }

  async function handleAnswer(rawAnswer: string) {
    if (!question || !sessionToken || !caseId) return;
    setIsLoading(true);
    try {
      const result = await api.questions.submitAnswer(sessionToken, caseId, question.field_key, rawAnswer);
      if (!result.is_validated && result.validation_errors.length > 0) {
        setValidationErrors(result.validation_errors);
      } else {
        await fetchNext();
      }
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : "Failed to submit answer.");
    } finally {
      setIsLoading(false);
    }
  }

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={1} />

        {fetchError && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">{fetchError}</div>
        )}

        {prefillCount !== null && prefillCount > 0 && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {(PREFILL_BANNER[locale] ?? PREFILL_BANNER.en)(prefillCount)}
          </div>
        )}

        {question && (
          <div className="mb-2 flex items-center justify-between text-sm text-gray-400">
            <span>
              {locale === "ar"
                ? `سؤال ${question.answered_count + 1} من ${question.total_count}`
                : `Question ${question.answered_count + 1} of ${question.total_count}`}
            </span>
            <div className="flex-1 mx-4 h-1.5 bg-gray-200 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-600 rounded-full transition-all duration-300"
                style={{ width: `${Math.round(((question.answered_count) / question.total_count) * 100)}%` }}
              />
            </div>
          </div>
        )}

        {!question && !fetchError && (
          <div className="text-center py-16 text-gray-400 text-lg">
            {LOADING[locale] ?? "Loading..."}
          </div>
        )}

        {question && (
          <QuestionCard
            question={question}
            locale={locale}
            onSubmit={handleAnswer}
            isLoading={isLoading}
            validationErrors={validationErrors}
            submitLabel={SUBMIT[locale] ?? "Next →"}
          />
        )}
      </main>
    </>
  );
}
