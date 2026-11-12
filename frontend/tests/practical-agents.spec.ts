import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("practical catalog contains four useful profiles and separate reference agents", async ({
  page,
}) => {
  await page.goto("/#/agents");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  await expect(page.getByLabel("Agent category")).toHaveValue("practical");
  await expect(page.locator(".agent-panel")).toHaveCount(4);
  for (const name of [
    "Customer Support Assistant",
    "Document Assistant",
    "Coding Assistant",
    "Research Assistant",
  ])
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  await page.getByLabel("Agent category").selectOption("reference");
  await expect(page.locator(".agent-panel")).toHaveCount(2);
  await expect(
    page.getByRole("heading", { name: "Scout", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Relay", exact: true }),
  ).toBeVisible();
});

test("each assistant opens a compatible workspace and loads real editable task checks without dispatch", async ({
  page,
}) => {
  let turns = 0;
  page.on("request", (request) => {
    if (
      request.method() === "POST" &&
      /conversations\/[^/]+\/turns$/.test(request.url())
    )
      turns++;
  });
  for (const [name, id, category] of [
    ["Customer Support Assistant", "customer_support", "chat"],
    ["Document Assistant", "document_analyst", "chat"],
    ["Coding Assistant", "repo_analyst", "repository"],
    ["Research Assistant", "web_analyst", "search"],
  ]) {
    await page.goto("/#/agents");
    const card = page
      .locator(".agent-panel")
      .filter({ has: page.getByRole("heading", { name, exact: true }) });
    await card.getByRole("link", { name: "Use assistant" }).click();
    await expect(page).toHaveURL(new RegExp(`#/${category}\\?profile=${id}$`));
    await expect(page.getByLabel("Agent A", { exact: true })).toHaveValue(id);
    await page.reload();
    await expect(page.getByLabel("Agent A", { exact: true })).toHaveValue(id);
    await page
      .getByRole("button", { name: `Load ${name} example`, exact: true })
      .click();
    await expect(page.getByLabel("What should the agents do?")).not.toHaveValue(
      "",
    );
    await expect(
      page.getByLabel("Success checks").locator("fieldset"),
    ).toHaveCount(
      id === "repo_analyst" ? 2 : id === "customer_support" ? 4 : 3,
    );
    await expect(page.getByLabel("Web search", { exact: true })).toHaveValue(
      "off",
    );
    await expect(
      page.getByText("Editable example loaded; nothing has been sent.", {
        exact: false,
      }),
    ).toBeVisible();
  }
  expect(turns).toBe(0);
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
