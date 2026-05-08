"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { StepProgress } from "@/components/layout/StepProgress";
import { ConfirmModal } from "@/components/layout/ConfirmModal";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import { resolveQuestionText } from "@/lib/labelUtils";
import { OutputGuarantee } from "@/components/questions/OutputGuarantee";

const T: Record<string, Record<string, string>> = {
  title:         { en: "Review your answers", ar: "راجع إجاباتك", tr: "Cevaplarınızı inceleyin", de: "Antworten überprüfen" },
  instr:         { en: "Check everything before generating the PDF.", ar: "تحقق من كل شيء قبل إنشاء PDF.", tr: "PDF'yi oluşturmadan önce kontrol edin.", de: "Alles prüfen, bevor das PDF erstellt wird." },
  generate:      { en: "Generate & Download PDF", ar: "إنشاء وتنزيل PDF", tr: "PDF Oluştur ve İndir", de: "PDF erstellen & herunterladen" },
  edit:          { en: "← Edit answers", ar: "← تعديل الإجابات", tr: "← Yanıtları düzenle", de: "← Antworten bearbeiten" },
  generating:    { en: "Generating PDF…", ar: "جارٍ إنشاء PDF…", tr: "PDF oluşturuluyor…", de: "PDF wird erstellt…" },
  no_token:      { en: "PDF session expired. Please re-upload your document.", ar: "انتهت الجلسة. يرجى رفع المستند مرة أخرى.", tr: "Oturum süresi doldu. Lütfen belgeyi tekrar yükleyin.", de: "Sitzung abgelaufen. Bitte Dokument erneut hochladen." },
  start_new:     { en: "Start a new form", ar: "ابدأ استمارة جديدة", tr: "Yeni form başlat", de: "Neues Formular starten" },
  manual_fields: { en: "Must be filled in manually after printing:", ar: "يجب ملؤها يدويًا بعد الطباعة:", tr: "Yazdırdıktan sonra manuel doldurulmalı:", de: "Nach dem Drucken manuell ausfüllen:" },
  no_answers:    { en: "Please answer the questions first.", ar: "يرجى الإجابة على الأسئلة أولاً.", tr: "Lütfen önce soruları yanıtlayın.", de: "Bitte beantworten Sie zuerst die Fragen.", fr: "Veuillez d'abord répondre aux questions.", es: "Por favor, responda primero las preguntas.", sq: "Ju lutemi përgjigjuni pyetjeve së pari.", ru: "Пожалуйста, сначала ответьте на вопросы.", uk: "Будь ласка, спочатку дайте відповіді на питання." },
  save_btn:      { en: "Save for later", ar: "حفظ لوقت لاحق", tr: "Sonra devam et", de: "Speichern" },
  saved_msg:     { en: "Saved on this device.", ar: "تم الحفظ على هذا الجهاز.", tr: "Bu cihaza kaydedildi.", de: "Auf diesem Gerät gespeichert." },
  saved_warn:    { en: "Only saved locally — do not use on a shared computer.", ar: "محفوظ محليًا فقط.", tr: "Yalnızca yerel olarak kaydedildi.", de: "Nur lokal gespeichert — nicht auf einem gemeinsam genutzten Computer verwenden." },
  new_doc_btn:   { en: "New document", ar: "مستند جديد", tr: "Yeni belge", de: "Neues Dokument" },
  modal_title:   { en: "Start a new document?", ar: "بدء مستند جديد؟", tr: "Yeni bir belge?", de: "Neues Dokument starten?" },
  modal_msg:     { en: "Your current answers will be lost. Click \"Save for later\" first if you want to return to this form.", ar: "ستُفقد إجاباتك الحالية. انقر على «حفظ» أولاً إذا كنت تريد العودة.", tr: "Mevcut yanitlariniz kaybolacak. Once \"Kaydet\" dugmesine tiklayin.", de: "Ihre aktuellen Antworten gehen verloren. Speichern Sie zuerst, wenn Sie spaeter zurueckkehren moechten." },
  save_first:    { en: "Save first, then start new", ar: "احفظ أولاً ثم ابدأ", tr: "Önce kaydet, sonra başla", de: "Erst speichern, dann neu" },
  start_new_btn: { en: "Start new (don't save)", ar: "ابدأ جديداً (بدون حفظ)", tr: "Kaydetmeden başla", de: "Neu starten (nicht speichern)" },
  cancel:        { en: "Cancel", ar: "إلغاء", tr: "İptal", de: "Abbrechen" },
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
  const { fields, answeredValues, pdfToken, extractedFieldIds, reset, markSaved, clearCurrentDocument, supportLevel } = useCaseStore();
  const [mounted, setMounted]             = useState(false);
  const [generating, setGenerating]       = useState(false);
  const [error, setError]                 = useState<string | null>(null);
  const [done, setDone]                   = useState(false);
  const [notFillable, setNotFillable]     = useState<string[]>([]);
  const [fillStrategy, setFillStrategy]   = useState<string>("");
  const [showNewDocModal, setShowNewDocModal] = useState(false);
  const [saveMsg, setSaveMsg]             = useState<string | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (mounted && (!fields || fields.length === 0)) {
      router.replace(`/${locale}/upload`);
    }
  }, [mounted, fields, locale, router]);

  if (!mounted) return null;

  const safeFields    = fields ?? [];
  const safeAnswers   = answeredValues ?? {};
  const safeExtracted = extractedFieldIds ?? [];

  const groundedFields   = safeExtracted.length > 0
    ? safeFields.filter(f => safeExtracted.includes(f.key))
    : [];
  const questionFields   = groundedFields.filter(f => f.show_question !== false && !f.is_prefilled);
  const unansweredFields = questionFields.filter(f => safeAnswers[f.key] === undefined);

  const answeredList = safeFields
    .filter((f) => safeAnswers[f.key] !== undefined)
    .map((f) => ({
      key:       f.key,
      label:     resolveQuestionText(f.question, f.original_label, f.key, locale),
      origLabel: f.original_label,
      value:     safeAnswers[f.key],
      inputType: f.input_type,
    }));

  function handleSave() {
    markSaved();
    setSaveMsg(`${t("saved_msg", locale)} ${t("saved_warn", locale)}`);
  }

  function handleStartNew() {
    clearCurrentDocument();
    router.push(`/${locale}/upload`);
  }

  async function handleGenerate() {
    if (!pdfToken) {
      setError(t("no_token", locale));
      return;
    }
    if (Object.keys(safeAnswers).length === 0) {
      setError(t("no_answers", locale));
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const fieldLabels: Record<string, string> = {};
      safeFields.forEach((f) => { fieldLabels[f.key] = f.original_label || f.key; });

      const { blob, notFillable: nf, strategy } = await api.fillPdf(pdfToken, safeAnswers, fieldLabels);

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
      // Always render a localized, plain-language message.
      // Never expose backend deployment / API URL / status codes to the user.
      const { friendlyError } = await import("@/lib/errors");
      setError(friendlyError(e, locale));
    } finally {
      setGenerating(false);
    }
  }

  if (done) {
    // iOS detection: Safari/Chrome/Firefox on iPhone or iPad all share the
    // "files saved via Share → Save to Files" pattern. Includes iPadOS 13+
    // which reports macOS userAgent — check touch points as a tie-breaker.
    const ua = typeof navigator !== "undefined" ? navigator.userAgent : "";
    const maxTouch = typeof navigator !== "undefined" ? (navigator as Navigator & { maxTouchPoints?: number }).maxTouchPoints ?? 0 : 0;
    const isIOS =
      /iPhone|iPad|iPod/i.test(ua) ||
      (/Macintosh/i.test(ua) && maxTouch > 1);
    const IOS_TITLE: Record<string, string> = {
      en: "On iPhone or iPad",
      de: "Auf iPhone oder iPad",
      fr: "Sur iPhone ou iPad",
      ar: "على iPhone أو iPad",
      tr: "iPhone veya iPad'de",
      sq: "Në iPhone ose iPad",
      es: "En iPhone o iPad",
      fa: "روی iPhone یا iPad",
      ru: "На iPhone или iPad",
      uk: "На iPhone або iPad",
    };
    const IOS_BODY: Record<string, string> = {
      en: "Tap the Share button, then choose Save to Files to keep your completed PDF on this device.",
      de: "Tippen Sie auf das Teilen-Symbol und wählen Sie In Dateien sichern, um Ihre PDF auf diesem Gerät zu speichern.",
      fr: "Appuyez sur le bouton Partager, puis choisissez Enregistrer dans Fichiers pour conserver le PDF sur cet appareil.",
      ar: "اضغط على زر المشاركة، ثم اختر حفظ في الملفات للاحتفاظ بملف PDF على هذا الجهاز.",
      tr: "Paylaş düğmesine dokunun, sonra Dosyalar'a Kaydet seçeneğini seçin.",
      sq: "Prekni butonin Ndaj, pastaj zgjidhni Ruaj në Skedarë për të mbajtur PDF-në në këtë pajisje.",
      es: "Toque el botón Compartir y luego elija Guardar en Archivos para conservar el PDF en este dispositivo.",
      fa: "روی دکمه اشتراک‌گذاری ضربه بزنید، سپس Save to Files را انتخاب کنید.",
      ru: "Нажмите кнопку Поделиться, затем выберите Сохранить в Файлы.",
      uk: "Натисніть кнопку Поділитися, потім виберіть Зберегти у Файли.",
    };
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

          {isIOS && (
            <div
              data-testid="ios-save-instructions"
              className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-xl flex items-start gap-3"
            >
              <span className="text-2xl leading-none mt-0.5" aria-hidden>📲</span>
              <div className="flex-1 min-w-0">
                <p className="text-blue-900 font-semibold text-sm mb-1">
                  {IOS_TITLE[locale] ?? IOS_TITLE.en}
                </p>
                <p className="text-blue-800 text-sm leading-relaxed">
                  {IOS_BODY[locale] ?? IOS_BODY.en}
                </p>
              </div>
            </div>
          )}

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

        {/* Action bar */}
        <div className="flex items-center justify-between gap-3 mb-5">
          <button
            onClick={() => setShowNewDocModal(true)}
            className="text-sm text-gray-500 hover:text-gray-800 font-medium transition-colors"
          >
            ← {t("new_doc_btn", locale)}
          </button>
          <button
            onClick={handleSave}
            className="px-4 py-2 bg-green-600 text-white text-sm font-semibold rounded-xl hover:bg-green-700 transition-colors"
          >
            {t("save_btn", locale)}
          </button>
        </div>

        {saveMsg && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-xl text-green-800 text-sm">
            {saveMsg}
          </div>
        )}

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

        {/* Missing answers warning */}
        {unansweredFields.length > 0 && (
          <div className="mb-6 p-4 bg-amber-50 border border-amber-300 rounded-xl">
            <p className="text-amber-800 text-sm font-semibold mb-3">
              {locale === "de"
                ? `⚠ ${unansweredFields.length} Frage${unansweredFields.length !== 1 ? "n" : ""} noch nicht beantwortet`
                : locale === "ar"
                ? `⚠ ${unansweredFields.length} سؤال لم تتم الإجابة عنه بعد`
                : locale === "tr"
                ? `⚠ ${unansweredFields.length} soru henüz yanıtlanmadı`
                : `⚠ ${unansweredFields.length} question${unansweredFields.length !== 1 ? "s" : ""} not answered yet`}
            </p>
            <div className="space-y-2">
              {unansweredFields.map((f) => {
                const qText = resolveQuestionText(f.question, f.original_label, f.key, locale);
                const globalIdx = questionFields.findIndex(q => q.key === f.key) + 1;
                return (
                  <div key={f.key} className="flex items-center justify-between gap-3 bg-white rounded-lg px-3 py-2 border border-amber-200">
                    <div className="flex-1 min-w-0">
                      <span className="text-xs text-amber-600 font-mono mr-2">{globalIdx}.</span>
                      <span className="text-sm text-gray-800">{qText}</span>
                      {f.original_label !== qText && (
                        <span className="block text-xs text-gray-400 mt-0.5 ml-5">{f.original_label}</span>
                      )}
                    </div>
                    <button
                      onClick={() => router.push(`/${locale}/questions?focus=${f.key}`)}
                      className="flex-shrink-0 px-3 py-1.5 bg-amber-600 text-white text-xs rounded-lg font-medium hover:bg-amber-700 transition-colors"
                    >
                      {locale === "de" ? "Antworten" : locale === "ar" ? "أجب" : locale === "tr" ? "Yanıtla" : "Answer"}
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        <OutputGuarantee supportLevel={supportLevel} locale={locale} />

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

      {showNewDocModal && (
        <ConfirmModal
          title={t("modal_title", locale)}
          message={t("modal_msg", locale)}
          onDismiss={() => setShowNewDocModal(false)}
          actions={[
            {
              label: t("save_first", locale),
              variant: "primary",
              onClick: () => { handleSave(); handleStartNew(); },
            },
            {
              label: t("start_new_btn", locale),
              variant: "danger",
              onClick: handleStartNew,
            },
            {
              label: t("cancel", locale),
              variant: "secondary",
              onClick: () => setShowNewDocModal(false),
            },
          ]}
        />
      )}
    </>
  );
}
