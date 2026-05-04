"use client";

import { useState } from "react";
import { OptionRead } from "@/types/api";

interface SelectInputProps {
  options: OptionRead[];
  locale: string;
  onSubmit: (value: string) => Promise<void>;
  isLoading: boolean;
  submitLabel: string;
}

export function SelectInput({ options, locale, onSubmit, isLoading, submitLabel }: SelectInputProps) {
  const [selected, setSelected] = useState<string>("");

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-2">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => setSelected(opt.value)}
            disabled={isLoading}
            className={`w-full text-left py-3 px-4 rounded-xl border-2 font-medium transition-all ${
              selected === opt.value
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-white text-gray-700 hover:border-brand-300"
            }`}
          >
            {opt.label[locale] ?? opt.label["en"]}
          </button>
        ))}
      </div>
      <button
        onClick={() => selected && onSubmit(selected)}
        disabled={!selected || isLoading}
        className="w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {isLoading ? "..." : submitLabel}
      </button>
    </div>
  );
}
