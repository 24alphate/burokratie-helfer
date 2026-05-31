import {
  getGroundedFields,
  getApplicableQuestionFields,
  getApplicableAnswers,
} from "@/lib/applicableFields";
import type { FieldDefinition } from "@/types/api";

// Minimal FieldDefinition factory (jest.config has strict:false).
function field(partial: Partial<FieldDefinition> & { key: string }): FieldDefinition {
  return {
    question: {},
    explanation: {},
    input_type: "text",
    options: [],
    original_label: partial.key,
    document_language: "de",
    source_page: 1,
    order: 0,
    is_prefilled: false,
    confidence: 1.0,
    needs_review: false,
    show_question: true,
    source_text: "",
    reason: "pdf_field",
    question_type: "pdf_field",
    ...partial,
  } as FieldDefinition;
}

// A KG1-shaped mini form: a gating radio + a partner field gated on it.
const STATUS = field({ key: "status" });
const PARTNER = field({
  key: "partner_name",
  condition: { type: "field_in", field_key: "status", values: ["verheiratet", "Lebenspartnerschaft"] },
});
const PREFILLED = field({ key: "prefilled", is_prefilled: true });
const BLOCKED = field({ key: "blocked", show_question: false });
const FIELDS = [STATUS, PARTNER, PREFILLED, BLOCKED];
const EXTRACTED = ["status", "partner_name", "prefilled", "blocked"];

describe("getGroundedFields", () => {
  it("keeps only fields present in extractedFieldIds", () => {
    const out = getGroundedFields([...FIELDS, field({ key: "ghost" })], EXTRACTED);
    expect(out.map((f) => f.key).sort()).toEqual(["blocked", "partner_name", "prefilled", "status"]);
  });

  it("returns nothing when extracted list is empty", () => {
    expect(getGroundedFields(FIELDS, [])).toEqual([]);
  });
});

describe("getApplicableQuestionFields", () => {
  it("hides conditional fields whose gate is unsatisfied", () => {
    const keys = getApplicableQuestionFields(FIELDS, EXTRACTED, { status: "ledig" }).map((f) => f.key);
    expect(keys).toContain("status");
    expect(keys).not.toContain("partner_name"); // gate not met
    expect(keys).not.toContain("prefilled");     // is_prefilled
    expect(keys).not.toContain("blocked");        // show_question=false
  });

  it("reveals conditional fields once the gate is satisfied", () => {
    const keys = getApplicableQuestionFields(FIELDS, EXTRACTED, { status: "verheiratet" }).map((f) => f.key);
    expect(keys).toContain("partner_name");
  });
});

describe("getApplicableAnswers", () => {
  it("drops a stale answer when a later answer turns its gate off", () => {
    // User picked verheiratet, answered the partner name, then switched to ledig.
    const answers = { status: "ledig", partner_name: "Müller" };
    const out = getApplicableAnswers(FIELDS, EXTRACTED, answers);
    expect(out).toEqual({ status: "ledig" }); // partner_name dropped
  });

  it("keeps the answer when the gate holds", () => {
    const answers = { status: "verheiratet", partner_name: "Müller" };
    const out = getApplicableAnswers(FIELDS, EXTRACTED, answers);
    expect(out).toEqual({ status: "verheiratet", partner_name: "Müller" });
  });

  it("drops answers whose key is not grounded", () => {
    const answers = { status: "ledig", ghost: "x" };
    const out = getApplicableAnswers(FIELDS, EXTRACTED, answers);
    expect(out).toEqual({ status: "ledig" });
  });
});
