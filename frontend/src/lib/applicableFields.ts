// Shared field-selection logic for the stateless question flow.
//
// Both the questions page and the review page must agree on (a) which fields
// are grounded, (b) which are shown as questions, and (c) which are currently
// *applicable* given the user's answers (conditional flow). Keeping this in one
// place is what prevents the two pages from drifting apart — and what stops a
// stale conditional answer (e.g. partner data after switching to "ledig") from
// being written to the PDF.

import type { FieldDefinition } from "@/types/api";
import { evaluateCondition } from "@/lib/conditions";

/**
 * Hard grounding gate: only fields whose key is in the authoritative
 * extracted_field_ids list survive. Empty extracted list → nothing is grounded.
 */
export function getGroundedFields(
  fields: FieldDefinition[],
  extractedFieldIds: string[],
): FieldDefinition[] {
  if (!extractedFieldIds || extractedFieldIds.length === 0) return [];
  const extracted = new Set(extractedFieldIds);
  return (fields ?? []).filter((f) => extracted.has(f.key));
}

/**
 * The questions the user should actually answer right now: grounded, shown
 * (confidence gate passed), not pre-filled, and whose conditional gate is
 * satisfied by the current answers. Recompute this whenever answers change so
 * the flow grows/shrinks live.
 */
export function getApplicableQuestionFields(
  fields: FieldDefinition[],
  extractedFieldIds: string[],
  answeredValues: Record<string, string>,
): FieldDefinition[] {
  const answers = answeredValues ?? {};
  return getGroundedFields(fields, extractedFieldIds).filter(
    (f) =>
      f.show_question !== false &&
      !f.is_prefilled &&
      evaluateCondition(f.condition, answers),
  );
}

/**
 * The answers safe to send to /fill-pdf: only those whose field is grounded AND
 * currently applicable. Drops answers to questions that a later answer made
 * irrelevant (the stale-answer guard), and any key not in the field map.
 */
export function getApplicableAnswers(
  fields: FieldDefinition[],
  extractedFieldIds: string[],
  answeredValues: Record<string, string>,
): Record<string, string> {
  const answers = answeredValues ?? {};
  const byKey = new Map(
    getGroundedFields(fields, extractedFieldIds).map((f) => [f.key, f]),
  );
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(answers)) {
    const field = byKey.get(key);
    if (field && evaluateCondition(field.condition, answers)) {
      out[key] = value;
    }
  }
  return out;
}
