"use client";

import { QuestionRead } from "@/types/api";
import { TextInput } from "./TextInput";
import { DateInput } from "./DateInput";
import { SelectInput } from "./SelectInput";
import { YesNoInput } from "./YesNoInput";

interface QuestionCardProps {
  question: QuestionRead;
  locale: string;
  onSubmit: (answer: string) => Promise<void>;
  isLoading: boolean;
  validationErrors: string[];
  submitLabel: string;
}

export function QuestionCard({
  question,
  locale,
  onSubmit,
  isLoading,
  validationErrors,
  submitLabel,
}: QuestionCardProps) {
  const questionText = question.question_text[locale] ?? question.question_text["en"] ?? "";
  const explanationText = question.explanation_text[locale] ?? question.explanation_text["en"] ?? "";

  const progressPct = question.total_count > 0
    ? Math.round((question.answered_count / question.total_count) * 100)
    : 0;

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

      <h2 className="text-xl font-semibold text-gray-900 mb-2">{questionText}</h2>
      <p className="text-sm text-gray-500 mb-6 leading-relaxed">{explanationText}</p>

      {validationErrors.length > 0 && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg">
          {validationErrors.map((err, i) => (
            <p key={i} className="text-red-600 text-sm">{err}</p>
          ))}
        </div>
      )}

      {question.input_type === "text" && (
        <TextInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}
      {question.input_type === "date" && (
        <DateInput onSubmit={onSubmit} isLoading={isLoading} submitLabel={submitLabel} />
      )}
      {question.input_type === "select" && question.options && (
        <SelectInput
          options={question.options}
          locale={locale}
          onSubmit={onSubmit}
          isLoading={isLoading}
          submitLabel={submitLabel}
        />
      )}
      {question.input_type === "yes_no" && (
        <YesNoInput
          locale={locale}
          onSubmit={onSubmit}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
