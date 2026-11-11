import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { Experiment } from "../src/types";

const evidenceDir = path.resolve("../docs/ui-evidence");

async function connected(page: Page) {
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("status", { name: "Loading workspace" }),
  ).toHaveCount(0);
}

async function review(page: Page, label: string) {
  await mkdir(evidenceDir, { recursive: true });
  await page.evaluate(async () => document.fonts.ready);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > innerWidth + 1,
  );
  expect(overflow).toBe(false);
  const axe = await new AxeBuilder({ page }).analyze();
  await writeFile(
    path.join(evidenceDir, `${label}-axe.json`),
    JSON.stringify(
      {
        violations: axe.violations,
        incomplete: axe.incomplete.map((rule) => ({
          id: rule.id,
          targets: rule.nodes.map((node) => node.target),
        })),
        overflow,
      },
      null,
      2,
    ),
  );
  expect(axe.violations).toEqual([]);
  await page.mouse.move(1, 1);
  await page.screenshot({
    path: path.join(evidenceDir, `${label}.png`),
    animations: "disabled",
  });
}

test("lower-left guide is accessible and explains requirements at every viewport", async ({
  page,
}) => {
  test.setTimeout(120_000);
  for (const viewport of [
    { width: 1440, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await connected(page);
    await expect(
      page.getByRole("heading", {
        name: "Find the failures your demo missed.",
      }),
    ).toBeVisible();
    await review(page, `recovery-home-${viewport.width}`);
    if (viewport.width <= 800)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    await page
      .getByRole("button", { name: "Start here A short guide to Rilo" })
      .click();
    await expect(page).toHaveURL(/#\/guide$/);
    await expect(
      page.getByRole("heading", { name: "Make your first failure useful." }),
    ).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await review(page, `recovery-guide-${viewport.width}`);
    await page
      .getByRole("link", { name: "What you need", exact: true })
      .click();
    await expect(page).toHaveURL(/#\/guide$/);
    await expect(page.locator("#guide-requirements")).toBeFocused();
    await expect(page.locator("#guide-requirements")).toContainText(
      "No model, account, or search key required.",
    );
    await page
      .getByRole("link", { name: "Read results correctly", exact: true })
      .click();
    await expect(page.locator("#guide-results")).toBeFocused();
    await expect(page.locator("#guide-results")).toContainText(
      "does not verify every claim",
    );
    await page.evaluate(() => window.scrollTo(0, 0));
    await page
      .getByRole("button", { name: "Try recovery example", exact: true })
      .click();
    const dialog = page.getByRole("dialog", {
      name: "New experiment",
      exact: true,
    });
    await expect(dialog.getByLabel("Execution engine")).toHaveValue("fixture");
    await expect(dialog.locator(".attempt-preview")).toContainText(
      "12 attempts",
    );
    await expect(dialog.getByLabel("Repetitions", { exact: true })).toHaveValue(
      "3",
    );
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Try recovery example", exact: true }),
    ).toBeFocused();
    if (viewport.width <= 800)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    await page
      .getByRole("button", { name: "Switch to light theme", exact: true })
      .click();
    await page.keyboard.press("Escape");
    await review(page, `recovery-guide-light-${viewport.width}`);
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () =>
          getComputedStyle(document.querySelector(".sidebar-guide")!)
            .transitionDuration,
      ),
    ).toBe("0s");
    expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([
      "rilo-theme",
    ]);
    await page.emulateMedia({ reducedMotion: "no-preference" });
    if (viewport.width <= 800)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    await page
      .getByRole("button", { name: "Switch to dark theme", exact: true })
      .click();
    await page.keyboard.press("Escape");
  }
});

test("recovery example runs twelve actual fixture attempts and exposes a focused retest", async ({
  page,
}) => {
  test.setTimeout(120_000);
  await page.goto("/");
  await connected(page);
  await page
    .getByRole("button", { name: "Try recovery example", exact: true })
    .click();
  const form = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await form
    .getByLabel("Experiment name")
    .fill(`Guided recovery acceptance ${Date.now()}`);
  const creation = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/experiments") &&
      response.request().method() === "POST",
  );
  await form
    .getByRole("button", { name: "Run experiment", exact: true })
    .click();
  const created = (await (await creation).json()) as Experiment;
  await expect
    .poll(
      async () =>
        (
          (await (
            await page.request.get(`/api/v1/experiments/${created.id}`)
          ).json()) as Experiment
        ).state,
      { timeout: 60_000 },
    )
    .toBe("completed");
  await expect(page.locator(".recovery-table tbody tr")).toHaveCount(2);
  await page
    .getByRole("button", {
      name: /^Inspect Scout Search timeout result:/,
    })
    .click();
  const inspector = page.getByRole("dialog", { name: "Scout", exact: true });
  await expect(inspector.locator(".trace-event").first()).toBeVisible();
  await expect(inspector).toContainText("Search timeout");
  await review(page, "guided-recovery-failure");
  await inspector
    .getByRole("button", { name: "Retest this case", exact: true })
    .click();
  const retest = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await expect(inspector).toHaveCount(0);
  await expect(retest.getByLabel("Execution engine")).toHaveValue("fixture");
  await expect(retest.getByLabel("Experiment name")).toHaveValue(/regression$/);
  await expect(retest.locator(".attempt-preview")).toContainText("12 attempts");
  await page.keyboard.press("Escape");
});

test("retesting a real-model failure preserves recorded model and budgets", async ({
  page,
}) => {
  await page.goto("/");
  await connected(page);
  const experiments = (await (
    await page.request.get("/api/v1/experiments")
  ).json()) as Experiment[];
  const experiment = experiments.find(
    (item) =>
      item.state === "completed" &&
      item.spec.engine === "bifrost" &&
      item.spec.mode === "controlled" &&
      item.spec.scenario_ids.includes("search_timeout") &&
      item.spec.agent_ids.includes("scout"),
  );
  test.skip(
    !experiment,
    "No recorded real-model failure exists in this workspace.",
  );
  const detail = (await (
    await page.request.get(`/api/v1/experiments/${experiment!.id}`)
  ).json()) as Experiment;
  await page.goto(`/#/experiments/${detail.id}`);
  await connected(page);
  await page
    .getByRole("button", {
      name: /^Inspect Scout Search timeout result:/,
    })
    .click();
  const inspector = page.getByRole("dialog", { name: "Scout", exact: true });
  await expect(inspector.locator(".trace-event").first()).toBeVisible();
  await inspector
    .getByRole("button", { name: "Retest this case", exact: true })
    .click();
  const retest = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await expect(retest.getByLabel("Execution engine")).toHaveValue("bifrost");
  await expect(retest.getByLabel("Model", { exact: true })).toHaveValue(
    detail.spec.model,
  );
  await expect(
    retest.getByLabel("Time / attempt (s)", { exact: true }),
  ).toHaveValue(String(detail.spec.limits.timeout_seconds));
  await expect(
    retest.getByLabel("Tool calls / attempt", { exact: true }),
  ).toHaveValue(String(detail.spec.limits.max_tool_calls));
  await expect(
    retest.getByLabel("Model calls / attempt", { exact: true }),
  ).toHaveValue(String(detail.spec.limits.max_model_calls));
  await review(page, "focused-real-model-retest");
  await page.keyboard.press("Escape");
});
