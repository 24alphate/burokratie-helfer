"use client";

import { useEffect } from "react";

export interface ModalAction {
  label: string;
  onClick: () => void;
  variant?: "primary" | "danger" | "secondary";
}

interface ConfirmModalProps {
  title: string;
  message: string;
  actions: ModalAction[];
  onDismiss: () => void;
}

const VARIANT_CLASS: Record<string, string> = {
  primary:   "bg-brand-600 text-white hover:bg-brand-700",
  danger:    "bg-red-600 text-white hover:bg-red-700",
  secondary: "border-2 border-gray-300 text-gray-700 hover:bg-gray-50",
};

export function ConfirmModal({ title, message, actions, onDismiss }: ConfirmModalProps) {
  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onDismiss(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onDismiss]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4"
      onClick={(e) => { if (e.target === e.currentTarget) onDismiss(); }}
    >
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-xl p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-900">{title}</h2>
        <p className="text-sm text-gray-600 leading-relaxed">{message}</p>
        <div className="flex flex-col gap-2 pt-1">
          {actions.map((a) => (
            <button
              key={a.label}
              onClick={a.onClick}
              className={`w-full py-3 rounded-xl font-semibold text-sm transition-colors ${
                VARIANT_CLASS[a.variant ?? "secondary"]
              }`}
            >
              {a.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
