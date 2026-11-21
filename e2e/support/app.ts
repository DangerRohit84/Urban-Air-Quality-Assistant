import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { textPdf } from "./pdf";

export const PASSWORD = "TestPass123";

export interface SeededUser {
  email: string;
  password: string;
  token: string;
}

export interface ProfilePayload {
  city: string;
  climate_zone: string;
  children: boolean;
  elderly: boolean;
  respiratory: boolean;
  commute_mode: string;
  commute_km: number;
  cooking_fuel: string;
  heating_type: string;
  budget_level: string;
}

export const DELHI_PROFILE: ProfilePayload = {
  city: "Delhi",
  climate_zone: "north",
  children: true,
  elderly: false,
  respiratory: true,
  commute_mode: "car",
  commute_km: 12,
  cooking_fuel: "lpg",
  heating_type: "none",
  budget_level: "medium",
};

const PDF_TEXT =
  "Delhi household notes: run a HEPA purifier in the bedroom and keep doors closed.";

export function uniqueEmail(prefix: string): string {
  const stamp = `${Date.now()}.${Math.floor(Math.random() * 1_000_000)}`;
  return `${prefix}.${stamp}@example.com`;
}

function auth(token: string): Record<string, string> {
  return { Authorization: `Bearer ${token}` };
}

function isRequest(
  response: { request(): { method(): string }; url(): string },
  method: string,
  pathname: string,
): boolean {
  return (
    response.request().method() === method &&
    new URL(response.url()).pathname === pathname
  );
}

export async function seedUser(
  request: APIRequestContext,
  prefix: string,
): Promise<SeededUser> {
  const email = uniqueEmail(prefix);
  const response = await request.post("/auth/register", {
    data: { email, password: PASSWORD },
  });
  expect(response.status()).toBe(201);
  const body = (await response.json()) as { token: string };
  return { email, password: PASSWORD, token: body.token };
}

export async function seedProfile(
  request: APIRequestContext,
  token: string,
  profile: ProfilePayload = DELHI_PROFILE,
): Promise<void> {
  const response = await request.put("/profile", {
    headers: auth(token),
    data: profile,
  });
  expect(response.status()).toBe(200);
}

export async function seedAirContext(
  request: APIRequestContext,
  token: string,
  band = "Poor",
): Promise<void> {
  const response = await request.post("/air/context", {
    headers: auth(token),
    data: { city: "Delhi", band, season: "winter" },
  });
  expect(response.status()).toBe(200);
}

export async function seedDocument(
  request: APIRequestContext,
  token: string,
  filename = "delhi-air-notes.pdf",
): Promise<void> {
  // The API intentionally rejects a second concurrent upload with 503 and a
  // Retry-After header; parallel specs retry instead of queueing.
  for (let attempt = 0; attempt < 20; attempt += 1) {
    const response = await request.post("/documents/upload", {
      headers: auth(token),
      multipart: {
        file: {
          name: filename,
          mimeType: "application/pdf",
          buffer: textPdf(PDF_TEXT),
        },
      },
    });
    if (response.status() === 201) {
      return;
    }
    if (response.status() === 503) {
      await new Promise((resolve) => setTimeout(resolve, 250));
      continue;
    }
    expect(response.status()).toBe(201);
  }
  throw new Error("document upload kept returning 503");
}

export async function registerViaUi(
  page: Page,
  email: string,
  password = PASSWORD,
): Promise<void> {
  await page.goto("/");
  const form = page.locator("#register-form");
  await form.getByLabel("Email").fill(email);
  await form.getByLabel("Password").fill(password);
  const responsePromise = page.waitForResponse((response) =>
    isRequest(response, "POST", "/auth/register"),
  );
  await form.getByRole("button", { name: "Create account" }).click();
  expect((await responsePromise).status()).toBe(201);
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();
}

export async function signInViaUi(
  page: Page,
  email: string,
  password = PASSWORD,
): Promise<void> {
  await page.goto("/");
  const form = page.locator("#login-form");
  await form.getByLabel("Email").fill(email);
  await form.getByLabel("Password").fill(password);
  const responsePromise = page.waitForResponse((response) =>
    isRequest(response, "POST", "/auth/login"),
  );
  await form.getByRole("button", { name: "Sign in" }).click();
  expect((await responsePromise).status()).toBe(200);
  await expect(
    page.getByRole("heading", { name: "Your profile" }),
  ).toBeVisible();
}

export async function signOutViaUi(page: Page): Promise<void> {
  const responsePromise = page.waitForResponse((response) =>
    isRequest(response, "POST", "/auth/logout"),
  );
  await page.getByRole("button", { name: "Sign out" }).click();
  expect((await responsePromise).status()).toBe(204);
  await expect(page.getByText("Signed out.", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();
}

export async function saveDelhiProfile(page: Page): Promise<void> {
  await page.getByLabel("City").fill(DELHI_PROFILE.city);
  await page
    .getByLabel("Climate zone")
    .selectOption(DELHI_PROFILE.climate_zone);
  await page.getByLabel("Children at home").check();
  await page.getByLabel("Respiratory conditions").check();
  await page.getByLabel("Commute mode").selectOption(DELHI_PROFILE.commute_mode);
  await page
    .getByLabel("One-way commute (km)")
    .fill(String(DELHI_PROFILE.commute_km));
  await page.getByLabel("Cooking fuel").selectOption(DELHI_PROFILE.cooking_fuel);
  await page.getByLabel("Heating").selectOption(DELHI_PROFILE.heating_type);
  await page
    .getByLabel("Budget sensitivity")
    .selectOption(DELHI_PROFILE.budget_level);

  const profileResponse = page.waitForResponse((response) =>
    isRequest(response, "PUT", "/profile"),
  );
  const plansResponse = page.waitForResponse((response) =>
    isRequest(response, "GET", "/plans"),
  );
  await page.getByRole("button", { name: "Save profile" }).click();
  expect((await profileResponse).status()).toBe(200);
  expect((await plansResponse).status()).toBe(200);

  await expect(page.locator("#plans-routines .plan-card").first()).toBeVisible();
}

export async function savePoorBandAndFetch(page: Page): Promise<void> {
  const contextResponse = page.waitForResponse((response) =>
    isRequest(response, "POST", "/air/context"),
  );
  await page.getByLabel("Current band").selectOption("Poor");
  expect((await contextResponse).status()).toBe(200);

  const airResponse = page.waitForResponse((response) =>
    isRequest(response, "GET", "/air"),
  );
  await page.getByRole("button", { name: "Fetch live AQI" }).click();
  expect((await airResponse).status()).toBe(200);

  const readout = page.locator("#aqi-readout");
  await expect(readout).toContainText("Poor (offline)");
  await expect(readout).toContainText(
    "live AQI provider unavailable; showing your saved band",
  );
}

export async function askQuestion(
  page: Page,
  question: string,
): Promise<void> {
  await page.getByLabel("Question").fill(question);
  const responsePromise = page.waitForResponse((response) =>
    isRequest(response, "POST", "/ask"),
  );
  await page.getByRole("button", { name: "Ask", exact: true }).click();
  expect((await responsePromise).status()).toBe(200);
}

export async function uploadPdf(
  page: Page,
  filename = "delhi-air-notes.pdf",
): Promise<void> {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await page.getByLabel("PDF file").setInputFiles({
      name: filename,
      mimeType: "application/pdf",
      buffer: textPdf(PDF_TEXT),
    });
    const responsePromise = page.waitForResponse((response) =>
      isRequest(response, "POST", "/documents/upload"),
    );
    await page.getByRole("button", { name: "Upload PDF" }).click();
    const response = await responsePromise;
    if (response.status() === 201) {
      await expect(
        page.getByText("Upload complete.", { exact: true }),
      ).toBeVisible();
      return;
    }
    if (response.status() === 503) {
      await page.waitForTimeout(250);
      continue;
    }
    expect(response.status()).toBe(201);
  }
  throw new Error("document upload kept returning 503");
}

export async function expectCitation(page: Page): Promise<void> {
  const citations = page.locator("#citations li");
  await expect(citations.first()).toBeVisible();
  await expect(citations.first()).toHaveText(/seed-\d{3}/);
}
