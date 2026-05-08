/**
 * cleanHumanLabel — make a raw PDF label readable for display.
 *
 * Used as the last-resort fallback when no translated question is available.
 * Never used as the primary question for Tier-A locales; the backend
 * guarantees question[locale] for those.
 */
export function cleanHumanLabel(label: string): string {
  if (!label) return label;

  let s = label.trim();

  // Replace "=" with " / " for compound labels: "Zielort=Startort" → "Zielort / Startort"
  s = s.replace(/\s*=\s*/g, " / ");

  // Strip leading number prefix: "13 - " or "13. "
  s = s.replace(/^\d+\s*[-–.]\s*/, "").trim();

  // Strip trailing number: " 13"
  s = s.replace(/\s+\d+$/, "").trim();

  return s || label;
}

const TIER_A = new Set(["en", "de", "fr", "ar", "tr", "sq"]);

/**
 * resolveQuestionText — pick the best available question text for a field.
 *
 * Priority for Tier-A locales (en/de/fr/ar/tr/sq):
 *   1. field.question[locale]
 *   2. field.question["en"]   (logged as a developer warning)
 *   3. cleanHumanLabel(originalLabel) — only when locale === document_language
 *      ("de"). For other Tier-A locales, this is a quality bug.
 *   4. cleanHumanLabel(key)   (last-resort, dev-only path)
 *
 * For Tier-B locales (es/fa/ru/uk/...): full permissive fallback chain.
 *
 * The function tags the global `__bh_locale_warnings__` array on `window`
 * with the field key + locale + chosen source, so dev tools / e2e tests
 * can assert that no Level-1 Tier-A flow ever falls back.
 */
export function resolveQuestionText(
  question: Record<string, string> | null | undefined,
  originalLabel: string,
  key: string,
  locale: string,
  options?: {
    /** Hint passed by the questions page when it knows the support level. */
    isLevel1?: boolean;
    /** ISO of the PDF's source language; defaults to "de". */
    documentLanguage?: string;
  },
): string {
  const documentLanguage = options?.documentLanguage ?? "de";

  if (question) {
    const direct = (question[locale] ?? "").trim();
    if (direct) return direct;
  }

  // From this point on, we know question[locale] was missing.
  // Record the gap so dev tools / tests can flag it.
  if (typeof window !== "undefined") {
    const w = window as unknown as { __bh_locale_warnings__?: Array<{ key: string; locale: string; source: string }> };
    if (!Array.isArray(w.__bh_locale_warnings__)) {
      w.__bh_locale_warnings__ = [];
    }
    w.__bh_locale_warnings__!.push({ key, locale, source: "fallback" });
    if (TIER_A.has(locale) && options?.isLevel1) {
      // Loud dev signal — backend invariant says this should never happen
      // for Tier-A on a Level 1 verified template.
      // eslint-disable-next-line no-console
      console.warn(
        `[locale] missing question[${locale}] on Level 1 field ${key} — backend bug`,
      );
    }
  }

  if (question) {
    const enFallback = (question["en"] ?? "").trim();
    if (enFallback && (!TIER_A.has(locale) || locale === "en")) {
      return enFallback;
    }
    if (TIER_A.has(locale) && enFallback) {
      // Tier-A non-English: showing the English fallback is the spec's
      // explicit anti-pattern. We still return SOMETHING (better than a
      // blank screen) but the warning above tells devs to fix the data.
      return enFallback;
    }
    if (locale === documentLanguage) {
      const docFallback = (question[documentLanguage] ?? "").trim();
      if (docFallback) return docFallback;
    }
    const first = Object.values(question).find((v) => (v ?? "").trim());
    if (first) return first;
  }

  // Last resort: ONLY use the original label as the main question when the
  // user's locale matches the document language. For other Tier-A locales
  // the backend should have provided a question — falling back to the raw
  // German label here would render German UX in a French/Arabic flow.
  if (originalLabel && (!TIER_A.has(locale) || locale === documentLanguage)) {
    return cleanHumanLabel(originalLabel);
  }
  return cleanHumanLabel(key);
}
