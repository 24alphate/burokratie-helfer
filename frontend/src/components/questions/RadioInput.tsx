"use client";

import { useState } from "react";
import { FieldOption } from "@/types/api";

interface RadioInputProps {
  options: FieldOption[];
  onSubmit: (value: string) => Promise<void>;
  isLoading: boolean;
  submitLabel: string;
  multi?: boolean;  // true = multi-select checkboxes, false = single radio
}

export function RadioInput({ options, onSubmit, isLoading, submitLabel, multi = false }: RadioInputProps) {
  const [selected, setSelected] = useState<string[]>([]);

  function toggle(value: string) {
    if (multi) {
      setSelected((prev) =>
        prev.includes(value) ? prev.filter((v) => v !== value) : [...prev, value]
      );
    } else {
      setSelected([value]);
    }
  }

  async function handleSubmit() {
    if (selected.length === 0) return;
    await onSubmit(selected.join(","));
  }

  return (
    <div className="flex flex-col gap-3">
      {options.map((opt) => {
        const active = selected.includes(opt.value);
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => toggle(opt.value)}
            className={`w-full text-left px-4 py-3 rounded-xl border-2 transition-colors font-medium ${
              active
                ? "border-brand-600 bg-brand-50 text-brand-700"
                : "border-gray-200 bg-white text-gray-700 hover:border-brand-300"
            }`}
          >
            <span className="mr-2">{active ? (multi ? "☑" : "●") : (multi ? "☐" : "○")}</span>
            {opt.label}
          </button>
        );
      })}
      <button
        onClick={handleSubmit}
        disabled={isLoading || selected.length === 0}
        className="mt-2 w-full py-3 bg-brand-600 text-white rounded-xl font-bold hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {isLoading ? "…" : submitLabel}
      </button>
    </div>
  );
}
