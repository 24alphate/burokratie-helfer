"use client";

import { Header } from "@/components/layout/Header";
import { LegalFooter } from "@/components/layout/LegalFooter";

/**
 * Datenschutzerklärung — DSGVO/GDPR privacy policy. The content reflects the
 * app's ACTUAL data posture (verify before changing wording):
 *   - the uploaded PDF is processed in memory to build the questions and is
 *     NOT persisted on the server (stateless token-only pipeline, 4 h expiry);
 *   - answers live only in the visitor's browser (localStorage) and can be
 *     wiped anytime via "Delete my saved data";
 *   - no accounts, no advertising, no analytics/tracking cookies;
 *   - server logs contain no personal form content (PII-free audit logs).
 *
 * ⚠️ BEFORE GOING LIVE: complete the «…» controller + hosting placeholders.
 */
export default function DatenschutzPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  return (
    <>
      <Header locale={locale} />
      <main className="max-w-2xl mx-auto px-4 py-8 text-gray-700 text-sm leading-relaxed">
        <div className="mb-6 p-3 bg-amber-50 border border-amber-200 rounded-xl text-amber-800 text-xs">
          Hinweis an den Betreiber: «…»-Platzhalter (Verantwortlicher, Hosting)
          vor Veröffentlichung ausfüllen.
        </div>

        <h1 className="text-2xl font-bold text-gray-900 mb-6">Datenschutzerklärung</h1>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">1. Verantwortlicher</h2>
          <p>
            «Vor- und Nachname / Firmenname», «Anschrift», «E-Mail». Bei Fragen
            zum Datenschutz erreichen Sie uns unter dieser Adresse.
          </p>
        </section>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">2. Welche Daten wir verarbeiten</h2>
          <p>
            <strong>Hochgeladenes PDF:</strong> Ihr Formular wird ausschließlich
            verarbeitet, um daraus die Fragen zu erzeugen und das ausgefüllte
            Dokument zu erstellen. Es wird <strong>nicht dauerhaft auf unserem
            Server gespeichert</strong>. Die Verarbeitung erfolgt zustandslos;
            ein technischer Token, der das Dokument für die Dauer Ihrer Sitzung
            vorhält, verfällt automatisch nach spätestens 4 Stunden.
          </p>
          <p>
            <strong>Ihre Antworten:</strong> werden nur lokal in Ihrem Browser
            (localStorage) gespeichert, damit Sie das Ausfüllen später fortsetzen
            können. Sie verlassen Ihr Gerät nur dann, wenn Sie das fertige PDF
            erzeugen. Über „Meine gespeicherten Daten löschen“ können Sie sie
            jederzeit selbst entfernen.
          </p>
          <p>
            <strong>Server-Protokolle:</strong> enthalten technische Angaben
            (z. B. Zeitpunkt, Formulartyp), aber <strong>keine</strong> der von
            Ihnen eingegebenen persönlichen Inhalte.
          </p>
        </section>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">3. Keine Tracker, keine Werbung</h2>
          <p>
            Wir setzen keine Analyse- oder Werbe-Cookies ein und geben Ihre Daten
            nicht zu Werbezwecken weiter.
          </p>
        </section>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">4. Rechtsgrundlage</h2>
          <p>
            Die Verarbeitung erfolgt zur Durchführung der von Ihnen angeforderten
            Funktion (Art. 6 Abs. 1 lit. b DSGVO) sowie zu unserem berechtigten
            Interesse am sicheren Betrieb des Dienstes (Art. 6 Abs. 1 lit. f DSGVO).
          </p>
        </section>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">5. Hosting</h2>
          <p>
            Der Dienst wird bei «Hosting-Anbieter» in einem Rechenzentrum
            innerhalb der EU (Region «z. B. Frankfurt») betrieben.
          </p>
        </section>

        <section className="space-y-2 mb-6">
          <h2 className="font-semibold text-gray-900">6. Ihre Rechte</h2>
          <p>
            Sie haben das Recht auf Auskunft, Berichtigung, Löschung und
            Einschränkung der Verarbeitung (Art. 15–18 DSGVO) sowie ein
            Beschwerderecht bei einer Aufsichtsbehörde. Da wir Ihre Formulardaten
            nicht serverseitig speichern, betreffen diese Rechte vor allem die in
            Ihrem Browser abgelegten Daten, die Sie selbst löschen können.
          </p>
        </section>

        {/* English summary */}
        <hr className="my-6 border-gray-100" />
        <h2 className="text-lg font-bold text-gray-900 mb-2">Privacy policy (English summary)</h2>
        <p className="mb-2">
          Your uploaded PDF is processed only to generate the questions and the
          filled document; it is <strong>not stored on our server</strong>
          (stateless processing, session token expires within 4 hours). Your
          answers are kept only in your browser and can be deleted anytime via
          “Delete my saved data”. We use no analytics or advertising cookies and
          host the service in the EU («provider», region «Frankfurt»). You have
          the GDPR rights of access, rectification, erasure and restriction;
          contact the controller above. Controller: «full name», «address»,
          «email».
        </p>

        <LegalFooter locale={locale} className="mt-10 flex items-center justify-center gap-4 text-xs text-gray-400" />
      </main>
    </>
  );
}
