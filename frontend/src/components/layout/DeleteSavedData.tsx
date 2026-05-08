"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import { useCaseStore } from "@/store/caseStore";
import { ConfirmModal } from "@/components/layout/ConfirmModal";

/**
 * DeleteSavedData — Phase E/E4
 *
 * Visible button + confirmation modal that lets the user wipe every piece
 * of document/answer state from this browser. Backed by the store's
 * `reset()` action.
 *
 * Wipes:
 *   pdfToken, fields, answeredValues, answeredKeys, extractedFieldIds,
 *   documentId, currentFilename, currentFileSize, currentFileLastModified,
 *   uploadAttemptId, fieldsForUploadAttemptId, fieldsForCaseId,
 *   pdfUploadedAt, lastSavedAt, supportLevel, templateId,
 *   sessionToken, caseId, pdfId
 *
 * Keeps:
 *   locale (UI preference, not user data)
 *
 * After wipe, navigates to the home page so the user lands in a known-clean
 * state.
 */

const T: Record<string, {
  button: string;
  modalTitle: string;
  modalBody: string;
  confirm: string;
  cancel: string;
}> = {
  en: {
    button:     "Delete my saved data",
    modalTitle: "Delete all your saved data?",
    modalBody:  "This will permanently remove the uploaded PDF, your answers, and all session data from this browser. This cannot be undone.",
    confirm:    "Yes, delete everything",
    cancel:     "Cancel",
  },
  de: {
    button:     "Meine gespeicherten Daten löschen",
    modalTitle: "Alle gespeicherten Daten löschen?",
    modalBody:  "Damit werden die hochgeladene PDF, Ihre Antworten und alle Sitzungsdaten aus diesem Browser dauerhaft entfernt. Dies kann nicht rückgängig gemacht werden.",
    confirm:    "Ja, alles löschen",
    cancel:     "Abbrechen",
  },
  fr: {
    button:     "Supprimer mes données enregistrées",
    modalTitle: "Supprimer toutes vos données enregistrées ?",
    modalBody:  "Le PDF téléversé, vos réponses et toutes les données de session seront définitivement supprimés de ce navigateur. Cette action est irréversible.",
    confirm:    "Oui, tout supprimer",
    cancel:     "Annuler",
  },
  ar: {
    button:     "احذف بياناتي المحفوظة",
    modalTitle: "حذف جميع بياناتك المحفوظة؟",
    modalBody:  "سيؤدي هذا إلى إزالة ملف PDF الذي تم تحميله وإجاباتك وجميع بيانات الجلسة من هذا المتصفح بشكل دائم. لا يمكن التراجع عن هذا الإجراء.",
    confirm:    "نعم، احذف كل شيء",
    cancel:     "إلغاء",
  },
  tr: {
    button:     "Kayıtlı verilerimi sil",
    modalTitle: "Tüm kayıtlı verileriniz silinsin mi?",
    modalBody:  "Bu işlem yüklenen PDF'yi, cevaplarınızı ve tüm oturum verilerini bu tarayıcıdan kalıcı olarak kaldırır. Bu geri alınamaz.",
    confirm:    "Evet, hepsini sil",
    cancel:     "İptal",
  },
  sq: {
    button:     "Fshini të dhënat e mia të ruajtura",
    modalTitle: "Të fshihen të gjitha të dhënat tuaja të ruajtura?",
    modalBody:  "Kjo do të heqë përgjithmonë PDF-në e ngarkuar, përgjigjet tuaja dhe të gjitha të dhënat e seancës nga ky shfletues. Kjo nuk mund të zhbëhet.",
    confirm:    "Po, fshini gjithçka",
    cancel:     "Anuloni",
  },
  es: {
    button:     "Eliminar mis datos guardados",
    modalTitle: "¿Eliminar todos sus datos guardados?",
    modalBody:  "Esto eliminará permanentemente el PDF cargado, sus respuestas y todos los datos de sesión de este navegador. Esto no se puede deshacer.",
    confirm:    "Sí, eliminar todo",
    cancel:     "Cancelar",
  },
  fa: {
    button:     "داده‌های ذخیره‌شده‌ام را حذف کن",
    modalTitle: "همه داده‌های ذخیره‌شده شما حذف شوند؟",
    modalBody:  "این کار PDF بارگذاری‌شده، پاسخ‌ها و تمام داده‌های جلسه را برای همیشه از این مرورگر حذف می‌کند. این عمل قابل برگشت نیست.",
    confirm:    "بله، همه چیز حذف شود",
    cancel:     "لغو",
  },
  ru: {
    button:     "Удалить мои сохранённые данные",
    modalTitle: "Удалить все ваши сохранённые данные?",
    modalBody:  "Это безвозвратно удалит загруженный PDF, ваши ответы и все данные сеанса из этого браузера. Это действие нельзя отменить.",
    confirm:    "Да, удалить всё",
    cancel:     "Отмена",
  },
  uk: {
    button:     "Видалити мої збережені дані",
    modalTitle: "Видалити всі ваші збережені дані?",
    modalBody:  "Це остаточно видалить завантажений PDF, ваші відповіді та всі дані сесії з цього браузера. Цю дію не можна скасувати.",
    confirm:    "Так, видалити все",
    cancel:     "Скасувати",
  },
};

function _t(locale: string) {
  return T[locale] ?? T.en;
}

interface Props {
  locale: string;
  /** Optional className override on the trigger button. */
  className?: string;
  /** When true, button text is rendered smaller (use as a footer link). */
  compact?: boolean;
}

export function DeleteSavedData({ locale, className, compact = false }: Props) {
  const router = useRouter();
  const reset = useCaseStore((s) => s.reset);
  const [open, setOpen] = useState(false);
  const t = _t(locale);

  const baseClass = compact
    ? "text-xs text-gray-400 hover:text-red-600 underline transition-colors"
    : "px-4 py-2 text-sm font-medium text-red-700 border border-red-200 hover:bg-red-50 rounded-xl transition-colors";

  return (
    <>
      <button
        type="button"
        data-testid="delete-saved-data-button"
        onClick={() => setOpen(true)}
        className={className ?? baseClass}
      >
        {t.button}
      </button>
      {open && (
        <ConfirmModal
          title={t.modalTitle}
          message={t.modalBody}
          onDismiss={() => setOpen(false)}
          actions={[
            {
              label: t.confirm, variant: "danger",
              onClick: () => {
                setOpen(false);
                reset();
                // sessionStorage backup of zustand persist isn't used, but be
                // explicit: clear the persisted key so a hard refresh stays clean.
                try { localStorage.removeItem("bh-store"); } catch {}
                router.push("/");
              },
            },
            {
              label: t.cancel, variant: "secondary",
              onClick: () => setOpen(false),
            },
          ]}
        />
      )}
    </>
  );
}
