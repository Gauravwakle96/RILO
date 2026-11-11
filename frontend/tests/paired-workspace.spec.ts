import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import type { Conversation } from "../src/workspace-types";

test("paired workspaces expose optional search and accessible input controls", async ({
  page,
}) => {
  test.setTimeout(120000);
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const route of [
      "chat",
      "repository",
      "documents",
      "website",
      "search",
    ]) {
      await page.goto(`/#/${route}`);
      await expect(
        page.getByText("Local API connected", { exact: true }),
      ).toBeVisible();
      await expect(page.getByLabel("Web search", { exact: true })).toHaveValue(
        "off",
      );
      await expect(
        page.getByRole("button", { name: "Send to both agents" }),
      ).toBeDisabled();
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth + 1,
        ),
      ).toBe(true);
    }
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations).toEqual([]);
  }
});

test("persisted paired model results, page citations and reports are inspectable", async ({
  page,
}) => {
  await page.goto("/#/documents");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  const conversations = (await (
    await page.request.get("/api/v1/workspace/conversations")
  ).json()) as Conversation[];
  const selected = conversations.find(
    (c) => c.title === "Live validation documents",
  );
  test.skip(!selected, "Requires a recorded real-model PDF validation run.");
  await page.getByLabel("Saved conversations").selectOption(selected!.id);
  await expect(page.locator(".agent-response")).toHaveCount(2);
  await page.locator(".workspace-findings details summary").first().click();
  await expect(page.locator("blockquote").first()).toContainText("Page 2");
  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await expect(page.locator(".check-comparison")).toContainText(
    "Accuracy and a winner remain undetermined",
  );
});

test("invalid website input reaches the real worker and returns an honest failure", async ({
  page,
}) => {
  test.setTimeout(90000);
  // Isolate the real worker's SSRF check from optional model services in CI.
  // The unsafe URL fails before inference; only the readiness response is stubbed.
  await page.route("**/api/v1/workspace/preflight", (route) =>
    route.fulfill({
      json: {
        ready: true,
        checks: [],
        scope: "Readiness stub for worker URL boundary test",
      },
    }),
  );
  await page.goto("/#/website");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("What should the agents do?")
    .fill("Analyze this private URL boundary.");
  await page.getByLabel("Public website URL").fill("http://127.0.0.1");
  await page.getByRole("button", { name: "Send to both agents" }).click();
  await expect(page.locator(".agent-response")).toHaveCount(2);
  await expect(page.locator(".agent-response").first()).toContainText(
    "Private and local destinations are blocked",
    { timeout: 60000 },
  );
  await expect(page.locator(".agent-response .response-text")).toHaveCount(0);
  await expect(page.locator(".agent-response").first()).toContainText(
    "Agent not started",
  );
  await expect(
    page.getByRole("button", { name: /Retry .* response/ }),
  ).toHaveCount(0);
  const retryResponse = page.waitForResponse(
    (r) => r.url().endsWith("/retest") && r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Retry source capture", exact: true })
    .click();
  const retried = await retryResponse;
  expect(retried.status()).toBe(202);
  await expect(page.locator(".agent-response").first()).toContainText(
    "Private and local destinations are blocked",
    { timeout: 60000 },
  );
});
