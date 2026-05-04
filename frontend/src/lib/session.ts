const SESSION_TOKEN_KEY = "bh_session_token";
const CASE_ID_KEY = "bh_case_id";
const LOCALE_KEY = "bh_locale";

export function getSessionToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(SESSION_TOKEN_KEY);
}

export function setSessionToken(token: string): void {
  localStorage.setItem(SESSION_TOKEN_KEY, token);
}

export function getCaseId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(CASE_ID_KEY);
}

export function setCaseId(id: string): void {
  localStorage.setItem(CASE_ID_KEY, id);
}

export function getLocale(): string {
  if (typeof window === "undefined") return "en";
  return localStorage.getItem(LOCALE_KEY) ?? "en";
}

export function setLocale(locale: string): void {
  localStorage.setItem(LOCALE_KEY, locale);
}

export function clearSession(): void {
  localStorage.removeItem(SESSION_TOKEN_KEY);
  localStorage.removeItem(CASE_ID_KEY);
}
