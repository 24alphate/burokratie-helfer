import { test, expect, type Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

/**
 * Level-2 AcroForm end-to-end, in French, for the RMV "Schulausflugticket"
 * Begleitbogen — the form that exposed the translation + choice-field bugs.
 *
 * It proves, in a real browser against the real backend (real Claude calls):
 *   • Feature D (section context): bare fields like "Tag"/"Ort"/"PLZ" become
 *     trip-/school-specific questions, never "the day you fill this form".
 *   • Feature E (option labels): radio groups whose PDF options are export
 *     codes ("0"/"1") show real, translated choices — never "0"/"1" or "we".
 *   • The whole flow still produces a downloadable, valid filled PDF.
 *
 * Assertions are tolerant of AI phrasing variance — they check structure and
 * negative patterns (the old bugs) rather than exact AI wording.
 */
const PDF = path.resolve(__dirname, "fixtures", "Formular_Schulausflugticket.pdf");

const SUBMIT = /Suivant/;

function pickValue(q: string): string {
  const s = q.toLowerCase();
  if (/code postal|postleitzahl|\bplz\b/.test(s)) return "60311";
  if (/jour|\btag\b|\bday\b/.test(s)) return "12";
  if (/mois|monat|month/.test(s)) return "5";
  if (/ann[ée]e|jahr|year/.test(s)) return "2026";
  if (/combien|nombre|anzahl|how many|élèves|personnes/.test(s)) return "25";
  if (/classe|klasse|class/.test(s)) return "4a";
  return "Frankfurt";
}

interface Answered {
  q: string;
  kind: "text" | "date" | "radio" | "yesno";
  options: string[];
}

/** Answer the single visible question; report its text, kind and any options. */
async function answerCurrent(page: Page): Promise<Answered> {
  const q = (await page.locator("h2:visible").first().innerText()).trim();
  const textInput = page.locator('main input[type="text"]');
  const dateInput = page.locator('main input[type="date"]');
  const submit = page.getByRole("button", { name: SUBMIT });

  if (await textInput.count()) {
    await textInput.first().fill(pickValue(q));
    await submit.first().click();
    return { q, kind: "text", options: [] };
  }
  if (await dateInput.count()) {
    await dateInput.first().fill("2026-05-12");
    await submit.first().click();
    return { q, kind: "date", options: [] };
  }
  if (await submit.count()) {
    // RadioInput / SelectInput: option buttons + the submit button share a
    // parent flex container (mirrors the KG1 spec's approach).
    const group = submit.first().locator("xpath=..");
    const buttons = group.getByRole("button");
    const labels: string[] = [];
    const n = await buttons.count();
    for (let i = 0; i < n; i++) {
      const txt = (await buttons.nth(i).innerText()).trim();
      if (!SUBMIT.test(txt)) labels.push(txt.replace(/^[○●☐☑]\s*/, "").trim());
    }
    await buttons.first().click();           // pick the first option
    await submit.first().click();
    return { q, kind: "radio", options: labels };
  }
  // YesNoInput: "Oui" / "Non" — clicking submits immediately.
  await page.getByRole("button", { name: "Oui" }).click();
  return { q, kind: "yesno", options: [] };
}

test("Schulausflug (Level-2 AcroForm) in French: section context + real choice options", async ({ page }, testInfo) => {
  expect(fs.existsSync(PDF), `fixture missing at ${PDF}`).toBeTruthy();

  await test.step("landing → Français → Commencer", async () => {
    await page.goto("/", { waitUntil: "networkidle" });
    await expect(async () => {
      await page.getByRole("button", { name: "Français" }).click();
      await expect(page.getByRole("button", { name: /Commencer/ })).toBeEnabled({ timeout: 1000 });
    }).toPass({ timeout: 15_000 });
    await page.getByRole("button", { name: /Commencer/ }).click();
  });

  await test.step("upload the Schulausflug PDF", async () => {
    await page.waitForURL("**/upload");
    await page.getByText("Téléverser un PDF", { exact: true }).click();   // choose → upload mode
    const fileInput = page.locator('input[type="file"]');
    await fileInput.waitFor({ state: "attached" });
    await fileInput.setInputFiles(PDF);
  });

  await test.step("questions render (Level 2 — real fillable fields)", async () => {
    await page.waitForURL("**/questions");
    await page.getByRole("button", { name: SUBMIT }).first().waitFor({ timeout: 60_000 });
  });

  const answered: Answered[] = [];
  await test.step("walk and answer every question", async () => {
    for (let i = 0; i < 40; i++) {
      if (page.url().includes("/review")) break;
      const prev = (await page.locator("h2:visible").first().innerText()).trim();
      answered.push(await answerCurrent(page));
      await page
        .waitForFunction((p) => {
          if (location.pathname.includes("/review")) return true;
          const vis = [...document.querySelectorAll("h2")].filter((h) => (h as HTMLElement).offsetParent !== null);
          return vis.length > 0 && (vis[0] as HTMLElement).innerText.trim() !== p;
        }, prev, { timeout: 20_000 })
        .catch(() => {});
    }
    await page.waitForURL("**/review", { timeout: 20_000 });
  });

  const questions = answered.map((a) => a.q);
  const radios = answered.filter((a) => a.kind === "radio");
  await testInfo.attach("questions-asked.txt", {
    body: answered.map((a, i) => `${i + 1}. [${a.kind}] ${a.q}${a.options.length ? "\n     options: " + JSON.stringify(a.options) : ""}`).join("\n"),
    contentType: "text/plain",
  });

  await test.step("Feature E — radios show real translated choices, never 0/1 or 'we'", async () => {
    expect(radios.length, "at least one radio/select question rendered").toBeGreaterThanOrEqual(1);
    for (const r of radios) {
      expect(r.options.length, `radio "${r.q}" has options`).toBeGreaterThanOrEqual(2);
      for (const o of r.options) {
        expect(o, "option is not the raw export code").not.toMatch(/^[01]$/);
        expect(o.toLowerCase(), "option is not the junk 'we' tooltip").not.toBe("we");
      }
      // At least one option carries a real word (≥4 letters), i.e. a label not a code.
      expect(r.options.some((o) => /[A-Za-zÀ-ÿ]{4,}/.test(o)), `radio "${r.q}" has a worded option`).toBeTruthy();
    }
  });

  await test.step("Feature D — section context fixed the bare-word questions", async () => {
    const joined = questions.join(" || ");
    expect(joined, "school fields became school-specific (école)").toMatch(/école/i);
    expect(joined, "date fields are NOT mislabelled as 'filling this form'").not.toMatch(/remplissez-vous ce formulaire/i);
    for (const q of questions) {
      expect(q.trim().toLowerCase(), "no raw junk label leaked through").not.toBe("we");
    }
  });

  await test.step("generate & download a valid filled PDF", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /Générer/i }).click(),
    ]);
    const out = testInfo.outputPath("schulausflug-filled.pdf");
    await download.saveAs(out);
    const buf = fs.readFileSync(out);
    expect(buf.subarray(0, 4).toString("latin1"), "starts with %PDF").toBe("%PDF");
    expect(buf.length, "filled PDF is non-trivial").toBeGreaterThan(10_000);
    await testInfo.attach("schulausflug-filled.pdf", { path: out, contentType: "application/pdf" });
  });
});
