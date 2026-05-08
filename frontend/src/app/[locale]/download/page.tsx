"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { t } from "@/lib/i18n";

export default function DownloadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { caseId, pdfId, reset } = useCaseStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!caseId || !pdfId)) {
      router.replace("/");
    }
  }, [mounted, caseId, pdfId, router]);

  function handleDownload() {
    if (!caseId || !pdfId) return;
    const url = api.pdf.downloadUrl(caseId, pdfId);
    window.open(url, "_blank");
  }

  function handleStartNew() {
    reset();
    router.push("/");
  }

  if (!mounted) return null;
  if (!caseId || !pdfId) return null;

  return (
    <>
      <Header locale={locale} />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={3} locale={locale} />

        <div className="text-center py-6">
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3">{t("download.title", locale)}</h1>
          <p className="text-gray-500 mb-8">{t("download.instruction", locale)}</p>

          <button
            onClick={handleDownload}
            className="w-full py-4 bg-brand-600 text-white rounded-xl font-bold text-lg hover:bg-brand-700 transition-colors mb-4"
          >
            {t("download.pdf", locale)}
          </button>

          <button
            onClick={handleStartNew}
            className="w-full py-3 border-2 border-gray-200 text-gray-600 rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            {t("review.start_new", locale)}
          </button>
        </div>

        <div className="mt-8 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-amber-800 text-sm leading-relaxed">{t("review.disclaimer", locale)}</p>
        </div>
      </main>
    </>
  );
}
