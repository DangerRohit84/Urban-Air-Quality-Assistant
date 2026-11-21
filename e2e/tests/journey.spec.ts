import { expect, test } from "@playwright/test";
import {
  askQuestion,
  expectCitation,
  PASSWORD,
  registerViaUi,
  saveDelhiProfile,
  savePoorBandAndFetch,
  signInViaUi,
  signOutViaUi,
  uniqueEmail,
  uploadPdf,
} from "../support/app";

test("register, personalize, fetch AQI, ask, upload and sign out", async ({
  page,
}) => {
  const email = uniqueEmail("journey");

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();

  await registerViaUi(page, email);
  await saveDelhiProfile(page);
  await savePoorBandAndFetch(page);

  await askQuestion(page, "indoor air purifier");
  await expect(
    page.getByText("Answered from the corpus.", { exact: true }),
  ).toBeVisible();
  await expectCitation(page);
  await expect(page.locator("#answer-text")).toContainText(/Sources: \[seed-/);

  await askQuestion(page, "Who won the 2018 world cup?");
  await expect(
    page.getByText("No corpus support found.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("This question is outside the air-quality guidance corpus."),
  ).toBeVisible();
  await expect(page.locator("#citations li")).toHaveCount(0);

  await uploadPdf(page);
  await expect(
    page.getByText("Document added to your corpus.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.locator("#docs-list li").filter({ hasText: "delhi-air-notes.pdf" }),
  ).toBeVisible();

  await signOutViaUi(page);
  const meStatus = await page.evaluate(
    async () => (await fetch("/auth/me")).status,
  );
  expect(meStatus).toBe(401);
  const plansStatus = await page.evaluate(
    async () => (await fetch("/plans")).status,
  );
  expect(plansStatus).toBe(401);

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeHidden();

  await signInViaUi(page, email, PASSWORD);
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();
});
