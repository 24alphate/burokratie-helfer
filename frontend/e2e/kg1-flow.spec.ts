import { test, expect, type Page } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";

// The official KG1 PDF lives at the repo root (../../ from frontend/e2e).
const KG1_PDF = path.resolve(__dirname, "..", "..", "templates_source", "familienkasse_kg1_v1.pdf");

// Pick a plausible value for a free-text question so the generated PDF is sane.
function pickValue(q: string): string {
  const s = q.toLowerCase();
  if (/steuer|identifikation|tax/.test(s)) return "12345678901"; // 11-digit Steuer-ID
  if (/iban/.test(s)) return "DE89370400440532013000";
  if (/\bbic\b|swift/.test(s)) return "COBADEFFXXX";
  if (/date|datum|geburt|birth|seit|since/.test(s)) return "15.03.1985";
  if (/first name|vorname/.test(s)) return "Anna";
  if (/family name|nachname|last name/.test(s)) return "Müller";
  if (/address|anschrift/.test(s)) return "Hauptstraße 12, 18055 Rostock";
  if (/phone|telefon/.test(s)) return "0151 12345678";
  if (/how many|anzahl/.test(s)) return "1";
  return "Test";
}

// Answer the single visible question. For radios/selects we always click the
// FIRST option, which for KG1 is exactly the "ledig" / "Antragsteller" / "m"
// persona we want to assert against.
async function answerCurrentQuestion(page: Page): Promise<void> {
  const nextBtn = page.getByRole("button", { name: "Next →" });
  const textInput = page.locator('main input[type="text"]');
  const dateInput = page.locator('main input[type="date"]');

  if (await textInput.count()) {
    const q = (await page.locator("h2:visible").first().innerText()).trim();
    await textInput.first().fill(pickValue(q));
  } else if (await dateInput.count()) {
    await dateInput.first().fill("1985-03-15");
  } else {
    // radio/select: option buttons share the Next button's flex container.
    await nextBtn.locator("xpath=..").getByRole("button").first().click();
  }
  await nextBtn.click();
}

test("KG1 ledig persona: conditional flow + Steuer-ID, end to end", async ({ page }, testInfo) => {
  expect(fs.existsSync(KG1_PDF), `KG1 fixture missing at ${KG1_PDF}`).toBeTruthy();

  await test.step("landing → choose English → Start", async () => {
    await page.goto("/", { waitUntil: "networkidle" });
    // Re-click English until Start enables (absorbs the React hydration race).
    await expect(async () => {
      await page.getByRole("button", { name: "English" }).click();
      await expect(page.getByRole("button", { name: /start/i })).toBeEnabled({ timeout: 1000 });
    }).toPass({ timeout: 15_000 });
    await page.getByRole("button", { name: /start/i }).click();
  });

  await test.step("upload the KG1 PDF", async () => {
    await page.waitForURL("**/upload");
    await page.getByText("Upload PDF", { exact: true }).click();
    const fileInput = page.locator('input[type="file"]');
    await fileInput.waitFor({ state: "attached" });
    await fileInput.setInputFiles(KG1_PDF);
  });

  await test.step("Level-1 verified banner appears", async () => {
    await page.waitForURL("**/questions");
    await page.getByRole("button", { name: "Next →" }).waitFor({ timeout: 45_000 });
    await expect(page.getByText(/verified form/i)).toBeVisible();
  });

  // Walk the whole applicable flow, recording every question asked.
  const asked: string[] = [];
  let sawSteuerId = false;
  await test.step("answer the applicable questions", async () => {
    for (let i = 0; i < 90; i++) {
      if (page.url().includes("/review")) break;
      const q = (await page.locator("h2:visible").first().innerText()).trim();
      asked.push(q);
      if (/steuer|identifikation|tax/i.test(q)) sawSteuerId = true;
      await answerCurrentQuestion(page);
      await page
        .waitForFunction((prev) => {
          if (location.pathname.includes("/review")) return true;
          const vis = [...document.querySelectorAll("h2")].filter((h) => (h as HTMLElement).offsetParent !== null);
          return vis.length > 0 && (vis[0] as HTMLElement).innerText.trim() !== prev;
        }, q, { timeout: 15_000 })
        .catch(() => {});
    }
    await page.waitForURL("**/review");
  });

  await testInfo.attach("questions-asked.txt", {
    body: asked.map((q, i) => `${i + 1}. ${q}`).join("\n"),
    contentType: "text/plain",
  });

  await test.step("conditional flow hid the right sections", async () => {
    const joined = asked.join(" || ");
    // No real partner fields ("…your partner's…"); the word "partner" in the
    // signature-date hint ("e.g. partner)") must not count.
    expect(joined, "no partner questions for a single applicant").not.toMatch(/partner['’]s|your partner|des partners/i);
    expect(joined, 'no "marital status since" for ledig').not.toMatch(/since when|marital status since|familienstand seit/i);
    expect(joined, "no abweichende-Person for own-account").not.toMatch(/alternative account holder|abweichende/i);
    expect(sawSteuerId, "Steuer-ID was asked once").toBeTruthy();
    expect(asked.length, "applicable count dropped well below the full 54").toBeLessThan(54);
    expect(asked.length, "applicable count is plausible").toBeGreaterThanOrEqual(25);
  });

  await test.step("generate & download a valid filled PDF", async () => {
    const [download] = await Promise.all([
      page.waitForEvent("download"),
      page.getByRole("button", { name: /generate/i }).click(),
    ]);
    const out = testInfo.outputPath("kg1-filled.pdf");
    await download.saveAs(out);
    const buf = fs.readFileSync(out);
    expect(buf.subarray(0, 4).toString("latin1"), "starts with %PDF magic").toBe("%PDF");
    expect(buf.length, "filled PDF is non-trivial").toBeGreaterThan(20_000);
    await testInfo.attach("kg1-filled.pdf", { path: out, contentType: "application/pdf" });
  });
});
