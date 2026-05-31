import { evaluateCondition } from "@/lib/conditions";
import type { FieldCondition } from "@/types/api";

describe("evaluateCondition", () => {
  const A = { status: "verheiratet", owner: "andere Person" };

  it("null/undefined condition → always shown", () => {
    expect(evaluateCondition(null, A)).toBe(true);
    expect(evaluateCondition(undefined, A)).toBe(true);
  });

  it("field_equals", () => {
    expect(evaluateCondition({ type: "field_equals", field_key: "status", value: "verheiratet" }, A)).toBe(true);
    expect(evaluateCondition({ type: "field_equals", field_key: "status", value: "ledig" }, A)).toBe(false);
  });

  it("field_not_equals requires the field to be answered", () => {
    // answered + different → true
    expect(evaluateCondition({ type: "field_not_equals", field_key: "status", value: "ledig" }, A)).toBe(true);
    // answered + same → false
    expect(evaluateCondition({ type: "field_not_equals", field_key: "status", value: "verheiratet" }, A)).toBe(false);
    // unanswered → false (matches backend: a null answer does not satisfy a "not")
    expect(evaluateCondition({ type: "field_not_equals", field_key: "missing", value: "x" }, A)).toBe(false);
  });

  it("field_in / field_not_in", () => {
    expect(evaluateCondition({ type: "field_in", field_key: "status", values: ["verheiratet", "Lebenspartnerschaft"] }, A)).toBe(true);
    expect(evaluateCondition({ type: "field_in", field_key: "status", values: ["ledig"] }, A)).toBe(false);
    expect(evaluateCondition({ type: "field_not_in", field_key: "status", values: ["ledig"] }, A)).toBe(true);
    // unanswered → false
    expect(evaluateCondition({ type: "field_not_in", field_key: "missing", values: ["ledig"] }, A)).toBe(false);
  });

  it("and / or nesting", () => {
    const and: FieldCondition = {
      type: "and",
      conditions: [
        { type: "field_equals", field_key: "status", value: "verheiratet" },
        { type: "field_equals", field_key: "owner", value: "andere Person" },
      ],
    };
    expect(evaluateCondition(and, A)).toBe(true);

    const or: FieldCondition = {
      type: "or",
      conditions: [
        { type: "field_equals", field_key: "status", value: "ledig" },
        { type: "field_equals", field_key: "owner", value: "andere Person" },
      ],
    };
    expect(evaluateCondition(or, A)).toBe(true);
    expect(evaluateCondition({ type: "and", conditions: [{ type: "field_equals", field_key: "status", value: "ledig" }] }, A)).toBe(false);
  });

  it("unknown condition type → safe default (shown)", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(evaluateCondition({ type: "bogus" } as any, A)).toBe(true);
  });
});
