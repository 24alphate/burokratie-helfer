"use client";

import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";

const T: Record<string, Record<string, string>> = {
  title: { en: "Your form is ready!", ar: "استمارتك جاهزة!", tr: "Formunuz hazır!", de: "Ihr Formular ist fertig!" },
  instruction: { en: "Download the completed form and bring it to the Jobcenter.", ar: "قم بتنزيل الاستمارة المكتملة وأحضرها إلى مركز التشغيل.", tr: "Tamamlanan formu indirin ve Jobcenter'a götürün.", de: "Laden Sie das ausgefüllte Formular herunter und bringen Sie es zum Jobcenter." },
  download: { en: "Download PDF", ar: "تنزيل PDF", tr: "PDF İndir", de: "PDF herunterladen" },
  start_new: { en: "Start a new form", ar: "ابدأ استمارة جديدة", tr: "Yeni form başlat", de: "Neues Formular starten" },
  disclaimer: {
    en: "⚠️ This is a form completion tool only. We provide no legal advice. Please verify all information before submitting to the Jobcenter. You remain responsible for the accuracy of your submission.",
    ar: "⚠️ هذه أداة لمساعدتك في تعبئة الاستمارات فقط. لا نقدم أي استشارات قانونية. يرجى التحقق من جميع المعلومات قبل تقديمها إلى مركز التشغيل. أنت المسؤول عن دقة المعلومات المقدمة.",
    tr: "⚠️ Bu yalnızca bir form doldurma aracıdır. Hukuki tavsiye vermiyoruz. Lütfen Jobcenter'a göndermeden önce tüm bilgileri doğrulayın. Başvurunuzun doğruluğundan siz sorumlusunuz.",
    de: "⚠️ Dies ist nur ein Formular-Ausfüllhilfe. Wir geben keine Rechtsberatung. Bitte überprüfen Sie alle Angaben, bevor Sie sie beim Jobcenter einreichen. Sie sind für die Richtigkeit Ihrer Angaben verantwortlich.",
  },
};

function t(key: string, locale: string): string {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

export default function DownloadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { caseId, pdfId, reset } = useCaseStore();

  function handleDownload() {
    if (!caseId || !pdfId) return;
    const url = api.pdf.downloadUrl(caseId, pdfId);
    window.open(url, "_blank");
  }

  function handleStartNew() {
    reset();
    router.push("/");
  }

  if (!caseId || !pdfId) {
    if (typeof window !== "undefined") router.replace("/");
    return null;
  }

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={3} />

        <div className="text-center py-6">
          <div className="text-6xl mb-4">✅</div>
          <h1 className="text-2xl font-bold text-gray-900 mb-3">{t("title", locale)}</h1>
          <p className="text-gray-500 mb-8">{t("instruction", locale)}</p>

          <button
            onClick={handleDownload}
            className="w-full py-4 bg-brand-600 text-white rounded-xl font-bold text-lg hover:bg-brand-700 transition-colors mb-4"
          >
            {t("download", locale)}
          </button>

          <button
            onClick={handleStartNew}
            className="w-full py-3 border-2 border-gray-200 text-gray-600 rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            {t("start_new", locale)}
          </button>
        </div>

        <div className="mt-8 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-amber-800 text-sm leading-relaxed">{t("disclaimer", locale)}</p>
        </div>
      </main>
    </>
  );
}
