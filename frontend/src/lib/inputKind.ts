import { InputType } from "@/types/api";

export type InputKind = "radio" | "select-legacy" | "yesno" | "date" | "text";

/**
 * Decide which single input control QuestionCard should render for a field.
 *
 * Exactly one kind is returned so a field is NEVER left without an input. The
 * key fix: a choice field (radio/select/multiselect) whose options we couldn't
 * extract falls back to free text instead of matching no branch and rendering
 * nothing. Checkbox/yes-no without options become a yes/no control; the legacy
 * ALG II template path (OptionRead[]) keeps its dedicated select.
 *
 * @param itype            the field's input_type
 * @param hasOptions       true when FieldOption[] was extracted for the field
 * @param hasLegacyOptions true when the legacy QuestionRead.options (OptionRead[]) is present
 */
export function pickInputKind(
  itype: InputType,
  hasOptions: boolean,
  hasLegacyOptions: boolean,
): InputKind {
  if (itype === "date") return "date";

  const choiceWithOptions =
    hasOptions &&
    (itype === "radio" || itype === "select" || itype === "checkbox" ||
     itype === "yes_no" || itype === "multiselect");
  if (choiceWithOptions) return "radio";

  if (itype === "select" && hasLegacyOptions) return "select-legacy";
  if (itype === "checkbox" || itype === "yes_no") return "yesno";

  // text, number, signature, and option-less radio/select/multiselect
  return "text";
}
