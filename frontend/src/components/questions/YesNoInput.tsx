"use client";

const YES_LABELS: Record<string, string> = {
  en: "Yes", ar: "نعم", tr: "Evet", de: "Ja", fa: "بله", ru: "Да", uk: "Так",
};
const NO_LABELS: Record<string, string> = {
  en: "No", ar: "لا", tr: "Hayır", de: "Nein", fa: "خیر", ru: "Нет", uk: "Ні",
};

interface YesNoInputProps {
  locale: string;
  onSubmit: (value: "yes" | "no") => Promise<void>;
  isLoading: boolean;
}

export function YesNoInput({ locale, onSubmit, isLoading }: YesNoInputProps) {
  const yesLabel = YES_LABELS[locale] ?? "Yes";
  const noLabel = NO_LABELS[locale] ?? "No";

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
