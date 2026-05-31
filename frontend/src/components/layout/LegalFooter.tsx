"use client";

import Link from "next/link";

/**
 * LegalFooter — German law (DDG/TMG §5, ex-Telemediengesetz) requires the
 * Impressum and the privacy policy (Datenschutzerklärung) to be reachable from
 * every page ("leicht erkennbar, unmittelbar erreichbar"). This footer provides
 * those two always-available links and should be rendered at the bottom of
 * every page surface (landing, upload, questions, review).
 */

const IMPRESSUM: Record<string, string> = {
  en: "Legal notice", de: "Impressum", fr: "Mentions légales",
  ar: "بيانات الناشر", tr: "Künye", sq: "Të dhënat ligjore",
  es: "Aviso legal", fa: "اطلاعات قانونی", ru: "Выходные данные", uk: "Реквізити",
};
const DATENSCHUTZ: Record<string, string> = {
  en: "Privacy", de: "Datenschutz", fr: "Confidentialité",
  ar: "الخصوصية", tr: "Gizlilik", sq: "Privatësia",
  es: "Privacidad", fa: "حریم خصوصی", ru: "Конфиденциальность", uk: "Конфіденційність",
};

export function LegalFooter({ locale, className }: { locale: string; className?: string }) {
  const impressum = IMPRESSUM[locale] ?? IMPRESSUM.en;
  const datenschutz = DATENSCHUTZ[locale] ?? DATENSCHUTZ.en;
  return (
    <footer
      data-testid="legal-footer"
      className={className ?? "mt-8 flex items-center justify-center gap-4 text-xs text-gray-400"}
    >
      <Link href={`/${locale}/impressum`} className="hover:text-gray-600 underline-offset-2 hover:underline">
        {impressum}
      </Link>
      <span aria-hidden>·</span>
      <Link href={`/${locale}/datenschutz`} className="hover:text-gray-600 underline-offset-2 hover:underline">
        {datenschutz}
      </Link>
    </footer>
  );
}
