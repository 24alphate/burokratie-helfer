"use client";

import React from "react";

/**
 * PrivacyNote — Phase E/E5
 *
 * Honest, plain-language statement of what we store and where. The exact
 * copy was written to:
 *   - tell the truth about server-side: PDF is processed, not stored
 *   - tell the truth about client-side: answers are saved in this browser
 *   - mention the user can delete them at any time (E4 button)
 *
 * Do NOT change the wording without re-checking the privacy claims:
 *   - "We do not store your PDF on our server"         → stateless pipeline (token-only)
 *   - "document and answers are saved in this browser" → pdfToken + answers in localStorage
 *   - "expire automatically after 4 hours"             → token TTL + rehydrate cleanup (caseStore)
 *   - "you can delete them anytime"                    → DeleteSavedData component
 */

const T: Record<string, string> = {
  en: "Your PDF is processed to create the form questions. We do not store your PDF on our server. Your document and answers are saved in this browser so you can continue — they expire automatically after 4 hours and you can delete them anytime.",
  de: "Ihre PDF wird verarbeitet, um die Formularfragen zu erstellen. Wir speichern Ihre PDF nicht auf unserem Server. Ihr Dokument und Ihre Antworten werden in diesem Browser gespeichert, damit Sie fortfahren können — sie laufen nach 4 Stunden automatisch ab und Sie können sie jederzeit löschen.",
  fr: "Votre PDF est traité pour créer les questions du formulaire. Nous ne stockons pas votre PDF sur notre serveur. Votre document et vos réponses sont enregistrés dans ce navigateur pour que vous puissiez continuer — ils expirent automatiquement après 4 heures et vous pouvez les supprimer à tout moment.",
  ar: "تتم معالجة ملف PDF الخاص بك لإنشاء أسئلة النموذج. نحن لا نخزن ملف PDF الخاص بك على خادمنا. يُحفظ مستندك وإجاباتك في هذا المتصفح حتى تتمكن من المتابعة — وتنتهي صلاحيتها تلقائيًا بعد 4 ساعات ويمكنك حذفها في أي وقت.",
  tr: "PDF'iniz form sorularını oluşturmak için işlenir. PDF'inizi sunucumuzda saklamıyoruz. Belgeniz ve yanıtlarınız devam edebilmeniz için bu tarayıcıda kaydedilir — 4 saat sonra otomatik olarak sona erer ve istediğiniz zaman silebilirsiniz.",
  sq: "PDF-ja juaj përpunohet për të krijuar pyetjet e formularit. Nuk ruajmë PDF-në tuaj në serverin tonë. Dokumenti dhe përgjigjet tuaja ruhen në këtë shfletues që të mund të vazhdoni — ato skadojnë automatikisht pas 4 orësh dhe mund t'i fshini në çdo kohë.",
  es: "Su PDF se procesa para crear las preguntas del formulario. No almacenamos su PDF en nuestro servidor. Su documento y sus respuestas se guardan en este navegador para que pueda continuar — caducan automáticamente después de 4 horas y puede eliminarlos en cualquier momento.",
  fa: "PDF شما برای ایجاد سؤالات فرم پردازش می‌شود. ما PDF شما را روی سرور خود ذخیره نمی‌کنیم. سند و پاسخ‌های شما در این مرورگر ذخیره می‌شوند تا بتوانید ادامه دهید — پس از ۴ ساعت به‌طور خودکار منقضی می‌شوند و می‌توانید هر زمان آنها را حذف کنید.",
  ru: "Ваш PDF обрабатывается для создания вопросов формы. Мы не храним ваш PDF на нашем сервере. Ваш документ и ответы сохраняются в этом браузере, чтобы вы могли продолжить — они автоматически истекают через 4 часа, и вы можете удалить их в любое время.",
  uk: "Ваш PDF обробляється для створення питань форми. Ми не зберігаємо ваш PDF на нашому сервері. Ваш документ і відповіді зберігаються в цьому браузері, щоб ви могли продовжити — вони автоматично закінчуються через 4 години, і ви можете видалити їх у будь-який час.",
};

interface Props {
  locale: string;
  className?: string;
}

export function PrivacyNote({ locale, className }: Props) {
  const text = T[locale] ?? T.en;
  return (
    <p
      data-testid="privacy-note"
      className={className ?? "text-xs text-gray-500 leading-relaxed"}
    >
      {text}
    </p>
  );
}
