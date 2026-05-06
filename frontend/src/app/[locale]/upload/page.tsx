"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { useCaseStore } from "@/store/caseStore";
import { api, API_BASE, isProductionWithoutApiUrl } from "@/lib/api";
import { AnalysisReport } from "@/types/api";

const T: Record<string, Record<string, string>> = {
  title:       { en: "Upload your PDF form", ar: "ارفع نموذج PDF", tr: "PDF formunuzu yükleyin", de: "PDF-Formular hochladen" },
  instr:       { en: "Drop any fillable PDF — fields are read directly from your document.", ar: "أسقط أي نموذج PDF — تُقرأ الحقول مباشرة من مستندك.", tr: "Doldurulabilir PDF'yi bırakın — alanlar doğrudan belgenizden okunur.", de: "Beliebiges PDF ablegen — Felder werden direkt gelesen." },
  supported:   { en: "Any fillable PDF (government forms, contracts, applications…)", ar: "أي نموذج PDF قابل للتعبئة", tr: "Her doldurulabilir PDF", de: "Jedes ausfüllbare PDF" },
  processing:  { en: "Reading your PDF…", ar: "جارٍ قراءة ملف PDF…", tr: "PDF okunuyor…", de: "PDF wird gelesen…" },
  proc_sub:    { en: "Extracting fields and translating questions. This takes a few seconds.", ar: "استخراج الحقول وترجمة الأسئلة. هذا يستغرق بضع ثوانٍ.", tr: "Alanlar çıkarılıyor. Birkaç saniye sürer.", de: "Felder werden extrahiert. Das dauert einige Sekunden." },
  no_fields:   { en: "No fillable fields found in this PDF.", ar: "لم يتم العثور على حقول قابلة للتعبئة.", tr: "Bu PDF'de doldurulabilir alan bulunamadı.", de: "Keine ausfüllbaren Felder in dieser PDF gefunden." },
};

function t(key: string, locale: string) {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

type Stage = "idle" | "processing" | "done" | "error";

export default function UploadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, setLocale, setFields, setPdfToken } = useCaseStore();
  const [mounted, setMounted]       = useState(false);
  const [stage, setStage]           = useState<Stage>("idle");
  const [error, setError]           = useState<string | null>(null);
  const [apiWarning, setApiWarning] = useState<string | null>(null);
  const [report, setReport]         = useState<AnalysisReport | null>(null);

  useEffect(() => { setMounted(true); setLocale(locale); }, [locale, setLocale]);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) router.replace("/");
  }, [mounted, sessionToken, caseId, router]);

  useEffect(() => {
    if (!mounted) return;
    if (isProductionWithoutApiUrl()) {
      setApiWarning(`API not configured. Set NEXT_PUBLIC_API_URL in Vercel env vars. Calling: ${API_BASE}`);
    }
  }, [mounted]);

  async function handleFileSelected(file: File) {
    setStage("processing");
    setError(null);

    try {
      // Single stateless call — no caseId needed, no DB writes on the backend.
      const result = await api.processPdf(file, locale);

      if (!result.fields || result.fields.length === 0 || result.extracted_field_ids.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      // Only show fields where show_question is not explicitly false.
      const showable = result.fields.filter((f) => f.show_question !== false);
      if (showable.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      // Store grounded fields + independent extracted_field_ids (grounding gate).
      // caseId from store is used for fieldsForCaseId so the old ownership check still passes.
      setFields(showable, caseId ?? "stateless", result.filename, result.extracted_field_ids);
      // Store the signed PDF token — needed by the review page to call /fill-pdf.
      setPdfToken(result.pdf_token);
      setReport(result.analysis_report ?? null);
      setStage("done");

      setTimeout(() => router.push(`/${locale}/questions`), 1200);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to process PDF.";
      if (msg.includes("422") || msg.toLowerCase().includes("no field")) {
        setError(t("no_fields", locale));
      } else {
        setError(msg);
      }
      setStage("error");
    }
  }

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={0} />
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t("title", locale)}</h1>

        {apiWarning && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-lg text-amber-800 text-sm font-mono break-all">
            ⚙ {apiWarning}
          </div>
        )}

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
            {stage === "error" && (
              <button className="ml-3 underline" onClick={() => { setStage("idle"); setError(null); }}>
                Try again
              </button>
            )}
          </div>
        )}

        {stage === "idle" && (
          <FileDropzone
            onFileSelected={handleFileSelected}
            onError={(msg) => { setError(msg); setStage("error"); }}
            isProcessing={false}
            uploadLabel={t("instr", locale)}
            supportedLabel={t("supported", locale)}
          />
        )}

        {stage === "processing" && (
          <div className="text-center py-16">
            <div className="animate-spin text-4xl mb-4">🔍</div>
            <p className="text-lg font-semibold text-brand-600 mb-2">{t("processing", locale)}</p>
            <p className="text-sm text-gray-400">{t("proc_sub", locale)}</p>
          </div>
        )}

        {stage === "done" && report && (
          <div className="py-8">
            <div className="text-center mb-6">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-lg font-semibold text-green-700">
                {report.questions_shown} question{report.questions_shown !== 1 ? "s" : ""} found
              </p>
              <p className="text-sm text-gray-400">Redirecting to questions…</p>
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm">
              <h3 className="font-semibold text-gray-700 mb-3 text-xs uppercase tracking-wide">Extraction report</h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-gray-600 font-mono text-xs">
                <span>pdf_type</span>       <span>{report.pdf_type}</span>
                <span>pages</span>          <span>{report.total_pages}</span>
                <span>fields extracted</span><span className="text-green-700">{report.field_count}</span>
                <span>questions shown</span> <span className="text-green-700">{report.questions_shown}</span>
                {report.questions_blocked > 0 && <><span>blocked</span><span className="text-amber-600">{report.questions_blocked}</span></>}
                {report.invented_questions_removed > 0 && <><span>invented removed</span><span className="text-red-600">{report.invented_questions_removed}</span></>}
                <span>grounding rate</span>  <span className="text-green-700 font-bold">{report.grounding_rate}</span>
              </div>
            </div>
          </div>
        )}

        {stage === "done" && !report && (
          <div className="text-center py-16">
            <div className="text-4xl mb-3">✅</div>
            <p className="text-sm text-gray-400">Redirecting…</p>
          </div>
        )}
      </main>
    </>
  );
}
