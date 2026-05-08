"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { QuestionCard } from "@/components/questions/QuestionCard";
import { QuestionOverview } from "@/components/questions/QuestionOverview";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { SupportLevelBanner } from "@/components/questions/SupportLevelBanner";
import { ReviewWarning } from "@/components/questions/ReviewWarning";
import { DeleteSavedData } from "@/components/layout/DeleteSavedData";
import { PrivacyNote } from "@/components/layout/PrivacyNote";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { AnalysisReport, QuestionRead, FieldDefinition } from "@/types/api";
import { cleanHumanLabel } from "@/lib/labelUtils";
import { t as ti18n } from "@/lib/i18n";

const LOADING: Record<string, string> = {
  en: "Reading your document…", de: "Dokument wird gelesen…",
  ar: "جارٍ قراءة مستندك…", tr: "Belgeniz okunuyor…",
  fr: "Lecture de votre document…", es: "Leyendo su documento…",
  sq: "Duke lexuar dokumentin tuaj…", ru: "Чтение документа…",
  uk: "Читання документа…", fa: "در حال خواندن سند شما…",
};
const SUBMIT: Record<string, string> = {
  en: "Next →", de: "Weiter →", ar: "التالي →", tr: "İleri →",
  fr: "Suivant →", es: "Siguiente →", sq: "Tjetër →",
  ru: "Далее →", uk: "Далі →", fa: "بعدی →",
};
const PREFILL_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `✓ ${n} field${n !== 1 ? "s" : ""} were read from your document and pre-filled.`,
  de: (n) => `✓ ${n} Feld${n !== 1 ? "er" : ""} wurden aus Ihrem Dokument gelesen und vorausgefüllt.`,
  ar: (n) => `✓ تم قراءة ${n} حقل من مستندك وتعبئته تلقائياً.`,
  tr: (n) => `✓ ${n} alan belgenizden okunarak otomatik dolduruldu.`,
  fr: (n) => `✓ ${n} champ${n !== 1 ? "s" : ""} ont été lus depuis votre document et pré-remplis.`,
  es: (n) => `✓ ${n} campo${n !== 1 ? "s" : ""} fueron leídos de su documento y pre-rellenados.`,
  sq: (n) => `✓ ${n} fushë u lexuan nga dokumenti juaj dhe u plotësuan automatikisht.`,
  ru: (n) => `✓ ${n} поле${n !== 1 ? "й" : ""} прочитано из вашего документа и предзаполнено.`,
  uk: (n) => `✓ ${n} пол${n !== 1 ? "і" : "е"} прочитано з вашого документа і попередньо заповнено.`,
};
const BLOCKED_BANNER: Record<string, (n: number) => string> = {
  en: (n) => `ℹ ${n} field${n !== 1 ? "s" : ""} could not be verified (low confidence) and were excluded.`,
  de: (n) => `ℹ ${n} Feld${n !== 1 ? "er" : ""} konnten nicht verifiziert werden und wurden ausgeschlossen.`,
  ar: (n) => `ℹ ${n} حقل لم يمكن التحقق منه واستُبعد.`,
  tr: (n) => `ℹ ${n} alan doğrulanamadı ve dışlandı.`,
  fr: (n) => `ℹ ${n} champ${n !== 1 ? "s" : ""} n'ont pas pu être vérifiés et ont été exclus.`,
  es: (n) => `ℹ ${n} campo${n !== 1 ? "s" : ""} no pudieron ser verificados y fueron excluidos.`,
  sq: (n) => `ℹ ${n} fushë nuk mund të verifikoheshin dhe u përjashtuan.`,
  ru: (n) => `ℹ ${n} пол${n !== 1 ? "я" : "е"} не могло быть проверено и было исключено.`,
  uk: (n) => `ℹ ${n} пол${n !== 1 ? "і" : "е"} не вдалося перевірити і було виключено.`,
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
  questionFields: FieldDefinition[];
  locale: string;
}

const WEAK_NOUN_PHRASES = new Set([
  "day", "month", "year", "time", "amount", "number / count", "number", "count",
  "starting location", "destination", "route / distance", "transportation",
  "description", "notes / remarks", "reason", "purpose", "we", "yes", "no",
]);

function isWeakQuestion(q: FieldDefinition, locale: string): boolean {
  const text = (q.question?.[locale] || q.question?.["en"] || "").trim();
  if (!text) return true;
  if (text.startsWith("⚠") || text.toLowerCase().startsWith("translation unavailable")) return true;
  if (text.toLowerCase() === (q.original_label || "").toLowerCase() && text.length < 30) return true;
  if (/\s+\d+$/.test(text)) return true;                    // trailing number: "Startort 13"
  if (text.includes("=")) return true;                      // "Zielort=Startort"
  if (text.split(" ").length < 4 && !["checkbox", "signature"].includes(q.input_type)) return true;
  if (WEAK_NOUN_PHRASES.has(text.toLowerCase())) return true; // noun not question
  return false;
}

function DebugPanel({
  caseId, documentId, extractedFieldIds, questionFieldIds, blockedByGuard, report,
  questionFields, locale,
}: DebugPanelProps) {
  const weakFields = questionFields.filter(f => isWeakQuestion(f, locale));
  const goodCount  = questionFields.length - weakFields.length;
  const sourceCounts = questionFields.reduce<Record<string, number>>((acc, f) => {
    const src = f.question_source || "unknown";
    acc[src] = (acc[src] || 0) + 1;
    return acc;
  }, {});
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

        {/* Question quality audit */}
        <div className={`p-3 rounded ${weakFields.length > 0 ? "bg-amber-50 border border-amber-200" : "bg-green-50 border border-green-200"}`}>
          <p className="font-semibold mb-1 text-xs">Question quality ({locale})</p>
          <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-xs">
            <span className="text-gray-400">total</span><span>{questionFields.length}</span>
            <span className="text-gray-400">good</span><span className="text-green-700">{goodCount}</span>
            <span className="text-gray-400">weak</span>
            <span className={weakFields.length > 0 ? "text-amber-700 font-bold" : "text-green-700"}>{weakFields.length}</span>
          </div>
          {weakFields.length > 0 && (
            <div className="mt-2">
              <p className="text-amber-700 text-xs font-semibold mb-1">Weak fields:</p>
              {weakFields.map(f => (
                <div key={f.key} className="text-xs text-amber-600 font-mono">
                  [{f.question_source || "?"}] {f.key}: {cleanHumanLabel(f.question?.[locale] || f.original_label || f.key)}
                </div>
              ))}
            </div>
          )}
          {Object.keys(sourceCounts).length > 0 && (
            <div className="mt-2">
              <p className="text-xs text-gray-500 font-semibold mb-1">Question sources:</p>
              {Object.entries(sourceCounts).map(([src, n]) => (
                <div key={src} className="text-xs font-mono text-gray-500">
                  <span className={src === "verified" ? "text-green-600" : src === "semantic" ? "text-blue-600" : src === "ai" ? "text-purple-600" : src === "deterministic" ? "text-teal-600" : "text-red-500"}>
                    {src}
                  </span>: {n}
                </div>
              ))}
            </div>
          )}
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
    answeredKeys, answeredValues, addAnswer,
    markSaved, clearCurrentDocument,
    supportLevel, templateId, ocrDiagnostic,
  } = useCaseStore();
  const [mounted, setMounted]       = useState(false);
  const [isLoading, setIsLoading]   = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [focusedKey, setFocusedKey] = useState<string | null>(null);
  const [showNewDocModal, setShowNewDocModal] = useState(false);
  const [saveMsg, setSaveMsg]       = useState<string | null>(null);

  // ALL hooks before any conditional return
  useEffect(() => { setMounted(true); }, []);

  // Read ?focus=<field_key> from URL so the review page can deep-link back here
  useEffect(() => {
    if (!mounted) return;
    try {
      const key = new URLSearchParams(window.location.search).get("focus");
      if (key) setFocusedKey(key);
    } catch { /* ignore */ }
  }, [mounted]);

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
        <Header locale={locale} />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={1} locale={locale} />
          <div className="p-6 bg-red-50 border border-red-200 rounded-xl">
            <p className="text-red-700 font-semibold mb-2">{ti18n("q.no_grounding", locale)}</p>
            <p className="text-red-600 text-sm mb-4">
              {ti18n("q.no_grounding_body", locale)}
            </p>
            <button
              onClick={() => router.replace(`/${locale}/upload`)}
              className="px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700"
            >
              {ti18n("q.upload_again", locale)}
            </button>
          </div>
          <DebugPanel
            caseId={caseId}
            documentId={documentId}
            extractedFieldIds={safeExtracted}
            questionFieldIds={safeFields.map((f) => f.key)}
            blockedByGuard={safeFields.map((f) => f.key)}
            report={null}
            questionFields={[]}
            locale={locale}
          />
        </main>
      </>
    );
  }

  if (safeFields.length === 0) {
    // Level 4: scanned/unknown — backend returned 0 fields by design.
    // Show an explicit "not supported" screen, not a perpetual "Loading…" spinner.
    if (supportLevel === 4) {
      const L4_TITLE: Record<string, string> = {
        en: "We can't read this document yet",
        de: "Wir können dieses Dokument noch nicht lesen",
        fr: "Nous ne pouvons pas encore lire ce document",
        ar: "لا يمكننا قراءة هذا المستند بعد",
        tr: "Bu belgeyi henüz okuyamıyoruz",
        sq: "Nuk mund ta lexojmë këtë dokument ende",
        es: "Aún no podemos leer este documento",
        fa: "ما هنوز نمی‌توانیم این سند را بخوانیم",
        ru: "Мы пока не можем прочитать этот документ",
        uk: "Ми поки не можемо прочитати цей документ",
      };
      const L4_BODY: Record<string, string> = {
        en: "It looks like a scanned image or photo. Please upload a digital PDF (one you downloaded from a website or generated on a computer).",
        de: "Es sieht aus wie ein gescanntes Bild oder Foto. Bitte laden Sie eine digitale PDF hoch (von einer Website oder am Computer erstellt).",
        fr: "Cela ressemble à une image scannée ou une photo. Veuillez téléverser un PDF numérique (téléchargé depuis un site web ou créé sur un ordinateur).",
        ar: "يبدو أنه صورة ممسوحة ضوئيًا. يرجى تحميل ملف PDF رقمي (تم تنزيله من موقع ويب أو إنشاؤه على جهاز كمبيوتر).",
        tr: "Bu taranmış bir görüntü veya fotoğraf gibi görünüyor. Lütfen dijital bir PDF yükleyin (bir web sitesinden indirilmiş veya bir bilgisayarda oluşturulmuş).",
        sq: "Duket si një imazh i skanuar ose fotografi. Ngarkoni një PDF dixhital (i shkarkuar nga një uebsajt ose i krijuar në një kompjuter).",
        es: "Parece una imagen escaneada o una foto. Suba un PDF digital (descargado de un sitio web o generado en una computadora).",
        fa: "به نظر می‌رسد این یک تصویر اسکن شده یا عکس است. لطفاً یک PDF دیجیتال آپلود کنید.",
        ru: "Похоже на отсканированное изображение или фотографию. Загрузите цифровой PDF.",
        uk: "Це виглядає як сканований документ або фото. Завантажте цифровий PDF.",
      };
      const L4_BUTTON: Record<string, string> = {
        en: "Upload a different PDF",
        de: "Andere PDF hochladen",
        fr: "Téléverser un autre PDF",
        ar: "تحميل ملف PDF آخر",
        tr: "Başka bir PDF yükle",
        sq: "Ngarko një PDF tjetër",
        es: "Subir un PDF diferente",
        fa: "آپلود PDF دیگر",
        ru: "Загрузить другой PDF",
        uk: "Завантажити інший PDF",
      };
      const title = L4_TITLE[locale] ?? L4_TITLE.en;
      const body  = L4_BODY[locale]  ?? L4_BODY.en;
      const btn   = L4_BUTTON[locale] ?? L4_BUTTON.en;

      // Stage 4A — OCR diagnostic panel. Only shown when the backend
      // returned an ocr_diagnostic (always for support_level=4 PDFs after
      // Stage 4A; absent on legacy responses signed before Stage 4A shipped).
      // The status drives copy; the user_message is the headline.
      const OCR_HEADER: Record<string, string> = {
        en: "We tried to read this scanned document",
        de: "Wir haben versucht, dieses gescannte Dokument zu lesen",
        fr: "Nous avons essayé de lire ce document scanné",
        ar: "حاولنا قراءة هذا المستند الممسوح ضوئيًا",
        tr: "Bu taranmış belgeyi okumaya çalıştık",
        sq: "Provuam ta lexojmë këtë dokument të skanuar",
        es: "Intentamos leer este documento escaneado",
        fa: "تلاش کردیم این سند اسکن شده را بخوانیم",
        ru: "Мы попытались прочитать этот отсканированный документ",
        uk: "Ми спробували прочитати цей сканований документ",
      };
      const OCR_PAGES_LABEL: Record<string, string> = {
        en: "Pages read", de: "Gelesene Seiten", fr: "Pages lues",
        ar: "الصفحات المقروءة", tr: "Okunan sayfalar", sq: "Faqe të lexuara",
        es: "Páginas leídas", fa: "صفحات خوانده شده",
        ru: "Прочитанные страницы", uk: "Прочитані сторінки",
      };
      const OCR_CONFIDENCE_LABEL: Record<string, string> = {
        en: "Average confidence", de: "Durchschnittliche Genauigkeit",
        fr: "Confiance moyenne", ar: "متوسط الثقة",
        tr: "Ortalama güven", sq: "Besimi mesatar",
        es: "Confianza promedio", fa: "میانگین اطمینان",
        ru: "Средняя уверенность", uk: "Середня впевненість",
      };

      // Localized status copy. The backend's user_message is English; we
      // override with locale-specific text when we have it for this status.
      const _localizedOcrCopy = (): string | null => {
        if (!ocrDiagnostic) return null;
        const dict: Record<string, Record<string, string>> = {
          readable: {
            en: "We can read some text from this scan, but OCR form filling is not enabled yet. This scan may be usable in a future step.",
            de: "Wir können Text aus diesem Scan lesen, aber das automatische Ausfüllen per OCR ist noch nicht aktiviert. Dieser Scan könnte in einem späteren Schritt nutzbar sein.",
            fr: "Nous pouvons lire du texte de ce scan, mais le remplissage automatique par OCR n'est pas encore activé. Ce scan pourra être utilisé plus tard.",
            ar: "يمكننا قراءة بعض النصوص من هذا المسح، لكن التعبئة التلقائية للنماذج عبر OCR غير مفعلة بعد.",
            tr: "Bu taramadan biraz metin okuyabiliyoruz, ancak OCR ile otomatik doldurma henüz etkin değil.",
            sq: "Mund të lexojmë pak tekst nga ky skanim, por plotësimi automatik i formularit me OCR nuk është aktivizuar ende.",
          },
          low_confidence: {
            en: "The scan is hard to read. Try again with better lighting, a flat page, and no shadows.",
            de: "Der Scan ist schwer zu lesen. Versuchen Sie es erneut mit besserem Licht, einer flachen Seite und ohne Schatten.",
            fr: "Le scan est difficile à lire. Réessayez avec un meilleur éclairage, une page plate et sans ombres.",
            ar: "المسح صعب القراءة. حاول مرة أخرى بإضاءة أفضل وصفحة مسطحة وبدون ظلال.",
            tr: "Tarama okunması zor. Daha iyi ışıkta, düz bir sayfada ve gölgesiz tekrar deneyin.",
            sq: "Skanimi është i vështirë për t'u lexuar. Provoni përsëri me dritë më të mirë, faqe të rrafshët dhe pa hije.",
          },
          no_text_found: {
            en: "We could not read text from this image. Please upload a digital PDF or retake the photo.",
            de: "Wir konnten keinen Text aus diesem Bild lesen. Bitte laden Sie eine digitale PDF hoch oder fotografieren Sie erneut.",
            fr: "Nous n'avons pas pu lire de texte sur cette image. Veuillez téléverser un PDF numérique ou reprendre la photo.",
            ar: "لم نتمكن من قراءة نص من هذه الصورة. يرجى تحميل ملف PDF رقمي أو إعادة التقاط الصورة.",
            tr: "Bu görüntüden metin okuyamadık. Lütfen dijital bir PDF yükleyin veya fotoğrafı yeniden çekin.",
            sq: "Nuk mund të lexojmë tekst nga kjo imazh. Ngarkoni një PDF dixhital ose rifotografojeni.",
          },
          ocr_unavailable: {
            en: "OCR is not installed on this server yet.",
            de: "OCR ist auf diesem Server noch nicht installiert.",
            fr: "L'OCR n'est pas encore installé sur ce serveur.",
            ar: "OCR غير مثبت على هذا الخادم بعد.",
            tr: "Bu sunucuda OCR henüz kurulu değil.",
            sq: "OCR nuk është instaluar ende në këtë server.",
          },
          failed: {
            en: "We could not read this document. Please try again or upload a digital PDF.",
            de: "Wir konnten dieses Dokument nicht lesen. Bitte versuchen Sie es erneut oder laden Sie eine digitale PDF hoch.",
            fr: "Nous n'avons pas pu lire ce document. Veuillez réessayer ou téléverser un PDF numérique.",
            ar: "لم نتمكن من قراءة هذا المستند. يرجى المحاولة مرة أخرى أو تحميل ملف PDF رقمي.",
            tr: "Bu belgeyi okuyamadık. Lütfen tekrar deneyin veya dijital bir PDF yükleyin.",
            sq: "Nuk mund ta lexojmë këtë dokument. Provoni përsëri ose ngarkoni një PDF dixhital.",
          },
        };
        const statusDict = dict[ocrDiagnostic.diagnostic_status];
        if (!statusDict) return ocrDiagnostic.user_message;
        return statusDict[locale] ?? statusDict.en ?? ocrDiagnostic.user_message;
      };

      return (
        <>
          <Header locale={locale} />
          <main className="max-w-2xl mx-auto px-4 py-8">
            <StepProgress currentStep={1} locale={locale} />
            <SupportLevelBanner supportLevel={4} locale={locale} />
            <div
              data-testid="level4-unsupported"
              className="p-6 bg-white border border-gray-200 rounded-xl text-center"
            >
              <div className="text-5xl mb-3" aria-hidden>📄</div>
              <p className="text-gray-900 font-semibold text-lg mb-2">{title}</p>
              <p className="text-gray-600 text-sm mb-5 max-w-md mx-auto">{body}</p>

              {ocrDiagnostic && (
                <div
                  data-testid="ocr-diagnostic-panel"
                  className="mt-2 mb-5 p-4 bg-gray-50 border border-gray-200 rounded-lg text-left max-w-md mx-auto"
                >
                  <p className="text-sm font-semibold text-gray-700 mb-2">
                    {OCR_HEADER[locale] ?? OCR_HEADER.en}
                  </p>
                  <p className="text-sm text-gray-600 mb-3">
                    {_localizedOcrCopy()}
                  </p>
                  {ocrDiagnostic.diagnostic_status !== "ocr_unavailable" && ocrDiagnostic.page_count > 0 && (
                    <div className="text-xs text-gray-500 space-y-1">
                      <p>
                        {OCR_PAGES_LABEL[locale] ?? OCR_PAGES_LABEL.en}:{" "}
                        <span className="font-mono text-gray-700">
                          {ocrDiagnostic.readable_pages} / {ocrDiagnostic.page_count}
                        </span>
                      </p>
                      <p>
                        {OCR_CONFIDENCE_LABEL[locale] ?? OCR_CONFIDENCE_LABEL.en}:{" "}
                        <span className="font-mono text-gray-700">
                          {Math.round(ocrDiagnostic.average_confidence * 100)}%
                        </span>
                      </p>
                    </div>
                  )}
                </div>
              )}

              <button
                onClick={() => router.replace(`/${locale}/upload`)}
                className="px-5 py-2.5 bg-brand-600 text-white rounded-xl text-sm font-medium hover:bg-brand-700"
              >
                {btn}
              </button>
            </div>
          </main>
        </>
      );
    }

    return (
      <>
        <Header locale={locale} />
        <main className="max-w-2xl mx-auto px-4 py-8">
          <StepProgress currentStep={1} locale={locale} />
          <div className="text-center py-16 text-gray-400 text-lg">
            {LOADING[locale] ?? ti18n("q.loading", locale)}
          </div>
        </main>
      </>
    );
  }

  // currentField: if the user jumped to a specific question use that; otherwise
  // show the next unanswered one.  focusedKey may point to an already-answered
  // field (for re-answering) so we don't filter by answered status here.
  const currentField =
    (focusedKey ? questionFields.find(f => f.key === focusedKey) : null)
    ?? nextField;

  const currentIndex = currentField
    ? questionFields.findIndex(f => f.key === currentField.key) + 1
    : answeredCount + 1;

  if (!currentField) return null;

  const question: QuestionRead = {
    id: currentField.key,
    field_key: currentField.key,
    order_index: currentField.order,
    input_type: currentField.input_type,
    question_text: currentField.question,
    explanation_text: currentField.explanation,
    options: null,
    answered_count: answeredCount,
    total_count: totalCount,
  };

  async function handleAnswer(rawAnswer: string) {
    if (!currentField) return;
    setIsLoading(true);
    setSubmitError(null);
    try {
      if (sessionToken && caseId) {
        api.questions.submitAnswer(sessionToken, caseId, currentField.key, rawAnswer).catch(() => {});
      }
    } finally {
      setIsLoading(false);
    }
    addAnswer(currentField.key, rawAnswer);
    // Return to normal sequential flow after answering a jump-to question
    setFocusedKey(null);
  }

  // ── Localised labels for buttons (all supported locales) ─────────────────────
  const LBL = {
    saveBtn:    { en: "Save for later", de: "Speichern", ar: "حفظ لوقت لاحق", tr: "Sonra devam et", fr: "Enregistrer", es: "Guardar", sq: "Ruaj", ru: "Сохранить", uk: "Зберегти", fa: "ذخیره" },
    newDocBtn:  { en: "New document", de: "Neues Dokument", ar: "مستند جديد", tr: "Yeni belge", fr: "Nouveau document", es: "Nuevo documento", sq: "Dokument i ri", ru: "Новый документ", uk: "Новий документ", fa: "سند جدید" },
    savedMsg:   { en: "Saved on this device.", de: "Auf diesem Gerät gespeichert.", ar: "تم الحفظ على هذا الجهاز.", tr: "Bu cihaza kaydedildi.", fr: "Enregistré sur cet appareil.", es: "Guardado en este dispositivo.", sq: "Ruajtur në këtë pajisje.", ru: "Сохранено на этом устройстве.", uk: "Збережено на цьому пристрої.", fa: "در این دستگاه ذخیره شد." },
    savedWarn:  { en: "Only saved locally — do not use on a shared computer.", de: "Nur lokal gespeichert.", ar: "محفوظ محليًا فقط.", tr: "Yalnızca yerel olarak kaydedildi.", fr: "Enregistré localement uniquement.", es: "Solo guardado localmente.", sq: "Ruajtur vetëm lokalisht.", ru: "Сохранено только локально.", uk: "Збережено лише локально.", fa: "فقط به صورت محلی ذخیره شده." },
    modalTitle: { en: "Start a new document?", de: "Neues Dokument starten?", ar: "بدء مستند جديد؟", tr: "Yeni bir belge?", fr: "Commencer un nouveau document ?", es: "¿Iniciar un nuevo documento?", sq: "Filloni një dokument të ri?", ru: "Начать новый документ?", uk: "Почати новий документ?", fa: "شروع سند جدید؟" },
    modalMsg:   { en: "Your current answers will be lost. Save first if you want to return to this form.", de: "Ihre aktuellen Antworten gehen verloren. Speichern Sie zuerst.", ar: "ستُفقد إجاباتك الحالية. احفظ أولاً.", tr: "Mevcut yanitlariniz kaybolacak. Once kaydedin.", fr: "Vos réponses actuelles seront perdues. Enregistrez d'abord.", es: "Sus respuestas actuales se perderán. Guarde primero.", sq: "Pergjigjet tuaja do te humbasin. Ruajeni fillimisht.", ru: "Ваши ответы будут потеряны. Сначала сохраните.", uk: "Ваші відповіді будуть втрачені. Спочатку збережіть.", fa: "پاسخ‌های شما از دست خواهند رفت. ابتدا ذخیره کنید." },
    saveFirst:  { en: "Save first, then start new", de: "Erst speichern, dann neu", ar: "احفظ أولاً ثم ابدأ", tr: "Önce kaydet, sonra başla", fr: "Enregistrer d'abord, puis nouveau", es: "Guardar primero, luego nuevo", sq: "Ruaj fillimisht, pastaj nis të ri", ru: "Сначала сохранить, затем новый", uk: "Спочатку зберегти, потім новий", fa: "ابتدا ذخیره کنید، سپس جدید" },
    startNew:   { en: "Start new (don't save)", de: "Neu starten (nicht speichern)", ar: "ابدأ جديداً (بدون حفظ)", tr: "Kaydetmeden basla", fr: "Nouveau (sans enregistrer)", es: "Nuevo (sin guardar)", sq: "Nis te ri (pa ruajtur)", ru: "Новый (без сохранения)", uk: "Новий (без збереження)", fa: "شروع جدید (بدون ذخیره)" },
    cancel:     { en: "Cancel", de: "Abbrechen", ar: "إلغاء", tr: "Iptal", fr: "Annuler", es: "Cancelar", sq: "Anulo", ru: "Отмена", uk: "Скасувати", fa: "لغو" },
    continueNow:{ en: "Continue answering", de: "Weiter ausfüllen", ar: "تابع الإجابة", tr: "Yanitlamaya devam et", fr: "Continuer", es: "Continuar respondiendo", sq: "Vazhdo te pergjigjesh", ru: "Продолжить отвечать", uk: "Продовжити відповідати", fa: "ادامه پاسخ‌دهی" },
  };
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const lbl = (k: keyof typeof LBL): string => (LBL[k] as any)[locale] ?? (LBL[k] as any)["en"];

  function handleSave() {
    markSaved();
    setSaveMsg(lbl("savedMsg") + " " + lbl("savedWarn"));
  }
  function handleStartNew() {
    clearCurrentDocument();
    router.push(`/${locale}/upload`);
  }

  return (
    <>
      {showNewDocModal && (
        <ConfirmModal
          title={lbl("modalTitle")}
          message={lbl("modalMsg")}
          onDismiss={() => setShowNewDocModal(false)}
          actions={[
            {
              label: lbl("saveFirst"), variant: "primary",
              onClick: () => { markSaved(); setShowNewDocModal(false); handleStartNew(); },
            },
            {
              label: lbl("startNew"), variant: "danger",
              onClick: () => { setShowNewDocModal(false); handleStartNew(); },
            },
            {
              label: lbl("cancel"), variant: "secondary",
              onClick: () => setShowNewDocModal(false),
            },
          ]}
        />
      )}

      <Header locale={locale} />
      <main className="max-w-2xl mx-auto px-4 py-8">
        <StepProgress currentStep={1} locale={locale} />

        <SupportLevelBanner
          supportLevel={supportLevel}
          locale={locale}
          templateName={templateId}
        />

        <ReviewWarning
          supportLevel={supportLevel}
          fields={safeFields}
          locale={locale}
        />

        {/* Action bar — save / new document */}
        <div className="mb-4 flex items-center justify-between gap-2">
          <button
            onClick={() => setShowNewDocModal(true)}
            className="text-xs text-gray-400 hover:text-gray-600 transition-colors flex items-center gap-1"
          >
            ← {lbl("newDocBtn")}
          </button>
          <button
            onClick={handleSave}
            className="text-xs text-brand-600 hover:text-brand-700 font-medium transition-colors"
          >
            {lbl("saveBtn")}
          </button>
        </div>

        {saveMsg && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-xs flex items-start justify-between gap-2">
            <span>{saveMsg}</span>
            <button onClick={() => setSaveMsg(null)} className="flex-shrink-0 text-green-600 font-bold">✕</button>
          </div>
        )}

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

        {/* Question overview — collapsed by default */}
        <QuestionOverview
          questionFields={questionFields}
          answeredKeys={safeAnswered}
          answeredValues={answeredValues ?? {}}
          currentKey={currentField.key}
          locale={locale}
          onJumpTo={(key) => setFocusedKey(key)}
        />

        {/* Progress line */}
        <div className="mb-3 flex items-center gap-3 text-sm text-gray-400">
          <span>
            {ti18n("q.question_n_of_m", locale, { n: currentIndex, m: totalCount })}
            {totalCount - answeredCount > 0 && (
              <span className="ml-2 text-amber-600">
                · {totalCount - answeredCount}{" "}
                {ti18n("q.missing", locale)}
              </span>
            )}
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
          options={currentField.options ?? []}
          needsReview={currentField.needs_review ?? false}
          originalLabel={currentField.original_label}
          fieldKey={currentField.key}
          guidance={currentField.guidance}
        />

        {/* Phase E/E4 + E5 — privacy-first footer: honest copy + wipe link */}
        <div className="mt-8 pt-4 border-t border-gray-100 flex flex-col items-center gap-3">
          <PrivacyNote locale={locale} className="text-center text-xs text-gray-500 leading-relaxed max-w-md" />
          <DeleteSavedData locale={locale} compact />
        </div>

        {/* Always-visible debug panel — shows grounding proof and question quality */}
        <DebugPanel
          caseId={caseId}
          documentId={documentId}
          extractedFieldIds={safeExtracted}
          questionFieldIds={questionFields.map((f) => f.key)}
          blockedByGuard={blockedByGuard.map((f) => f.key)}
          report={null}
          questionFields={questionFields}
          locale={locale}
        />
      </main>
    </>
  );
}
