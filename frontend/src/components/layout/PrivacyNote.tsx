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
 *   - "We do not store your PDF on our server"  → stateless pipeline (token-only)
 *   - "Your answers are saved in this browser"  → Zustand persist → localStorage
 *   - "you can delete them anytime"             → DeleteSavedData component
 */

const T: Record<string, string> = {
  en: "Your PDF is processed to create the form questions. We do not store your PDF on our server. Your answers are saved in this browser so you can continue, and you can delete them anytime.",
  de: "Ihre PDF wird verarbeitet, um die Formularfragen zu erstellen. Wir speichern Ihre PDF nicht auf unserem Server. Ihre Antworten werden in diesem Browser gespeichert, damit Sie fortfahren können, und Sie können sie jederzeit löschen.",
  fr: "Votre PDF est traité pour créer les questions du formulaire. Nous ne stockons pas votre PDF sur notre serveur. Vos réponses sont enregistrées dans ce navigateur pour que vous puissiez continuer, et vous pouvez les supprimer à tout moment.",
  ar: "تتم معالجة ملف PDF الخاص بك لإنشاء أسئلة النموذج. نحن لا نخزن ملف PDF الخاص بك على خادمنا. يتم حفظ إجاباتك في هذا المتصفح حتى تتمكن من المتابعة، ويمكنك حذفها في أي وقت.",
  tr: "PDF'iniz form sorularını oluşturmak için işlenir. PDF'inizi sunucumuzda saklamıyoruz. Yanıtlarınız bu tarayıcıda kaydedilir, böylece devam edebilirsiniz ve istediğiniz zaman silebilirsiniz.",
  sq: "PDF-ja juaj përpunohet për të krijuar pyetjet e formularit. Nuk ruajmë PDF-në tuaj në serverin tonë. Përgjigjet tuaja ruhen në këtë shfletues që të mund të vazhdoni dhe mund t'i fshini në çdo kohë.",
  es: "Su PDF se procesa para crear las preguntas del formulario. No almacenamos su PDF en nuestro servidor. Sus respuestas se guardan en este navegador para que pueda continuar, y puede eliminarlas en cualquier momento.",
  fa: "PDF شما برای ایجاد سؤالات فرم پردازش می‌شود. ما PDF شما را روی سرور خود ذخیره نمی‌کنیم. پاسخ‌های شما در این مرورگر ذخیره می‌شوند تا بتوانید ادامه دهید و می‌توانید هر زمان آنها را حذف کنید.",
  ru: "Ваш PDF обрабатывается для создания вопросов формы. Мы не храним ваш PDF на нашем сервере. Ваши ответы сохраняются в этом браузере, чтобы вы могли продолжить, и вы можете удалить их в любое время.",
  uk: "Ваш PDF обробляється для створення питань форми. Ми не зберігаємо ваш PDF на нашому сервері. Ваші відповіді зберігаються в цьому браузері, щоб ви могли продовжити, і ви можете видалити їх у будь-який час.",
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
