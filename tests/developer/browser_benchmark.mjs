import assert from "node:assert/strict";
import { mkdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import path from "node:path";

const require = createRequire(new URL("../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const { default: AxeBuilder } = require("@axe-core/playwright");
const baseUrl = process.argv[2] || "http://127.0.0.1:8018";
const evidenceDir = path.resolve("docs/ui-evidence");
const experimentId = "exp_8b95841fed304432";
const browser = await chromium.launch({ headless: true });
const errors = [];
const failedRequests = [];
const observations = [];

try {
  await mkdir(evidenceDir, { recursive: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(15_000);
  page.on("pageerror", error => errors.push(error.message));
  page.on("console", message => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("requestfailed", request => failedRequests.push(request.url()));

  const connected = async () => {
    await page.getByText("Local API connected", { exact: true }).waitFor();
    await page.getByRole("status", { name: "Loading workspace" }).waitFor({ state: "hidden" });
    await page.evaluate(async () => document.fonts.ready);
  };
  const capture = async name => {
    await page.mouse.move(1, 1);
    await page.screenshot({ path: path.join(evidenceDir, name), animations: "disabled" });
  };
  const audit = async label => {
    const result = await new AxeBuilder({ page }).analyze();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    const item = {
      label,
      viewport: page.viewportSize(),
      overflow,
      axeViolations: result.violations,
      axeIncomplete: result.incomplete.map(rule => ({ id: rule.id, targets: rule.nodes.map(node => node.target) })),
    };
    observations.push(item);
    assert.equal(overflow, false);
    assert.deepEqual(result.violations, []);
  };
  await page.goto(`${baseUrl}/#/experiments/${experimentId}`, { waitUntil: "domcontentloaded" });
  await connected();
  const experimentResponse = await page.request.get(`${baseUrl}/api/v1/experiments/${experimentId}`);
  assert.equal(experimentResponse.status(), 200);
  const experiment = await experimentResponse.json();
  assert.equal(experiment.state, "completed");
  assert.deepEqual(experiment.progress, { completed: 120, total: 120 });
  await page.getByRole("heading", { name: experiment.name, exact: true }).waitFor();
  await page.locator(".metrics-table").waitFor();
  await audit("actual-model metric comparison");
  await capture("model-v2-comparison.png");

  for (const sample of [
    { id: "run_fa7fda3a493e4423", label: "recovery", expected: "pass", tab: "Trace", event: "recovery" },
    { id: "run_84e2c96b06c7402b", label: "unhandled-fault", expected: "fail", tab: "Trace", event: "agent_error" },
    { id: "run_24efebfe6cd0435b", label: "insufficient-evidence", expected: "fail", tab: "Output" },
  ]) {
    const response = await page.request.get(`${baseUrl}/api/v1/runs/${sample.id}`);
    assert.equal(response.status(), 200);
    const run = await response.json();
    assert.equal(run.experiment_id, experimentId);
    assert.equal(run.assessment_status, sample.expected);
    if (sample.event) assert.ok(run.events.some(event => event.type === sample.event));
    await page.getByRole("button", { name: /^Runs/ }).click();
    await page.getByRole("button", {
      name: `Inspect ${run.agent_name} ${run.task_name} ${run.scenario_name} trial ${run.repetition}`,
      exact: true,
    }).first().click();
    const inspector = page.getByRole("dialog", { name: run.agent_name, exact: true });
    await inspector.locator(".trace-event").first().waitFor();
    if (sample.tab !== "Trace") await inspector.getByRole("button", { name: sample.tab, exact: true }).click();
    await audit(sample.label);
    await capture(`model-v2-${sample.label}-1440x900.png`);
    if (sample.label === "recovery") {
      await page.setViewportSize({ width: 390, height: 844 });
      await audit("recovery mobile");
      await capture("model-v2-recovery-390x844.png");
      await page.setViewportSize({ width: 1440, height: 900 });
    }
    if (sample.label === "insufficient-evidence") {
      const body = inspector.locator(".inspector-body");
      await body.focus();
      assert.equal(await body.evaluate(element => element === document.activeElement), true);
      await inspector.getByRole("button", { name: "Evaluation", exact: true }).click();
      await inspector.getByRole("heading", { name: "Grader evidence" }).waitFor();
      await audit("insufficient-evidence evaluation");
      await capture("model-v2-insufficient-evidence-evaluation-1440x900.png");
    }
    await page.keyboard.press("Escape");
    await inspector.waitFor({ state: "hidden" });
  }
  assert.deepEqual(errors, []);
  assert.deepEqual(failedRequests, []);
  const evidence = { status: "passed", url: baseUrl, experimentId, observations, errors, failedRequests };
  await writeFile(path.join(evidenceDir, "model-v2-browser.json"), JSON.stringify(evidence, null, 2) + "\n");
  console.log(JSON.stringify({ status: evidence.status, screens: observations.length, errors, failedRequests }));
} finally {
  await browser.close();
}
