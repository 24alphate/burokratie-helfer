import { pickInputKind } from "@/lib/inputKind";
import { InputType } from "@/types/api";

describe("pickInputKind", () => {
  it("choice fields with options render as radio (multi handled by caller)", () => {
    const choices: InputType[] = ["radio", "select", "checkbox", "yes_no", "multiselect"];
    for (const t of choices) {
      expect(pickInputKind(t, true, false)).toBe("radio");
    }
  });

  it("option-less radio/select/multiselect fall back to text (never nothing)", () => {
    expect(pickInputKind("radio", false, false)).toBe("text");
    expect(pickInputKind("select", false, false)).toBe("text");
    expect(pickInputKind("multiselect", false, false)).toBe("text");
  });

  it("checkbox / yes_no without options become yes/no", () => {
    expect(pickInputKind("checkbox", false, false)).toBe("yesno");
    expect(pickInputKind("yes_no", false, false)).toBe("yesno");
  });

  it("date is always date, regardless of options", () => {
    expect(pickInputKind("date", false, false)).toBe("date");
    expect(pickInputKind("date", true, false)).toBe("date");
  });

  it("legacy ALG II select (OptionRead[]) uses the dedicated select", () => {
    expect(pickInputKind("select", false, true)).toBe("select-legacy");
  });

  it("text / number / signature render as text", () => {
    expect(pickInputKind("text", false, false)).toBe("text");
    expect(pickInputKind("number", false, false)).toBe("text");
    expect(pickInputKind("signature", false, false)).toBe("text");
  });
});
