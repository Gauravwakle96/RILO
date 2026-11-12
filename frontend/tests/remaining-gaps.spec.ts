import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("saved records expose retention controls with accessible layout", async ({
  page,
}) => {
  await page.goto("/#/reports");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  const session = await (await page.request.get("/api/v1/session")).json();
  const title = `Retention controls acceptance ${Date.now()}`;
  const created = await page.request.post("/api/v1/workspace/conversations", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: { title, category: "chat" },
  });
  expect(created.status()).toBe(201);
  await page.getByLabel("Saved record type").selectOption("conversations");
  await page.getByLabel("Search all evaluations", { exact: true }).fill(title);
  await expect(
    page.getByRole("button", { name: "Archive", exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Archive", exact: true }).click();
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
  await page.getByLabel("Show archived records").check();
  await expect(page.getByLabel("Show archived records")).toBeChecked();
  await expect(
    page.getByRole("button", { name: "Restore", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Restore", exact: true }).click();
  await expect(page.getByRole("link", { name: title })).toHaveCount(0);
  await page.getByLabel("Show archived records").uncheck();
  await expect(page.getByRole("link", { name: title })).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("saved conversation links survive reload and browser navigation", async ({
  page,
}) => {
  await page.goto("/#/reports");
  await expect(
    page.getByText("Local API connected", { exact: true }),
  ).toBeVisible();
  const session = await (await page.request.get("/api/v1/session")).json();
  const title = `Conversation link acceptance ${Date.now()}`;
  const response = await page.request.post("/api/v1/workspace/conversations", {
    headers: { "X-CSRF-Token": session.csrf_token },
    data: { title, category: "chat" },
  });
  expect(response.status()).toBe(201);
  const conversation = await response.json();
  await page.getByLabel("Saved record type").selectOption("conversations");
  await page.getByLabel("Search all evaluations", { exact: true }).fill(title);
  await page.getByRole("link", { name: title }).click();
  await expect(page.getByLabel("Saved conversations")).toHaveValue(
    conversation.id,
  );
  await expect(
    page.getByRole("button", { name: "Export conversation", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Saved conversations")).toHaveValue(
    conversation.id,
  );
  await page
    .getByRole("button", { name: "New conversation", exact: true })
    .click();
  await expect(page).toHaveURL(/#\/chat$/);
  await expect(page.getByLabel("Saved conversations")).toHaveValue("");
  await page.goBack();
  await expect(page.getByLabel("Saved conversations")).toHaveValue(
    conversation.id,
  );
});

test("public URL investigation and local folder input are discoverable", async ({
  page,
}) => {
  await page.goto("/#/search");
  await expect(page.getByLabel("Public website URL")).toBeVisible();
  await page.goto("/#/repository");
  await expect(page.getByLabel("Import local repository folder")).toBeVisible();
  await expect(
    page.getByText("Creates a bounded ZIP in your browser.", { exact: false }),
  ).toBeVisible();
});

test("folder archive has actual safe relative files readable by Python", async ({
  page,
}) => {
  await page.goto("/#/repository");
  const result = await page.evaluate(async () => {
    const { repositoryZip } = await import("/src/lib/repository-zip.ts");
    const files = [
      ["project/src/main.py", 'print("hello")'],
      ["project/.env", "PRIVATE"],
      ["project/node_modules/a.js", "DEPENDENCY"],
    ].map(([path, content]) => {
      const file = new File([content], path.split("/").pop()!);
      Object.defineProperty(file, "webkitRelativePath", { value: path });
      return file;
    });
    const result = await repositoryZip(files);
    const bytes = new Uint8Array(await result.file.arrayBuffer());
    return {
      included: result.included,
      skipped: result.skipped,
      bytes: Array.from(bytes),
    };
  });
  expect(result.included).toBe(1);
  expect(result.skipped).toBe(2);
  const { spawnSync } = await import("node:child_process");
  const parsed = spawnSync(
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python",
    [
      "-c",
      "import sys,io,zipfile; z=zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())); assert z.namelist()==['src/main.py']; assert z.read('src/main.py')==b'print(\"hello\")'; print('valid')",
    ],
    { input: Buffer.from(result.bytes), encoding: "utf-8" },
  );
  expect(parsed.status, parsed.stderr).toBe(0);
  expect(parsed.stdout).toContain("valid");
});
