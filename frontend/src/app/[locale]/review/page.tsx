"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { AnswerSummary } from "@/components/review/AnswerSummary";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { AnswerRead } from "@/types/api";

const T: Record<string, Record<string, string>> = {
  title: { en: "Review your answers", ar: "راجع إجاباتك", tr: "Cevaplarınızı inceleyin", de: "Antworten überprüfen" },
  instruction: { en: "Check your answers before we generate the PDF.", ar: "تحقق من إجاباتك قبل إنشاء PDF.", tr: "PDF'i oluşturmadan önce cevaplarınızı kontrol edin.", de: "Überprüfen Sie Ihre Antworten, bevor wir das PDF erstellen." },
  generate: { en: "Generate PDF", ar: "إنشاء PDF", tr: "PDF Oluştur", de: "PDF erstellen" },
  edit: { en: "Edit", ar: "تعديل", tr: "Düzenle", de: "Bearbeiten" },
  generating: { en: "Generating PDF...", ar: "جارٍ إنشاء PDF...", tr: "PDF oluşturuluyor...", de: "PDF wird erstellt..." },
};

function t(key: string, locale: string): string {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

export default function ReviewPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, setPdfId } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [answers, setAnswers] = useState<AnswerRead[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!sessionToken || !caseId) { router.replace("/"); return; }
    api.questions.getAll(sessionToken, caseId)
      .then(setAnswers)
      .catch(() => setError("Could not load answers — please try refreshing the page."));
  }, [mounted]);

  function handleEdit() {
    router.push(`/${locale}/questions`);
  }

  async function handleGenerate() {
    if (!sessionToken || !caseId) return;
    setGenerating(true);
    setError(null);
    try {
      const result = await api.pdf.generate(sessionToken, caseId);
      if (result.status === "ready") {
        setPdfId(result.pdf_id);
        router.push(`/${locale}/download`);
      } else {
        setError("PDF generation failed. Please try again.");
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed to generate PDF.");
    } finally {
      setGenerating(false);
    }
  }

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={2} />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t("title", locale)}</h1>
        <p className="text-gray-500 mb-6">{t("instruction", locale)}</p>

        {error && <p className="text-red-600 text-sm mb-4 p-3 bg-red-50 rounded-lg">{error}</p>}

        {answers.length === 0 ? (
          <p className="text-gray-400 text-center py-8">Loading answers...</p>
        ) : (
          <AnswerSummary
            answers={answers}
            onEdit={handleEdit}
            editLabel={t("edit", locale)}
          />
        )}

        <button
          onClick={handleGenerate}
          disabled={generating || answers.length === 0}
          className="w-full mt-8 py-4 bg-brand-600 text-white rounded-xl font-bold text-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
        >
          {generating ? t("generating", locale) : t("generate", locale)}
        </button>
      </main>
    </>
  );
}
