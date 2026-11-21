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
  request,
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

  // A stale error banner must not survive sign-out.
  await page.getByLabel("Question").fill("");
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  await expect(page.locator("#errors")).toHaveText("Enter a question first.");

  const revokedToken = await page.evaluate(() =>
    sessionStorage.getItem("uqa_token"),
  );
  expect(revokedToken).toBeTruthy();

  await signOutViaUi(page);
  await expect(page.locator("#errors")).toBeEmpty();

  const revokedHeaders = { Authorization: `Bearer ${revokedToken}` };
  const meStatus = await request.get("/auth/me", {
    headers: revokedHeaders,
  });
  expect(meStatus.status()).toBe(401);
  const askStatus = await request.post("/ask", {
    headers: revokedHeaders,
    data: { question: "indoor air purifier" },
  });
  expect(askStatus.status()).toBe(401);

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

test("offline sign-out clears local state and stays local", async ({ page }) => {
  await registerViaUi(page, uniqueEmail("offline-logout"));
  await page.route("**/auth/logout", (route) => route.abort());
  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(
    page.getByText("Signed out on this device.", { exact: true }),
  ).toBeVisible();
  await expect(page.locator("#errors")).toBeEmpty();
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
  expect(
    await page.evaluate(() => sessionStorage.getItem("uqa_token")),
  ).toBeNull();

  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
});
