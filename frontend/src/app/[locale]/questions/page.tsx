"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { CompletedSignal, QuestionRead } from "@/types/api";

export default function QuestionsPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId } = useCaseStore();

  const [question, setQuestion] = useState<QuestionRead | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const submitLabel = { en: "Next →", ar: "التالي →", tr: "İleri →", de: "Weiter →" }[locale] ?? "Next →";

  async function fetchNext() {
    if (!sessionToken || !caseId) return;
    setFetchError(null);
    try {
      const result = await api.questions.getNext(sessionToken, caseId);
      if ("completed" in result) {
        router.push(`/${locale}/review`);
      } else {
        setQuestion(result as QuestionRead);
        setValidationErrors([]);
      }
    } catch (e: unknown) {
      setFetchError(e instanceof Error ? e.message : "Failed to load question.");
    }
  }

  useEffect(() => {
    if (!sessionToken || !caseId) {
      router.replace("/");
      return;
    }
    fetchNext();
  }, []);

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

  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={1} />

        {fetchError && (
          <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-600">{fetchError}</div>
        )}

        {!question && !fetchError && (
          <div className="text-center py-16 text-gray-400 text-lg">
            {{ en: "Loading...", ar: "جارٍ التحميل...", tr: "Yükleniyor...", de: "Wird geladen..." }[locale] ?? "Loading..."}
          </div>
        )}

        {question && (
          <QuestionCard
            question={question}
            locale={locale}
            onSubmit={handleAnswer}
            isLoading={isLoading}
            validationErrors={validationErrors}
            submitLabel={submitLabel}
          />
        )}
      </main>
    </>
  );
}
