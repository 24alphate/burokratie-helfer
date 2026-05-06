"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { useCaseStore } from "@/store/caseStore";
import { api, API_BASE, isProductionWithoutApiUrl } from "@/lib/api";
import { AnalysisReport, AIComparisonEntry, RawFieldEntry } from "@/types/api";

const T: Record<string, Record<string, string>> = {
  title:      { en: "Upload your PDF form", ar: "ارفع نموذج PDF", tr: "PDF formunuzu yükleyin", de: "PDF-Formular hochladen" },
  instr:      { en: "Drop any fillable PDF — fields are read directly from your document.", ar: "أسقط أي نموذج PDF — تُقرأ الحقول مباشرة من مستندك.", tr: "Doldurulabilir PDF'yi bırakın.", de: "Beliebiges PDF ablegen." },
  supported:  { en: "Any fillable PDF (government forms, contracts, applications…)", ar: "أي نموذج PDF قابل للتعبئة", tr: "Her doldurulabilir PDF", de: "Jedes ausfüllbare PDF" },
  processing: { en: "Reading your PDF…", ar: "جارٍ قراءة ملف PDF…", tr: "PDF okunuyor…", de: "PDF wird gelesen…" },
  proc_sub:   { en: "Extracting fields and translating questions. This takes a few seconds.", ar: "استخراج الحقول وترجمة الأسئلة.", tr: "Alanlar çıkarılıyor.", de: "Felder werden extrahiert." },
  no_fields:  { en: "No fillable fields found in this PDF.", ar: "لم يتم العثور على حقول.", tr: "Alan bulunamadı.", de: "Keine ausfüllbaren Felder gefunden." },
};

function t(key: string, locale: string) {
  return T[key]?.[locale] ?? T[key]?.["en"] ?? key;
}

type Stage = "idle" | "processing" | "done" | "error";

// ── Confidence badge ──────────────────────────────────────────────────────────

function ConfBadge({ conf, source }: { conf: number; source: string }) {
  const color =
    source === "acroform" ? "bg-green-100 text-green-700" :
    conf >= 0.90 ? "bg-yellow-100 text-yellow-700" :
    "bg-red-100 text-red-700";
  return (
    <span className={`text-xs font-mono px-1.5 py-0.5 rounded ${color}`}>
      {source === "acroform" ? "acroform" : `pdfplumber ${(conf * 100).toFixed(0)}%`}
    </span>
  );
}

// ── MODE 2: Raw extraction table ──────────────────────────────────────────────

function RawExtractionTable({ fields }: { fields: RawFieldEntry[] }) {
  if (fields.length === 0) return null;
  return (
    <details className="mt-4 border border-gray-200 rounded-xl overflow-hidden" open>
      <summary className="cursor-pointer bg-gray-50 px-4 py-2 font-mono text-xs text-gray-500 hover:bg-gray-100 select-none">
        MODE 2 — Raw extraction ({fields.length} fields, BEFORE AI translation)
      </summary>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead className="bg-gray-100 text-gray-500">
            <tr>
              {["#", "field_id", "original_label", "type", "page", "conf/source", "source_text", "options"].map((h) => (
                <th key={h} className="px-2 py-1.5 text-left whitespace-nowrap font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {fields.map((f, i) => (
              <tr key={f.field_id} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                <td className="px-2 py-1 text-gray-400">{i + 1}</td>
                <td className="px-2 py-1 text-blue-700 max-w-[160px] truncate" title={f.field_id}>{f.field_id}</td>
                <td className="px-2 py-1 text-gray-800 max-w-[180px] truncate" title={f.original_label}>{f.original_label}</td>
                <td className="px-2 py-1 text-purple-700">{f.field_type}</td>
                <td className="px-2 py-1 text-center text-gray-500">{f.source_page}</td>
                <td className="px-2 py-1 whitespace-nowrap">
                  <ConfBadge conf={f.confidence} source={f.source} />
                </td>
                <td className="px-2 py-1 text-gray-600 max-w-[200px] truncate" title={f.source_text}>
                  {f.source_text}
                </td>
                <td className="px-2 py-1 text-gray-500">
                  {f.options.length > 0 ? f.options.join(", ") : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ── MODE 3: AI comparison table ───────────────────────────────────────────────

function AIComparisonTable({ entries, aiUsed }: { entries: AIComparisonEntry[]; aiUsed: boolean }) {
  if (entries.length === 0) return null;

  // Flag entries where AI question looks significantly different from original_label.
  // Heuristic: AI question is more than 3× longer AND contains none of the original words.
  function likelyMismatch(e: AIComparisonEntry): boolean {
    if (!e.ai_used) return false;
    if (e.ai_question === e.original_label) return false;
    const origWords = e.original_label.toLowerCase().replace(/[^a-zäöüß0-9 ]/g, " ").split(/\s+/).filter((w) => w.length > 3);
    const qLower = e.ai_question.toLowerCase();
    const anyMatch = origWords.some((w) => qLower.includes(w));
    return !anyMatch && e.ai_question.length > e.original_label.length * 2;
  }

  return (
    <details className="mt-4 border border-gray-200 rounded-xl overflow-hidden" open>
      <summary className="cursor-pointer bg-gray-50 px-4 py-2 font-mono text-xs text-gray-500 hover:bg-gray-100 select-none">
        MODE 3 — AI comparison ({entries.length} fields) — AI {aiUsed ? "✅ used (Groq)" : "⚠️ NOT used (no API key / fallback)"}
      </summary>
      <div className="overflow-x-auto">
        <table className="w-full text-xs font-mono">
          <thead className="bg-gray-100 text-gray-500">
            <tr>
              {["#", "field_id", "original_label (PDF)", "AI question", "AI explanation", "conf", "flag"].map((h) => (
                <th key={h} className="px-2 py-1.5 text-left whitespace-nowrap font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {entries.map((e, i) => {
              const mismatch = likelyMismatch(e);
              return (
                <tr key={e.field_id} className={mismatch ? "bg-red-50" : i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
                  <td className="px-2 py-1 text-gray-400">{i + 1}</td>
                  <td className="px-2 py-1 text-blue-700 max-w-[130px] truncate" title={e.field_id}>{e.field_id}</td>
                  <td className="px-2 py-1 text-gray-700 max-w-[160px]" title={e.original_label}>
                    <span className="bg-gray-100 px-1 rounded">{e.original_label}</span>
                  </td>
                  <td className={`px-2 py-1 max-w-[200px] ${mismatch ? "text-red-700 font-bold" : "text-green-700"}`}
                    title={e.ai_question}>
                    {e.ai_used ? e.ai_question : <span className="text-gray-400 italic">{e.original_label} (no AI)</span>}
                  </td>
                  <td className="px-2 py-1 text-gray-500 max-w-[160px] truncate" title={e.ai_explanation}>
                    {e.ai_explanation || "—"}
                  </td>
                  <td className="px-2 py-1 text-center">
                    <ConfBadge conf={e.confidence} source={e.ai_used ? "ai" : "acroform"} />
                  </td>
                  <td className="px-2 py-1">
                    {mismatch && <span className="text-red-600 font-bold">⚠ MISMATCH?</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="px-4 py-2 text-xs text-gray-400 bg-gray-50">
        ⚠ MISMATCH? = heuristic flag: AI question is long AND shares no words with original_label. Inspect manually.
      </p>
    </details>
  );
}

// ── Main upload page ──────────────────────────────────────────────────────────

export default function UploadPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const {
    sessionToken, caseId,
    setLocale, setFields, setPdfToken,
    beginNewUpload,
  } = useCaseStore();
  const [mounted, setMounted]       = useState(false);
  const [stage, setStage]           = useState<Stage>("idle");
  const [error, setError]           = useState<string | null>(null);
  const [apiWarning, setApiWarning] = useState<string | null>(null);
  const [report, setReport]         = useState<AnalysisReport | null>(null);
  const [noAiMode, setNoAiMode]     = useState(false);

  // Diagnostic data from last upload
  const [rawFields, setRawFields]         = useState<RawFieldEntry[]>([]);
  const [aiComparison, setAiComparison]   = useState<AIComparisonEntry[]>([]);
  const [aiUsed, setAiUsed]               = useState(false);
  const lastFileRef                        = useRef<File | null>(null);  // for re-run without AI

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

  async function runUpload(file: File, useNoAi: boolean) {
    const attemptId = beginNewUpload({
      filename:         file.name,
      fileSize:         file.size,
      fileLastModified: file.lastModified,
    });

    setStage("processing");
    setError(null);
    setReport(null);
    setRawFields([]);
    setAiComparison([]);

    try {
      const result = await api.processPdf(file, locale, "de", useNoAi);

      // Race condition guard
      const currentAttemptId = useCaseStore.getState().uploadAttemptId;
      if (currentAttemptId !== attemptId) return;

      // Store diagnostic data
      setRawFields(result.raw_extracted_fields ?? []);
      setAiComparison(result.ai_comparison ?? []);
      setAiUsed(result.ai_used ?? false);

      if (!result.fields || result.fields.length === 0 || result.extracted_field_ids.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      const showable = result.fields.filter((f) => f.show_question !== false);
      if (showable.length === 0) {
        setError(t("no_fields", locale));
        setStage("error");
        return;
      }

      setFields(
        showable,
        caseId ?? "stateless",
        result.filename,
        result.extracted_field_ids,
        attemptId,
      );
      setPdfToken(result.pdf_token);
      setReport(result.analysis_report ?? null);
      setStage("done");

      // Only auto-navigate if NOT in diagnostic mode (let user read the tables)
      if (!useNoAi) {
        setTimeout(() => router.push(`/${locale}/questions`), 1800);
      }

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

  async function handleFileSelected(file: File) {
    lastFileRef.current = file;
    await runUpload(file, noAiMode);
  }

  async function handleRerunNoAi() {
    if (!lastFileRef.current) return;
    setNoAiMode(true);
    await runUpload(lastFileRef.current, true);
  }

  async function handleRerunWithAi() {
    if (!lastFileRef.current) return;
    setNoAiMode(false);
    await runUpload(lastFileRef.current, false);
  }

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  return (
    <>
      <Header />
      <main className="max-w-4xl mx-auto px-4 py-8">
        <StepProgress currentStep={0} />
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">{t("title", locale)}</h1>
          {/* MODE 1 toggle — visible in idle */}
          {stage === "idle" && (
            <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
              <input
                type="checkbox"
                checked={noAiMode}
                onChange={(e) => setNoAiMode(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300"
              />
              <span className={`font-mono ${noAiMode ? "text-orange-600 font-bold" : "text-gray-400"}`}>
                MODE 1: no AI (raw labels)
              </span>
            </label>
          )}
        </div>

        {noAiMode && stage === "idle" && (
          <div className="mb-4 p-3 bg-orange-50 border border-orange-300 rounded-lg text-orange-800 text-sm font-mono">
            MODE 1 ACTIVE — Groq is bypassed. Questions will show raw PDF labels.
            Use this to verify extraction accuracy before AI translation.
          </div>
        )}

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
            {noAiMode && <p className="mt-2 text-xs font-mono text-orange-600">MODE 1: bypassing AI…</p>}
          </div>
        )}

        {stage === "done" && (
          <div className="space-y-4">
            {/* Summary card */}
            {report && (
              <div className="py-4">
                <div className="text-center mb-4">
                  <div className="text-4xl mb-2">✅</div>
                  <p className="text-lg font-semibold text-green-700">
                    {report.questions_shown} question{report.questions_shown !== 1 ? "s" : ""} extracted
                    {noAiMode && <span className="ml-2 text-orange-600 text-sm font-mono">[MODE 1: no AI]</span>}
                  </p>
                </div>
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-4 text-sm">
                  <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-600 font-mono text-xs">
                    <span>pdf_type</span>        <span>{report.pdf_type}</span>
                    <span>pages</span>           <span>{report.total_pages}</span>
                    <span>fields extracted</span><span className="text-green-700">{report.field_count}</span>
                    <span>questions shown</span> <span className="text-green-700">{report.questions_shown}</span>
                    {report.questions_blocked > 0 && <><span>blocked (low conf)</span><span className="text-amber-600">{report.questions_blocked}</span></>}
                    {report.invented_questions_removed > 0 && <><span>invented removed</span><span className="text-red-600">{report.invented_questions_removed}</span></>}
                    <span>grounding rate</span>  <span className="text-green-700 font-bold">{report.grounding_rate}</span>
                    <span>AI used</span>         <span className={aiUsed ? "text-blue-600" : "text-orange-600"}>{aiUsed ? "yes (Groq)" : "no (raw labels)"}</span>
                  </div>
                </div>

                {/* Action buttons */}
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => router.push(`/${locale}/questions`)}
                    className="flex-1 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 transition-colors"
                  >
                    Continue to Questions →
                  </button>
                  {!noAiMode && (
                    <button
                      onClick={handleRerunNoAi}
                      className="px-4 py-3 border-2 border-orange-300 text-orange-700 rounded-xl font-mono text-sm hover:bg-orange-50 transition-colors whitespace-nowrap"
                    >
                      Re-run MODE 1 (no AI)
                    </button>
                  )}
                  {noAiMode && (
                    <button
                      onClick={handleRerunWithAi}
                      className="px-4 py-3 border-2 border-blue-300 text-blue-700 rounded-xl font-mono text-sm hover:bg-blue-50 transition-colors whitespace-nowrap"
                    >
                      Re-run with AI
                    </button>
                  )}
                  <button
                    onClick={() => { setStage("idle"); setError(null); }}
                    className="px-4 py-3 border-2 border-gray-200 text-gray-600 rounded-xl text-sm hover:bg-gray-50 transition-colors"
                  >
                    Upload different PDF
                  </button>
                </div>
              </div>
            )}

            {!report && (
              <div className="text-center py-8">
                <div className="text-4xl mb-3">✅</div>
                <div className="flex gap-3 justify-center mt-4">
                  <button onClick={() => router.push(`/${locale}/questions`)}
                    className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700">
                    Continue →
                  </button>
                  {!noAiMode && (
                    <button onClick={handleRerunNoAi}
                      className="px-4 py-3 border-2 border-orange-300 text-orange-700 rounded-xl font-mono text-sm hover:bg-orange-50">
                      Re-run MODE 1 (no AI)
                    </button>
                  )}
                </div>
              </div>
            )}

            {/* MODE 2: Raw extraction table */}
            <RawExtractionTable fields={rawFields} />

            {/* MODE 3: AI comparison table */}
            <AIComparisonTable entries={aiComparison} aiUsed={aiUsed} />
          </div>
        )}
      </main>
    </>
  );
}
