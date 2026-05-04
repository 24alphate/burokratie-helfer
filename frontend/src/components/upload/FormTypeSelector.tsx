"use client";

import { useEffect, useState } from "react";
import { FormTemplateSummary } from "@/types/api";
import { api } from "@/lib/api";

interface FormTypeSelectorProps {
  onSelect: (templateId: string) => void;
  prompt: string;
  confirmLabel: string;
}

export function FormTypeSelector({ onSelect, prompt, confirmLabel }: FormTypeSelectorProps) {
  const [templates, setTemplates] = useState<FormTemplateSummary[]>([]);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    api.templates.list().then(setTemplates).catch(console.error);
  }, []);

  return (
    <div className="mt-6">
      <p className="text-gray-700 font-medium mb-3">{prompt}</p>
      <select
        className="w-full border border-gray-300 rounded-lg p-3 text-gray-800 focus:outline-none focus:ring-2 focus:ring-brand-500"
        value={selected}
        onChange={(e) => setSelected(e.target.value)}
      >
        <option value="">— Select —</option>
        {templates.map((t) => (
          <option key={t.id} value={t.id}>
            {t.name} ({t.institution})
          </option>
        ))}
      </select>
      <button
        onClick={() => selected && onSelect(selected)}
        disabled={!selected}
        className="mt-3 w-full py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 disabled:opacity-50 transition-colors"
      >
        {confirmLabel}
      </button>
    </div>
  );
}
