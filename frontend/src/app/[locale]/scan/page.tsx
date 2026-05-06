"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/Header";
import { useCaseStore } from "@/store/caseStore";
import { api } from "@/lib/api";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Quality {
  status: "good" | "review" | "bad";
  message: string;
  messageAr?: string;
  messageTr?: string;
  messageDe?: string;
}

interface ScannedPage {
  id: string;
  dataUrl: string;
  quality: Quality;
}

type ScanStage =
  | "requesting"      // waiting for camera permission
  | "capturing"       // live preview, waiting for capture
  | "preview"         // showing captured frame + quality result
  | "processing"      // converting to PDF + sending to /process-pdf
  | "error_camera"    // camera denied or not available
  | "error_processing"; // /process-pdf returned error

// ── Quality check (client-side, no network) ───────────────────────────────────

function checkQuality(canvas: HTMLCanvasElement): Quality {
  const ctx = canvas.getContext("2d");
  if (!ctx) return { status: "review", message: "Could not analyze image." };

  const { width, height } = canvas;

  // Resolution gate
  if (width < 400 || height < 400) {
    return {
      status: "bad",
      message: "The page is too far away. Move closer.",
      messageDe: "Die Seite ist zu weit entfernt. Näher herangehen.",
      messageAr: "الصفحة بعيدة جدًا. اقترب أكثر.",
      messageTr: "Sayfa çok uzakta. Daha yakına gidin.",
    };
  }

  // Sample every 8th pixel for performance
  const imageData = ctx.getImageData(0, 0, width, height);
  const data = imageData.data;
  const step = 8;
  let totalLum = 0;
  let count = 0;
  const lums: number[] = [];

  for (let i = 0; i < data.length; i += 4 * step) {
    const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    totalLum += lum;
    lums.push(lum);
    count++;
  }

  const avgLum = totalLum / count;

  if (avgLum < 50) {
    return {
      status: "bad",
      message: "The page is too dark. Try better lighting.",
      messageDe: "Die Seite ist zu dunkel. Bessere Beleuchtung verwenden.",
      messageAr: "الصفحة مظلمة جدًا. جرب إضاءة أفضل.",
      messageTr: "Sayfa çok karanlık. Daha iyi aydınlatma deneyin.",
    };
  }

  if (avgLum > 245) {
    return {
      status: "review",
      message: "The image may be overexposed. Try shading slightly.",
      messageDe: "Das Bild könnte überbelichtet sein.",
      messageAr: "الصورة قد تكون مضاءة بشكل مفرط.",
      messageTr: "Görüntü aşırı pozlanmış olabilir.",
    };
  }

  // Contrast check — standard deviation of luminance
  const variance =
    lums.reduce((sum, l) => sum + (l - avgLum) ** 2, 0) / lums.length;
  const stdDev = Math.sqrt(variance);

  if (stdDev < 12) {
    return {
      status: "bad",
      message: "We could not detect enough readable text. Move closer or improve lighting.",
      messageDe: "Kein lesbarer Text erkannt. Näher herangehen oder Beleuchtung verbessern.",
      messageAr: "لم نتمكن من اكتشاف نص كافٍ. اقترب أو حسّن الإضاءة.",
      messageTr: "Yeterli metin algılanamadı. Yaklaşın veya aydınlatmayı iyileştirin.",
    };
  }

  if (stdDev < 22) {
    return {
      status: "review",
      message: "This scan may be blurry. Please retake if possible.",
      messageDe: "Dieser Scan könnte unscharf sein. Wenn möglich, bitte wiederholen.",
      messageAr: "قد تكون هذه المسحة ضبابية. أعد التصوير إن أمكن.",
      messageTr: "Bu tarama bulanık olabilir. Mümkünse yeniden çekin.",
    };
  }

  return {
    status: "good",
    message: "Looks good.",
    messageDe: "Sieht gut aus.",
    messageAr: "يبدو جيدًا.",
    messageTr: "Görünüm iyi.",
  };
}

function localQualityMsg(q: Quality, locale: string): string {
  if (locale === "de" && q.messageDe) return q.messageDe;
  if (locale === "ar" && q.messageAr) return q.messageAr;
  if (locale === "tr" && q.messageTr) return q.messageTr;
  return q.message;
}

// ── Convert scanned images to a PDF file (jsPDF) ─────────────────────────────

async function imagesToPdf(pages: ScannedPage[]): Promise<File> {
  const { default: jsPDF } = await import("jspdf");
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });
  for (let i = 0; i < pages.length; i++) {
    if (i > 0) doc.addPage();
    doc.addImage(pages[i].dataUrl, "JPEG", 0, 0, 210, 297);
  }
  const blob = doc.output("blob");
  return new File([blob], "scanned_document.pdf", { type: "application/pdf" });
}

// ── Localised strings ─────────────────────────────────────────────────────────

const L: Record<string, Record<string, string>> = {
  instructions: {
    en: "Place the full page inside the frame. Use good lighting. Avoid shadows.",
    ar: "ضع الصفحة كاملة داخل الإطار. استخدم إضاءة جيدة. تجنب الظلال.",
    tr: "Sayfanın tamamını çerçeveye yerleştirin. İyi aydınlatma kullanın. Gölgelerden kaçının.",
    de: "Legen Sie die vollständige Seite in den Rahmen. Gute Beleuchtung verwenden. Schatten vermeiden.",
  },
  capture:       { en: "Capture", ar: "التقاط", tr: "Çek", de: "Aufnehmen" },
  retake:        { en: "Retake", ar: "إعادة", tr: "Yeniden çek", de: "Wiederholen" },
  use_page:      { en: "Use this page", ar: "استخدم هذه الصفحة", tr: "Bu sayfayı kullan", de: "Seite verwenden" },
  add_page:      { en: "Add another page", ar: "إضافة صفحة أخرى", tr: "Başka sayfa ekle", de: "Weitere Seite hinzufügen" },
  finish:        { en: "Finish scanning", ar: "إنهاء المسح", tr: "Taramayı bitir", de: "Scannen beenden" },
  page_n:        { en: "Page", ar: "صفحة", tr: "Sayfa", de: "Seite" },
  processing:    { en: "Processing scanned document…", ar: "جارٍ معالجة المستند الممسوح…", tr: "Taranan belge işleniyor…", de: "Gescanntes Dokument wird verarbeitet…" },
  no_camera:     { en: "Camera access was blocked. You can still upload a PDF instead.", ar: "تم حظر الوصول إلى الكاميرا. يمكنك رفع ملف PDF بدلاً من ذلك.", tr: "Kamera erişimi engellendi. Bunun yerine bir PDF yükleyebilirsiniz.", de: "Kamerazugriff wurde verweigert. Sie können stattdessen noch ein PDF hochladen." },
  no_fields:     { en: "This scanned document could not be read reliably yet. Please upload the official PDF if possible.", ar: "لم نتمكن من قراءة هذا المستند الممسوح بشكل موثوق بعد. يرجى رفع الـ PDF الرسمي إن أمكن.", tr: "Bu taranan belge henüz güvenilir şekilde okunamadı. Mümkünse lütfen resmi PDF'yi yükleyin.", de: "Dieses gescannte Dokument konnte noch nicht zuverlässig gelesen werden. Bitte laden Sie wenn möglich das offizielle PDF hoch." },
  upload_instead: { en: "Upload PDF instead", ar: "رفع PDF بدلاً من ذلك", tr: "Bunun yerine PDF yükle", de: "Stattdessen PDF hochladen" },
  delete:        { en: "Delete", ar: "حذف", tr: "Sil", de: "Löschen" },
};

function l(key: string, locale: string) {
  return L[key]?.[locale] ?? L[key]?.["en"] ?? key;
}

// ── Main scan page ─────────────────────────────────────────────────────────────

export default function ScanPage({ params }: { params: { locale: string } }) {
  const { locale } = params;
  const router = useRouter();
  const {
    sessionToken, caseId,
    setFields, setPdfToken, beginNewUpload,
  } = useCaseStore();

  const [mounted, setMounted]       = useState(false);
  const [stage, setStage]           = useState<ScanStage>("requesting");
  const [pages, setPages]           = useState<ScannedPage[]>([]);
  const [preview, setPreview]       = useState<{ dataUrl: string; quality: Quality } | null>(null);
  const [processError, setProcessError] = useState<string | null>(null);

  const videoRef  = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  useEffect(() => { setMounted(true); }, []);

  useEffect(() => {
    if (!mounted) return;
    if (!sessionToken || !caseId) { router.replace("/"); return; }
    startCamera();
    return () => { streamRef.current?.getTracks().forEach((t) => t.stop()); };
  }, [mounted]);

  async function startCamera() {
    if (!navigator.mediaDevices?.getUserMedia) {
      setStage("error_camera");
      return;
    }
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
      }
      setStage("capturing");
    } catch {
      setStage("error_camera");
    }
  }

  const capture = useCallback(() => {
    const video  = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width  = video.videoWidth  || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d")!;
    ctx.drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    const quality = checkQuality(canvas);
    setPreview({ dataUrl, quality });
    setStage("preview");
  }, []);

  function acceptPage() {
    if (!preview) return;
    const newPage: ScannedPage = {
      id:      `page-${Date.now()}`,
      dataUrl: preview.dataUrl,
      quality: preview.quality,
    };
    setPages((prev) => [...prev, newPage]);
    setPreview(null);
    setStage("capturing");
  }

  function retake() {
    setPreview(null);
    setStage("capturing");
  }

  function deletePage(id: string) {
    setPages((prev) => prev.filter((p) => p.id !== id));
  }

  async function handleFinish() {
    if (pages.length === 0) return;
    setStage("processing");
    setProcessError(null);

    let file: File;
    try {
      file = await imagesToPdf(pages);
    } catch (e) {
      setProcessError(e instanceof Error ? e.message : "Failed to create PDF.");
      setStage("error_processing");
      return;
    }

    // Mirrors upload/page.tsx handleFileSelected — same race guard + beginNewUpload
    const attemptId = beginNewUpload({
      filename:         file.name,
      fileSize:         file.size,
      fileLastModified: file.lastModified,
    });

    try {
      const result = await api.processPdf(file, locale);

      const currentAttemptId = useCaseStore.getState().uploadAttemptId;
      if (currentAttemptId !== attemptId) return; // race: another upload started

      if (!result.fields || result.fields.length === 0 ||
          result.extracted_field_ids.length === 0) {
        setProcessError(l("no_fields", locale));
        setStage("error_processing");
        return;
      }

      const showable = result.fields.filter((f) => f.show_question !== false);
      if (showable.length === 0) {
        setProcessError(l("no_fields", locale));
        setStage("error_processing");
        return;
      }

      setFields(showable, caseId ?? "stateless", result.filename,
                result.extracted_field_ids, attemptId);
      setPdfToken(result.pdf_token);
      router.push(`/${locale}/questions`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Failed to process document.";
      setProcessError(
        msg.includes("422") || msg.toLowerCase().includes("no field")
          ? l("no_fields", locale)
          : msg
      );
      setStage("error_processing");
    }
  }

  if (!mounted || !sessionToken || !caseId) return null;

  // ── Camera denied ───────────────────────────────────────────────────────────
  if (stage === "error_camera") {
    return (
      <>
        <Header />
        <main className="max-w-lg mx-auto px-4 py-16 text-center">
          <div className="text-5xl mb-6">🚫</div>
          <p className="text-gray-700 mb-6">{l("no_camera", locale)}</p>
          <button
            onClick={() => router.replace(`/${locale}/upload`)}
            className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700 transition-colors"
          >
            {l("upload_instead", locale)}
          </button>
        </main>
      </>
    );
  }

  // ── Processing / PDF error ──────────────────────────────────────────────────
  if (stage === "processing") {
    return (
      <>
        <Header />
        <main className="max-w-lg mx-auto px-4 py-16 text-center">
          <div className="animate-spin text-5xl mb-6">🔍</div>
          <p className="text-lg font-semibold text-brand-600">{l("processing", locale)}</p>
          <p className="text-sm text-gray-400 mt-2">
            {locale === "de" ? `${pages.length} Seite(n) werden verarbeitet…` : `Processing ${pages.length} page(s)…`}
          </p>
        </main>
      </>
    );
  }

  if (stage === "error_processing") {
    return (
      <>
        <Header />
        <main className="max-w-lg mx-auto px-4 py-16 text-center">
          <div className="text-5xl mb-6">⚠️</div>
          <p className="text-gray-700 mb-4">{processError}</p>
          <div className="flex flex-col gap-3">
            <button
              onClick={() => { setProcessError(null); setPages([]); setStage("capturing"); }}
              className="px-6 py-3 bg-brand-600 text-white rounded-xl font-semibold hover:bg-brand-700"
            >
              {locale === "de" ? "Erneut scannen" : locale === "ar" ? "مسح مجددًا" : locale === "tr" ? "Yeniden tara" : "Scan again"}
            </button>
            <button
              onClick={() => router.replace(`/${locale}/upload`)}
              className="px-6 py-3 border-2 border-gray-200 text-gray-600 rounded-xl hover:bg-gray-50"
            >
              {l("upload_instead", locale)}
            </button>
          </div>
        </main>
      </>
    );
  }

  // ── Main scanning UI ────────────────────────────────────────────────────────
  return (
    <>
      <Header />
      <main className="flex flex-col" style={{ minHeight: "calc(100vh - 64px)" }}>

        {/* Camera viewport */}
        <div className="relative bg-black flex-1 flex items-center justify-center overflow-hidden"
             style={{ minHeight: 300 }}>

          {/* Live video — hidden during preview */}
          <video
            ref={videoRef}
            playsInline
            muted
            autoPlay
            className={`w-full h-full object-cover transition-opacity ${
              stage === "preview" ? "opacity-0 pointer-events-none" : "opacity-100"
            }`}
            style={{ maxHeight: "60vh" }}
          />

          {/* Preview of captured frame */}
          {stage === "preview" && preview && (
            <img
              src={preview.dataUrl}
              alt="Captured page"
              className="absolute inset-0 w-full h-full object-contain"
            />
          )}

          {/* Page counter badge */}
          <div className="absolute top-4 left-4 bg-black/60 text-white text-sm px-3 py-1 rounded-full font-mono">
            {l("page_n", locale)} {pages.length + (stage === "preview" ? 1 : 1)}
          </div>

          {/* Instructions overlay (capturing state) */}
          {stage === "capturing" && (
            <div className="absolute bottom-4 left-4 right-4 bg-black/60 text-white text-xs text-center px-3 py-2 rounded-lg">
              {l("instructions", locale)}
            </div>
          )}

          {/* Quality badge (preview state) */}
          {stage === "preview" && preview && (
            <div className={`absolute top-4 right-4 px-3 py-1.5 rounded-full text-sm font-semibold ${
              preview.quality.status === "good"
                ? "bg-green-500 text-white"
                : preview.quality.status === "review"
                ? "bg-yellow-400 text-gray-900"
                : "bg-red-500 text-white"
            }`}>
              {preview.quality.status === "good" ? "✓" : preview.quality.status === "review" ? "⚠" : "✗"}{" "}
              {localQualityMsg(preview.quality, locale)}
            </div>
          )}
        </div>

        {/* Hidden canvas for frame capture */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Controls */}
        <div className="bg-white px-4 py-5 space-y-4 border-t border-gray-200">

          {/* Thumbnail strip */}
          {pages.length > 0 && (
            <div className="flex gap-2 overflow-x-auto pb-1">
              {pages.map((p, i) => (
                <div key={p.id} className="relative flex-shrink-0">
                  <img
                    src={p.dataUrl}
                    alt={`Page ${i + 1}`}
                    className="h-16 w-12 object-cover rounded border-2 border-gray-200"
                  />
                  <span className="absolute bottom-0.5 left-0.5 bg-black/60 text-white text-[9px] px-1 rounded">
                    {i + 1}
                  </span>
                  <button
                    onClick={() => deletePage(p.id)}
                    className="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-xs w-4 h-4 rounded-full flex items-center justify-center leading-none"
                    aria-label="Delete"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Capture / Preview actions */}
          {stage === "capturing" && (
            <div className="flex flex-col gap-3">
              <button
                onClick={capture}
                className="w-full py-4 bg-brand-600 text-white rounded-2xl font-bold text-lg hover:bg-brand-700 active:scale-95 transition-all"
              >
                {l("capture", locale)}
              </button>
              {pages.length > 0 && (
                <button
                  onClick={handleFinish}
                  className="w-full py-3 border-2 border-brand-600 text-brand-700 rounded-2xl font-semibold hover:bg-brand-50 transition-colors"
                >
                  {l("finish", locale)} ({pages.length} {pages.length === 1 ? "page" : "pages"})
                </button>
              )}
              <button
                onClick={() => router.replace(`/${locale}/upload`)}
                className="w-full py-2 text-sm text-gray-400 hover:text-gray-600"
              >
                ← {l("upload_instead", locale)}
              </button>
            </div>
          )}

          {stage === "preview" && preview && (
            <div className="flex gap-3">
              <button
                onClick={retake}
                className="flex-1 py-3 border-2 border-gray-300 text-gray-700 rounded-2xl font-semibold hover:bg-gray-50 transition-colors"
              >
                {l("retake", locale)}
              </button>
              <button
                onClick={acceptPage}
                className="flex-1 py-3 bg-green-600 text-white rounded-2xl font-semibold hover:bg-green-700 transition-colors"
              >
                {l("use_page", locale)}
              </button>
            </div>
          )}
        </div>
      </main>
    </>
  );
}
