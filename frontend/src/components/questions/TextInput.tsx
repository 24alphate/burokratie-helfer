"use client";

import { useState } from "react";

interface TextInputProps {
  onSubmit: (value: string) => Promise<void>;
  isLoading: boolean;
  submitLabel: string;
  initialValue?: string;
}

export function TextInput({ onSubmit, isLoading, submitLabel, initialValue = "" }: TextInputProps) {
  const [value, setValue] = useState(initialValue);

  return (
    <div className="flex flex-col gap-3">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && value.trim() && onSubmit(value.trim())}
        className="w-full border border-gray-300 rounded-xl p-3 text-gray-900 text-lg focus:outline-none focus:ring-2 focus:ring-brand-500"
        disabled={isLoading}
        autoFocus
      />
      <button
        onClick={() => value.trim() && onSubmit(value.trim())}
        disabled={!value.trim() || isLoading}
        className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {isLoading ? "..." : submitLabel}
      </button>
    </div>
  );
}
