import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("local settings expose provider status, privacy and private backup", async ({
  page,
}) => {
  await page.goto("/#/settings");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "AgentRouter inference" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Bynara inference" }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Privacy and local storage" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Download private backup" }),
  ).toBeVisible();
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
});

test("same agent candidates expose independent configuration without dispatch", async ({
  page,
}) => {
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await page
    .getByText("Compare models and instructions", { exact: true })
    .click();
  for (const name of [
    "Model A",
    "Model B",
    "Version A",
    "Version B",
    "Temperature A",
    "Temperature B",
    "Recovery A",
    "Recovery B",
  ])
    await expect(page.getByLabel(name)).toBeVisible();
  await expect(page.getByLabel("Find conversations")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("captured website sources can be inspected and focused without sending a task", async ({
  page,
}) => {
  await page.goto("/#/chat");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  const response = await page.request.get(
    "/api/v1/workspace/history?kind=conversations&category=chat&query=Local%20product%20%C2%B7%20actual%20website%20in%20chat",
  );
  const record = (await response.json()).items[0];
  test.skip(!record, "Requires the actual public website acceptance record.");
  await page
    .getByLabel("Find conversations")
    .fill("Local product · actual website in chat");
  await expect(
    page
      .getByLabel("Saved conversations")
      .locator(`option[value="${record.id}"]`),
  ).toHaveCount(1);
  await page.getByLabel("Saved conversations").selectOption(record.id);
  await page
    .getByText("Inspect captured sources and focus your next task", {
      exact: true,
    })
    .click();
  await page.getByRole("button", { name: "Load captured sources" }).click();
  await expect(page.locator(".source-inspector pre")).toContainText(
    "documentation examples",
  );
  await page
    .getByRole("button", { name: "Focus next task on this source" })
    .click();
  await expect(
    page.getByRole("button", { name: "Remove focus", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Send to both agents", exact: true }),
  ).toBeDisabled();
});
