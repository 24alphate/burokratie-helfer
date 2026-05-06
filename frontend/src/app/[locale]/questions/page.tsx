"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { AnalysisReport, QuestionRead } from "@/types/api";

const LOADING: Record<string, string> = {
  en: "Reading your document…", ar: "جارٍ قراءة مستندك…",
  tr: "Belgeniz okunuyor…", de: "Dokument wird gelesen…",
};
const SUBMIT: Record<string, string> = {
  en: "Next →", ar: "التالي →", tr: "İleri →", de: "Weiter →",
};
const PREFILL_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `✓ ${n} field${n !== 1 ? "s" : ""} were read from your document and pre-filled.`,
  ar: (n) => `✓ تم قراءة ${n} حقل من مستندك وتعبئته تلقائياً.`,
  tr: (n) => `✓ ${n} alan belgenizden okunarak otomatik dolduruldu.`,
  de: (n) => `✓ ${n} Feld${n !== 1 ? "er" : ""} wurden aus Ihrem Dokument gelesen und vorausgefüllt.`,
};
const BLOCKED_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `ℹ ${n} field${n !== 1 ? "s" : ""} could not be verified (low confidence) and were excluded.`,
  ar: (n) => `ℹ ${n} حقل لم يمكن التحقق منه واستُبعد.`,
  tr: (n) => `ℹ ${n} alan doğrulanamadı ve dışlandı.`,
  de: (n) => `ℹ ${n} Feld${n !== 1 ? "er" : ""} konnten nicht verifiziert werden und wurden ausgeschlossen.`,
};

// ── Debug panel ───────────────────────────────────────────────────────────────
// Always visible (not gated on NODE_ENV). Shows exact grounding proof.

interface DebugPanelProps {
  caseId: string | null;
  documentId: string | null;
  extractedFieldIds: string[];
  questionFieldIds: string[];
  blockedByGuard: string[];
  report: AnalysisReport | null | undefined;
}

function DebugPanel({
  caseId, documentId, extractedFieldIds, questionFieldIds, blockedByGuard, report,
}: DebugPanelProps) {
  const allGrounded = questionFieldIds.every((id) => extractedFieldIds.includes(id));
  const source = blockedByGuard.length > 0 ? "⛔ UNGROUNDED" : "✅ pdf_field_map";

  return (
    <details className="mt-6 text-xs border border-gray-200 rounded-xl overflow-hidden">
      <summary className="cursor-pointer bg-gray-50 px-4 py-2 font-mono text-gray-500 hover:bg-gray-100 select-none">
        🔍 Grounding Debug Panel — {allGrounded ? "✅ All questions grounded" : "⛔ UNGROUNDED QUESTIONS DETECTED"}
      </summary>
      <div className="p-4 font-mono bg-white space-y-3 text-gray-700">
        <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <span className="text-gray-400">case_id</span>
          <span className="break-all">{caseId ?? "—"}</span>
          <span className="text-gray-400">document_id</span>
          <span className="break-all">{documentId ?? "—"}</span>
          <span className="text-gray-400">pdf_type</span>
          <span>{report?.pdf_type ?? "—"}</span>
          <span className="text-gray-400">extracted field_count</span>
          <span className={extractedFieldIds.length === 0 ? "text-red-600 font-bold" : "text-green-700"}>
            {extractedFieldIds.length}
          </span>
          <span className="text-gray-400">question_count</span>
          <span>{questionFieldIds.length}</span>
          <span className="text-gray-400">blocked_by_guard</span>
          <span className={blockedByGuard.length > 0 ? "text-red-600 font-bold" : ""}>
            {blockedByGuard.length}
          </span>
          <span className="text-gray-400">invented_removed</span>
          <span>{report?.invented_questions_removed ?? 0}</span>
          <span className="text-gray-400">extraction_source</span>
          <span className={report?.extraction_source === "verified_template" ? "text-green-700 font-bold" : "text-amber-600"}>
            {report?.extraction_source ?? "—"}
          </span>
          {report?.template_id && <>
            <span className="text-gray-400">template_id</span>
            <span className="text-green-700">{report.template_id}</span>
          </>}
          <span className="text-gray-400">source</span>
          <span className={blockedByGuard.length > 0 ? "text-red-600 font-bold" : "text-green-700"}>
            {source}
          </span>
          <span className="text-gray-400">grounding_rate</span>
          <span className="text-green-700">{report?.grounding_rate ?? "—"}</span>
          <span className="text-gray-400">every q.field_id in map</span>
          <span className={allGrounded ? "text-green-700" : "text-red-600 font-bold"}>
            {allGrounded ? "true" : "FALSE — BUG DETECTED"}
          </span>
        </div>

        <div>
          <p className="text-gray-400 mb-1">first 20 extracted field_ids:</p>
          <div className="space-y-0.5">
            {extractedFieldIds.slice(0, 20).map((id) => (
              <div key={id} className="text-green-700">✓ {id}</div>
            ))}
            {extractedFieldIds.length === 0 && <div className="text-red-600">NONE — no fields extracted</div>}
          </div>
        </div>

        <div>
          <p className="text-gray-400 mb-1">first 20 question field_ids (rendered):</p>
          <div className="space-y-0.5">
            {questionFieldIds.slice(0, 20).map((id) => {
              const inMap = extractedFieldIds.includes(id);
              return (
                <div key={id} className={inMap ? "text-green-700" : "text-red-600 font-bold"}>
                  {inMap ? "✓" : "⛔"} {id}
                  {!inMap && " ← NOT IN EXTRACTED MAP"}
                </div>
              );
            })}
            {questionFieldIds.length === 0 && <div className="text-gray-400">none</div>}
          </div>
        </div>

        {blockedByGuard.length > 0 && (
          <div className="bg-red-50 border border-red-200 rounded p-3">
            <p className="text-red-700 font-bold mb-1">⛔ BLOCKED BY GUARD ({blockedByGuard.length}):</p>
            {blockedByGuard.map((id) => <div key={id} className="text-red-600">{id}</div>)}
          </div>
        )}
      </div>
    </details>
  );
}

// ── Main questions page ───────────────────────────────────────────────────────

export default function QuestionsPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const {
    sessionToken, caseId,
    fields,
    documentId, extractedFieldIds,
    pdfToken,
    uploadAttemptId, fieldsForUploadAttemptId,
    answeredKeys, addAnswer,
  } = useCaseStore();
  const [mounted, setMounted] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // ALL hooks before any conditional return
  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) router.replace("/");
  }, [mounted, sessionToken, caseId, router]);

  // ── OWNERSHIP GUARD ───────────────────────────────────────────────────────
  // Conditions that must ALL hold before any question is shown:
  //
  //   1. fields exist (non-empty)
  //   2. extractedFieldIds exist (non-empty) — confirmed grounding list
  //   3. pdfToken exists — confirms a successful /process-pdf call returned
  //   4. fieldsForUploadAttemptId matches uploadAttemptId — confirms the stored
  //      fields were produced by the MOST RECENT upload attempt, not a previous
  //      one that failed or was superseded
  //
  // If any condition fails, all document state is stale → redirect to upload.
  // This is the fix for the core bug: PDF A's fields cannot survive into a
  // failed PDF B upload attempt.
  useEffect(() => {
    if (!mounted || !sessionToken || !caseId) return;

    const hasFields    = (fields ?? []).length > 0;
    const hasExtracted = (extractedFieldIds ?? []).length > 0;
    const hasToken     = pdfToken !== null;
    const attemptMatch = fieldsForUploadAttemptId !== null
                         && uploadAttemptId !== null
                         && fieldsForUploadAttemptId === uploadAttemptId;

    if (!hasFields || !hasExtracted || !hasToken || !attemptMatch) {
      if (hasFields && (!hasToken || !attemptMatch)) {
        // Fields exist but the upload attempt is stale or missing — this is the bug scenario.
        console.warn(
          "[OWNERSHIP GUARD] Stale document state detected. Redirecting to upload.",
          {
            hasFields, hasExtracted, hasToken,
            uploadAttemptId, fieldsForUploadAttemptId,
            attemptMatch,
          }
        );
      }
      router.replace(`/${locale}/upload`);
    }
  }, [
    mounted, sessionToken, caseId,
    fields, extractedFieldIds, pdfToken,
    uploadAttemptId, fieldsForUploadAttemptId,
    locale, router,
  ]);

  // Derive question state
  const safeFields      = fields ?? [];
  const safeAnswered    = answeredKeys ?? [];
  const safeExtracted   = extractedFieldIds ?? [];

  // ── HARD GROUNDING GUARD ──────────────────────────────────────────────────
  // Every question must have its key in the authoritative extractedFieldIds list.
  // If extractedFieldIds is empty, block all questions.
  const groundedFields = safeExtracted.length > 0
    ? safeFields.filter((f) => safeExtracted.includes(f.key))
    : [];

  const blockedByGuard = safeFields.filter(
    (f) => !safeExtracted.includes(f.key)
  );

  if (blockedByGuard.length > 0) {
    console.error(
      "[GROUNDING GUARD] Blocked non-PDF questions:",
      blockedByGuard.map((q) => q.key),
      "| Extracted IDs:", safeExtracted,
    );
  }

  const questionFields  = groundedFields.filter((f) => f.show_question !== false && !f.is_prefilled);
  const blockedFields   = groundedFields.filter((f) => f.show_question === false);
  const unanswered      = questionFields.filter((f) => !safeAnswered.includes(f.key));
  const nextField       = unanswered[0] ?? null;
  const answeredCount   = questionFields.length - unanswered.length;
  const totalCount      = questionFields.length;
  const prefillCount    = groundedFields.filter((f) => f.is_prefilled && f.show_question !== false).length;

  useEffect(() => {
    if (mounted && safeFields.length > 0 && unanswered.length === 0 && groundedFields.length > 0) {
      router.push(`/${locale}/review`);
    }
  }, [mounted, safeFields.length, unanswered.length, groundedFields.length, locale, router]);

  if (!mounted) return null;
  if (!sessionToken || !caseId) return null;

  // ── No grounding: extractedFieldIds is empty but fields exist ────────────
  // This means the fields came from before the grounding fix (old localStorage).
  // We cannot safely show any questions.
  if (safeFields.length > 0 && safeExtracted.length === 0) {
    return (
      <>
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={1} />
          <div className="p-6 bg-red-50 border border-red-200 rounded-xl">
            <p className="text-red-700 font-semibold mb-2">No fields were extracted from this PDF.</p>
            <p className="text-red-600 text-sm mb-4">
              The app cannot safely generate questions without a verified PDF field map.
            </p>
            <button
              onClick={() => router.replace(`/${locale}/upload`)}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700"
            >
              Upload again
            </button>
          </div>
          <DebugPanel
            caseId={caseId}
            documentId={documentId}
            extractedFieldIds={safeExtracted}
            questionFieldIds={safeFields.map((f) => f.key)}
            blockedByGuard={safeFields.map((f) => f.key)}
            report={null}
          />
        </main>
      </>
    );
  }

  if (safeFields.length === 0) {
    return (
      <>
        <Header />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={1} />
          <div className="text-center py-16 text-gray-400 text-lg">
            {LOADING[locale] ?? "Loading…"}
          </div>
        </main>
      </>
    );
  }

  if (!nextField) return null;

  const question: QuestionRead = {
    id: nextField.key,
    field_key: nextField.key,
    order_index: nextField.order,
    input_type: nextField.input_type,
    question_text: nextField.question,
    explanation_text: nextField.explanation,
    options: null,
    answered_count: answeredCount,
    total_count: totalCount,
  };

  async function handleAnswer(rawAnswer: string) {
    if (!nextField) return;
    setIsLoading(true);
    setSubmitError(null);
    try {
      // Store answer locally for stateless PDF generation.
      // The backend submitAnswer call is kept for audit purposes but is not critical.
      if (sessionToken && caseId) {
        api.questions.submitAnswer(sessionToken, caseId, nextField.key, rawAnswer).catch(() => {});
      }
    } finally {
      setIsLoading(false);
    }
    // addAnswer stores both key (for progress) and value (for fill-pdf).
    addAnswer(nextField.key, rawAnswer);
  }

  return (
    <>
      <Header />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={1} />

        {prefillCount > 0 && answeredCount === 0 && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
            {(PREFILL_BANNER[locale] ?? PREFILL_BANNER.en)(prefillCount)}
          </div>
        )}

        {blockedFields.length > 0 && answeredCount === 0 && (
          <div className="mb-4 p-3 bg-gray-50 border border-gray-200 rounded-xl text-gray-500 text-sm">
            {(BLOCKED_BANNER[locale] ?? BLOCKED_BANNER.en)(blockedFields.length)}
          </div>
        )}

        {submitError && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
            {submitError}
          </div>
        )}

        <div className="mb-3 flex items-center gap-3 text-sm text-gray-400">
          <span>
            {locale === "ar"
              ? `سؤال ${answeredCount + 1} من ${totalCount}`
              : `Question ${answeredCount + 1} of ${totalCount}`}
          </span>
          <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-600 rounded-full transition-all duration-300"
              style={{ width: `${totalCount > 0 ? Math.round((answeredCount / totalCount) * 100) : 0}%` }}
            />
          </div>
        </div>

        <QuestionCard
          question={question}
          locale={locale}
          onSubmit={handleAnswer}
          isLoading={isLoading}
          validationErrors={submitError ? [submitError] : []}
          submitLabel={SUBMIT[locale] ?? "Next →"}
          options={nextField.options ?? []}
          needsReview={nextField.needs_review ?? false}
          originalLabel={nextField.original_label}
        />

        {/* Always-visible debug panel — shows grounding proof for current question set */}
        <DebugPanel
          caseId={caseId}
          documentId={documentId}
          extractedFieldIds={safeExtracted}
          questionFieldIds={questionFields.map((f) => f.key)}
          blockedByGuard={blockedByGuard.map((f) => f.key)}
          report={null}
        />
      </main>
    </>
  );
}
