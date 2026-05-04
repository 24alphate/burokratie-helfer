"use client";

import { AnswerRead } from "@/types/api";

interface AnswerSummaryProps {
  answers: AnswerRead[];
  onEdit: (fieldKey: string, currentValue: string) => void;
  editLabel: string;
}

export function AnswerSummary({ answers, onEdit, editLabel }: AnswerSummaryProps) {
  return (
    <div className="flex flex-col gap-2">
      {answers.map((answer) => (
        <div
          key={answer.id}
          className="flex items-center justify-between bg-white border border-gray-100 rounded-xl px-4 py-3"
        >
          <div className="flex-1 min-w-0">
            <p className="text-xs text-gray-400 mb-0.5 font-medium uppercase tracking-wide">
              {answer.field_key.replace(/_/g, " ")}
            </p>
            <p className="text-gray-800 font-medium truncate">{answer.raw_answer}</p>
            {!answer.is_validated && answer.validation_errors.length > 0 && (
              <p className="text-red-500 text-xs mt-0.5">{answer.validation_errors[0]}</p>
            )}
          </div>
          <button
            onClick={() => onEdit(answer.field_key, answer.raw_answer)}
            className="ml-3 text-brand-600 text-sm font-medium hover:underline flex-shrink-0"
          >
            {editLabel}
          </button>
        </div>
      ))}
    </div>
  );
}
