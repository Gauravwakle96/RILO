import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type { Experiment } from "../src/types";

const evidenceDir = path.resolve("../docs/ui-evidence");
const runLabel = `UI recovery verification ${Date.now()}`;

async function connected(page: Page) {
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("status", { name: "Loading workspace" }),
  ).toHaveCount(0);
}

async function navigate(page: Page, label: string) {
  if (
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .isVisible()
  ) {
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
  }
  await page
    .locator(".sidebar")
    .getByRole("button", { name: label, exact: true })
    .click();
}

async function capture(page: Page, name: string, fullPage = false) {
  await mkdir(evidenceDir, { recursive: true });
  await page.evaluate(async () => {
    await document.fonts.ready;
    window.scrollTo(0, 0);
  });
  await page.mouse.move(1, 1);
  await page.screenshot({
    path: path.join(evidenceDir, name),
    fullPage,
    animations: "disabled",
  });
}

async function accessibility(page: Page, name: string) {
  const result = await new AxeBuilder({ page }).analyze();
  await mkdir(evidenceDir, { recursive: true });
  await writeFile(
    path.join(evidenceDir, `${name}-axe.json`),
    JSON.stringify(
      {
        url: page.url(),
        violations: result.violations,
        incomplete: result.incomplete.map((rule) => ({
          id: rule.id,
          targets: rule.nodes.map((node) => node.target),
        })),
      },
      null,
      2,
    ),
  );
  expect(
    result.violations,
    JSON.stringify(
      result.violations.map((rule) => ({
        id: rule.id,
        nodes: rule.nodes.map((node) => node.target),
      })),
    ),
  ).toEqual([]);
}

async function noOverflow(page: Page) {
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBe(true);
}

test("existing recorded fixture and real-model traces remain inspectable at each viewport", async ({
  page,
}) => {
  await page.goto("/");
  await connected(page);
  const experiments = (await (
    await page.request.get("/api/v1/experiments")
  ).json()) as Experiment[];
  for (const engine of ["fixture", "bifrost"] as const) {
    if (engine === "bifrost" && process.env.CI_SKIP_LIVE_TRACE === "1")
      continue;
    const experiment = experiments.find(
      (item) =>
        item.spec.engine === engine &&
        item.summary.passes + item.summary.failures > 0,
    );
    if (!experiment) continue;
    const detail = (await (
      await page.request.get(`/api/v1/experiments/${experiment.id}`)
    ).json()) as Experiment;
    const selectedRun =
      detail.runs?.find((run) => run.assessment_status === "pass") ??
      detail.runs?.[0];
    expect(selectedRun).toBeDefined();
    for (const viewport of [
      { width: 390, height: 844 },
      { width: 768, height: 1024 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(viewport);
      await page.goto(`/#/experiments/${experiment.id}`);
      await connected(page);
      await expect(
        page.getByRole("heading", { name: experiment.name, exact: true }),
      ).toBeVisible();
      await noOverflow(page);
      await page.getByRole("button", { name: /^Runs/ }).click();
      await page
        .getByRole("button", {
          name: `Inspect ${selectedRun!.agent_name} ${selectedRun!.task_name} ${selectedRun!.scenario_name} trial ${selectedRun!.repetition}`,
          exact: true,
        })
        .first()
        .click();
      const inspector = page.getByRole("dialog", {
        name: selectedRun!.agent_name,
        exact: true,
      });
      await expect(inspector.locator(".trace-event").first()).toBeVisible();
      await noOverflow(page);
      await accessibility(
        page,
        `${engine}-inspector-${viewport.width}x${viewport.height}`,
      );
      await capture(
        page,
        `${engine}-trace-${viewport.width}x${viewport.height}.png`,
      );
      await inspector
        .getByRole("button", { name: "Output", exact: true })
        .click();
      await expect(
        inspector.getByText(
          "Claims in the free-text summary are not independently assessed.",
          { exact: false },
        ),
      ).toBeVisible();
      await inspector
        .getByRole("button", { name: "Evaluation", exact: true })
        .click();
      await expect(
        inspector.getByRole("heading", { name: "Grader evidence" }),
      ).toBeVisible();
      await page.keyboard.press("Escape");
      await expect(inspector).toHaveCount(0);
    }
  }
});

test("real fixture flow: create, inspect, export, rerun, baseline and compare", async ({
  page,
}) => {
  test.setTimeout(180_000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await connected(page);
  const opener = page.getByRole("button", {
    name: "New experiment",
    exact: true,
  });
  await opener.click();
  const dialog = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await dialog.getByLabel("Experiment name").fill(runLabel);
  await dialog.getByLabel("Repetitions", { exact: true }).fill("1");
  await dialog.getByLabel("Execution engine").selectOption("fixture");
  const conditions = dialog.getByRole("group", { name: "Test conditions" });
  for (const checkbox of await conditions.getByRole("checkbox").all())
    await checkbox.check();
  await accessibility(page, "experiment-form");
  await capture(page, "experiment-form-desktop.png");
  const createdResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/experiments") &&
      response.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Run experiment", exact: true })
    .click();
  const response = await createdResponse;
  expect(response.status()).toBe(202);
  const created = (await response.json()) as Experiment;
  await expect(
    page.getByRole("heading", { name: runLabel, exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("This is a deterministic demonstration.", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Rerun", exact: true }),
  ).toBeVisible({ timeout: 120_000 });
  const detail = (await (
    await page.request.get(`/api/v1/experiments/${created.id}`)
  ).json()) as Experiment;
  expect(detail.state).toBe("completed");
  expect(detail.runs).toHaveLength(8);
  expect(
    detail.summary.passes +
      detail.summary.failures +
      detail.summary.inconclusive +
      detail.summary.infrastructure_errors,
  ).toBe(8);
  await expect(page.locator(".metrics-table")).toContainText("Not applicable");
  await expect(page.locator(".metrics-table")).toContainText("No API fees");
  await accessibility(page, "completed-comparison");
  await capture(page, "completed-comparison-desktop.png");

  await page.getByRole("button", { name: /^Runs/ }).click();
  await expect(page.locator(".runs-table tbody tr")).toHaveCount(8);
  const inspect = page
    .locator(".runs-table tbody tr")
    .filter({ has: page.locator(".badge-good") })
    .first()
    .getByRole("button", { name: /^Inspect / });
  await inspect.click();
  const inspector = page.getByRole("dialog", { name: /Scout|Relay/ });
  await expect(inspector.locator(".trace-event").first()).toBeVisible();
  await accessibility(page, "run-inspector");
  await capture(page, "trace-inspector-desktop.png");
  await inspector.getByRole("button", { name: "Output", exact: true }).click();
  await expect(
    inspector.getByRole("heading", { name: "Agent response" }),
  ).toBeVisible();
  await expect(inspector.locator(".output-text")).toBeVisible();
  await inspector
    .getByRole("button", { name: "Evaluation", exact: true })
    .click();
  await expect(inspector.locator(".assessment-check").first()).toBeVisible();
  for (let index = 0; index < 10; index++) {
    await page.keyboard.press("Tab");
    expect(
      await inspector.evaluate((element) =>
        element.contains(document.activeElement),
      ),
    ).toBe(true);
  }
  await page.keyboard.press("Escape");
  await expect(inspector).toHaveCount(0);
  await expect(inspect).toBeFocused();

  const downloaded = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export JSON", exact: true }).click();
  const download = await downloaded;
  expect(download.suggestedFilename()).toBe(`rilo-${created.id}.json`);
  expect(await download.failure()).toBeNull();
  await page.getByRole("button", { name: "Comparison", exact: true }).click();
  await page
    .getByRole("button", { name: "Save baseline", exact: true })
    .click();
  const baselineDialog = page.getByRole("dialog", {
    name: "Save baseline",
    exact: true,
  });
  await baselineDialog.getByLabel("Baseline name").fill(`${runLabel} baseline`);
  await baselineDialog
    .getByRole("button", { name: "Save baseline", exact: true })
    .click();
  await expect(baselineDialog).toHaveCount(0);
  await page.getByRole("button", { name: "Rerun", exact: true }).click();
  const rerunDialog = page.getByRole("dialog", {
    name: "Rerun experiment",
    exact: true,
  });
  await expect(
    rerunDialog.getByLabel("Repetitions", { exact: true }),
  ).toHaveValue("1");
  const rerunResponse = page.waitForResponse(
    (value) =>
      value.url().endsWith("/api/v1/experiments") &&
      value.request().method() === "POST",
  );
  await rerunDialog
    .getByRole("button", { name: "Run experiment", exact: true })
    .click();
  const candidate = (await (await rerunResponse).json()) as Experiment;
  await expect(
    page.getByRole("button", { name: "Rerun", exact: true }),
  ).toBeVisible({ timeout: 120_000 });
  await navigate(page, "Compare & baselines");
  await page.getByLabel("Baseline experiment").selectOption(created.id);
  await page.getByLabel("Candidate experiment").selectOption(candidate.id);
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Conditions are comparable" }),
  ).toBeVisible();
  await expect(page.locator(".baseline-list")).toContainText(
    `${runLabel} baseline`,
  );
  await accessibility(page, "baseline-comparison");
  await capture(page, "baseline-comparison-desktop.png");
  await page
    .getByLabel("This candidate changes agent code or configuration", {
      exact: false,
    })
    .check();
  await expect(
    page.getByRole("heading", { name: "Conditions are comparable" }),
  ).toHaveCount(0);
  await page
    .getByLabel("This candidate changes agent code or configuration", {
      exact: false,
    })
    .uncheck();
  const incompatible = (
    (await (
      await page.request.get("/api/v1/experiments")
    ).json()) as Experiment[]
  ).find(
    (experiment) =>
      experiment.id !== created.id &&
      !["queued", "running"].includes(experiment.state) &&
      (experiment.spec.repetitions !== created.spec.repetitions ||
        experiment.spec.engine !== created.spec.engine ||
        experiment.spec.task_ids.length !== created.spec.task_ids.length),
  );
  if (incompatible) {
    await page.getByLabel("Candidate experiment").selectOption(incompatible.id);
    await page.getByRole("button", { name: "Compare", exact: true }).click();
    await expect(
      page.getByRole("heading", { name: "Conditions differ" }),
    ).toBeVisible();
    await expect(
      page.getByText("Different inputs:", { exact: false }),
    ).toBeVisible();
    await capture(page, "incompatible-comparison.png");
  }
  expect(errors).toEqual([]);
  await writeFile(
    path.join(evidenceDir, "real-ui-flow.json"),
    JSON.stringify(
      {
        experiment_id: created.id,
        candidate_id: candidate.id,
        attempts: detail.runs?.length,
        engine: "fixture",
        mode: "controlled",
        checked: [
          "create",
          "actual-results",
          "trace",
          "output",
          "evaluation",
          "focus-containment",
          "escape-focus-return",
          "json-download",
          "baseline-save",
          "rerun",
          "compatible-comparison",
        ],
      },
      null,
      2,
    ),
  );
});

test("cancel a real scheduled fixture experiment and preserve interruption evidence", async ({
  page,
}) => {
  await page.goto("/");
  await connected(page);
  await page
    .getByRole("button", { name: "New experiment", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await dialog
    .getByLabel("Experiment name")
    .fill(`UI cancellation verification ${Date.now()}`);
  await dialog.getByLabel("Repetitions", { exact: true }).fill("5");
  const taskGroup = dialog.getByRole("group", { name: /Tasks/ });
  for (const task of (await taskGroup.getByRole("checkbox").all()).slice(0, 10))
    await task.check();
  const creation = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/experiments") &&
      response.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Run experiment", exact: true })
    .click();
  const experiment = (await (await creation).json()) as Experiment;
  const cancellation = page.waitForResponse((response) =>
    response.url().endsWith(`/api/v1/experiments/${experiment.id}/cancel`),
  );
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  expect((await cancellation).ok()).toBe(true);
  await expect(
    page.getByRole("button", { name: "Rerun", exact: true }),
  ).toBeVisible({ timeout: 30_000 });
  const result = (await (
    await page.request.get(`/api/v1/experiments/${experiment.id}`)
  ).json()) as Experiment;
  expect(result.state).toBe("cancelled");
  expect(result.runs).toHaveLength(experiment.progress.total);
  expect(
    result.summary.inconclusive + result.summary.infrastructure_errors,
  ).toBeGreaterThan(0);
  await expect(
    page.getByText("Available results are preserved.", { exact: false }),
  ).toBeVisible();
  await capture(page, "cancelled-experiment.png");
});

test("actual catalogs, source search, referenced task, endpoint validation and settings", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await connected(page);
  await navigate(page, "Agents");
  await page.getByLabel("Agent category").selectOption("reference");
  await expect(
    page.getByRole("heading", { name: "Scout", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Check connection", exact: true })
    .first()
    .click();
  await expect(page.locator(".check-result").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Connect agent", exact: true })
    .click();
  const agentDialog = page.getByRole("dialog", { name: "Connect an agent" });
  await agentDialog.getByLabel("Agent name").fill("UI rejected endpoint check");
  await agentDialog
    .getByLabel("Local run endpoint")
    .fill("https://example.com/run");
  await agentDialog
    .getByRole("button", { name: "Connect agent", exact: true })
    .click();
  await expect(agentDialog.getByRole("alert")).toBeVisible();
  await capture(page, "validation-error.png");
  await page.keyboard.press("Escape");
  await navigate(page, "Evidence");
  await expect(page.locator(".source-content")).not.toBeEmpty();
  await page.getByLabel("Search evidence").fill("not-a-source-ui-check");
  await expect(
    page.getByRole("heading", { name: "No evidence available" }),
  ).toBeVisible();
  await page.getByLabel("Search evidence").fill("Aurora");
  await expect(page.locator(".source-item").first()).toBeVisible();
  await capture(page, "evidence-desktop.png");
  await accessibility(page, "evidence");
  const sources = (await (
    await page.request.get("/api/v1/sources")
  ).json()) as { id: string; title: string }[];
  await navigate(page, "Tasks");
  await page.locator(".task-summary").first().click();
  await expect(page.locator(".task-expanded")).toBeVisible();
  await page.getByRole("button", { name: "Create task", exact: true }).click();
  const taskDialog = page.getByRole("dialog", {
    name: "Create a referenced task",
  });
  const title = `UI reference verification ${Date.now()}`;
  await taskDialog.getByLabel("Task title").fill(title);
  await taskDialog.getByLabel("Company or entity").fill("Aurora Labs");
  await taskDialog
    .getByLabel("Task instructions")
    .fill(
      "Report the documented launch date for Beacon at Aurora Labs with a source citation.",
    );
  await taskDialog
    .getByLabel("Expected facts", { exact: false })
    .fill("Aurora Labs launched Beacon on October 14, 2026.");
  await taskDialog
    .getByRole("checkbox", { name: new RegExp(sources[0].title) })
    .check();
  await taskDialog
    .getByRole("button", { name: "Create task", exact: true })
    .click();
  await expect(taskDialog).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: title, exact: true }),
  ).toBeVisible();
  await navigate(page, "Scenarios");
  await expect(page.locator(".scenario-card")).toHaveCount(4);
  await accessibility(page, "scenarios");
  await navigate(page, "Settings");
  await expect(
    page.getByRole("heading", { name: "Bifrost gateway" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Tavily research" }),
  ).toBeVisible();
  const settings = (await (
    await page.request.get("/api/v1/settings")
  ).json()) as { config: { bifrost_url: string; model: string } };
  await expect(page.getByLabel("Bifrost URL")).toHaveValue(
    settings.config.bifrost_url,
  );
  await expect(page.getByLabel("Default model")).toHaveValue(
    settings.config.model,
  );
  await page
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await expect(
    page.getByText("Execution settings saved.", { exact: false }),
  ).toBeVisible();
  await accessibility(page, "settings");
});

test("registered HTTP agent version flow preserves identity and bounds its experiment options", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await connected(page);
  await navigate(page, "Agents");
  await page
    .getByRole("button", { name: "Connect agent", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Connect an agent",
    exact: true,
  });
  const name = `UI version workflow ${Date.now()}`;
  // Registered adapters are separate from the default practical-assistant list.
  // Select their category after closing the registration form below.
  await dialog.getByLabel("Agent name").fill(name);
  await dialog
    .getByLabel("Local run endpoint")
    .fill("http://127.0.0.1:9019/run");
  const created = page.waitForResponse(
    (response) =>
      response.url().endsWith("/api/v1/agents") &&
      response.request().method() === "POST",
  );
  await dialog
    .getByRole("button", { name: "Connect agent", exact: true })
    .click();
  const original = (await (await created).json()) as { id: string };
  await page.getByLabel("Agent category").selectOption("custom");
  const card = page
    .locator(".agent-panel")
    .filter({ has: page.getByRole("heading", { name, exact: true }) });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "New version", exact: true }).click();
  const versionDialog = page.getByRole("dialog", {
    name: `New version of ${name}`,
    exact: true,
  });
  await versionDialog.getByLabel("Version label").fill("1.1.0");
  await versionDialog
    .getByLabel("Local run endpoint")
    .fill("http://127.0.0.1:9020/run");
  await accessibility(page, "agent-version-form");
  await capture(page, "agent-version-form.png");
  await versionDialog
    .getByRole("button", { name: "Register version", exact: true })
    .click();
  await expect(versionDialog).toHaveCount(0);
  await expect(card.locator(".agent-heading")).toContainText("1.1.0");
  const versions = (await (
    await page.request.get(`/api/v1/agents/${original.id}/versions`)
  ).json()) as { version: string }[];
  expect(versions.map((version) => version.version)).toEqual([
    "1.0.0",
    "1.1.0",
  ]);
  await card.getByRole("button", { name: "Test agent", exact: true }).click();
  const experiment = page.getByRole("dialog", {
    name: "New experiment",
    exact: true,
  });
  await expect(experiment.getByLabel("Execution engine")).toHaveValue(
    "bifrost",
  );
  await expect(experiment.getByLabel("Research evidence")).toHaveValue(
    "controlled",
  );
  await expect(
    experiment
      .getByRole("group", { name: "Test conditions" })
      .getByRole("checkbox", { checked: true }),
  ).toHaveCount(1);
  await expect(
    experiment.getByText("HTTP adapters provide final-output observations", {
      exact: false,
    }),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(experiment).toHaveCount(0);
});

test("declared agent change posts the real flag and explicitly simulated record fields render", async ({
  page,
}) => {
  await page.goto("/");
  await connected(page);
  const available = (
    (await (
      await page.request.get("/api/v1/experiments")
    ).json()) as Experiment[]
  ).filter((experiment) => !["queued", "running"].includes(experiment.state));
  test.skip(
    available.length < 2,
    "Requires two real experiment records for the comparison request.",
  );
  await navigate(page, "Compare & baselines");
  await page.getByLabel("Baseline experiment").selectOption(available[0].id);
  await page.getByLabel("Candidate experiment").selectOption(available[1].id);
  await page
    .getByLabel("This candidate changes agent code or configuration", {
      exact: false,
    })
    .check();
  const request = page.waitForRequest(
    (value) =>
      value.url().endsWith("/api/v1/comparisons") && value.method() === "POST",
  );
  const response = page.waitForResponse((value) =>
    value.url().endsWith("/api/v1/comparisons"),
  );
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  expect((await request).postDataJSON().allow_agent_changes).toBe(true);
  const actualResponse = await response;
  expect(actualResponse.ok()).toBe(true);
  const comparison = await actualResponse.json();
  await expect(
    page.getByRole("heading", { name: /Conditions (are comparable|differ)/ }),
  ).toBeVisible();
  // This interception tests rendering of the declared-change records only; it does not claim a real agent regression improved.
  await page.route("**/api/v1/comparisons", (route) =>
    route.fulfill({
      status: 200,
      json: {
        ...comparison,
        declared_changes: [
          {
            field: "agent_hash",
            baseline: "simulated-baseline-hash",
            candidate: "simulated-candidate-hash",
          },
        ],
      },
    }),
  );
  await page.getByRole("button", { name: "Compare", exact: true }).click();
  await expect(
    page.getByText("Declared candidate changes: Agent Hash", { exact: false }),
  ).toBeVisible();
  await capture(page, "simulated-declared-change-records.png");
  await accessibility(page, "simulated-declared-change-records");
  await page.unroute("**/api/v1/comparisons");
});

for (const viewport of [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1440, height: 900 },
]) {
  test(`responsive, accessible real workspace ${viewport.width}x${viewport.height}`, async ({
    page,
  }) => {
    await page.setViewportSize(viewport);
    await page.goto("/");
    await connected(page);
    await page
      .getByLabel("Search experiments")
      .fill("no matching experiment ui-verification");
    await expect(
      page.getByRole("heading", { name: "No matching experiments" }),
    ).toBeVisible();
    await capture(page, `empty-filter-${viewport.width}.png`);
    await page.getByRole("button", { name: "Clear filters" }).click();
    await noOverflow(page);
    await accessibility(page, `dashboard-${viewport.width}x${viewport.height}`);
    await capture(page, `dashboard-${viewport.width}x${viewport.height}.png`);
    await navigate(page, "Tasks");
    await noOverflow(page);
    await navigate(page, "Evidence");
    await noOverflow(page);
    await accessibility(page, `evidence-${viewport.width}x${viewport.height}`);
    await navigate(page, "Settings");
    await noOverflow(page);
    await navigate(page, "Agents");
    await noOverflow(page);
    await navigate(page, "Scenarios");
    await noOverflow(page);
    await accessibility(page, `scenarios-${viewport.width}x${viewport.height}`);
    await page
      .getByRole("button", { name: "Run a scenario", exact: true })
      .click();
    const dialog = page.getByRole("dialog", {
      name: "New experiment",
      exact: true,
    });
    await dialog
      .getByLabel("Experiment name")
      .fill(
        "Long label layout verification: compare agent recovery under repeated adverse conditions",
      );
    await noOverflow(page);
    await accessibility(page, `form-${viewport.width}x${viewport.height}`);
    await capture(page, `form-${viewport.width}x${viewport.height}.png`);
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Run a scenario", exact: true }),
    ).toBeFocused();
    if (viewport.width <= 800)
      await page
        .getByRole("button", { name: "Open navigation", exact: true })
        .click();
    await page.getByRole("button", { name: "Switch to light theme" }).click();
    await page.keyboard.press("Escape");
    await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
    await accessibility(page, `light-${viewport.width}x${viewport.height}`);
    await capture(page, `light-${viewport.width}x${viewport.height}.png`);
    await page.emulateMedia({ reducedMotion: "reduce" });
    expect(
      await page.evaluate(
        () =>
          getComputedStyle(document.querySelector(".sidebar")!)
            .transitionDuration,
      ),
    ).toBe("0s");
    expect(await page.evaluate(() => Object.keys(localStorage))).toEqual([
      "rilo-theme",
    ]);
  });
}

test("simulated UI boundary: loading, partial catalog, error recovery and permission", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let releaseLoading: () => void = () => undefined;
  const loadingGate = new Promise<void>((resolve) => {
    releaseLoading = resolve;
  });
  await page.route("**/api/v1/session", async (route) => {
    await loadingGate;
    await route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByRole("status", { name: "Loading workspace" }),
  ).toBeVisible();
  await capture(page, "simulated-loading.png");
  releaseLoading();
  await connected(page);
  await page.unroute("**/api/v1/session");
  await page.route("**/api/v1/sources", (route) =>
    route.fulfill({
      status: 503,
      json: {
        error: {
          code: "simulated_unavailable",
          message: "Simulated source service unavailable.",
        },
      },
    }),
  );
  await page
    .getByRole("button", { name: "Refresh workspace", exact: true })
    .click();
  await expect(
    page.getByText("Some workspace data is unavailable.", { exact: false }),
  ).toBeVisible();
  await expect(page.locator(".experiment-table")).toBeVisible();
  await capture(page, "simulated-partial.png");
  await page.unroute("**/api/v1/sources");
  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect(
    page.getByText("Some workspace data is unavailable.", { exact: false }),
  ).toHaveCount(0);
  await page.route("**/api/v1/session", (route) =>
    route.fulfill({
      status: 403,
      json: {
        error: {
          code: "simulated_origin_denied",
          message: "Simulated origin is not approved.",
        },
      },
    }),
  );
  await page.reload();
  await expect(
    page.getByText("Local session was rejected.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reconnect", exact: true }).first(),
  ).toBeVisible();
  await capture(page, "simulated-permission.png");
  await page.unroute("**/api/v1/session");
  await page
    .getByRole("button", { name: "Reconnect", exact: true })
    .first()
    .click();
  await connected(page);
  await page.route("**/api/v1/session", (route) =>
    route.abort("connectionrefused"),
  );
  await page.reload();
  await expect(
    page.getByText("Workspace connection failed.", { exact: true }),
  ).toBeVisible();
  await capture(page, "simulated-connection-error.png");
  await page.unroute("**/api/v1/session");
  await page
    .getByRole("button", { name: "Reconnect", exact: true })
    .first()
    .click();
  await connected(page);
});
