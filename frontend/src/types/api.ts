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

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
