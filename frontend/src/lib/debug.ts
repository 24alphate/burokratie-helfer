/**
 * Developer debug-mode toggle.
 *
 * The diagnostic UI (MODE 1 no-AI toggle, raw-extraction / AI-comparison
 * tables, grounding debug panel) is developer tooling and must not be shown
 * to end users. It is enabled by either:
 *
 *   - visiting any page with ?debug=1   (persists via localStorage)
 *   - setting NEXT_PUBLIC_DEBUG_PANELS=1 at build time
 *
 * Disable again with ?debug=0.
 *
 * Call only after mount (client-side) — pages already gate rendering on a
 * `mounted` flag, which also avoids SSR/hydration mismatches.
 */
export function isDebugMode(): boolean {
  if (process.env.NEXT_PUBLIC_DEBUG_PANELS === "1") return true;
  if (typeof window === "undefined") return false;
  try {
    const param = new URLSearchParams(window.location.search).get("debug");
    if (param === "1") window.localStorage.setItem("bh-debug", "1");
    if (param === "0") window.localStorage.removeItem("bh-debug");
    return window.localStorage.getItem("bh-debug") === "1";
  } catch {
    return false;
  }
}
