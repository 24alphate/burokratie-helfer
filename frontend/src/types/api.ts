export interface SessionRead {
  session_token: string;
  user_id: string;
  preferred_language: string;
}

export interface CaseRead {
  id: string;
  user_id: string;
  form_template_id: string | null;
  status: CaseStatus;
  current_question_index: number;
  created_at: string;
  updated_at: string;
}

export type CaseStatus =
  | "created" | "uploaded" | "form_selected"
  | "in_progress" | "review" | "completed";

export type InputType =
  | "text" | "date" | "number" | "yes_no"
  | "checkbox" | "radio" | "select" | "multiselect" | "signature";

// Option in a radio/select/checkbox field
export interface FieldOption {
  value: string;   // value written to the PDF (document language, e.g. "verheiratet")
  label: string;   // shown to user (user language, e.g. "Marié(e)")
}

/**
 * Optional human-language guidance for a single field.
 * All values are objects keyed by locale (e.g. { "en": "...", "de": "..." }).
 * Fallback order in the UI: user locale → "en" → "de".
 * This is additive metadata — it never affects field_id, PDF filling, or grounding.
 */
export interface GuidanceText {
  plain_language?: Record<string, string>;
  why_needed?: Record<string, string>;
  where_to_find?: Record<string, string>;
  format_hint?: Record<string, string>;
  example?: Record<string, string>;
  required_documents?: Record<string, string[]>;
  common_mistakes?: Record<string, string[]>;
  warning?: Record<string, string>;
}

// One field from the uploaded PDF, with translated question text and grounding metadata
export interface FieldDefinition {
  key: string;                         // exact PDF widget name
  question: Record<string, string>;    // {user_lang: question text}
  explanation: Record<string, string>;
  input_type: InputType;
  options: FieldOption[];              // for radio/select/checkbox
  original_label: string;              // label as it appears in the document (PDF language)
  document_language: string;
  source_page: number;
  order: number;
  is_prefilled: boolean;
  confidence: number;                  // 1.0 = AcroForm; 0.75 = pdfplumber; 0.5 = ocr
  needs_review: boolean;               // true when confidence in [0.70, 0.90)
  // Grounding metadata
  show_question: boolean;              // false when confidence < 0.70 (question is blocked)
  source_text: string;                 // exact PDF text that grounds this question
  reason: string;                      // "pdf_field" | "derived_helper"
  question_type: string;
  // ── Guidance layer — optional, never affects field_id or PDF filling ──────
  guidance?: GuidanceText | null;
  semantic_key?: string | null;
  // ── Question quality metadata ─────────────────────────────────────────────
  question_source?: string;           // "verified" | "semantic" | "ai" | "deterministic" | "label" | "key"
  question_weak_reasons?: string[];
}

// Accuracy report included with every field extraction
export interface AnalysisReport {
  pdf_type: string;
  total_pages: number;
  field_count: number;               // fields extracted from PDF
  questions_shown: number;           // show_question=true (conf >= 0.70)
  questions_blocked: number;         // show_question=false (conf < 0.70)
  low_confidence_fields: number;     // conf in [0.70, 0.90) — shown but needs_review
  invented_questions_removed: number;
  coverage_rate: string;             // questions_shown / field_count
  grounding_rate: string;            // always "100%"
  grounding_ok: boolean;             // always true
  // Template metadata
  template_id: string | null;        // set when a verified template matched
  extraction_source: string;         // "verified_template" | "acroform" | "pdfplumber" | "ocr" | "auto"
  support_level: number;             // 1=verified | 2=acroform | 3=flat | 4=scanned/unknown
  // Phase D/D2 — AcroForm-specific metrics. Present on every extraction
  // (zeroed for Level 1). Mirrors AnalysisReport.acroform_metrics on the backend.
  acroform_metrics?: {
    text_count: number;
    date_count: number;
    number_count: number;
    checkbox_count: number;
    radio_count: number;
    select_count: number;
    multiselect_count: number;
    signature_count: number;
    fields_missing_bbox: number;
    fields_with_semantic_key: number;
    fields_without_semantic_key: number;
    fields_with_tu_label: number;
    fields_with_weak_label: number;
    duplicate_label_groups: number;
  } | null;
  // Phase D/D2 — fill strategy advertisement.
  // "fitz_overlay" | "acroform" | "summary" | null (extraction-only call)
  fill_strategy?: string | null;
  // Stage 4A/4B — OCR diagnostic.
  //   • Stage 4A: support_level === 4 AND fields = []. The Level-4 unsupported
  //     screen reads diagnostic_status to pick the right user-facing copy.
  //   • Stage 4B: support_level === 3 AND extraction_source === "ocr" AND
  //     fields populated. The diagnostic is attached for transparency so the
  //     UI can show "questions came from OCR — please verify" copy.
  // `technical_message` is intentionally NOT included — backend logs only.
  ocr_diagnostic?: {
    provider: string;            // "tesseract" | "unavailable"
    page_count: number;
    pages: Array<{
      page: number;
      blocks: Array<{ text: string; page: number; bbox: number[]; confidence: number; language?: string | null }>;
      quality: {
        page: number;
        width: number;
        height: number;
        dpi_estimate: number | null;
        text_block_count: number;
        average_confidence: number;
        readable: boolean;
        issues: string[];
      };
    }>;
    full_text: string;
    average_confidence: number;
    detected_languages: string[];
    readable_pages: number;
    unreadable_pages: number;
    diagnostic_status: "readable" | "low_confidence" | "no_text_found" | "ocr_unavailable" | "failed";
    user_message: string;
  } | null;
  // Question quality report
  question_quality?: {
    locale: string;
    total_fields: number;
    strong_questions: number;
    weak_questions: number;
    weak_field_ids: string[];
    weak_reasons_by_field: Record<string, string[]>;
    question_source_counts: Record<string, number>;
    ai_calls_made: number;
    ai_calls_skipped: number;
  } | null;
}

export interface UploadResponse {
  document_id: string;
  detected_form_type: string | null;
  confidence: number;
  requires_manual_selection: boolean;
  prefilled_fields: number;
  fields: FieldDefinition[];
  document_language: string;
  user_language: string;
  analysis_report?: AnalysisReport | null;
  // Authoritative list of field_ids extracted directly from the PDF.
  // Every key in `fields` must appear here. Used as the hard grounding gate.
  extracted_field_ids: string[];
}

// Legacy: used by the ALG II fixed-template select inputs
export interface OptionRead {
  value: string;
  label: Record<string, string>;
}

export interface QuestionRead {
  id: string;
  field_key: string;
  order_index: number;
  input_type: InputType;
  question_text: Record<string, string>;
  explanation_text: Record<string, string>;
  options: OptionRead[] | null;
  answered_count: number;
  total_count: number;
}

export interface CompletedSignal {
  completed: true;
  answered_count: number;
  total_count: number;
}

export interface AnswerRead {
  id: string;
  field_key: string;
  raw_answer: string;
  translated_answer: string | null;
  is_validated: boolean;
  validation_errors: string[];
  is_active: boolean;
}

export interface FormTemplateSummary {
  id: string;
  name: string;
  institution: string;
  version: string;
  supported_languages: string[];
}

export interface PDFGenerateResponse {
  pdf_id: string;
  status: "ready" | "failed";
}

// ── Stateless pipeline types ──────────────────────────────────────────────────

/** One extracted field BEFORE AI translation — extraction ground truth (MODE 2) */
export interface RawFieldEntry {
  field_id: string;
  original_label: string;
  field_type: string;
  source_page: number;
  source_text: string;
  confidence: number;
  source: string;          // "acroform" | "pdfplumber" | "ocr"
  bbox: number[] | null;
  options: string[];
  reason: string;
}

/** Side-by-side original label vs AI question for one field (MODE 3) */
export interface AIComparisonEntry {
  field_id: string;
  original_label: string;  // raw PDF label
  ai_question: string;     // AI output (== original_label when no_ai=true or fallback)
  ai_explanation: string;
  confidence: number;
  ai_used: boolean;
}

/** Response from POST /api/v1/process-pdf */
export interface ProcessPdfResponse {
  fields: FieldDefinition[];
  extracted_field_ids: string[];
  /** Signed JWT — store in Zustand, send with fillPdf() */
  pdf_token: string;
  analysis_report?: AnalysisReport | null;
  filename: string;
  /** Diagnostic: field map BEFORE AI translation */
  raw_extracted_fields: RawFieldEntry[];
  /** Diagnostic: original_label vs AI question for every field */
  ai_comparison: AIComparisonEntry[];
  /** Whether Groq was attempted (false when no_ai=true or GROQ_API_KEY not set) */
  ai_used: boolean;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
