"use client";

import { QuestionRead, FieldOption, GuidanceText } from "@/types/api";
import { resolveQuestionText } from "@/lib/labelUtils";
import { t } from "@/lib/i18n";
import { TextInput } from "./TextInput";
import { DateInput } from "./DateInput";
import { SelectInput } from "./SelectInput";
import { YesNoInput } from "./YesNoInput";
import { RadioInput } from "./RadioInput";
import { GuidancePanel } from "./GuidancePanel";

interface QuestionCardProps {
  question: QuestionRead;
  locale: string;
  onSubmit: (answer: string) => Promise<void>;
  isLoading: boolean;
  validationErrors: string[];
  submitLabel: string;
  options?: FieldOption[];
  needsReview?: boolean;
  originalLabel?: string;
  fieldKey?: string;
  guidance?: GuidanceText | null;
  /** Used by resolveQuestionText to enforce strict Tier-A locale rules. */
  supportLevel?: number | null;
}

export function QuestionCard({
  question,
  locale,
  onSubmit,
  isLoading,
  validationErrors,
  submitLabel,
  options = [],
  needsReview = false,
  originalLabel = "",
  fieldKey = "",
  guidance,
  supportLevel = null,
}: QuestionCardProps) {
  const questionText = resolveQuestionText(
    question.question_text, originalLabel, fieldKey, locale,
    { isLevel1: supportLevel === 1 },
  );
  const explanationText =
    question.explanation_text?.[locale] ||
    question.explanation_text?.["en"] ||
    question.explanation_text?.["de"] ||
    "";

  const progressPct = question.total_count > 0
    ? Math.round((question.answered_count / question.total_count) * 100)
    : 0;

  // Determine how to render the input. Exactly one branch fires (inputKind),
  // so a field is never left without an input — including choice fields whose
  // options we couldn't extract (they fall back to free text instead of
  // rendering nothing, which was the old behavior for option-less radio/select).
  const hasOptions = options.length > 0;
  const itype = question.input_type;
  const hasLegacyOptions = (question.options?.length ?? 0) > 0;
  const choiceWithOptions =
    hasOptions &&
    (itype === "radio" || itype === "select" || itype === "checkbox" ||
     itype === "yes_no" || itype === "multiselect");

  type InputKind = "radio" | "select-legacy" | "yesno" | "date" | "text";
  const inputKind: InputKind = (() => {
    if (itype === "date") return "date";
    if (choiceWithOptions) return "radio";
    if (itype === "select" && hasLegacyOptions) return "select-legacy";
    if (itype === "checkbox" || itype === "yes_no") return "yesno";
    // text, number, signature, and option-less radio/select/multiselect
    return "text";
  })();

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs text-gray-400 font-medium">
          {question.answered_count} / {question.total_count}
        </span>
        <div className="flex-1 mx-3 h-1.5 bg-gray-200 rounded-full">
          <div
            className="h-1.5 bg-brand-600 rounded-full transition-all"
            style={{ width: `${progressPct}%` }}
          />
        </div>
        <span className="text-xs text-gray-400">{progressPct}%</span>
      </div>

      {needsReview && (
        <div className="mb-3 px-3 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-700 text-xs">
          {t("field.needs_review", locale)}
          {originalLabel && <span className="ml-1 font-mono">({originalLabel})</span>}
        </div>
      )}

      <h2 className="text-xl font-semibold text-gray-900 mb-2">{questionText}</h2>
      {explanationText && (
        <p className="text-sm text-gray-500 mb-2 leading-relaxed">{explanationText}</p>
      )}

      {guidance && <GuidancePanel guidance={guidance} locale={locale} />}

      {validationErrors.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          {validationErrors.map((err, i) => (
            <p key={i} className="text-red-600 text-sm">{err}</p>
          ))}
        </div>
      )}

      {/* Choice field with extracted options (radio / select / checkbox group) */}
      {inputKind === "radio" && (
        <RadioInput
          options={options}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
          multi={itype === "multiselect"}
        />
      )}

      {/* Legacy ALG II select carrying OptionRead[] */}
      {inputKind === "select-legacy" && question.options && (
        <SelectInput
          options={question.options}
          locale={locale}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
        />
      )}

      {/* Yes/No and single checkbox (no PDF options = checked or not) */}
      {inputKind === "yesno" && (
        <YesNoInput locale={locale} onSubmit={onSubmit} isLoading={isLoading} />
      )}

      {/* Date */}
      {inputKind === "date" && (
        <DateInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}

      {/* Text / number / signature — and option-less radio/select/multiselect,
          which fall back to free text so the field stays answerable. */}
      {inputKind === "text" && (
        <TextInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}
    </div>
  );
}
