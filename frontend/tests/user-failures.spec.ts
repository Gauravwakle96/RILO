import { expect, test } from "@playwright/test";

test.skip(
  process.env.RILO_USER_FAILURE_ACCEPTANCE !== "1",
  "Local acceptance against the user's original immutable records.",
);

test("original failed literal checks are shown without a reassuring tie", async ({
  page,
}) => {
  await page.goto("/#/experiments/exp_d8e812dccc5e46e5");
  await expect(
    page.getByText("Neither met the checks", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByText("Tie on declared checks", { exact: true }),
  ).toHaveCount(0);
  await expect(page.locator(".metrics-strip")).toContainText(
    "declared checks only",
  );
  await expect(page.locator(".check-comparison")).toContainText(
    "global ai hakathon",
  );
});

test("old source-free chat keeps notes without unsupported evidence badges", async ({
  page,
}) => {
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  const original = await (
    await page.request.get("/api/v1/workspace/evaluations/exp_7716a10d16ca4be0")
  ).json();
  await page
    .getByLabel("Saved conversations")
    .selectOption(original.manifest.workspace.conversation_id);
  await expect(page.locator(".agent-response").first()).toContainText(
    "Conversation response",
  );
  await expect(page.locator(".agent-response .workspace-findings")).toHaveCount(
    0,
  );
  await expect(page.locator(".workspace-turn").last().locator(".agent-response").first()).toContainText(
    "not evidence-verified",
  );
});
