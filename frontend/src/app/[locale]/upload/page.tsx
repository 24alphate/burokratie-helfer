"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { useCaseStore } from "@/store/caseStore";
import { api, API_BASE, isProductionWithoutApiUrl } from "@/lib/api";
import { AnalysisReport, AIComparisonEntry, RawFieldEntry } from "@/types/api";
import { t } from "@/lib/i18n";

// Map old short keys to centralized i18n keys (kept for minimal diff in JSX).
function tu(key: string, locale: string): string {
  const map: Record<string, string> = {
    title:      "upload.title",
    instr:      "upload.instr",
    supported:  "upload.supported",
    processing: "upload.processing",
    proc_sub:   "upload.proc_sub",
    no_fields:  "upload.no_fields",
  };
  return t(map[key] ?? key, locale);
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
    fields, pdfToken, pdfUploadedAt, lastSavedAt, currentFilename,
  } = useCaseStore();
  const [mounted, setMounted]         = useState(false);
  const [stage, setStage]             = useState<Stage>("idle");
  const [inputMode, setInputMode]     = useState<"choose" | "upload">("choose");
  const [error, setError]             = useState<string | null>(null);
  const [apiWarning, setApiWarning]   = useState<string | null>(null);
  const [report, setReport]           = useState<AnalysisReport | null>(null);
  const [noAiMode, setNoAiMode]       = useState(false);
  const [showLeaveModal, setShowLeaveModal] = useState(false);

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
      // Misconfiguration is a developer problem, not a user problem.
      // Log to console so devs see it, but show users a generic
      // "service unavailable" message instead of leaking env-var names.
      console.error("[upload] API not configured. Set NEXT_PUBLIC_API_URL.");
      setApiWarning(t("upload.api_unavailable", locale));
    }
  }, [mounted, locale]);

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
        setError(tu("no_fields", locale));
        setStage("error");
        return;
      }

      const showable = result.fields.filter((f) => f.show_question !== false);
      if (showable.length === 0) {
        setError(tu("no_fields", locale));
        setStage("error");
        return;
      }

      setFields(
        showable,
        caseId ?? "stateless",
        result.filename,
        result.extracted_field_ids,
        attemptId,
        {
          supportLevel: result.analysis_report?.support_level ?? null,
          templateId: result.analysis_report?.template_id ?? null,
          ocrDiagnostic: result.analysis_report?.ocr_diagnostic
            ? {
                diagnostic_status: result.analysis_report.ocr_diagnostic.diagnostic_status,
                user_message: result.analysis_report.ocr_diagnostic.user_message,
                page_count: result.analysis_report.ocr_diagnostic.page_count,
                readable_pages: result.analysis_report.ocr_diagnostic.readable_pages,
                average_confidence: result.analysis_report.ocr_diagnostic.average_confidence,
                provider: result.analysis_report.ocr_diagnostic.provider,
              }
            : null,
        },
      );
      setPdfToken(result.pdf_token);
      setReport(result.analysis_report ?? null);
      setStage("done");

      // Only auto-navigate if NOT in diagnostic mode (let user read the tables)
      if (!useNoAi) {
        setTimeout(() => router.push(`/${locale}/questions`), 1800);
      }

    } catch (e: unknown) {
      // Always render a localized, plain-language message.
      // Never expose backend deployment / API URL / status codes to the user.
      const { friendlyError } = await import("@/lib/errors");
      setError(friendlyError(e, locale));
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
      <Header
        locale={locale}
        onLogoClick={stage === "processing"
          ? () => setShowLeaveModal(true)
          : undefined}
      />
      {showLeaveModal && (
        <ConfirmModal
          title={t("upload.leave_title", locale)}
          message={t("upload.leave_body", locale)}
          onDismiss={() => setShowLeaveModal(false)}
          actions={[
            {
              label: t("upload.leave_anyway", locale),
              variant: "danger",
              onClick: () => { setShowLeaveModal(false); router.push("/"); },
            },
            {
              label: t("upload.stay", locale),
              variant: "primary",
              onClick: () => setShowLeaveModal(false),
            },
          ]}
        />
      )}
      <main className="max-w-4xl mx-auto px-4 py-8">
        <StepProgress currentStep={0} locale={locale} />
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">{tu("title", locale)}</h1>
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
                {t("upload.try_again", locale)}
              </button>
            )}
          </div>
        )}

        {/* Continue saved form card */}
        {stage === "idle" && inputMode === "choose" &&
          fields.length > 0 && pdfToken &&
          pdfUploadedAt && (Date.now() - pdfUploadedAt) < 4 * 60 * 60 * 1000 && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-2xl flex flex-col sm:flex-row sm:items-center gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-blue-900">
                {t("upload.continue_saved", locale)}
              </p>
              {currentFilename && (
                <p className="text-xs text-blue-700 mt-0.5 truncate">{currentFilename}</p>
              )}
              {lastSavedAt && (
                <p className="text-xs text-blue-500 mt-0.5">
                  {t("saved.saved_at", locale)}{" "}
                  {new Date(lastSavedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                </p>
              )}
            </div>
            <button
              onClick={() => router.push(`/${locale}/questions`)}
              className="flex-shrink-0 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-xl hover:bg-blue-700 transition-colors"
            >
              {t("upload.continue", locale)} →
            </button>
          </div>
        )}

        {/* Mode selector — shown first in idle state */}
        {stage === "idle" && inputMode === "choose" && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <button
              onClick={() => setInputMode("upload")}
              className="flex flex-col items-start gap-3 p-6 bg-white border-2 border-gray-200 rounded-2xl hover:border-brand-400 hover:bg-brand-50 transition-all text-left group"
            >
              <span className="text-3xl">📄</span>
              <div>
                <p className="text-lg font-semibold text-gray-900 group-hover:text-brand-700">
                  {t("upload.upload_pdf", locale)}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  {t("upload.upload_pdf_desc", locale)}
                </p>
              </div>
            </button>

            <button
              onClick={() => router.push(`/${locale}/scan`)}
              className="relative flex flex-col items-start gap-3 p-6 bg-white border-2 border-gray-200 rounded-2xl hover:border-amber-400 hover:bg-amber-50 transition-all text-left group"
            >
              <span
                className="absolute top-3 right-3 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-100 text-amber-800 border border-amber-300 rounded"
                aria-label="Beta feature"
              >
                Beta
              </span>
              <span className="text-3xl">📷</span>
              <div>
                <p className="text-lg font-semibold text-gray-900 group-hover:text-amber-700">
                  {t("upload.scan_doc", locale)}
                </p>
                <p className="text-sm text-gray-500 mt-1">
                  {t("upload.scan_desc", locale)}
                </p>
                <p className="text-xs text-amber-700 mt-2 font-medium">
                  ⚠ {t("upload.scan_warning", locale)}
                </p>
              </div>
            </button>
          </div>
        )}

        {stage === "idle" && inputMode === "upload" && (
          <>
            <button
              onClick={() => setInputMode("choose")}
              className="mb-4 text-sm text-gray-400 hover:text-gray-600 transition-colors"
            >
              ← {t("common.back", locale)}
            </button>
            <FileDropzone
              onFileSelected={handleFileSelected}
              onError={async (msg) => {
                console.error("[upload] dropzone error:", msg);
                const { errorMessage } = await import("@/lib/errors");
                setError(errorMessage("unknown", locale));
                setStage("error");
              }}
              isProcessing={false}
              uploadLabel={tu("instr", locale)}
              supportedLabel={tu("supported", locale)}
            />
          </>
        )}

        {stage === "processing" && (
          <div className="text-center py-16">
            <div className="animate-spin text-4xl mb-4">🔍</div>
            <p className="text-lg font-semibold text-brand-600 mb-2">{tu("processing", locale)}</p>
            <p className="text-sm text-gray-400">{tu("proc_sub", locale)}</p>
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
                    <span>pdf_type</span>          <span className={report.pdf_type === "verified_template" ? "text-green-700 font-bold" : ""}>{report.pdf_type}</span>
                    <span>extraction_source</span>  <span className={report.extraction_source === "verified_template" ? "text-green-700 font-bold" : "text-amber-600"}>{report.extraction_source ?? "auto"}</span>
                    {report.template_id && <><span>template_id</span><span className="text-green-700">{report.template_id}</span></>}
                    <span>pages</span>             <span>{report.total_pages}</span>
                    <span>fields extracted</span>  <span className="text-green-700">{report.field_count}</span>
                    <span>questions shown</span>   <span className="text-green-700">{report.questions_shown}</span>
                    {report.questions_blocked > 0 && <><span>blocked (low conf)</span><span className="text-amber-600">{report.questions_blocked}</span></>}
                    {report.invented_questions_removed > 0 && <><span>invented removed</span><span className="text-red-600">{report.invented_questions_removed}</span></>}
                    <span>grounding rate</span>    <span className="text-green-700 font-bold">{report.grounding_rate}</span>
                    <span>AI used</span>           <span className={aiUsed ? "text-blue-600" : "text-orange-600"}>{aiUsed ? "yes (Groq)" : "no (raw labels)"}</span>
                  </div>
                  {report.extraction_source === "verified_template" && (
                    <p className="mt-3 text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1.5">
                      ✅ Verified template matched — all {report.field_count} fields are hand-verified, confidence 1.0
                    </p>
                  )}
                  {report.extraction_source !== "verified_template" && (
                    <p className="mt-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1.5">
                      ⚠ Experimental extraction ({report.extraction_source}) — accuracy not guaranteed for all fields
                    </p>
                  )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-3 mt-4">
                  <button
                    onClick={() => router.push(`/${locale}/questions`)}
                    className="flex-1 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 transition-colors"
                  >
                    {t("upload.continue_to_questions", locale)}
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
                    {t("upload.upload_different", locale)}
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
                    {t("upload.continue", locale)} →
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
