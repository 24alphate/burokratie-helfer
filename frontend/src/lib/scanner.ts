/**
 * Document scanner utilities using OpenCV.js.
 *
 * All functions that take a `cv` argument require OpenCV to be loaded first via loadOpenCV().
 * The cv object is loaded once (singleton) and cached for the session.
 */
"use client";

// ── Types ──────────────────────────────────────────────────────────────────────

export interface Point { x: number; y: number }

export type RenderMode = "document" | "grayscale" | "color";

export interface Quality {
  status: "good" | "review" | "bad";
  message: string;
  blur: number;        // Laplacian variance — higher is sharper
  brightness: number;  // average luminance 0–255
}

// ── OpenCV loader (CDN, singleton) ───────────────────────────────────────────
//
// @techstark/opencv-js imports Node.js `fs` which breaks Next.js browser builds.
// Instead we load OpenCV.js from the official CDN at runtime (browser only).
// The CDN version uses the same API as the npm package.

// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _cv: any = null;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let _loadPromise: Promise<any> | null = null;

const OPENCV_CDN = "https://docs.opencv.org/4.8.0/opencv.js";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function loadOpenCV(): Promise<any> {
  if (typeof window === "undefined") return Promise.reject(new Error("SSR: OpenCV is browser-only"));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const win = window as any;
  if (_cv) return Promise.resolve(_cv);
  if (win.cv?.Mat) { _cv = win.cv; return Promise.resolve(_cv); }

  if (!_loadPromise) {
    _loadPromise = new Promise((resolve, reject) => {
      let resolved = false;

      // OpenCV.js calls Module.onRuntimeInitialized when WASM is ready
      win.Module = {
        onRuntimeInitialized() {
          if (!resolved) {
            resolved = true;
            _cv = win.cv;
            resolve(_cv);
          }
        },
      };

      const script = document.createElement("script");
      script.src   = OPENCV_CDN;
      script.async = true;
      script.onload = () => {
        // Some builds call the callback before onload; poll as fallback
        setTimeout(() => {
          if (win.cv?.Mat && !resolved) {
            resolved = true;
            _cv = win.cv;
            resolve(_cv);
          }
        }, 500);
      };
      script.onerror = () => {
        _loadPromise = null;
        reject(new Error("Failed to load OpenCV.js from CDN"));
      };
      document.head.appendChild(script);

      // Hard timeout after 60 s
      setTimeout(() => {
        if (!resolved) {
          _loadPromise = null;
          reject(new Error("OpenCV.js load timeout after 60 s"));
        }
      }, 60_000);
    });
  }

  return _loadPromise;
}

// ── Corner ordering (TL → TR → BR → BL) ──────────────────────────────────────

export function orderCorners(pts: Point[]): [Point, Point, Point, Point] {
  const sorted = [...pts].sort((a, b) => a.y - b.y);
  const top    = sorted.slice(0, 2).sort((a, b) => a.x - b.x);
  const bottom = sorted.slice(2).sort((a, b) => a.x - b.x);
  return [top[0], top[1], bottom[1], bottom[0]]; // TL TR BR BL
}

/** Default corners with 10% inset from image edges. */
export function defaultCorners(w: number, h: number): [Point, Point, Point, Point] {
  const px = w * 0.10;
  const py = h * 0.10;
  return [
    { x: px,     y: py     },   // TL
    { x: w - px, y: py     },   // TR
    { x: w - px, y: h - py },   // BR
    { x: px,     y: h - py },   // BL
  ];
}

// ── Output size estimation ────────────────────────────────────────────────────

export function computeOutputSize(
  corners: [Point, Point, Point, Point],
  maxDim = 1800
): { width: number; height: number } {
  const [tl, tr, br, bl] = corners;
  const topW    = Math.hypot(tr.x - tl.x, tr.y - tl.y);
  const bottomW = Math.hypot(br.x - bl.x, br.y - bl.y);
  const leftH   = Math.hypot(bl.x - tl.x, bl.y - tl.y);
  const rightH  = Math.hypot(br.x - tr.x, br.y - tr.y);
  const w = (topW + bottomW) / 2;
  const h = (leftH + rightH) / 2;
  const scale = Math.min(1, maxDim / Math.max(w, h, 1));
  return { width: Math.round(w * scale), height: Math.round(h * scale) };
}

// ── Document quad detection ───────────────────────────────────────────────────

/**
 * Detect the largest quadrilateral (document outline) in the canvas.
 * Returns [TL, TR, BR, BL] corners in image coordinates, or null if none found.
 */
export function detectDocumentQuad(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  canvas: HTMLCanvasElement, cv: any
): [Point, Point, Point, Point] | null {
  let src: any, gray: any, blur: any, edges: any,
      contours: any, hierarchy: any, approx: any;
  try {
    src = cv.imread(canvas);
    gray = new cv.Mat();
    blur = new cv.Mat();
    edges = new cv.Mat();
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
    cv.GaussianBlur(gray, blur, new cv.Size(5, 5), 0);
    cv.Canny(blur, edges, 75, 200);

    // Dilate edges to close small gaps
    const kernel = cv.getStructuringElement(cv.MORPH_RECT, new cv.Size(3, 3));
    const dilated = new cv.Mat();
    cv.dilate(edges, dilated, kernel);
    kernel.delete();

    contours = new cv.MatVector();
    hierarchy = new cv.Mat();
    cv.findContours(dilated, contours, hierarchy, cv.RETR_LIST, cv.CHAIN_APPROX_SIMPLE);
    dilated.delete();

    const imageArea = canvas.width * canvas.height;
    let bestQuad: Point[] | null = null;
    let maxArea = 0;

    for (let i = 0; i < contours.size(); i++) {
      const contour = contours.get(i);
      const peri = cv.arcLength(contour, true);
      approx = new cv.Mat();
      cv.approxPolyDP(contour, approx, 0.02 * peri, true);

      if (approx.rows === 4) {
        const area = cv.contourArea(approx);
        if (area > maxArea && area > imageArea * 0.10) {
          maxArea = area;
          const pts: Point[] = [];
          for (let j = 0; j < 4; j++) {
            pts.push({ x: approx.data32S[j * 2], y: approx.data32S[j * 2 + 1] });
          }
          bestQuad = pts;
        }
      }
      approx.delete();
      contour.delete();
    }

    return bestQuad ? orderCorners(bestQuad) : null;
  } catch {
    return null;
  } finally {
    src?.delete(); gray?.delete(); blur?.delete(); edges?.delete();
    contours?.delete(); hierarchy?.delete();
  }
}

// ── Perspective warp ──────────────────────────────────────────────────────────

/**
 * Warp the source canvas so the four corner points map to a clean rectangle.
 * Returns a new canvas with the corrected image.
 */
export function warpDocument(
  srcCanvas: HTMLCanvasElement,
  corners: [Point, Point, Point, Point],
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cv: any,
  maxDim?: number
): HTMLCanvasElement {
  const [tl, tr, br, bl] = corners;
  const { width: outW, height: outH } = computeOutputSize(corners, maxDim ?? 1800);

  let src: any, dst: any, srcPts: any, dstPts: any, M: any;
  try {
    src = cv.imread(srcCanvas);
    dst = new cv.Mat();
    srcPts = cv.matFromArray(4, 1, cv.CV_32FC2, [
      tl.x, tl.y, tr.x, tr.y, br.x, br.y, bl.x, bl.y,
    ]);
    dstPts = cv.matFromArray(4, 1, cv.CV_32FC2, [
      0, 0, outW, 0, outW, outH, 0, outH,
    ]);
    M = cv.getPerspectiveTransform(srcPts, dstPts);
    cv.warpPerspective(src, dst, M, new cv.Size(outW, outH), cv.INTER_LINEAR);

    const out = document.createElement("canvas");
    out.width = outW;
    out.height = outH;
    cv.imshow(out, dst);
    return out;
  } finally {
    src?.delete(); dst?.delete(); srcPts?.delete(); dstPts?.delete(); M?.delete();
  }
}

// ── Image enhancement ─────────────────────────────────────────────────────────

/**
 * Apply a render mode to the warped canvas.
 * "document"  → adaptive threshold (crisp black text on white)
 * "grayscale" → grayscale conversion
 * "color"     → no change (returns the same canvas)
 */
export function enhanceDocument(
  srcCanvas: HTMLCanvasElement,
  mode: RenderMode,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cv: any
): HTMLCanvasElement {
  if (mode === "color") return srcCanvas;

  let src: any, gray: any, out: any, rgba: any;
  try {
    src = cv.imread(srcCanvas);
    gray = new cv.Mat();
    cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);

    if (mode === "document") {
      out = new cv.Mat();
      cv.adaptiveThreshold(
        gray, out, 255,
        cv.ADAPTIVE_THRESH_GAUSSIAN_C, cv.THRESH_BINARY,
        21, 15
      );
      rgba = new cv.Mat();
      cv.cvtColor(out, rgba, cv.COLOR_GRAY2RGBA);
    } else {
      // grayscale
      rgba = new cv.Mat();
      cv.cvtColor(gray, rgba, cv.COLOR_GRAY2RGBA);
    }

    const result = document.createElement("canvas");
    result.width  = srcCanvas.width;
    result.height = srcCanvas.height;
    cv.imshow(result, rgba);
    return result;
  } finally {
    src?.delete(); gray?.delete(); out?.delete(); rgba?.delete();
  }
}

// ── Quality check ─────────────────────────────────────────────────────────────

/**
 * Check blur and brightness.
 * Uses OpenCV Laplacian for blur if cv is provided; otherwise uses pixel variance.
 */
export function checkQuality(
  canvas: HTMLCanvasElement,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  cv?: any
): Quality {
  const ctx = canvas.getContext("2d");
  if (!ctx) return { status: "review", message: "Could not analyse image.", blur: 0, brightness: 128 };

  // Sample every 8th pixel for speed
  const { width: W, height: H } = canvas;
  if (W < 100 || H < 100) {
    return { status: "bad", message: "Image too small.", blur: 0, brightness: 0 };
  }

  const imgData = ctx.getImageData(0, 0, W, H).data;
  const step = 8;
  let totalLum = 0;
  const lums: number[] = [];
  for (let i = 0; i < imgData.length; i += 4 * step) {
    const l = 0.299 * imgData[i] + 0.587 * imgData[i + 1] + 0.114 * imgData[i + 2];
    totalLum += l;
    lums.push(l);
  }
  const avgLum = totalLum / lums.length;

  // Blur via Laplacian with cv; fallback to stddev
  let blurScore = 0;
  if (cv) {
    let src: any, gray: any, lap: any, mean: any, stddev: any;
    try {
      src = cv.imread(canvas);
      gray = new cv.Mat();
      lap  = new cv.Mat();
      cv.cvtColor(src, gray, cv.COLOR_RGBA2GRAY);
      cv.Laplacian(gray, lap, cv.CV_64F);
      mean   = new cv.Mat();
      stddev = new cv.Mat();
      cv.meanStdDev(lap, mean, stddev);
      blurScore = stddev.data64F[0] ** 2;
    } catch {
      blurScore = 0;
    } finally {
      src?.delete(); gray?.delete(); lap?.delete(); mean?.delete(); stddev?.delete();
    }
  } else {
    const variance = lums.reduce((s, l) => s + (l - avgLum) ** 2, 0) / lums.length;
    blurScore = variance;
  }

  // Classify
  if (avgLum < 50) return { status: "bad",    message: "Too dark — try better lighting.",         blur: blurScore, brightness: avgLum };
  if (avgLum > 245) return { status: "review", message: "Overexposed — try shading slightly.",     blur: blurScore, brightness: avgLum };
  if (blurScore < 30) return { status: "bad",  message: "Too blurry — hold steady and retake.",    blur: blurScore, brightness: avgLum };
  if (blurScore < 80) return { status: "review", message: "Slightly blurry — retake if possible.", blur: blurScore, brightness: avgLum };
  return { status: "good", message: "Looks good.", blur: blurScore, brightness: avgLum };
}

// ── Canvas from dataUrl ───────────────────────────────────────────────────────

export function dataUrlToCanvas(dataUrl: string): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width  = img.naturalWidth;
      canvas.height = img.naturalHeight;
      canvas.getContext("2d")!.drawImage(img, 0, 0);
      resolve(canvas);
    };
    img.onerror = reject;
    img.src = dataUrl;
  });
}

export function canvasToDataUrl(canvas: HTMLCanvasElement, quality = 0.92): string {
  return canvas.toDataURL("image/jpeg", quality);
}

// ── PDF assembly ──────────────────────────────────────────────────────────────

export async function buildScanPdf(
  pages: { dataUrl: string; naturalWidth: number; naturalHeight: number }[]
): Promise<File> {
  const { default: jsPDF } = await import("jspdf");

  // Use portrait A4 for every page
  const doc = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4" });

  for (let i = 0; i < pages.length; i++) {
    if (i > 0) doc.addPage();
    // Fit image to A4 (210 × 297 mm) preserving aspect ratio with letterbox
    const { naturalWidth: iw, naturalHeight: ih } = pages[i];
    const a4W = 210, a4H = 297;
    const scale = Math.min(a4W / iw, a4H / ih);
    const dispW = iw * scale;
    const dispH = ih * scale;
    const offX = (a4W - dispW) / 2;
    const offY = (a4H - dispH) / 2;
    doc.addImage(pages[i].dataUrl, "JPEG", offX, offY, dispW, dispH);
  }

  const blob = doc.output("blob");
  return new File([blob], "scanned_document.pdf", { type: "application/pdf" });
}
