import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("success check editor is accessible and does not submit incomplete rules", async ({
  page,
}) => {
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Add success check" }).click();
  await page
    .getByLabel("What should the agents do?")
    .fill("Name the storage engine.");
  await expect(page.getByLabel("Check 1 expected text")).toHaveValue("");
  await page.getByRole("button", { name: "Send to both agents" }).click();
  await expect(page.locator(".agent-response")).toHaveCount(0);
  await page.getByLabel("Check 1 expected text").fill("SQLite");
  for (const width of [390, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth + 1,
      ),
    ).toBe(true);
  }
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.getByRole("button", { name: "Remove check 1" }).click();
  await expect(page.getByLabel("Check 1 expected text")).toHaveCount(0);
});

test("readiness failure retains task and explains unavailable services", async ({
  page,
}) => {
  // This is explicitly a UI failure test with a stubbed dependency response.
  await page.route("**/api/v1/workspace/preflight", (route) =>
    route.fulfill({
      json: {
        ready: false,
        checks: [
          {
            name: "Model gateway",
            ready: false,
            detail: "Start Bifrost to continue.",
          },
        ],
        scope: "Dependency readiness only.",
      },
    }),
  );
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("What should the agents do?")
    .fill("Keep my unsent task.");
  await page.getByRole("button", { name: "Send to both agents" }).click();
  await expect(page.locator(".readiness-checks")).toContainText(
    "Start Bifrost to continue.",
  );
  await expect(page.getByLabel("What should the agents do?")).toHaveValue(
    "Keep my unsent task.",
  );
  await expect(page.locator(".agent-response")).toHaveCount(0);
});

test("actual paired inference, Promptfoo checks, saved suite and retest work together", async ({
  page,
}) => {
  test.skip(
    process.env.RILO_LIVE_ACCEPTANCE !== "1",
    "Requires the user's running local model; never silently substitute mock inference.",
  );
  test.setTimeout(300_000);
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "Rilo integration check: name the database and the cache in the supplied context. Answer in one short sentence.",
    );
  await page.getByText("Supporting context", { exact: true }).click();
  await page
    .getByLabel("Source text", { exact: true })
    .fill(
      "The application stores records in SQLite. It caches lookups in Redis.",
    );
  await page.getByRole("button", { name: "Add success check" }).click();
  await page.getByLabel("Check 1 name").fill("Names the database");
  await page.getByLabel("Check 1 expected text").fill("SQLite");
  await page.getByRole("button", { name: "Add success check" }).click();
  await page.getByLabel("Check 2 name").fill("Names the cache");
  await page.getByLabel("Check 2 expected text").fill("Redis");
  await page.getByRole("button", { name: "Send to both agents" }).click();
  await expect(page.locator(".agent-response .response-text")).toHaveCount(2, {
    timeout: 150_000,
  });
  await expect(
    page.getByRole("table", {
      name: "Identical success checks applied independently to each recorded answer",
    }),
  ).toBeVisible({ timeout: 40_000 });
  await expect(page.locator(".check-table thead")).toContainText(
    "2/2 checks passed",
  );
  await expect(page.locator(".check-comparison")).toContainText(
    "Tie on declared checks",
  );
  await page.getByLabel("Show checks", { exact: true }).selectOption("failed");
  await expect(
    page.getByText("No failed checks in these recorded answers."),
  ).toBeVisible();
  await page.getByLabel("Show checks", { exact: true }).selectOption("all");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "../docs/ui-evidence/promptfoo-real-paired-checks.png",
    fullPage: true,
  });
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export PDF", exact: true }).click();
  expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
  await page
    .getByRole("button", { name: "Save task as regression test" })
    .click();
  await expect(
    page.getByRole("button", { name: "Saved in Benchmarks" }),
  ).toBeVisible();
  const retestResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/retest") &&
      response.request().method() === "POST",
  );
  await page.getByRole("button", { name: "Retest", exact: true }).click();
  const retest = (await (await retestResponse).json()) as { id: string };
  await expect(page.getByRole("link", { name: "Inspect run" })).toHaveAttribute(
    "href",
    `#/experiments/${retest.id}`,
  );
  await expect(page.locator(".agent-response .response-text")).toHaveCount(2, {
    timeout: 150_000,
  });
  await expect(page.locator(".check-comparison")).toContainText(
    "Tie on declared checks",
    { timeout: 40_000 },
  );
  await page.getByRole("link", { name: "Inspect run" }).click();
  await expect(page).toHaveURL(new RegExp(retest.id));
  await expect(page.locator(".check-table")).toContainText(
    "Names the database",
  );
  await expect(page.locator(".check-table")).toContainText("Names the cache");
});
