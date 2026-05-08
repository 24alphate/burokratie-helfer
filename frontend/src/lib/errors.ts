/**
 * User-facing error messages — Phase A C4.
 *
 * Replaces leaking technical messages (NEXT_PUBLIC_API_URL, "backend deployment",
 * 404, 500, stack traces) with plain language users can act on.
 *
 * Error CODES are stable across releases. Pages map codes → localized strings.
 *
 * Anyone catching an exception in the UI MUST call `friendlyError(err, locale)`
 * before passing the message to setError(). Never render `e.message` directly.
 */

import { ApiError } from "@/types/api";

export type ErrorCode =
  | "network"          // cannot reach the service
  | "session_expired"  // token expired (401/403)
  | "file_too_large"   // 413
  | "no_fields"        // 422 — no fields detectable
  | "scanned_pdf"      // OCR not supported (special case of no_fields when scan detected)
  | "fill_failed"      // 500 during fill
  | "service_error"    // generic 5xx
  | "unknown";         // anything else

const MESSAGES: Record<string, Record<ErrorCode, string>> = {
  en: {
    network:         "We cannot connect to the service right now. Please check your internet connection and try again in a few minutes.",
    session_expired: "Your session has expired. Please re-upload your document to continue.",
    file_too_large:  "This file is too large. Please upload a PDF smaller than 10 MB.",
    no_fields:       "We couldn't find any questions in this PDF. Please make sure you uploaded the correct form.",
    scanned_pdf:     "This looks like a scanned document or photo. Scanning is not fully supported yet — please upload a digital PDF if you can.",
    fill_failed:     "Something went wrong while preparing your form. Please try again, or upload a different copy of the PDF.",
    service_error:   "Something went wrong on our end. Please try again in a few minutes.",
    unknown:         "Something went wrong. Please try again.",
  },
  de: {
    network:         "Wir können den Dienst gerade nicht erreichen. Bitte prüfen Sie Ihre Internetverbindung und versuchen Sie es in einigen Minuten erneut.",
    session_expired: "Ihre Sitzung ist abgelaufen. Bitte laden Sie Ihr Dokument erneut hoch.",
    file_too_large:  "Diese Datei ist zu groß. Bitte laden Sie eine PDF unter 10 MB hoch.",
    no_fields:       "Wir konnten keine Fragen in dieser PDF finden. Bitte prüfen Sie, ob Sie das richtige Formular hochgeladen haben.",
    scanned_pdf:     "Das sieht wie ein gescanntes Dokument aus. Scannen wird noch nicht vollständig unterstützt — bitte laden Sie wenn möglich eine digitale PDF hoch.",
    fill_failed:     "Beim Erstellen Ihrer Datei ist etwas schiefgelaufen. Bitte versuchen Sie es erneut oder laden Sie eine andere Kopie der PDF hoch.",
    service_error:   "Auf unserer Seite ist etwas schiefgelaufen. Bitte versuchen Sie es in einigen Minuten erneut.",
    unknown:         "Etwas ist schiefgelaufen. Bitte versuchen Sie es erneut.",
  },
  fr: {
    network:         "Nous ne pouvons pas joindre le service pour le moment. Vérifiez votre connexion et réessayez dans quelques minutes.",
    session_expired: "Votre session a expiré. Veuillez recharger votre document.",
    file_too_large:  "Ce fichier est trop volumineux. Téléversez un PDF de moins de 10 Mo.",
    no_fields:       "Nous n'avons trouvé aucune question dans ce PDF. Vérifiez que vous avez téléversé le bon formulaire.",
    scanned_pdf:     "Cela ressemble à un document scanné. Le scan n'est pas encore entièrement pris en charge — téléversez un PDF numérique si possible.",
    fill_failed:     "Une erreur s'est produite lors de la préparation de votre formulaire. Réessayez ou téléversez une autre copie du PDF.",
    service_error:   "Une erreur de notre côté. Veuillez réessayer dans quelques minutes.",
    unknown:         "Une erreur s'est produite. Veuillez réessayer.",
  },
  ar: {
    network:         "لا يمكننا الاتصال بالخدمة الآن. يرجى التحقق من اتصالك بالإنترنت والمحاولة مرة أخرى بعد بضع دقائق.",
    session_expired: "انتهت جلستك. يرجى إعادة تحميل المستند.",
    file_too_large:  "هذا الملف كبير جدًا. يرجى تحميل ملف PDF أصغر من 10 ميغابايت.",
    no_fields:       "لم نتمكن من العثور على أي أسئلة في هذا الملف. يرجى التأكد من تحميل النموذج الصحيح.",
    scanned_pdf:     "يبدو هذا كمستند ممسوح ضوئيًا. المسح غير مدعوم بالكامل بعد — يرجى تحميل ملف PDF رقمي إن أمكن.",
    fill_failed:     "حدث خطأ أثناء إعداد النموذج. يرجى المحاولة مرة أخرى أو تحميل نسخة أخرى من PDF.",
    service_error:   "حدث خطأ من جانبنا. يرجى المحاولة مرة أخرى بعد بضع دقائق.",
    unknown:         "حدث خطأ. يرجى المحاولة مرة أخرى.",
  },
  tr: {
    network:         "Şu anda hizmete bağlanamıyoruz. Lütfen internet bağlantınızı kontrol edin ve birkaç dakika sonra tekrar deneyin.",
    session_expired: "Oturumunuzun süresi doldu. Lütfen belgenizi yeniden yükleyin.",
    file_too_large:  "Bu dosya çok büyük. Lütfen 10 MB'dan küçük bir PDF yükleyin.",
    no_fields:       "Bu PDF'de soru bulamadık. Lütfen doğru formu yüklediğinizden emin olun.",
    scanned_pdf:     "Bu taranmış bir belge gibi görünüyor. Tarama henüz tam desteklenmiyor — mümkünse dijital bir PDF yükleyin.",
    fill_failed:     "Formunuz hazırlanırken bir hata oluştu. Lütfen tekrar deneyin veya PDF'in başka bir kopyasını yükleyin.",
    service_error:   "Bizim tarafımızda bir hata oluştu. Lütfen birkaç dakika sonra tekrar deneyin.",
    unknown:         "Bir hata oluştu. Lütfen tekrar deneyin.",
  },
  sq: {
    network:         "Nuk mund të lidhemi me shërbimin tani. Kontrolloni lidhjen tuaj dhe provoni përsëri pas disa minutash.",
    session_expired: "Sesioni juaj ka skaduar. Ju lutemi ringarkoni dokumentin tuaj.",
    file_too_large:  "Ky skedar është shumë i madh. Ngarkoni një PDF më të vogël se 10 MB.",
    no_fields:       "Nuk gjetëm asnjë pyetje në këtë PDF. Sigurohuni që keni ngarkuar formularin e duhur.",
    scanned_pdf:     "Kjo duket si një dokument i skanuar. Skanimi nuk mbështetet ende plotësisht — ngarkoni një PDF dixhital nëse mundeni.",
    fill_failed:     "Diçka shkoi keq gjatë përgatitjes së formularit. Provoni përsëri ose ngarkoni një kopje tjetër të PDF.",
    service_error:   "Diçka shkoi keq nga ana jonë. Provoni përsëri pas disa minutash.",
    unknown:         "Diçka shkoi keq. Provoni përsëri.",
  },
  es: {
    network:         "No podemos conectar con el servicio ahora. Compruebe su conexión a internet y vuelva a intentarlo en unos minutos.",
    session_expired: "Su sesión ha caducado. Vuelva a subir su documento.",
    file_too_large:  "Este archivo es demasiado grande. Suba un PDF de menos de 10 MB.",
    no_fields:       "No encontramos preguntas en este PDF. Verifique que subió el formulario correcto.",
    scanned_pdf:     "Esto parece un documento escaneado. El escaneo aún no es totalmente compatible — suba un PDF digital si puede.",
    fill_failed:     "Algo salió mal al preparar su formulario. Intente de nuevo o suba otra copia del PDF.",
    service_error:   "Algo salió mal de nuestro lado. Intente de nuevo en unos minutos.",
    unknown:         "Algo salió mal. Intente de nuevo.",
  },
  fa: {
    network:         "در حال حاضر نمی‌توانیم به سرویس متصل شویم. لطفاً اتصال اینترنت خود را بررسی کنید.",
    session_expired: "جلسه شما منقضی شده است. لطفاً سند خود را دوباره آپلود کنید.",
    file_too_large:  "این فایل بیش از حد بزرگ است. لطفاً یک PDF کمتر از 10 مگابایت آپلود کنید.",
    no_fields:       "در این PDF هیچ سؤالی پیدا نکردیم. لطفاً مطمئن شوید فرم درست را آپلود کرده‌اید.",
    scanned_pdf:     "این مانند یک سند اسکن شده به نظر می‌رسد. اسکن هنوز به طور کامل پشتیبانی نمی‌شود.",
    fill_failed:     "هنگام آماده‌سازی فرم خطایی رخ داد. لطفاً دوباره امتحان کنید.",
    service_error:   "خطایی از سمت ما رخ داد. لطفاً چند دقیقه دیگر دوباره امتحان کنید.",
    unknown:         "خطایی رخ داد. لطفاً دوباره امتحان کنید.",
  },
  ru: {
    network:         "Сейчас не удаётся подключиться к сервису. Проверьте интернет-соединение и попробуйте через несколько минут.",
    session_expired: "Ваша сессия истекла. Пожалуйста, загрузите документ заново.",
    file_too_large:  "Файл слишком большой. Загрузите PDF меньше 10 МБ.",
    no_fields:       "В этом PDF не найдено вопросов. Убедитесь, что вы загрузили правильную форму.",
    scanned_pdf:     "Похоже на отсканированный документ. Сканирование пока не полностью поддерживается — загрузите цифровой PDF.",
    fill_failed:     "Произошла ошибка при подготовке формы. Попробуйте ещё раз или загрузите другую копию PDF.",
    service_error:   "Что-то пошло не так на нашей стороне. Попробуйте через несколько минут.",
    unknown:         "Что-то пошло не так. Попробуйте ещё раз.",
  },
  uk: {
    network:         "Зараз не вдається підключитися до сервісу. Перевірте з'єднання та спробуйте через кілька хвилин.",
    session_expired: "Ваш сеанс закінчився. Будь ласка, завантажте документ знову.",
    file_too_large:  "Файл занадто великий. Завантажте PDF менше 10 МБ.",
    no_fields:       "У цьому PDF не знайдено питань. Переконайтеся, що ви завантажили правильну форму.",
    scanned_pdf:     "Це виглядає як сканований документ. Сканування поки не повністю підтримується — завантажте цифровий PDF.",
    fill_failed:     "Сталася помилка при підготовці форми. Спробуйте ще раз або завантажте іншу копію PDF.",
    service_error:   "Щось пішло не так на нашій стороні. Спробуйте через кілька хвилин.",
    unknown:         "Щось пішло не так. Спробуйте ще раз.",
  },
};

function pickLocale(locale: string): string {
  return locale in MESSAGES ? locale : "en";
}

/**
 * Translate an error code to a user-facing string in the given locale.
 * Falls back to English when the locale isn't covered.
 */
export function errorMessage(code: ErrorCode, locale: string): string {
  return MESSAGES[pickLocale(locale)][code] ?? MESSAGES.en[code];
}

/**
 * Map an unknown thrown value (Error, ApiError, string) to an ErrorCode.
 * Inspects ApiError.status when present, otherwise scans the message text.
 */
export function classify(err: unknown): ErrorCode {
  if (err instanceof ApiError) {
    const s = err.status;
    if (s === 0)   return "network";
    if (s === 401 || s === 403) return "session_expired";
    if (s === 413) return "file_too_large";
    if (s === 422) {
      const msg = (err.message || "").toLowerCase();
      if (msg.includes("scan") || msg.includes("ocr")) return "scanned_pdf";
      return "no_fields";
    }
    if (s === 500) return "fill_failed";
    if (s >= 500)  return "service_error";
    return "unknown";
  }
  // Treat raw network failures (TypeError "Failed to fetch") as connectivity issues.
  if (err instanceof TypeError && /fail|network/i.test(err.message)) return "network";
  return "unknown";
}

/**
 * One-shot helper: convert any caught error into a user-facing localized string.
 * Use this in every catch block:
 *
 *   catch (e) { setError(friendlyError(e, locale)); }
 */
export function friendlyError(err: unknown, locale: string): string {
  return errorMessage(classify(err), locale);
}
