"use client";

import { Header } from "@/components/layout/Header";
import { LegalFooter } from "@/components/layout/LegalFooter";

/**
 * Impressum — required by German law (§ 5 DDG, the 2024 successor to § 5 TMG)
 * for any business-like online service offered in Germany. The legally
 * authoritative version is German; an English courtesy translation follows.
 *
 * ⚠️ BEFORE GOING LIVE: replace every «…» placeholder with the operator's real
 * legal identity. A public Impressum with missing/false data is an
 * Abmahnung risk. These are the only fields that must be completed.
 */
export default function ImpressumPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  return (
    <>
      <Header locale={locale} />
      <main className="max-w-2xl mx-auto px-4 py-8 text-gray-700">
        {/* Build-time reminder; harmless if it ships, but complete the data. */}
        <div className="mb-6 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs">
          Hinweis an den Betreiber: Bitte ersetzen Sie alle «…»-Platzhalter durch
          Ihre echten Angaben, bevor die Seite öffentlich erreichbar ist.
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">Impressum</h1>

        <section className="space-y-1 mb-6">
          <h2 className="font-semibold text-gray-900">Angaben gemäß § 5 DDG</h2>
          <p>«Vor- und Nachname / Firmenname»</p>
          <p>«Straße und Hausnummer»</p>
          <p>«PLZ und Ort»</p>
          <p>Deutschland</p>
        </section>

        <section className="space-y-1 mb-6">
          <h2 className="font-semibold text-gray-900">Kontakt</h2>
          <p>E-Mail: «kontakt@ihre-domain.de»</p>
          <p>Telefon: «optional»</p>
        </section>

        <section className="space-y-1 mb-6">
          <h2 className="font-semibold text-gray-900">Verantwortlich für den Inhalt</h2>
          <p>«Vor- und Nachname», Anschrift wie oben</p>
        </section>

        <section className="mb-8 text-sm leading-relaxed">
          <h2 className="font-semibold text-gray-900 mb-1">Haftungsausschluss</h2>
          <p>
            Bürokratie-Helfer ist eine Ausfüllhilfe für Formulare und stellt
            <strong> keine Rechtsberatung</strong> dar. Für die Richtigkeit und
            Vollständigkeit der von Ihnen eingegebenen Angaben sind ausschließlich
            Sie selbst verantwortlich. Prüfen Sie das erstellte Formular vor der
            Abgabe sorgfältig.
          </p>
        </section>

        {/* English courtesy translation */}
        <hr className="my-6 border-gray-100" />
        <h2 className="text-lg font-bold text-gray-900 mb-3">Legal notice (English)</h2>
        <p className="text-sm leading-relaxed mb-2">
          Information pursuant to § 5 DDG (German Digital Services Act). Operator:
          «full name / company», «street», «postal code and city», Germany.
          Contact: «contact@your-domain.de».
        </p>
        <p className="text-sm leading-relaxed">
          Bürokratie-Helfer is a form-completion aid and does <strong>not</strong>{" "}
          provide legal advice. You are solely responsible for the accuracy of the
          information you enter. Review the generated form carefully before
          submitting it.
        </p>

        <LegalFooter locale={locale} className="mt-10 flex items-center justify-center gap-4 text-xs text-gray-400" />
      </main>
    </>
  );
}
