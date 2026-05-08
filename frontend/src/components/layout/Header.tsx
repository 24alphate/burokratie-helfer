"use client";

import { useRouter } from "next/navigation";
import { useCaseStore } from "@/store/caseStore";
import { t } from "@/lib/i18n";

interface HeaderProps {
  /** Override the logo click. When omitted the logo saves progress and goes home. */
  onLogoClick?: () => void;
  /** Locale for the header tagline. Falls back to the persisted locale or "en". */
  locale?: string;
}

export function Header({ onLogoClick, locale }: HeaderProps = {}) {
  const router = useRouter();
  const { markSaved, locale: storeLocale } = useCaseStore();
  const effectiveLocale = locale || storeLocale || "en";

  function handleLogoClick() {
    if (onLogoClick) {
      onLogoClick();
    } else {
      markSaved();
      router.push("/");
    }
  }

  return (
    <header className="bg-white border-b border-gray-200 px-4 py-3">
      <div className="max-w-2xl mx-auto flex items-center justify-between">
        <button
          onClick={handleLogoClick}
          className="font-bold text-brand-700 text-lg hover:text-brand-900 transition-colors cursor-pointer"
        >
          Bürokratie-Helfer
        </button>
        <span className="text-xs text-gray-400">{t("header.tagline", effectiveLocale)}</span>
      </div>
    </header>
  );
}
