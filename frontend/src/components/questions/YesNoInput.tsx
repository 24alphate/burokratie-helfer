"use client";

import { t } from "@/lib/i18n";

interface YesNoInputProps {
  locale: string;
  onSubmit: (value: "yes" | "no") => Promise<void>;
  isLoading: boolean;
}

export function YesNoInput({ locale, onSubmit, isLoading }: YesNoInputProps) {
  const yesLabel = t("yn.yes", locale);
  const noLabel = t("yn.no", locale);

  return (
    <div className="flex gap-4">
      <button
        onClick={() => onSubmit("yes")}
        disabled={isLoading}
        className="flex-1 py-4 bg-green-600 text-white rounded-xl font-bold text-xl hover:bg-green-700 disabled:opacity-50 transition-colors"
      >
        {yesLabel}
      </button>
      <button
        onClick={() => onSubmit("no")}
        disabled={isLoading}
        className="flex-1 py-4 bg-gray-600 text-white rounded-xl font-bold text-xl hover:bg-gray-700 disabled:opacity-50 transition-colors"
      >
        {noLabel}
      </button>
    </div>
  );
}
