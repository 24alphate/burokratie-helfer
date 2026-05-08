"use client";

import React from "react";
import { FieldDefinition } from "@/types/api";

/**
 * ReviewWarning — Phase D/D7
 *
 * For Level 2 (AcroForm) and Level 3 (flat) PDFs, some auto-generated
 * questions can be unclear. The product still lets the user proceed, but
 * we surface an honest, locale-aware "please double-check" warning naming
 * how many fields are flagged.
 *
 * Level 1 (verified) is exempt — Phase C asserts weak_questions = 0 there.
 *
 * Renders nothing when:
 *   - supportLevel is null or 1
 *   - weakCount == 0
 *
 * The component is presentational only. It reads `question_weak_reasons`
 * directly off the FieldDefinition list passed in by the parent.
 */

const T: Record<string, { title: string; body: string; one: string; many: string }> = {
  en: {
    title: "Please review these questions carefully",
    body:  "These questions came from the PDF's internal form structure. Some labels may be unclear or technical.",
    one:   "1 question needs your review",
    many:  "%n questions need your review",
  },
  de: {
    title: "Bitte prüfen Sie diese Fragen sorgfältig",
    body:  "Diese Fragen stammen aus der internen Formularstruktur der PDF. Manche Bezeichnungen können unklar oder technisch sein.",
    one:   "1 Frage benötigt Ihre Überprüfung",
    many:  "%n Fragen benötigen Ihre Überprüfung",
  },
  fr: {
    title: "Veuillez vérifier ces questions attentivement",
    body:  "Ces questions proviennent de la structure interne du formulaire PDF. Certaines étiquettes peuvent être peu claires ou techniques.",
    one:   "1 question nécessite votre vérification",
    many:  "%n questions nécessitent votre vérification",
  },
  ar: {
    title: "يرجى مراجعة هذه الأسئلة بعناية",
    body:  "جاءت هذه الأسئلة من بنية النموذج الداخلية للملف. قد تكون بعض التسميات غير واضحة أو تقنية.",
    one:   "سؤال واحد يحتاج إلى مراجعتك",
    many:  "%n أسئلة تحتاج إلى مراجعتك",
  },
  tr: {
    title: "Bu soruları lütfen dikkatlice inceleyin",
    body:  "Bu sorular PDF'in iç form yapısından geldi. Bazı etiketler belirsiz veya teknik olabilir.",
    one:   "1 soru incelemenizi gerektiriyor",
    many:  "%n soru incelemenizi gerektiriyor",
  },
  sq: {
    title: "Ju lutemi kontrolloni këto pyetje me kujdes",
    body:  "Këto pyetje vijnë nga struktura e brendshme e formularit të PDF-së. Disa etiketa mund të jenë të paqarta ose teknike.",
    one:   "1 pyetje kërkon rishikimin tuaj",
    many:  "%n pyetje kërkojnë rishikimin tuaj",
  },
  es: {
    title: "Por favor revise estas preguntas con cuidado",
    body:  "Estas preguntas provienen de la estructura interna del formulario PDF. Algunas etiquetas pueden ser poco claras o técnicas.",
    one:   "1 pregunta necesita su revisión",
    many:  "%n preguntas necesitan su revisión",
  },
  fa: {
    title: "لطفاً این سؤالات را با دقت بررسی کنید",
    body:  "این سؤالات از ساختار داخلی فرم PDF آمده‌اند. برخی برچسب‌ها ممکن است نامشخص یا فنی باشند.",
    one:   "1 سؤال نیاز به بررسی شما دارد",
    many:  "%n سؤال نیاز به بررسی شما دارد",
  },
  ru: {
    title: "Пожалуйста, внимательно проверьте эти вопросы",
    body:  "Эти вопросы взяты из внутренней структуры формы PDF. Некоторые подписи могут быть нечёткими или техническими.",
    one:   "1 вопрос требует вашей проверки",
    many:  "%n вопросов требуют вашей проверки",
  },
  uk: {
    title: "Будь ласка, уважно перевірте ці питання",
    body:  "Ці питання походять з внутрішньої структури форми PDF. Деякі підписи можуть бути нечіткими або технічними.",
    one:   "1 питання потребує вашої перевірки",
    many:  "%n питань потребують вашої перевірки",
  },
};

function _t(locale: string) {
  return T[locale] ?? T.en;
}

interface Props {
  supportLevel: number | null;
  fields: FieldDefinition[];
  locale: string;
}

export function ReviewWarning({ supportLevel, fields, locale }: Props) {
  // Level 1 is exempt — C2 asserts weak_questions = 0 there.
  if (supportLevel == null || supportLevel === 1) return null;

  const weakCount = (fields ?? []).reduce((n, f) => {
    const reasons = f.question_weak_reasons || [];
    return reasons.length > 0 ? n + 1 : n;
  }, 0);
  if (weakCount === 0) return null;

  const t = _t(locale);
  const phrase = (weakCount === 1 ? t.one : t.many).replace("%n", String(weakCount));

  return (
    <div
      role="status"
      data-testid="review-warning"
      className="mb-4 px-4 py-3 bg-amber-50 border border-amber-300 rounded-xl flex items-start gap-3"
    >
      <span className="text-xl leading-none mt-0.5" aria-hidden>⚠</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-amber-900">{t.title}</p>
        <p className="text-xs text-amber-800 mt-0.5">{t.body}</p>
        <p className="text-xs font-medium text-amber-900 mt-1">{phrase}</p>
      </div>
    </div>
  );
}
