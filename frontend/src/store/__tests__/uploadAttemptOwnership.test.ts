/**
 * Tests for the upload-attempt ownership fix.
 *
 * Core bug being tested:
 *   1. User uploads PDF A → fields stored with attemptId "A"
 *   2. User uploads PDF B → beginNewUpload() generates attemptId "B", clears fields
 *   3. PDF B fails → fields stay empty, fieldsForUploadAttemptId stays null
 *   4. User navigates to /questions
 *   5. Guard: "B" !== null → blocked → redirect to upload
 *
 * Previously the guard only checked fieldsForCaseId === caseId, which passed
 * because both came from the same session. PDF A's questions were shown.
 *
 * These tests verify the store logic in isolation (no React, no router).
 */

// Simulate the store logic without full Zustand wiring.
// These are pure function tests extracted from the store actions.

const FAKE_FIELD = {
  key: "name_vorname",
  question: { en: "What is your name?" },
  explanation: { en: "" },
  input_type: "text" as const,
  options: [],
  original_label: "Name, Vorname",
  document_language: "de",
  source_page: 1,
  order: 1,
  is_prefilled: false,
  confidence: 0.75,
  needs_review: true,
  show_question: true,
  source_text: "Name, Vorname",
  reason: "pdf_field",
  question_type: "pdf_field",
};

// ── Simulated store state ──────────────────────────────────────────────────────

interface StoreState {
  uploadAttemptId: string | null;
  fieldsForUploadAttemptId: string | null;
  fields: typeof FAKE_FIELD[];
  extractedFieldIds: string[];
  pdfToken: string | null;
  answeredValues: Record<string, string>;
  answeredKeys: string[];
  documentId: string | null;
  fieldsForCaseId: string | null;
  currentFilename: string | null;
  currentFileSize: number | null;
  currentFileLastModified: number | null;
}

function emptyState(): StoreState {
  return {
    uploadAttemptId: null,
    fieldsForUploadAttemptId: null,
    fields: [],
    extractedFieldIds: [],
    pdfToken: null,
    answeredValues: {},
    answeredKeys: [],
    documentId: null,
    fieldsForCaseId: null,
    currentFilename: null,
    currentFileSize: null,
    currentFileLastModified: null,
  };
}

// Simulates beginNewUpload() store action
function beginNewUpload(
  state: StoreState,
  params: { filename: string; fileSize: number; fileLastModified: number },
): [StoreState, string] {
  const id = `attempt-${Math.random().toString(36).slice(2)}`;
  return [
    {
      ...state,
      uploadAttemptId: id,
      fieldsForUploadAttemptId: null,   // NOT set until setFields() succeeds
      fields: [],
      extractedFieldIds: [],
      pdfToken: null,
      answeredValues: {},
      answeredKeys: [],
      documentId: null,
      fieldsForCaseId: null,
      currentFilename: params.filename,
      currentFileSize: params.fileSize,
      currentFileLastModified: params.fileLastModified,
    },
    id,
  ];
}

// Simulates setFields() — only called on successful /process-pdf response
function setFields(
  state: StoreState,
  fields: typeof FAKE_FIELD[],
  caseId: string,
  documentId: string,
  extractedFieldIds: string[],
  uploadAttemptId: string,
): StoreState {
  return {
    ...state,
    fields,
    fieldsForCaseId: caseId,
    documentId,
    extractedFieldIds,
    fieldsForUploadAttemptId: uploadAttemptId,  // now they match
    answeredKeys: [],
    answeredValues: {},
  };
}

// Simulates the questions page ownership guard
function ownershipGuardPasses(state: StoreState): boolean {
  const hasFields    = state.fields.length > 0;
  const hasExtracted = state.extractedFieldIds.length > 0;
  const hasToken     = state.pdfToken !== null;
  const attemptMatch = state.fieldsForUploadAttemptId !== null
                       && state.uploadAttemptId !== null
                       && state.fieldsForUploadAttemptId === state.uploadAttemptId;
  return hasFields && hasExtracted && hasToken && attemptMatch;
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe("Upload attempt ownership — core bug fix", () => {

  // ── Scenario 1: Core bug scenario ────────────────────────────────────────
  test("PDF A fields do not leak when PDF B upload fails", () => {
    let state = emptyState();

    // Upload PDF A — succeeds
    let attemptAId: string;
    [state, attemptAId] = beginNewUpload(state, { filename: "form_a.pdf", fileSize: 100, fileLastModified: 1000 });
    state = setFields(state, [FAKE_FIELD], "case-1", "form_a.pdf", ["name_vorname"], attemptAId);
    state = { ...state, pdfToken: "token-a" };

    expect(ownershipGuardPasses(state)).toBe(true); // PDF A questions shown correctly

    // Upload PDF B — fails (beginNewUpload clears state, setFields never called)
    let attemptBId: string;
    [state, attemptBId] = beginNewUpload(state, { filename: "form_b.pdf", fileSize: 200, fileLastModified: 2000 });
    // Simulate failure: do NOT call setFields or setPdfToken

    // Navigate to /questions: guard must block
    expect(state.fields).toHaveLength(0);                  // cleared by beginNewUpload
    expect(state.extractedFieldIds).toHaveLength(0);       // cleared
    expect(state.pdfToken).toBeNull();                     // cleared
    expect(state.fieldsForUploadAttemptId).toBeNull();     // never set (upload failed)
    expect(state.uploadAttemptId).toBe(attemptBId);        // current attempt

    expect(ownershipGuardPasses(state)).toBe(false);       // BLOCKED
  });

  // ── Scenario 2: Race condition ────────────────────────────────────────────
  test("stale response from PDF A is ignored when PDF B is already in flight", () => {
    let state = emptyState();

    // User drops PDF A — upload starts
    let attemptAId: string;
    [state, attemptAId] = beginNewUpload(state, { filename: "a.pdf", fileSize: 100, fileLastModified: 1 });

    // User immediately drops PDF B — before A's response arrives
    let attemptBId: string;
    [state, attemptBId] = beginNewUpload(state, { filename: "b.pdf", fileSize: 200, fileLastModified: 2 });

    // Now PDF A's response arrives — the race condition check in upload/page.tsx:
    //   currentAttemptId = state.uploadAttemptId = attemptBId
    //   attemptAId !== attemptBId → discard PDF A's response
    const raceCheckPassesForA = state.uploadAttemptId === attemptAId;
    expect(raceCheckPassesForA).toBe(false); // PDF A response must be discarded

    // PDF B's response arrives — race check passes
    const raceCheckPassesForB = state.uploadAttemptId === attemptBId;
    expect(raceCheckPassesForB).toBe(true);

    // Apply PDF B's result
    state = setFields(state, [FAKE_FIELD], "case-1", "b.pdf", ["name_vorname"], attemptBId);
    state = { ...state, pdfToken: "token-b" };

    expect(ownershipGuardPasses(state)).toBe(true);
    expect(state.currentFilename).toBe("b.pdf");           // B's identity
    expect(state.fieldsForUploadAttemptId).toBe(attemptBId); // B's attemptId
  });

  // ── Scenario 3: Attempt ID mismatch blocks questions ─────────────────────
  test("fieldsForUploadAttemptId mismatch blocks questions even with valid fields", () => {
    let state = emptyState();

    // Manually construct a state where fields exist but attemptIds don't match
    // (This simulates a corrupted / legacy localStorage state)
    let attemptId: string;
    [state, attemptId] = beginNewUpload(state, { filename: "x.pdf", fileSize: 1, fileLastModified: 1 });

    state = {
      ...state,
      fields: [FAKE_FIELD],
      extractedFieldIds: ["name_vorname"],
      pdfToken: "some-token",
      fieldsForUploadAttemptId: "old-attempt-id",  // does NOT match current uploadAttemptId
    };

    expect(state.uploadAttemptId).toBe(attemptId);
    expect(state.fieldsForUploadAttemptId).toBe("old-attempt-id");
    expect(state.uploadAttemptId).not.toBe("old-attempt-id");

    expect(ownershipGuardPasses(state)).toBe(false); // BLOCKED
  });

  // ── Successful upload: all checks pass ───────────────────────────────────
  test("successful upload: all guard conditions pass", () => {
    let state = emptyState();
    let attemptId: string;
    [state, attemptId] = beginNewUpload(state, { filename: "form.pdf", fileSize: 500, fileLastModified: 999 });
    state = setFields(state, [FAKE_FIELD], "case-123", "form.pdf", ["name_vorname"], attemptId);
    state = { ...state, pdfToken: "valid-token" };

    expect(ownershipGuardPasses(state)).toBe(true);
  });

  // ── beginNewUpload always clears fields ───────────────────────────────────
  test("beginNewUpload clears fields, token, answers, and extractedFieldIds", () => {
    let state = emptyState();
    let id: string;

    // First upload succeeds
    [state, id] = beginNewUpload(state, { filename: "a.pdf", fileSize: 1, fileLastModified: 1 });
    state = setFields(state, [FAKE_FIELD], "case-1", "a.pdf", ["name_vorname"], id);
    state = { ...state, pdfToken: "token", answeredValues: { name_vorname: "Max" }, answeredKeys: ["name_vorname"] };

    expect(state.fields).toHaveLength(1);
    expect(state.pdfToken).toBe("token");
    expect(state.answeredKeys).toHaveLength(1);

    // Second upload begins — must clear everything
    [state, id] = beginNewUpload(state, { filename: "b.pdf", fileSize: 2, fileLastModified: 2 });

    expect(state.fields).toHaveLength(0);
    expect(state.extractedFieldIds).toHaveLength(0);
    expect(state.pdfToken).toBeNull();
    expect(state.answeredValues).toEqual({});
    expect(state.answeredKeys).toHaveLength(0);
    expect(state.fieldsForUploadAttemptId).toBeNull(); // not set until success
    expect(state.uploadAttemptId).toBe(id);            // new attempt ID
  });

  // ── Empty extractedFieldIds blocks questions ──────────────────────────────
  test("empty extractedFieldIds blocks questions even if fields exist", () => {
    let state = emptyState();
    let id: string;
    [state, id] = beginNewUpload(state, { filename: "f.pdf", fileSize: 1, fileLastModified: 1 });

    // Manually inject fields but leave extractedFieldIds empty (legacy state)
    state = {
      ...state,
      fields: [FAKE_FIELD],
      extractedFieldIds: [],           // empty — no grounding proof
      pdfToken: "token",
      fieldsForUploadAttemptId: id,
    };

    expect(ownershipGuardPasses(state)).toBe(false); // BLOCKED — no grounding
  });

  // ── Missing pdfToken blocks questions ─────────────────────────────────────
  test("missing pdfToken blocks questions even with grounded fields", () => {
    let state = emptyState();
    let id: string;
    [state, id] = beginNewUpload(state, { filename: "f.pdf", fileSize: 1, fileLastModified: 1 });
    state = setFields(state, [FAKE_FIELD], "case-1", "f.pdf", ["name_vorname"], id);
    // pdfToken intentionally not set

    expect(state.pdfToken).toBeNull();
    expect(ownershipGuardPasses(state)).toBe(false); // BLOCKED
  });
});
