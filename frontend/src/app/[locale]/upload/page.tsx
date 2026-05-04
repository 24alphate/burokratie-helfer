"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { FormTypeSelector } from "@/components/upload/FormTypeSelector";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { UploadResponse } from "@/types/api";

const T: Record<string, Record<string, string>> = {
  upload_title: { en: "Upload your Jobcenter form", ar: "ارفع استمارة مركز التشغيل", tr: "Jobcenter formunuzu yükleyin", de: "Formular hochladen" },
  upload_instruction: { en: "Drag & drop your PDF or image here, or click to select.", ar: "اسحب وأفلت PDF أو صورة، أو انقر للاختيار.", tr: "PDF'i sürükleyip bırakın veya seçmek için tıklayın.", de: "PDF hier ablegen oder klicken." },
  supported: { en: "PDF, JPG, PNG (max 10MB)", ar: "PDF، JPG، PNG (أقصى 10 ميجابايت)", tr: "PDF, JPG, PNG (maks. 10MB)", de: "PDF, JPG, PNG (max. 10 MB)" },
  detecting: { en: "Detecting form type...", ar: "جارٍ التعرف على الاستمارة...", tr: "Form türü tespit ediliyor...", de: "Formular wird erkannt..." },
  confirm: { en: "Confirm & Continue", ar: "تأكيد ومتابعة", tr: "Onayla ve Devam Et", de: "Bestätigen & Weiter" },
  select_prompt: { en: "Please select your form type:", ar: "يرجى تحديد نوع الاستمارة:", tr: "Lütfen form türünüzü seçin:", de: "Bitte Formulartyp wählen:" },
};

function t(key: string, locale: string): string {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

export default function UploadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, setLocale } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    setMounted(true);
    setLocale(locale);
  }, [locale, setLocale]);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) {
      router.replace("/");
    }
  }, [mounted, sessionToken, caseId, router]);

  async function handleConfirm(templateId: string) {
    if (!sessionToken || !caseId) return;
    setConfirming(true);
    try {
      await api.cases.setFormType(sessionToken, caseId, templateId);
      router.push(`/${locale}/questions`);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Failed.");
    } finally {
      setConfirming(false);
    }
  }

  async function handleUploadComplete(result: UploadResponse) {
    setUploadResult(result);
    if (!result.requires_manual_selection && result.detected_form_type) {
      await handleConfirm(result.detected_form_type);
    }
  }

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={0} />
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t("upload_title", locale)}</h1>

        {error && <p className="text-red-600 text-sm mb-4 p-3 bg-red-50 rounded-lg">{error}</p>}

        {!uploadResult ? (
          <FileDropzone
            token={sessionToken}
            caseId={caseId}
            onUploadComplete={handleUploadComplete}
            onError={setError}
            uploadLabel={t("upload_instruction", locale)}
            supportedLabel={t("supported", locale)}
          />
        ) : uploadResult.requires_manual_selection ? (
          <FormTypeSelector
            onSelect={handleConfirm}
            prompt={t("select_prompt", locale)}
            confirmLabel={confirming ? "..." : t("confirm", locale)}
          />
        ) : (
          <div className="text-center py-8">
            <p className="text-brand-600 text-lg font-semibold">{t("detecting", locale)}</p>
          </div>
        )}
      </main>
    </>
  );
}
