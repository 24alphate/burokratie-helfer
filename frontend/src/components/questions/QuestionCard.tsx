"use client";

import { QuestionRead } from "@/types/api";
import { FieldOption } from "@/types/api";
import { TextInput } from "./TextInput";
import { DateInput } from "./DateInput";
import { SelectInput } from "./SelectInput";
import { YesNoInput } from "./YesNoInput";
import { RadioInput } from "./RadioInput";

interface QuestionCardProps {
  question: QuestionRead;
  locale: string;
  onSubmit: (answer: string) => Promise<void>;
  isLoading: boolean;
  validationErrors: string[];
  submitLabel: string;
  options?: FieldOption[];      // radio/select/checkbox options from FieldDefinition
  needsReview?: boolean;        // low-confidence vision field
  originalLabel?: string;       // label as it appears in the document
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
  originalLabel,
}: QuestionCardProps) {
  const questionText   = question.question_text[locale] ?? question.question_text["en"] ?? "";
  const explanationText = question.explanation_text[locale] ?? question.explanation_text["en"] ?? "";

  const progressPct = question.total_count > 0
    ? Math.round((question.answered_count / question.total_count) * 100)
    : 0;

  // Determine how to render the input
  const hasOptions = options.length > 0;
  const itype = question.input_type;

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
          ⚠ Field detected from image — please verify the question matches your form.
          {originalLabel && <span className="ml-1 font-mono">({originalLabel})</span>}
        </div>
      )}

      <h2 className="text-xl font-semibold text-gray-900 mb-2">{questionText}</h2>
      {explanationText && (
        <p className="text-sm text-gray-500 mb-6 leading-relaxed">{explanationText}</p>
      )}

      {validationErrors.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          {validationErrors.map((err, i) => (
            <p key={i} className="text-red-600 text-sm">{err}</p>
          ))}
        </div>
      )}

      {/* Radio / single-select (most common for checkbox groups in forms) */}
      {hasOptions && (itype === "radio" || itype === "select" || itype === "checkbox" || itype === "yes_no") && (
        <RadioInput
          options={options}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
          multi={false}
        />
      )}

      {/* Multi-select checkboxes */}
      {hasOptions && itype === "multiselect" && (
        <RadioInput
          options={options}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
          multi={true}
        />
      )}

      {/* Yes/No when no explicit options (legacy) */}
      {!hasOptions && itype === "yes_no" && (
        <YesNoInput locale={locale} onSubmit={onSubmit} isLoading={isLoading} />
      )}

      {/* Text / number / address / signature */}
      {(!hasOptions && (itype === "text" || itype === "number" || itype === "signature" || itype === "multiselect")) && (
        <TextInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}

      {/* Date */}
      {itype === "date" && (
        <DateInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}

      {/* Select with OptionRead format (legacy ALG II template) */}
      {!hasOptions && itype === "select" && question.options && (
        <SelectInput
          options={question.options}
          locale={locale}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
        />
      )}
    </div>
  );
}
