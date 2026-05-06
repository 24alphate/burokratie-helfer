"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";

const T: Record<string, Record<string, string>> = {
  title:         { en: "Review your answers", ar: "راجع إجاباتك", tr: "Cevaplarınızı inceleyin", de: "Antworten überprüfen" },
  instr:         { en: "Check everything before generating the PDF.", ar: "تحقق من كل شيء قبل إنشاء PDF.", tr: "PDF'yi oluşturmadan önce kontrol edin.", de: "Alles prüfen, bevor das PDF erstellt wird." },
  generate:      { en: "Generate & Download PDF", ar: "إنشاء وتنزيل PDF", tr: "PDF Oluştur ve İndir", de: "PDF erstellen & herunterladen" },
  edit:          { en: "← Edit answers", ar: "← تعديل الإجابات", tr: "← Yanıtları düzenle", de: "← Antworten bearbeiten" },
  generating:    { en: "Generating PDF…", ar: "جارٍ إنشاء PDF…", tr: "PDF oluşturuluyor…", de: "PDF wird erstellt…" },
  no_token:      { en: "PDF session expired. Please re-upload your document.", ar: "انتهت الجلسة. يرجى رفع المستند مرة أخرى.", tr: "Oturum süresi doldu. Lütfen belgeyi tekrar yükleyin.", de: "Sitzung abgelaufen. Bitte Dokument erneut hochladen." },
  start_new:     { en: "Start a new form", ar: "ابدأ استمارة جديدة", tr: "Yeni form başlat", de: "Neues Formular starten" },
  manual_fields: { en: "Must be filled in manually after printing:", ar: "يجب ملؤها يدويًا بعد الطباعة:", tr: "Yazdırdıktan sonra manuel doldurulmalı:", de: "Nach dem Drucken manuell ausfüllen:" },
  disclaimer:    {
    en: "⚠️ This is a form completion tool only. We provide no legal advice. Please verify all information before submitting.",
    ar: "⚠️ هذه أداة لمساعدتك في تعبئة الاستمارات فقط. لا نقدم أي استشارات قانونية.",
    tr: "⚠️ Bu yalnızca bir form doldurma aracıdır. Hukuki tavsiye vermiyoruz.",
    de: "⚠️ Dies ist nur eine Formular-Ausfüllhilfe. Wir geben keine Rechtsberatung.",
  },
};

function t(key: string, locale: string) {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

export default function ReviewPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { fields, answeredValues, pdfToken, reset } = useCaseStore();
  const [mounted, setMounted]       = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError]           = useState<string | null>(null);
  const [done, setDone]             = useState(false);
  const [notFillable, setNotFillable] = useState<string[]>([]);
  const [fillStrategy, setFillStrategy] = useState<string>("");

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!fields || fields.length === 0)) {
      router.replace(`/${locale}/upload`);
    }
  }, [mounted, fields, locale, router]);

  if (!mounted) return null;

  const safeFields  = fields ?? [];
  const safeAnswers = answeredValues ?? {};

  const answeredList = safeFields
    .filter((f) => safeAnswers[f.key] !== undefined)
    .map((f) => ({
      key:      f.key,
      label:    f.question[locale] ?? f.question["en"] ?? f.original_label,
      origLabel: f.original_label,
      value:    safeAnswers[f.key],
      inputType: f.input_type,
    }));

  async function handleGenerate() {
    if (!pdfToken) {
      setError(t("no_token", locale));
      return;
    }
    if (Object.keys(safeAnswers).length === 0) {
      setError("No answers to fill. Please answer the questions first.");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const fieldLabels: Record<string, string> = {};
      safeFields.forEach((f) => { fieldLabels[f.key] = f.original_label || f.key; });

      const { blob, notFillable: nf, strategy } = await api.fillPdf(pdfToken, safeAnswers, fieldLabels);

      // Resolve not-fillable field IDs back to original German labels
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
      const msg = e instanceof Error ? e.message : "Failed to generate PDF.";
      if (msg.includes("401") || msg.toLowerCase().includes("expired")) {
        setError(t("no_token", locale));
      } else {
        setError(msg);
      }
    } finally {
      setGenerating(false);
    }
  }

  if (done) {
    return (
      <>
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={3} />
          <div className="text-center py-8">
            <div className="text-6xl mb-4">✅</div>
            <p className="text-xl font-semibold text-gray-800 mb-2">
              {locale === "ar" ? "تم تنزيل PDF!" : locale === "tr" ? "PDF indirildi!" : locale === "de" ? "PDF heruntergeladen!" : "PDF downloaded!"}
            </p>
            {fillStrategy === "fitz_overlay" && (
              <p className="text-xs font-mono text-green-600 mb-2">
                ✅ Written directly onto the original form layout
              </p>
            )}
            <p className="text-gray-500 text-sm mb-6">
              {locale === "de" ? "Bitte beim Jobcenter einreichen." : "Please submit it to the Jobcenter."}
            </p>
          </div>

          {notFillable.length > 0 && (
            <div className="mb-6 p-4 bg-amber-50 border border-amber-300 rounded-xl">
              <p className="text-amber-800 text-sm font-semibold mb-2">
                ⚠ {t("manual_fields", locale)}
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
            {t("start_new", locale)}
          </button>

          <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <p className="text-amber-800 text-sm leading-relaxed">{t("disclaimer", locale)}</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={2} />
        <h1 className="text-2xl font-bold text-gray-900 mb-2">{t("title", locale)}</h1>
        <p className="text-gray-500 mb-6">{t("instr", locale)}</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
            {error}
          </div>
        )}

        {!pdfToken && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-700 text-sm">
            {t("no_token", locale)}
            <button
              onClick={() => router.push(`/${locale}/upload`)}
              className="ml-3 underline font-medium"
            >
              Re-upload
            </button>
          </div>
        )}

        {/* Answer list */}
        <div className="space-y-3 mb-8">
          {answeredList.length === 0 ? (
            <p className="text-gray-400 text-center py-8">No answers yet.</p>
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
                    ? (["yes","ja","true","1"].includes(String(value).toLowerCase()) ? "☑ Yes" : "☐ No")
                    : value}
                </span>
              </div>
            ))
          )}
        </div>

        <div className="flex flex-col gap-3">
          <button
            onClick={handleGenerate}
            disabled={generating || !pdfToken || answeredList.length === 0}
            className="w-full py-4 bg-brand-600 text-white rounded-xl font-bold text-lg hover:bg-brand-700 disabled:opacity-50 transition-colors"
          >
            {generating ? t("generating", locale) : t("generate", locale)}
          </button>
          <button
            onClick={() => router.push(`/${locale}/questions`)}
            className="w-full py-3 border-2 border-gray-200 text-gray-600 rounded-xl font-medium hover:bg-gray-50 transition-colors"
          >
            {t("edit", locale)}
          </button>
        </div>

        <div className="mt-6 p-4 bg-amber-50 border border-amber-200 rounded-xl">
          <p className="text-amber-800 text-sm leading-relaxed">{t("disclaimer", locale)}</p>
        </div>
      </main>
    </>
  );
}
