"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { useCaseStore } from "@/store/caseStore";
import { api, API_BASE, isProductionWithoutApiUrl } from "@/lib/api";
import { AnalysisReport, UploadResponse } from "@/types/api";

const T: Record<string, Record<string, string>> = {
  upload_title:    { en: "Upload your PDF form", ar: "ارفع نموذج PDF", tr: "PDF formunuzu yükleyin", de: "PDF-Formular hochladen" },
  upload_instr:    { en: "Drop any fillable PDF — fields are read directly from your document.", ar: "أسقط أي نموذج PDF — تُقرأ الحقول مباشرة من مستندك.", tr: "Doldurulabilir PDF'yi bırakın — alanlar doğrudan belgenizden okunur.", de: "Beliebiges PDF ablegen — Felder werden direkt gelesen." },
  supported:       { en: "Any fillable PDF (government forms, contracts, applications…)", ar: "أي نموذج PDF قابل للتعبئة", tr: "Her doldurulabilir PDF", de: "Jedes ausfüllbare PDF" },
  analysing:       { en: "Reading your PDF…", ar: "جارٍ قراءة ملف PDF…", tr: "PDF okunuyor…", de: "PDF wird gelesen…" },
  analysing_sub:   { en: "Extracting fields and translating questions. This takes a few seconds.", ar: "استخراج الحقول وترجمة الأسئلة. هذا يستغرق بضع ثوانٍ.", tr: "Alanlar ayıklanıyor ve sorular çevriliyor. Bu birkaç saniye sürer.", de: "Felder werden extrahiert und Fragen übersetzt. Das dauert einige Sekunden." },
  no_fields:       { en: "No fillable fields found in this PDF.", ar: "لم يتم العثور على حقول قابلة للتعبئة في هذا PDF.", tr: "Bu PDF'de doldurulabilir alan bulunamadı.", de: "Keine ausfüllbaren Felder in dieser PDF gefunden." },
  blocked_warn:    { en: "fields could not be verified (low confidence) and were excluded.", ar: "حقول لم يمكن التحقق منها واستُبعدت.", tr: "alan doğrulanamadı ve dışlandı.", de: "Felder konnten nicht verifiziert werden und wurden ausgeschlossen." },
};

function t(key: string, locale: string): string {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

type Stage = "idle" | "uploading" | "analysing" | "done" | "error";

export default function UploadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, setLocale, setFields } = useCaseStore();
  const [mounted, setMounted]         = useState(false);
  const [stage, setStage]             = useState<Stage>("idle");
  const [error, setError]             = useState<string | null>(null);
  const [apiWarning, setApiWarning]   = useState<string | null>(null);
  const [report, setReport]           = useState<AnalysisReport | null>(null);

  useEffect(() => { setMounted(true); setLocale(locale); }, [locale, setLocale]);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) router.replace("/");
  }, [mounted, sessionToken, caseId, router]);

  useEffect(() => {
    if (!mounted) return;
    if (isProductionWithoutApiUrl()) {
      setApiWarning(
        `API not configured. Set NEXT_PUBLIC_API_URL in Vercel frontend env vars. Currently: ${API_BASE}`
      );
    }
  }, [mounted]);

  async function handleUploadComplete(uploadResult: UploadResponse) {
    // uploadResult.fields is intentionally [] — the upload route returns no questions.
    // We must call extractPdfFields and AWAIT it before navigating.
    if (!sessionToken || !caseId) return;

    setStage("analysing");
    setError(null);

    try {
      const extracted = await api.documents.extractPdfFields(sessionToken, caseId, locale);

      if (!extracted.fields || extracted.fields.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      // Only keep fields where show_question is not explicitly false
      const showableFields = extracted.fields.filter(
        (f) => f.show_question !== false
      );

      if (showableFields.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      setFields(showableFields);
      setReport(extracted.analysis_report ?? null);
      setStage("done");

      // Navigate to questions after a short delay so user can see the report
      setTimeout(() => router.push(`/${locale}/questions`), 1200);

    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to analyse PDF.";
      // 422 = no extractable fields — not a crash, show friendly message
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
        <h1 className="text-2xl font-bold text-gray-900 mb-6">{t("upload_title", locale)}</h1>

        {/* Misconfiguration warning */}
        {apiWarning && (
          <div className="mb-4 p-3 bg-amber-50 border border-amber-300 rounded-lg text-amber-800 text-sm font-mono break-all">
            ⚙ {apiWarning}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
            {stage === "error" && (
              <button
                className="ml-3 underline text-red-600"
                onClick={() => { setStage("idle"); setError(null); }}
              >
                Try again
              </button>
            )}
          </div>
        )}

        {/* Idle: show dropzone */}
        {stage === "idle" && (
          <FileDropzone
            token={sessionToken}
            caseId={caseId}
            locale={locale}
            onUploadComplete={handleUploadComplete}
            onError={(msg) => { setError(msg); setStage("error"); }}
            onUploadStart={() => setStage("uploading")}
            uploadLabel={t("upload_instr", locale)}
            supportedLabel={t("supported", locale)}
          />
        )}

        {/* Uploading */}
        {stage === "uploading" && (
          <div className="text-center py-16">
            <div className="animate-spin text-4xl mb-4">⏳</div>
            <p className="text-gray-500">Uploading…</p>
          </div>
        )}

        {/* Analysing: extractPdfFields in progress */}
        {stage === "analysing" && (
          <div className="text-center py-16">
            <div className="animate-spin text-4xl mb-4">🔍</div>
            <p className="text-lg font-semibold text-brand-600 mb-2">
              {t("analysing", locale)}
            </p>
            <p className="text-sm text-gray-400">{t("analysing_sub", locale)}</p>
          </div>
        )}

        {/* Done: show accuracy report before navigating */}
        {stage === "done" && report && (
          <div className="py-8">
            <div className="text-center mb-6">
              <div className="text-4xl mb-3">✅</div>
              <p className="text-lg font-semibold text-green-700">
                {report.questions_shown} question{report.questions_shown !== 1 ? "s" : ""} found
              </p>
              <p className="text-sm text-gray-400">Redirecting to questions…</p>
            </div>

            {/* Accuracy report table */}
            <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm">
              <h3 className="font-semibold text-gray-700 mb-3 text-xs uppercase tracking-wide">
                Extraction report
              </h3>
              <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-gray-600">
                <span>PDF type</span>
                <span className="font-mono">{report.pdf_type}</span>
                <span>Pages</span>
                <span className="font-mono">{report.total_pages}</span>
                <span>Fields extracted</span>
                <span className="font-mono">{report.field_count}</span>
                <span>Questions shown</span>
                <span className="font-mono text-green-700">{report.questions_shown}</span>
                {report.questions_blocked > 0 && (
                  <>
                    <span>Blocked (low confidence)</span>
                    <span className="font-mono text-amber-600">{report.questions_blocked}</span>
                  </>
                )}
                {report.low_confidence_fields > 0 && (
                  <>
                    <span>Needs review</span>
                    <span className="font-mono text-yellow-600">{report.low_confidence_fields}</span>
                  </>
                )}
                {report.invented_questions_removed > 0 && (
                  <>
                    <span>Invented (removed)</span>
                    <span className="font-mono text-red-600">{report.invented_questions_removed}</span>
                  </>
                )}
                <span>Grounding rate</span>
                <span className="font-mono text-green-700 font-bold">{report.grounding_rate}</span>
                <span>Coverage rate</span>
                <span className="font-mono">{report.coverage_rate}</span>
              </div>
            </div>
          </div>
        )}

        {/* Done without report */}
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
