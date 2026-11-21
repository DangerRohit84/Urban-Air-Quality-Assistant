import { mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import {
  askQuestion,
  expectCitation,
  PASSWORD,
  saveDelhiProfile,
  savePoorBandAndFetch,
  uploadPdf,
} from "../support/app";

const OUTPUT = path.resolve(__dirname, "../../docs/screenshots");

test("capture the documented screenshots", async ({ page }) => {
  test.slow();
  mkdirSync(OUTPUT, { recursive: true });

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
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
  await page.locator("#air-panel").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(OUTPUT, "dashboard-aqi.png"),
    animations: "disabled",
  });

  await askQuestion(page, "indoor air purifier");
  await expectCitation(page);
  await page.locator("#ask").screenshot({
    path: path.join(OUTPUT, "grounded-answer.png"),
    animations: "disabled",
  });

  await uploadPdf(page);
  await page.locator("#documents").screenshot({
    path: path.join(OUTPUT, "documents.png"),
    animations: "disabled",
  });

  await page.setViewportSize({ width: 375, height: 812 });
  await page.locator("#air-panel").scrollIntoViewIfNeeded();
  await page.screenshot({
    path: path.join(OUTPUT, "mobile-dashboard.png"),
    animations: "disabled",
  });
});
