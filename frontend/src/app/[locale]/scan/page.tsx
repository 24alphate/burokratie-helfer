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
  const [stage, setStage]             = useState<Stage>("loading_cv");
  const [cvReady, setCvReady]         = useState(false);
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

  // ── Mount: load OpenCV ──────────────────────────────────────────────────────
  useEffect(() => {
    if (!sessionToken || !caseId) { router.replace("/"); return; }

    loadOpenCV()
      .then(cv => {
        cvRef.current = cv;
        setCvReady(true);
        setStage("camera");
      })
      .catch(() => setStage("error_cv"));
  }, []);

  // ── Start camera when OpenCV is ready ──────────────────────────────────────
  useEffect(() => {
    if (!cvReady || stage !== "camera") return;
    startCamera();
    return () => stopCamera();
  }, [cvReady, stage]);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { setStage("error_camera"); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width:  { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play().catch(() => {});
        videoRef.current.onloadedmetadata = () => {
          if (!videoRef.current) return;
          setVideoSize({ w: videoRef.current.videoWidth, h: videoRef.current.videoHeight });
        };
      }
      // Run quad detection every 500ms
      detectTimer.current = setInterval(runLiveDetection, 500);
    } catch {
      setStage("error_camera");
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach(t => t.stop());
    if (detectTimer.current) clearInterval(detectTimer.current);
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

    // Use detected corners or defaults
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
      // Reset for next page
      setCapturedDataUrl(null);
      setPreviewDataUrl(null);
      setWarpPreviewUrl(null);
      setStage("camera");
      startCamera();
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
    startCamera();
  }

  function retakeFromPreview() {
    setPreviewDataUrl(null);
    setStage("adjusting");
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
        startCamera();
        return;
      }
      const showable = result.fields.filter(f => f.show_question !== false);
      if (!showable.length) {
        setProcessError(l("no_fields", locale));
        setStage("camera");
        startCamera();
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
      startCamera();
    }
  }

  // ── Guard ───────────────────────────────────────────────────────────────────
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

        {/* ── Image area ── */}
        <div className="flex-1 bg-black flex flex-col">
          {/* Loading */}
          {stage === "loading_cv" && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center text-white">
                <div className="animate-spin text-4xl mb-4">⚙️</div>
                <p>{l("loading", locale)}</p>
              </div>
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
              <p className="text-xs text-gray-400 text-center">{l("aim", locale)}</p>
              <button
                onClick={capture}
                className="w-full py-4 bg-brand-600 text-white rounded-2xl font-bold text-lg hover:bg-brand-700 active:scale-95 transition-all"
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
