"use client";

import { useState } from "react";

interface DateInputProps {
  onSubmit: (value: string) => Promise<void>;
  isLoading: boolean;
  submitLabel: string;
  initialValue?: string;
}

export function DateInput({ onSubmit, isLoading, submitLabel, initialValue = "" }: DateInputProps) {
  const [value, setValue] = useState(initialValue);

  function handleChange(raw: string) {
    // Accept HTML date input (YYYY-MM-DD) and convert to DD.MM.YYYY for backend
    setValue(raw);
  }

  function getFormattedValue(): string {
    if (!value) return "";
    // HTML date inputs return YYYY-MM-DD
    const parts = value.split("-");
    if (parts.length === 3) {
      return `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
    return value;
  }

  return (
    <div className="flex flex-col gap-3">
      <input
        type="date"
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        className="w-full border border-gray-300 rounded-xl p-3 text-gray-900 text-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        disabled={isLoading}
        autoFocus
      />
      <button
        onClick={() => value && onSubmit(getFormattedValue())}
        disabled={!value || isLoading}
        className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {isLoading ? "..." : submitLabel}
      </button>
    </div>
  );
}
