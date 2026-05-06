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
  upload_title: { en: "Upload any fillable PDF form", ar: "ارفع أي نموذج PDF قابل للتعبئة", tr: "Herhangi bir doldurulabilir PDF yükleyin", de: "Beliebiges PDF-Formular hochladen" },
  upload_instruction: { en: "Drag & drop any fillable PDF here — fields are read directly from your document.", ar: "اسحب أي نموذج PDF قابل للتعبئة هنا — تُقرأ الحقول مباشرة من مستندك.", tr: "Doldurulabilir herhangi bir PDF'yi buraya sürükleyin — alanlar doğrudan belgenizden okunur.", de: "Beliebiges ausfüllbares PDF hier ablegen — Felder werden direkt aus dem Dokument gelesen." },
  supported: { en: "Any fillable PDF (government forms, contracts, applications…)", ar: "أي نموذج PDF قابل للتعبئة (نماذج حكومية، عقود، طلبات...)", tr: "Her doldurulabilir PDF (resmi formlar, sözleşmeler, başvurular…)", de: "Jedes ausfüllbare PDF (Behördenformulare, Verträge, Anträge…)" },
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
  const { sessionToken, caseId, setLocale, setFields } = useCaseStore();
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
    // Persist field definitions to localStorage so questions page survives cold starts
    if (result.fields?.length) {
      setFields(result.fields);
    }
    setUploadResult(result);
    if (!result.requires_manual_selection && result.detected_form_type) {
      await handleConfirm(result.detected_form_type);
    }
  }

  const prefilledMsg: Record<string, (n: number) => string> = {
    en: (n) => `✓ Form detected. ${n > 0 ? `${n} fields pre-filled from your document.` : "No pre-filled data — you will answer all questions."}`,
    ar: (n) => `✓ تم التعرف على الاستمارة. ${n > 0 ? `تم ملء ${n} حقل تلقائياً.` : "لم يتم العثور على بيانات مملوءة — ستجيب على جميع الأسئلة."}`,
    tr: (n) => `✓ Form tespit edildi. ${n > 0 ? `${n} alan otomatik dolduruldu.` : "Önceden doldurulmuş veri yok — tüm soruları yanıtlayacaksınız."}`,
    de: (n) => `✓ Formular erkannt. ${n > 0 ? `${n} Felder wurden vorausgefüllt.` : "Keine vorausgefüllten Daten — Sie beantworten alle Fragen."}`,
  };
  function getPrefilledMsg(n: number) {
    return (prefilledMsg[locale] ?? prefilledMsg.en)(n);
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
            <div className="text-4xl mb-3">🔍</div>
            <p className="text-brand-600 text-lg font-semibold mb-2">
              {getPrefilledMsg(uploadResult.prefilled_fields)}
            </p>
            <p className="text-gray-400 text-sm">{t("detecting", locale)}</p>
          </div>
        )}
      </main>
    </>
  );
}
