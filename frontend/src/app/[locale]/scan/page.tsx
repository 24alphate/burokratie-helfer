"use client";

/**
 * Document scanner page.
 *
 * Flow:
 *   loading → camera → [ adjusting corners ] → preview → (loop) → building → pipeline
 *
 * OpenCV.js is loaded lazily on mount. Everything runs in the browser; no backend
 * changes. The final PDF is passed to the existing /process-pdf endpoint.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";
import {
  loadOpenCV,
  detectDocumentQuad,
  warpDocument,
  enhanceDocument,
  checkQuality,
  defaultCorners,
  dataUrlToCanvas,
  canvasToDataUrl,
  buildScanPdf,
  orderCorners,
  type Point,
  type Quality,
  type RenderMode,
} from "@/lib/scanner";

// ── Types ──────────────────────────────────────────────────────────────────────

interface ScannedPage {
  id: string;
  dataUrl: string;         // processed (warped + enhanced)
  thumbUrl: string;        // small thumbnail
  naturalWidth: number;
  naturalHeight: number;
}

type Stage =
  | "loading_cv"
  | "camera"
  | "adjusting"
  | "preview"
  | "building"
  | "error_camera"
  | "error_cv";

const HANDLE_COLORS = ["#ef4444", "#3b82f6", "#22c55e", "#f59e0b"]; // TL TR BR BL
const HANDLE_LABELS = ["TL", "TR", "BR", "BL"];

// ── Localisation ───────────────────────────────────────────────────────────────

const L: Record<string, Record<string, string>> = {
  loading:      { en: "Loading scanner…",                  de: "Scanner wird geladen…",              ar: "جارٍ تحميل الماسح…",              tr: "Tarayıcı yükleniyor…" },
  aim:          { en: "Aim at the document. The green outline shows what will be captured.", de: "Auf das Dokument richten. Grüne Kontur zeigt den Erfassungsbereich.", ar: "وجّه الكاميرا نحو المستند. الخطوط الخضراء توضح المنطقة.", tr: "Belgeyi hedefleyin. Yeşil çerçeve taranacak alanı gösterir." },
  capture:      { en: "Capture",       de: "Aufnehmen",   ar: "التقاط",  tr: "Çek" },
  adjust_title: { en: "Adjust corners", de: "Ecken anpassen", ar: "ضبط الزوايا", tr: "Köşeleri ayarla" },
  adjust_hint:  { en: "Drag the coloured handles to fit the document edges exactly.", de: "Bunte Griffe auf die Dokumentkanten ziehen.", ar: "اسحب المقابض الملوّنة لتحديد حدود المستند.", tr: "Belge kenarlarına uyacak şekilde renkli tutamaçları sürükleyin." },
  retake:       { en: "Retake",        de: "Wiederholen", ar: "إعادة",  tr: "Yeniden çek" },
  confirm:      { en: "Confirm crop",  de: "Zuschnitt bestätigen", ar: "تأكيد القص", tr: "Kırpmayı onayla" },
  preview_title:{ en: "Page preview",  de: "Seitenvorschau", ar: "معاينة الصفحة", tr: "Sayfa önizlemesi" },
  mode_doc:     { en: "Document",      de: "Dokument",    ar: "مستند",  tr: "Belge" },
  mode_gray:    { en: "Grayscale",     de: "Graustufen",  ar: "رمادي",  tr: "Gri ton" },
  mode_color:   { en: "Color",         de: "Farbe",       ar: "ملوّن",   tr: "Renkli" },
  use_page:     { en: "Use this page", de: "Seite verwenden", ar: "استخدم هذه الصفحة", tr: "Bu sayfayı kullan" },
  add_next:     { en: "Scan next page",de: "Nächste Seite scannen", ar: "مسح الصفحة التالية", tr: "Sonraki sayfayı tara" },
  finish:       { en: "Finish scanning", de: "Scannen beenden", ar: "إنهاء المسح", tr: "Taramayı bitir" },
  building:     { en: "Building PDF…", de: "PDF wird erstellt…", ar: "جارٍ إنشاء PDF…", tr: "PDF oluşturuluyor…" },
  no_camera:    { en: "Camera access was blocked. You can still upload a PDF instead.", de: "Kamerazugriff verweigert. Sie können trotzdem ein PDF hochladen.", ar: "تم حظر الوصول إلى الكاميرا. يمكنك رفع ملف PDF بدلاً من ذلك.", tr: "Kamera erişimi engellendi. Bunun yerine PDF yükleyebilirsiniz." },
  no_cv:        { en: "Scanner engine failed to load. Please check your internet connection.", de: "Scanner-Engine konnte nicht geladen werden.", ar: "فشل تحميل محرك الماسح.", tr: "Tarayıcı motoru yüklenemedi." },
  no_fields:    { en: "This scanned document could not be read automatically. Please upload the official PDF if available.", de: "Dieses gescannte Dokument konnte nicht automatisch gelesen werden. Bitte laden Sie wenn möglich das offizielle PDF hoch.", ar: "لم نتمكن من قراءة هذا المستند تلقائياً. الرجاء رفع الملف الرسمي إن أمكن.", tr: "Bu taranan belge otomatik okunamadı. Lütfen mümkünse resmi PDF'yi yükleyin." },
  upload_instead:{ en: "Upload PDF instead", de: "Stattdessen PDF hochladen", ar: "رفع PDF بدلاً من ذلك", tr: "Bunun yerine PDF yükle" },
  delete:       { en: "×", de: "×", ar: "×", tr: "×" },
  page:         { en: "Page", de: "Seite", ar: "صفحة", tr: "Sayfa" },
};
function l(k: string, locale: string) { return L[k]?.[locale] ?? L[k]?.["en"] ?? k; }

// ── Quality badge ──────────────────────────────────────────────────────────────

function QualityBadge({ quality }: { quality: Quality }) {
  const bg =
    quality.status === "good"   ? "bg-green-500 text-white" :
    quality.status === "review" ? "bg-yellow-400 text-gray-900" :
                                  "bg-red-500 text-white";
  const icon = quality.status === "good" ? "✓" : quality.status === "review" ? "⚠" : "✗";
  return (
    <div className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-semibold ${bg}`}>
      <span>{icon}</span>
      <span>{quality.message}</span>
    </div>
  );
}

// ── Render mode toggle ─────────────────────────────────────────────────────────

function ModeToggle({
  mode, onChange, locale,
}: { mode: RenderMode; onChange: (m: RenderMode) => void; locale: string }) {
  const modes: RenderMode[] = ["document", "grayscale", "color"];
  const labels: Record<RenderMode, string> = {
    document: l("mode_doc", locale),
    grayscale: l("mode_gray", locale),
    color: l("mode_color", locale),
  };
  return (
    <div className="flex rounded-xl overflow-hidden border border-gray-200 text-sm">
      {modes.map(m => (
        <button
          key={m}
          onClick={() => onChange(m)}
          className={`flex-1 px-3 py-2 font-medium transition-colors ${
            mode === m ? "bg-brand-600 text-white" : "bg-white text-gray-600 hover:bg-gray-50"
          }`}
        >
          {labels[m]}
        </button>
      ))}
    </div>
  );
}

// ── Corner editor ──────────────────────────────────────────────────────────────

interface CornerEditorProps {
  dataUrl: string;
  imageWidth: number;
  imageHeight: number;
  corners: [Point, Point, Point, Point];
  onCornersChange: (corners: [Point, Point, Point, Point]) => void;
}

function CornerEditor({ dataUrl, imageWidth, imageHeight, corners, onCornersChange }: CornerEditorProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const draggingRef = useRef<number | null>(null);

  function screenToSVG(clientX: number, clientY: number): Point {
    if (!svgRef.current) return { x: 0, y: 0 };
    const pt = svgRef.current.createSVGPoint();
    pt.x = clientX; pt.y = clientY;
    const ctm = svgRef.current.getScreenCTM();
    if (!ctm) return { x: 0, y: 0 };
    const svgPt = pt.matrixTransform(ctm.inverse());
    return {
      x: Math.max(0, Math.min(imageWidth,  svgPt.x)),
      y: Math.max(0, Math.min(imageHeight, svgPt.y)),
    };
  }

  function onPointerDown(e: React.PointerEvent, idx: number) {
    e.preventDefault();
    draggingRef.current = idx;
    (e.currentTarget as SVGElement).setPointerCapture(e.pointerId);
  }

  function onPointerMove(e: React.PointerEvent) {
    if (draggingRef.current === null) return;
    const pt = screenToSVG(e.clientX, e.clientY);
    const next = [...corners] as [Point, Point, Point, Point];
    next[draggingRef.current] = pt;
    onCornersChange(next);
  }

  function onPointerUp() {
    draggingRef.current = null;
  }

  const polyPoints = corners.map(c => `${c.x},${c.y}`).join(" ");

  return (
    <div
      className="relative w-full bg-black"
      style={{ aspectRatio: `${imageWidth} / ${imageHeight}` }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={dataUrl}
        alt="Captured document"
        className="absolute inset-0 w-full h-full object-fill"
        draggable={false}
      />
      <svg
        ref={svgRef}
        className="absolute inset-0 w-full h-full touch-none"
        viewBox={`0 0 ${imageWidth} ${imageHeight}`}
        preserveAspectRatio="none"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        {/* Semi-transparent crop overlay */}
        <polygon
          points={polyPoints}
          fill="rgba(59,130,246,0.18)"
          stroke="rgba(59,130,246,0.9)"
          strokeWidth={imageWidth * 0.004}
          strokeLinejoin="round"
        />
        {/* Corner handles */}
        {corners.map((c, i) => (
          <g key={i}>
            {/* Shadow/outline for visibility */}
            <circle
              cx={c.x} cy={c.y}
              r={imageWidth * 0.028}
              fill="white"
              opacity={0.6}
            />
            <circle
              cx={c.x} cy={c.y}
              r={imageWidth * 0.022}
              fill={HANDLE_COLORS[i]}
              stroke="white"
              strokeWidth={imageWidth * 0.005}
              onPointerDown={(e) => onPointerDown(e, i)}
              className="cursor-grab"
              style={{ touchAction: "none" }}
            />
            <text
              x={c.x} y={c.y + imageWidth * 0.007}
              textAnchor="middle"
              fill="white"
              fontSize={imageWidth * 0.016}
              fontWeight="bold"
              style={{ pointerEvents: "none", userSelect: "none" }}
            >
              {HANDLE_LABELS[i]}
            </text>
          </g>
        ))}
      </svg>
    </div>
  );
}

// ── Camera view with quad overlay ─────────────────────────────────────────────

interface CameraViewProps {
  videoRef: React.RefObject<HTMLVideoElement>;
  detectedQuad: [Point, Point, Point, Point] | null;
  videoWidth: number;
  videoHeight: number;
}

function CameraView({ videoRef, detectedQuad, videoWidth, videoHeight }: CameraViewProps) {
  const polyPoints = detectedQuad?.map(c => `${c.x},${c.y}`).join(" ");
  const fallback = videoWidth > 0 ? defaultCorners(videoWidth, videoHeight) : null;
  const guidePoints = (detectedQuad ?? fallback)?.map(c => `${c.x},${c.y}`).join(" ");
  const isDetected = Boolean(detectedQuad);

  return (
    <div className="relative w-full bg-black" style={{ aspectRatio: videoWidth && videoHeight ? `${videoWidth} / ${videoHeight}` : "4/3" }}>
      <video
        ref={videoRef}
        autoPlay playsInline muted
        className="absolute inset-0 w-full h-full object-cover"
      />
      {guidePoints && videoWidth > 0 && (
        <svg
          className="absolute inset-0 w-full h-full pointer-events-none"
          viewBox={`0 0 ${videoWidth} ${videoHeight}`}
          preserveAspectRatio="none"
        >
          <polygon
            points={guidePoints}
            fill={isDetected ? "rgba(34,197,94,0.15)" : "rgba(255,255,255,0.08)"}
            stroke={isDetected ? "rgba(34,197,94,0.9)" : "rgba(255,255,255,0.4)"}
            strokeWidth={videoWidth * 0.004}
            strokeDasharray={isDetected ? "0" : `${videoWidth * 0.02}`}
            strokeLinejoin="round"
          />
          {/* Corner markers */}
          {(detectedQuad ?? fallback)!.map((c, i) => (
            <circle key={i} cx={c.x} cy={c.y}
              r={videoWidth * 0.015}
              fill={isDetected ? HANDLE_COLORS[i] : "white"}
              stroke="white" strokeWidth={videoWidth * 0.003}
            />
          ))}
        </svg>
      )}
    </div>
  );
}

// ── Page thumbnail strip ───────────────────────────────────────────────────────

function PageStrip({
  pages, locale, onDelete,
}: {
  pages: ScannedPage[];
  locale: string;
  onDelete: (id: string) => void;
}) {
  if (pages.length === 0) return null;
  return (
    <div className="flex gap-2 overflow-x-auto py-1 px-1">
      {pages.map((p, i) => (
        <div key={p.id} className="relative flex-shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={p.thumbUrl}
            alt={`${l("page", locale)} ${i + 1}`}
            className="h-16 w-12 object-cover rounded border-2 border-gray-200"
          />
          <span className="absolute bottom-0.5 left-0.5 bg-black/60 text-white text-[9px] px-1 rounded">
            {i + 1}
          </span>
          <button
            onClick={() => onDelete(p.id)}
            className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center leading-none"
          >
            {l("delete", locale)}
          </button>
        </div>
      ))}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function ScanPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const { sessionToken, caseId, setFields, setPdfToken, beginNewUpload } = useCaseStore();

  // ── Core state ──────────────────────────────────────────────────────────────
  const [mounted, setMounted]         = useState(false);
  const [stage, setStage]             = useState<Stage>("loading_cv");
  const [cvReady, setCvReady]         = useState(false);
  const [cameraReady, setCameraReady] = useState(false);
  const [pages, setPages]             = useState<ScannedPage[]>([]);
  const [processError, setProcessError] = useState<string | null>(null);

  // Camera state
  const [detectedQuad, setDetectedQuad] = useState<[Point, Point, Point, Point] | null>(null);
  const [videoSize, setVideoSize]       = useState({ w: 0, h: 0 });

  // Adjusting state
  const [capturedDataUrl, setCapturedDataUrl] = useState<string | null>(null);
  const [capturedSize, setCapturedSize]       = useState({ w: 0, h: 0 });
  const [corners, setCorners] = useState<[Point, Point, Point, Point]>([
    { x: 0, y: 0 }, { x: 1, y: 0 }, { x: 1, y: 1 }, { x: 0, y: 1 },
  ]);
  const [warpPreviewUrl, setWarpPreviewUrl] = useState<string | null>(null);

  // Preview state
  const [previewDataUrl, setPreviewDataUrl] = useState<string | null>(null);
  const [previewSize, setPreviewSize]       = useState({ w: 0, h: 0 });
  const [renderMode, setRenderMode]         = useState<RenderMode>("document");
  const [quality, setQuality]               = useState<Quality | null>(null);

  // ── Refs ────────────────────────────────────────────────────────────────────
  const videoRef    = useRef<HTMLVideoElement>(null);
  const streamRef   = useRef<MediaStream | null>(null);
  const cvRef       = useRef<unknown>(null);
  const detectTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const warpTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Step 1: mark client-side mount so Zustand localStorage has hydrated ─────
  useEffect(() => { setMounted(true); }, []);

  // ── Step 2: redirect if no valid session (after Zustand has hydrated) ────────
  useEffect(() => {
    if (mounted && (!sessionToken || !caseId)) router.replace("/");
  }, [mounted, sessionToken, caseId, router]);

  // ── Step 3: go to camera immediately — OpenCV loads in background ─────────────
  // NEVER block the UI on OpenCV. Camera works without it (basic mode).
  // OpenCV enhances capture when ready; if it fails the user never notices.
  useEffect(() => {
    if (!mounted || !sessionToken || !caseId) return;
    setStage("camera");
    loadOpenCV()
      .then(cv => { cvRef.current = cv; setCvReady(true); })
      .catch(() => { /* stay in basic mode — camera still works */ });
  }, [mounted, sessionToken, caseId]);

  // ── Start camera whenever stage becomes "camera" (with or without OpenCV) ──
  useEffect(() => {
    if (stage !== "camera") return;
    startCamera();
    return () => stopCamera();
  }, [stage]);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { setStage("error_camera"); return; }
    setCameraReady(false);

    // Attach a stream to the video element and start playback
    async function attach(stream: MediaStream) {
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) return;
      video.srcObject = stream;
      try { await video.play(); } catch { /* muted+playsInline should handle autoplay */ }
    }

    // Poll (via rAF) until the video has real dimensions or timeout
    function waitForDimensions(ms = 4000): Promise<boolean> {
      return new Promise(resolve => {
        const deadline = setTimeout(() => resolve(false), ms);
        function check() {
          const v = videoRef.current;
          if (!v) { clearTimeout(deadline); resolve(false); return; }
          if (v.videoWidth > 0 && v.videoHeight > 0) {
            clearTimeout(deadline);
            setVideoSize({ w: v.videoWidth, h: v.videoHeight });
            resolve(true);
            return;
          }
          requestAnimationFrame(check);
        }
        check();
      });
    }

    // Try getUserMedia; return null instead of throwing
    async function tryGet(c: MediaStreamConstraints): Promise<MediaStream | null> {
      try { return await navigator.mediaDevices.getUserMedia(c); }
      catch { return null; }
    }

    try {
      // Attempt 1: ideal rear camera, reasonable resolution (1280×720)
      let stream = await tryGet({
        video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });

      // Attempt 2: any camera, simplest constraints
      if (!stream) stream = await tryGet({ video: true, audio: false });

      if (!stream) { setStage("error_camera"); return; }

      await attach(stream);
      const hasVideo = await waitForDimensions(4000);

      if (!hasVideo) {
        // Stream established but video is black — stop and retry with bare constraints
        stream.getTracks().forEach(t => t.stop());
        const fallback = await tryGet({ video: true, audio: false });
        if (fallback) { await attach(fallback); await waitForDimensions(3000); }
      }

      setCameraReady(true);
      detectTimer.current = setInterval(runLiveDetection, 500);
    } catch {
      setStage("error_camera");
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach(t => t.stop());
    streamRef.current = null;
    if (detectTimer.current) clearInterval(detectTimer.current);
    setCameraReady(false);
  }

  function runLiveDetection() {
    const video = videoRef.current;
    const cv    = cvRef.current;
    if (!video || !cv || video.videoWidth === 0) return;

    // Downscale to 640px for speed
    const scale  = Math.min(1, 640 / video.videoWidth);
    const w = Math.round(video.videoWidth  * scale);
    const h = Math.round(video.videoHeight * scale);
    const canvas = document.createElement("canvas");
    canvas.width = w; canvas.height = h;
    canvas.getContext("2d")!.drawImage(video, 0, 0, w, h);

    const quad = detectDocumentQuad(canvas, cv);
    if (quad) {
      // Scale corners back to full video coordinates
      const scaled = quad.map(p => ({ x: p.x / scale, y: p.y / scale }));
      setDetectedQuad(orderCorners(scaled) as [Point, Point, Point, Point]);
    } else {
      setDetectedQuad(null);
    }
  }

  // ── Capture ─────────────────────────────────────────────────────────────────
  function capture() {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;

    stopCamera();

    const canvas = document.createElement("canvas");
    canvas.width  = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")!.drawImage(video, 0, 0);

    const dataUrl = canvasToDataUrl(canvas, 0.95);
    setCapturedDataUrl(dataUrl);
    setCapturedSize({ w: canvas.width, h: canvas.height });

    if (!cvReady) {
      // Basic fallback: no warp/enhance — go straight to preview with raw capture
      const q = checkQuality(canvas);
      setPreviewDataUrl(dataUrl);
      setPreviewSize({ w: canvas.width, h: canvas.height });
      setQuality(q);
      setStage("preview");
      return;
    }

    // Full OpenCV mode: corner adjustment
    const initCorners = detectedQuad ?? defaultCorners(canvas.width, canvas.height);
    setCorners(initCorners);
    setDetectedQuad(null);
    setStage("adjusting");
  }

  // ── Live warp preview (debounced 250ms) ────────────────────────────────────
  useEffect(() => {
    if (stage !== "adjusting" || !capturedDataUrl) return;
    if (warpTimer.current) clearTimeout(warpTimer.current);
    warpTimer.current = setTimeout(async () => {
      try {
        const srcCanvas = await dataUrlToCanvas(capturedDataUrl);
        const warped    = warpDocument(srcCanvas, corners, cvRef.current, 600);
        setWarpPreviewUrl(canvasToDataUrl(warped, 0.85));
      } catch { /* ignore */ }
    }, 250);
  }, [corners, capturedDataUrl, stage]);

  // ── Confirm crop → warp at full resolution and enhance ────────────────────
  async function confirmCrop() {
    if (!capturedDataUrl) return;
    try {
      const srcCanvas = await dataUrlToCanvas(capturedDataUrl);
      const warped    = warpDocument(srcCanvas, corners, cvRef.current, 1800);
      const enhanced  = enhanceDocument(warped, renderMode, cvRef.current);
      const q         = checkQuality(enhanced, cvRef.current);
      setPreviewDataUrl(canvasToDataUrl(enhanced, 0.92));
      setPreviewSize({ w: enhanced.width, h: enhanced.height });
      setQuality(q);
      setStage("preview");
    } catch (e) {
      console.error("warp failed", e);
    }
  }

  // ── Re-apply render mode without re-warping ────────────────────────────────
  async function applyMode(mode: RenderMode) {
    setRenderMode(mode);
    if (!capturedDataUrl || stage !== "preview") return;
    try {
      const srcCanvas = await dataUrlToCanvas(capturedDataUrl);
      const warped    = warpDocument(srcCanvas, corners, cvRef.current, 1800);
      const enhanced  = enhanceDocument(warped, mode, cvRef.current);
      const q         = checkQuality(enhanced, cvRef.current);
      setPreviewDataUrl(canvasToDataUrl(enhanced, 0.92));
      setPreviewSize({ w: enhanced.width, h: enhanced.height });
      setQuality(q);
    } catch { /* ignore */ }
  }

  // ── Accept page ─────────────────────────────────────────────────────────────
  function acceptPage() {
    if (!previewDataUrl) return;
    // Make thumbnail (~80×120)
    const thumbCanvas = document.createElement("canvas");
    thumbCanvas.width = 80; thumbCanvas.height = 120;
    const tImg = new Image();
    tImg.onload = () => {
      thumbCanvas.getContext("2d")!.drawImage(tImg, 0, 0, 80, 120);
      const thumbUrl = thumbCanvas.toDataURL("image/jpeg", 0.7);
      setPages(prev => [...prev, {
        id: `p-${Date.now()}`,
        dataUrl: previewDataUrl!,
        thumbUrl,
        naturalWidth:  previewSize.w,
        naturalHeight: previewSize.h,
      }]);
      // Reset for next page — the camera-start effect fires when stage → "camera"
      setCapturedDataUrl(null);
      setPreviewDataUrl(null);
      setWarpPreviewUrl(null);
      setStage("camera");
    };
    tImg.src = previewDataUrl;
  }

  function deletePage(id: string) {
    setPages(prev => prev.filter(p => p.id !== id));
  }

  function retakeFromAdjust() {
    setCapturedDataUrl(null);
    setWarpPreviewUrl(null);
    setStage("camera");
  }

  function retakeFromPreview() {
    setPreviewDataUrl(null);
    // In basic fallback mode (no OpenCV) there is no adjusting step — go back to camera
    setStage(cvReady ? "adjusting" : "camera");
  }

  // ── Build PDF and send to existing pipeline ────────────────────────────────
  async function handleFinish() {
    if (pages.length === 0) return;
    setStage("building");
    setProcessError(null);

    let file: File;
    try {
      file = await buildScanPdf(pages);
    } catch (e) {
      setProcessError(e instanceof Error ? e.message : "Failed to build PDF.");
      setStage("camera");
      return;
    }

    // Same logic as upload/page.tsx
    const attemptId = beginNewUpload({
      filename:         file.name,
      fileSize:         file.size,
      fileLastModified: file.lastModified,
    });

    try {
      const result = await api.processPdf(file, locale);
      if (useCaseStore.getState().uploadAttemptId !== attemptId) return;

      if (!result.fields?.length || !result.extracted_field_ids?.length) {
        setProcessError(l("no_fields", locale));
        setStage("camera");
        return;
      }
      const showable = result.fields.filter(f => f.show_question !== false);
      if (!showable.length) {
        setProcessError(l("no_fields", locale));
        setStage("camera");
        return;
      }
      setFields(showable, caseId ?? "stateless", result.filename, result.extracted_field_ids, attemptId);
      setPdfToken(result.pdf_token);
      router.push(`/${locale}/questions`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Processing failed.";
      setProcessError(
        msg.includes("422") || msg.toLowerCase().includes("no field")
          ? l("no_fields", locale)
          : msg
      );
      setStage("camera");
    }
  }

  // ── Guard ───────────────────────────────────────────────────────────────────
  if (!mounted) return null;             // wait for Zustand localStorage hydration
  if (!sessionToken || !caseId) return null;

  // ── Error screens ───────────────────────────────────────────────────────────
  if (stage === "error_camera" || stage === "error_cv") {
    const msg = stage === "error_camera" ? l("no_camera", locale) : l("no_cv", locale);
    return (
      <>
        <Header />
        <main className="max-w-lg mx-auto px-4 py-16 text-center">
          <div className="text-5xl mb-6">{stage === "error_camera" ? "🚫" : "⚠️"}</div>
          <p className="text-gray-700 mb-6">{msg}</p>
          <button
            onClick={() => router.replace(`/${locale}/upload`)}
            className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700"
          >
            {l("upload_instead", locale)}
          </button>
        </main>
      </>
    );
  }

  // ── Building ────────────────────────────────────────────────────────────────
  if (stage === "building") {
    return (
      <>
        <Header />
        <main className="max-w-lg mx-auto px-4 py-16 text-center">
          <div className="animate-spin text-5xl mb-6">🔍</div>
          <p className="text-lg font-semibold text-brand-600">{l("building", locale)}</p>
          <p className="text-sm text-gray-400 mt-2">{pages.length} page{pages.length !== 1 ? "s" : ""}</p>
        </main>
      </>
    );
  }

  // ── Main UI ─────────────────────────────────────────────────────────────────
  return (
    <>
      <Header />
      <main className="flex flex-col" style={{ minHeight: "calc(100vh - 64px)" }}>

        {/* Beta disclaimer banner — sets expectations before camera opens */}
        <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center gap-2 text-xs">
          <span className="px-1.5 py-0.5 bg-amber-200 text-amber-900 font-bold uppercase tracking-wider rounded text-[10px]">
            Beta
          </span>
          <span className="text-amber-900">
            {locale === "de"
              ? "Scan ist experimentell. Wenn es nicht funktioniert, laden Sie eine PDF hoch."
              : locale === "ar"
              ? "المسح تجريبي. إذا لم يعمل، يرجى تحميل ملف PDF."
              : locale === "tr"
              ? "Tarama deneyseldir. Çalışmazsa lütfen bir PDF yükleyin."
              : locale === "fr"
              ? "Le scan est expérimental. Si cela ne fonctionne pas, téléversez un PDF."
              : locale === "es"
              ? "El escaneo es experimental. Si no funciona, suba un PDF."
              : locale === "sq"
              ? "Skanimi është eksperimental. Nëse nuk funksionon, ngarkoni një PDF."
              : locale === "ru"
              ? "Сканирование экспериментальное. Если не работает, загрузите PDF."
              : locale === "uk"
              ? "Сканування експериментальне. Якщо не працює, завантажте PDF."
              : "Scanning is experimental. If it doesn't work, please upload a PDF instead."}
          </span>
        </div>

        {/* ── Image area ── */}
        <div className="flex-1 bg-black flex flex-col">
          {/* Dev debug bar — only in development */}
          {process.env.NODE_ENV === "development" && (
            <div className="bg-gray-900/90 text-green-400 text-[10px] font-mono px-2 py-1 flex gap-3 flex-wrap z-50">
              <span>stage={stage}</span>
              <span>cam={cameraReady ? "✓" : "✗"}</span>
              <span>cv={cvReady ? "✓" : "✗"}</span>
              <span>video={videoSize.w}×{videoSize.h}</span>
              <span>secure={typeof window !== "undefined" && window.isSecureContext ? "✓" : "⚠"}</span>
              <span>gum={typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia ? "✓" : "✗"}</span>
            </div>
          )}
          {/* Loading */}
          {stage === "loading_cv" && (
            <div className="flex-1 flex flex-col items-center justify-center gap-6">
              <div className="text-center text-white">
                <div className="animate-spin text-4xl mb-4">⚙️</div>
                <p>{l("loading", locale)}</p>
              </div>
              <button
                onClick={() => router.replace(`/${locale}/upload`)}
                className="text-sm text-white/60 hover:text-white/90 underline"
              >
                ← {l("upload_instead", locale)}
              </button>
            </div>
          )}

          {/* Camera live view */}
          {stage === "camera" && (
            <CameraView
              videoRef={videoRef}
              detectedQuad={detectedQuad}
              videoWidth={videoSize.w}
              videoHeight={videoSize.h}
            />
          )}

          {/* Corner adjustment */}
          {stage === "adjusting" && capturedDataUrl && (
            <CornerEditor
              dataUrl={capturedDataUrl}
              imageWidth={capturedSize.w}
              imageHeight={capturedSize.h}
              corners={corners}
              onCornersChange={setCorners}
            />
          )}

          {/* Preview */}
          {stage === "preview" && previewDataUrl && (
            <div className="flex-1 flex items-center justify-center bg-gray-900 p-2">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={previewDataUrl}
                alt="Processed page"
                className="max-h-full max-w-full object-contain rounded shadow-lg"
              />
            </div>
          )}
        </div>

        {/* ── Controls ── */}
        <div className="bg-white border-t border-gray-200 px-4 py-4 space-y-3">

          {/* Error banner */}
          {processError && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              {processError}
            </div>
          )}

          {/* Page strip */}
          <PageStrip pages={pages} locale={locale} onDelete={deletePage} />

          {/* ── Camera stage ── */}
          {stage === "camera" && (
            <>
              <p className="text-xs text-gray-400 text-center">
                {cameraReady ? l("aim", locale) : "Camera starting…"}
              </p>
              <button
                onClick={capture}
                disabled={!cameraReady}
                className={`w-full py-4 rounded-2xl font-bold text-lg transition-all ${
                  cameraReady
                    ? "bg-brand-600 text-white hover:bg-brand-700 active:scale-95"
                    : "bg-gray-200 text-gray-400 cursor-not-allowed"
                }`}
              >
                {l("capture", locale)}
              </button>
              {pages.length > 0 && (
                <button
                  onClick={handleFinish}
                  className="w-full py-3 border-2 border-brand-600 text-brand-700 rounded-2xl font-semibold hover:bg-brand-50"
                >
                  {l("finish", locale)} ({pages.length})
                </button>
              )}
              <button
                onClick={() => router.replace(`/${locale}/upload`)}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
              >
                ← {l("upload_instead", locale)}
              </button>
            </>
          )}

          {/* ── Adjusting stage ── */}
          {stage === "adjusting" && (
            <>
              <div>
                <p className="font-semibold text-gray-800 text-sm mb-1">{l("adjust_title", locale)}</p>
                <p className="text-xs text-gray-400">{l("adjust_hint", locale)}</p>
              </div>

              {/* Render mode selection (preview is shown in mini-form) */}
              <ModeToggle mode={renderMode} onChange={setRenderMode} locale={locale} />

              {/* Warp preview */}
              {warpPreviewUrl && (
                <div className="flex gap-2 items-center">
                  <span className="text-xs text-gray-400 w-14 flex-shrink-0">Preview:</span>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={warpPreviewUrl}
                    alt="Warp preview"
                    className="h-20 rounded border border-gray-200 object-contain"
                  />
                </div>
              )}

              <div className="flex gap-3">
                <button
                  onClick={retakeFromAdjust}
                  className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-2xl font-semibold hover:bg-gray-50"
                >
                  {l("retake", locale)}
                </button>
                <button
                  onClick={confirmCrop}
                  className="flex-1 py-3 bg-brand-600 text-white rounded-2xl font-semibold hover:bg-brand-700"
                >
                  {l("confirm", locale)}
                </button>
              </div>
            </>
          )}

          {/* ── Preview stage ── */}
          {stage === "preview" && (
            <>
              <p className="font-semibold text-gray-800 text-sm">{l("preview_title", locale)}</p>

              {quality && <QualityBadge quality={quality} />}

              <ModeToggle mode={renderMode} onChange={applyMode} locale={locale} />

              <div className="flex gap-3">
                <button
                  onClick={retakeFromPreview}
                  className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-2xl font-semibold hover:bg-gray-50"
                >
                  {l("retake", locale)}
                </button>
                <button
                  onClick={acceptPage}
                  className="flex-1 py-3 bg-green-600 text-white rounded-2xl font-semibold hover:bg-green-700"
                >
                  {l("use_page", locale)}
                </button>
              </div>

              {pages.length > 0 && (
                <button
                  onClick={handleFinish}
                  className="w-full py-3 border-2 border-brand-600 text-brand-700 rounded-2xl font-semibold hover:bg-brand-50"
                >
                  {l("finish", locale)} ({pages.length + 1})
                </button>
              )}
            </>
          )}
        </div>
      </main>
    </>
  );
}
