import { mkdirSync, statSync } from "node:fs";
import path from "node:path";
import { expect, test, type Page } from "@playwright/test";
import {
  askQuestion,
  expectCitation,
  PASSWORD,
  saveDelhiProfile,
  savePoorBandAndFetch,
  uploadPdf,
} from "../support/app";

const OUTPUT = path.resolve(__dirname, "../../docs/screenshots");
const UPDATE = process.env.UPDATE_SCREENSHOTS === "1";
const SCREENSHOTS = [
  "home.png",
  "register.png",
  "dashboard-aqi.png",
  "grounded-answer.png",
  "documents.png",
  "mobile-dashboard.png",
] as const;

/** Remove focus rings/carets so the evidence images show the resting UI. */
async function blurActiveElement(page: Page): Promise<void> {
  await page.evaluate(() => {
    const active = document.activeElement;
    if (active instanceof HTMLElement) {
      active.blur();
    }
  });
}

test("documented screenshots are present and stable", async ({ page }) => {
  if (!UPDATE) {
    for (const name of SCREENSHOTS) {
      const stats = statSync(path.join(OUTPUT, name));
      expect(stats.isFile()).toBe(true);
      expect(stats.size).toBeGreaterThan(0);
    }
    return;
  }

  test.slow();
  mkdirSync(OUTPUT, { recursive: true });

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
  await expect(page.locator("#errors")).toBeEmpty();
  await blurActiveElement(page);
  await page.screenshot({
    path: path.join(OUTPUT, "home.png"),
    fullPage: true,
    animations: "disabled",
  });

  const email = "asha.delhi@example.com";
  await page.locator("#register-form").getByLabel("Email").fill(email);
  await page
    .locator("#register-form")
    .getByLabel("Password")
    .fill(PASSWORD);
  await blurActiveElement(page);
  await page.locator("#auth-card").screenshot({
    path: path.join(OUTPUT, "register.png"),
    animations: "disabled",
  });

  await page.getByRole("button", { name: "Create account" }).click();
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();

  await saveDelhiProfile(page);
  await savePoorBandAndFetch(page);
  await blurActiveElement(page);
  await page
    .locator("#air-panel")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  await page.screenshot({
    path: path.join(OUTPUT, "dashboard-aqi.png"),
    animations: "disabled",
  });

  await askQuestion(page, "indoor air purifier");
  await expectCitation(page);
  await blurActiveElement(page);
  await page.locator("#ask").screenshot({
    path: path.join(OUTPUT, "grounded-answer.png"),
    animations: "disabled",
  });

  await uploadPdf(page);
  await blurActiveElement(page);
  await page.locator("#documents").screenshot({
    path: path.join(OUTPUT, "documents.png"),
    animations: "disabled",
  });

  await page.setViewportSize({ width: 375, height: 812 });
  await blurActiveElement(page);
  await page
    .locator("#air-panel")
    .evaluate((element) => element.scrollIntoView({ block: "start" }));
  await page.screenshot({
    path: path.join(OUTPUT, "mobile-dashboard.png"),
    animations: "disabled",
  });
});
