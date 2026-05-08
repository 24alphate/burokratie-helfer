/**
 * cleanHumanLabel — make a raw PDF label readable for display.
 *
 * Used as the last-resort fallback when no translated question is available.
 * Never used as the primary question; AI translation always wins if present.
 *
 * Examples:
 *   "Startort 13"        → "Startort"
 *   "Zielort 15"         → "Zielort"
 *   "Zielort=Startort 16"→ "Zielort / Startort"
 *   "1 - Vorname"        → "Vorname"
 *   "txtfPersonVorname"  → "txtfPersonVorname"  (left as-is; backend should never send this)
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

/**
 * resolveQuestionText — pick the best available question text for a field.
 *
 * Priority:
 *   1. field.question[locale]        — AI or deterministic in selected language
 *   2. field.question["en"]          — English fallback
 *   3. field.question["de"]          — German fallback
 *   4. any available translation     — first value in question dict
 *   5. cleanHumanLabel(original_label) — cleaned label from PDF
 *   6. cleanHumanLabel(key)          — cleaned field ID (last resort)
 */
export function resolveQuestionText(
  question: Record<string, string> | null | undefined,
  originalLabel: string,
  key: string,
  locale: string,
): string {
  if (question) {
    if (question[locale]) return question[locale];
    if (question["en"])   return question["en"];
    if (question["de"])   return question["de"];
    const first = Object.values(question)[0];
    if (first) return first;
  }
  if (originalLabel) return cleanHumanLabel(originalLabel);
  return cleanHumanLabel(key);
}
