"use client";

/**
 * Small footer bar showing build identity — lets you confirm on mobile
 * that you are looking at the correct version after a deploy or local restart.
 *
 * Visible on every page. Tapping it expands the full API URL.
 */

import { useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const BUILD_TIME = process.env.NEXT_PUBLIC_BUILD_TIME ?? "";
const VERSION = process.env.NEXT_PUBLIC_APP_VERSION ?? "0.1.0";

// Determine environment from the API URL
const ENV: "local" | "production" =
  !API || API.startsWith("http://") ? "local" : "production";

// Format timestamp as "HH:MM:SS" (local time) so it's short enough for mobile
function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour12: false });
  } catch {
    return iso.slice(11, 19);
  }
}

// Format date as "DD MMM" for context
function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
  } catch {
    return iso.slice(0, 10);
  }
}

export function BuildStamp() {
  const [expanded, setExpanded] = useState(false);

  const envColor =
    ENV === "local" ? "text-orange-500" : "text-green-600";

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 bg-gray-900/90 text-gray-300 text-[10px] font-mono px-3 py-1 flex items-center gap-2 cursor-pointer select-none"
      onClick={() => setExpanded((v) => !v)}
      title="Tap to expand"
    >
      {/* Always-visible summary */}
      <span className={`font-bold ${envColor}`}>{ENV}</span>
      <span className="text-gray-500">·</span>
      <span>v{VERSION}</span>
      <span className="text-gray-500">·</span>
      <span>
        built {formatDate(BUILD_TIME)} {formatTime(BUILD_TIME)}
      </span>

      {/* Expanded: show full API URL */}
      {expanded && (
        <>
          <span className="text-gray-500">·</span>
          <span className="text-blue-400 break-all">
            {API || "local (rewrite → :8000)"}
          </span>
        </>
      )}

      <span className="ml-auto text-gray-600">{expanded ? "▲" : "▼"}</span>
    </div>
  );
}
