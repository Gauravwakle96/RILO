import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import path from "node:path";

// Opt-in acceptance uses actual local inference and public retrieval. CI's fixture
// suite must not pretend these integrations ran without configured services.
test.skip(
  process.env.RILO_LIVE_ACCEPTANCE !== "1",
  "Set RILO_LIVE_ACCEPTANCE=1 with Bifrost/Ollama running.",
);
test.setTimeout(300000);
const root = path.resolve("..");
const inputs = path.join(root, ".rilo", "browser-acceptance");

test.beforeAll(() => {
  execFileSync(
    path.join(
      root,
      ".venv",
      process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
    ),
    [
      "-c",
      `
from pathlib import Path
from reportlab.pdfgen import canvas
import zipfile
p=Path(${JSON.stringify(inputs)});p.mkdir(parents=True,exist_ok=True)
c=canvas.Canvas(str(p/'source.pdf'))
c.drawString(50,700,'Rilo is an evaluation workspace.');c.showPage()
c.drawString(50,700,'The retention period is 30 days.');c.save()
with zipfile.ZipFile(p/'sample-repository.zip','w') as z:
 z.writestr('app.py','def add(left, right):\\n    return left + right\\n')
 z.writestr('test_app.py','import unittest\\nfrom app import add\\nclass AdditionTest(unittest.TestCase):\\n    def test_addition(self):\\n        self.assertEqual(add(2, 3), 5)\\n')
`,
    ],
  );
});

async function open(page: Page, category: string) {
  await page.goto(`/#/${category}`);
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Web search", { exact: true })).toHaveValue(
    "off",
  );
}

async function send(page: Page, permitPartial = false) {
  const submitted = page.waitForResponse(
    (r) =>
      /workspace\/conversations\/[^/]+\/turns$/.test(r.url()) &&
      r.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: "Send to both agents", exact: true })
    .click();
  const response = await submitted;
  expect(response.status()).toBe(202);
  const evaluation = await response.json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(
              `/api/v1/workspace/evaluations/${evaluation.id}`,
            )
          ).json()
        ).state,
      { timeout: 240000, intervals: [1500] },
    )
    .toMatch(permitPartial ? /^(completed|partial)$/ : /^completed$/);
  const stored = await (
    await page.request.get(`/api/v1/workspace/evaluations/${evaluation.id}`)
  ).json();
  if (!permitPartial)
    expect(
      stored.runs.every((r: { outcome: string }) => r.outcome === "completed"),
    ).toBe(true);
  return stored;
}

test("live paired chat keeps follow-ups independent and supports retest reports", async ({
  page,
}) => {
  await open(page, "chat");
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "State Rilo's storage choice using one short quotation. Keep one finding.",
    );
  await page.getByText("Supporting context", { exact: true }).click();
  await page
    .getByLabel("Source text", { exact: true })
    .fill("Rilo stores execution history in SQLite.");
  const first = await send(page);
  await expect(page.locator(".agent-response .response-text")).toHaveCount(2);
  await page
    .getByLabel("Send the same follow-up to both agents")
    .fill("Recall your previous conclusion in one sentence.");
  const followup = await send(page);
  for (const agent of first.spec.agent_ids as string[]) {
    const own = first.runs.find(
      (r: { agent_id: string }) => r.agent_id === agent,
    );
    expect(
      JSON.parse(followup.manifest.workspace.histories[agent][1].content),
    ).toEqual(own.output);
    expect(followup.manifest.workspace.histories[agent]).toHaveLength(2);
  }
  const download = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "Export PDF", exact: true })
    .first()
    .click();
  expect((await download).suggestedFilename()).toContain(first.id);
  const retestResponse = page.waitForResponse((r) =>
    r.url().endsWith(`/evaluations/${first.id}/retest`),
  );
  await page
    .getByRole("button", { name: "Retest", exact: true })
    .first()
    .click();
  const repeated = await (await retestResponse).json();
  await expect
    .poll(
      async () =>
        (
          await (
            await page.request.get(
              `/api/v1/workspace/evaluations/${repeated.id}`,
            )
          ).json()
        ).state,
      { timeout: 240000, intervals: [1500] },
    )
    .toBe("completed");
  await page.goto("/#/regression");
  await page.getByLabel("Baseline evaluation").selectOption(first.id);
  await page.getByLabel("Candidate evaluation").selectOption(repeated.id);
  await page.getByRole("button", { name: "Compare recorded results" }).click();
  await expect(
    page.getByText("Compatible recorded conditions", { exact: true }),
  ).toBeVisible();
});

test("live GitHub repository captures unfamiliar sources and actual file citations", async ({
  page,
}) => {
  await open(page, "repository");
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "Explain one core function in this repository using one short exact code quote. Note limitations.",
    );
  await page
    .getByLabel("GitHub repository URL")
    .fill("https://github.com/pallets/itsdangerous");
  const result = await send(page);
  expect(result.manifest.snapshot.metadata.commit_sha).toMatch(
    /^[a-f0-9]{40}$/,
  );
  expect(result.manifest.snapshot.sources.length).toBeGreaterThan(5);
  for (const run of result.runs)
    expect(
      run.assessment.findings.some(
        (f: { verification: { citations: { valid: boolean }[] } }) =>
          f.verification.citations.some((c) => c.valid),
      ),
    ).toBe(true);
  await expect(page.locator(".workspace-findings")).toHaveCount(2);
  await page.screenshot({
    path: path.join(inputs, "repository-desktop.png"),
    fullPage: true,
  });
});

test("live PDF upload returns the actual page and downloads persisted report", async ({
  page,
}) => {
  await open(page, "documents");
  await page
    .getByLabel("Attach documents", { exact: false })
    .setInputFiles(path.join(inputs, "source.pdf"));
  await expect(page.locator(".upload-list")).toContainText("source.pdf");
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "What is the retention period? Quote its exact supporting sentence. One finding.",
    );
  const result = await send(page);
  for (const run of result.runs)
    expect(
      run.assessment.findings.some(
        (f: {
          verification: { citations: { valid: boolean; page: number }[] };
        }) => f.verification.citations.some((c) => c.valid && c.page === 2),
      ),
    ).toBe(true);
  await page.locator(".workspace-findings summary").first().click();
  await expect(page.locator("blockquote").first()).toContainText("Page 2");
});

test("live website and source-only research preserve source references", async ({
  page,
}) => {
  await open(page, "website");
  await page.getByLabel("Public website URL").fill("https://example.com");
  await page.getByLabel("Maximum pages").fill("1");
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "What is this domain for? Quote one sentence from the page. One finding.",
    );
  const website = await send(page);
  expect(website.manifest.snapshot.sources[0].reference).toContain(
    "example.com",
  );
  await open(page, "search");
  await page.getByText("Supporting context", { exact: true }).click();
  await page
    .getByLabel("Source text", { exact: true })
    .fill(
      "Source note: The fictional test release was published on 2 November 2026.",
    );
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "Summarize this provided source. Quote the release date; do not claim a live search.",
    );
  const search = await send(page);
  expect(search.manifest.workspace.search_provider).toBe("off");
  expect(search.manifest.snapshot.metadata.search).toBeUndefined();
});

test("live uploaded repository tests execute only in the isolated Docker runner", async ({
  page,
}) => {
  await open(page, "repository");
  await page
    .getByLabel("Repository ZIP", { exact: false })
    .setInputFiles(path.join(inputs, "sample-repository.zip"));
  await expect(page.locator(".upload-list")).toContainText(
    "sample-repository.zip",
  );
  await page.getByRole("checkbox", { name: /Run Python unittest/ }).check();
  await page
    .getByLabel("What should the agents do?")
    .fill(
      "Explain the add function and its test. Cite one exact line. One finding.",
    );
  const result = await send(page, true);
  const tests = result.manifest.snapshot.metadata.runtime_tests;
  expect(tests.executed).toBe(true);
  expect(tests.exit_code).toBe(0);
  expect(tests.stderr).toContain("Ran 1 test");
  expect(tests.network).toBe("none");
  expect(tests.cleanup.status).toBe("completed");
  for (const run of result.runs.filter(
    (item: { outcome: string }) => item.outcome !== "completed",
  )) {
    await page
      .getByRole("button", {
        name: `Retry ${run.agent_name} response`,
        exact: true,
      })
      .click();
    await expect
      .poll(
        async () => {
          const conversation = await (
            await page.request.get(
              `/api/v1/workspace/conversations/${result.manifest.workspace.conversation_id}`,
            )
          ).json();
          const latest = conversation.turns[0].runs.find(
            (item: { agent_id: string }) => item.agent_id === run.agent_id,
          );
          return latest.id === run.id ? "waiting_for_retry" : latest.outcome;
        },
        { timeout: 180000, intervals: [1500] },
      )
      .toMatch(/^(completed|agent_error)$/);
    const conversation = await (
      await page.request.get(
        `/api/v1/workspace/conversations/${result.manifest.workspace.conversation_id}`,
      )
    ).json();
    expect(
      conversation.turns[0].attempts.some(
        (attempt: { id: string }) => attempt.id === run.id,
      ),
    ).toBe(true);
    const retry = conversation.turns[0].runs.find(
      (item: { agent_id: string }) => item.agent_id === run.agent_id,
    );
    expect(retry.id).not.toBe(run.id);
    expect(retry.model_calls).toBeGreaterThan(0);
    expect(retry.output_tokens).toBeGreaterThan(0);
    for (const sibling of result.runs.filter(
      (item: { outcome: string }) => item.outcome === "completed",
    )) {
      expect(
        conversation.turns[0].runs.find(
          (item: { id: string }) => item.id === sibling.id,
        ).output,
      ).toEqual(sibling.output);
    }
  }
});
