import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";
import {
  askQuestion,
  expectCitation,
  savePoorBandAndFetch,
  seedDocument,
  seedProfile,
  seedUser,
  signInViaUi,
} from "../support/app";

const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function audit(page: Page, label: string, include?: string): Promise<void> {
  let builder = new AxeBuilder({ page }).withTags(TAGS);
  if (include) {
    builder = builder.include(include);
  }
  const results = await builder.analyze();
  const ids = results.violations.map((violation) => violation.id);
  const rulesRun =
    results.passes.length +
    results.incomplete.length +
    results.violations.length;

  console.log(
    `AXE ${label}: violations=${results.violations.length} ` +
      `rules_run=${rulesRun} ids=${ids.join(",") || "none"}`,
  );
  for (const violation of results.violations) {
    console.log(
      `  ${violation.id} (${violation.impact}) x${violation.nodes.length}: ` +
        `${violation.help} -> ${violation.nodes
          .map((node) => node.target.join(" "))
          .join(" | ")}`,
    );
  }

  expect(
    results.violations,
    `axe violations on ${label}: ${ids.join(", ")}`,
  ).toEqual([]);
}

test("home and register expose no axe violations", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Sign in or register" }),
  ).toBeVisible();

  await audit(page, "home");
  await audit(page, "register", "#auth-card");
});

test("dashboard with AQI, answer and documents exposes no axe violations", async ({
  page,
  request,
}) => {
  const user = await seedUser(request, "axe-dashboard");
  await seedProfile(request, user.token);
  await seedDocument(request, user.token);
  await signInViaUi(page, user.email);

  await savePoorBandAndFetch(page);
  await askQuestion(page, "indoor air purifier");
  await expectCitation(page);

  await audit(page, "dashboard");
});

test("documents view exposes no axe violations", async ({ page, request }) => {
  const user = await seedUser(request, "axe-documents");
  await seedProfile(request, user.token);
  await seedDocument(request, user.token);
  await signInViaUi(page, user.email);

  await page
    .getByRole("heading", { name: "Document library" })
    .scrollIntoViewIfNeeded();
  await expect(page.locator("#docs-list li")).toHaveCount(1);

  await audit(page, "documents");
});

test("profile view exposes no axe violations", async ({ page, request }) => {
  const user = await seedUser(request, "axe-profile");
  await seedProfile(request, user.token);
  await signInViaUi(page, user.email);

  await page
    .getByRole("heading", { name: "Your profile" })
    .scrollIntoViewIfNeeded();

  await audit(page, "profile");
});
