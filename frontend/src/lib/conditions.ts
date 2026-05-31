// Client-side conditional-flow evaluator.
//
// Direct port of the backend FormEngine.evaluate_condition
// (backend/app/services/form_engine.py). The stateless pipeline ships every
// field at once with an optional `condition`; this decides whether a field is
// currently applicable given the user's answers so far.
//
// Invariants kept identical to the backend so a field never shows here but is
// rejected there (or vice-versa):
//   - condition == null  → always applicable (show)
//   - field_not_equals / field_not_in are only true when the referenced field
//     HAS been answered (a null answer does not satisfy a "not" condition).
//   - unknown condition type → safe default: applicable (show).

import type { FieldCondition } from "@/types/api";

export function evaluateCondition(
  condition: FieldCondition | null | undefined,
  answers: Record<string, string>,
): boolean {
  if (!condition) return true;

  switch (condition.type) {
    case "field_equals":
      return answers[condition.field_key] === condition.value;

    case "field_not_equals": {
      const current = answers[condition.field_key];
      return current !== undefined && current !== condition.value;
    }

    case "field_in":
      return condition.values.includes(answers[condition.field_key]);

    case "field_not_in": {
      const current = answers[condition.field_key];
      return current !== undefined && !condition.values.includes(current);
    }

    case "and":
      return condition.conditions.every((c) => evaluateCondition(c, answers));

    case "or":
      return condition.conditions.some((c) => evaluateCondition(c, answers));

    default:
      // Unknown type — match the backend's safe default.
      return true;
  }
}
