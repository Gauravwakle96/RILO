import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../frontend/package.json", import.meta.url));
const { chromium } = require("@playwright/test");
const baseUrl = process.argv[2] || "http://127.0.0.1:8018";
const origin = new URL(baseUrl).origin;
const browser = await chromium.launch({ headless: true });
const errors = [];
const failedRequests = [];
const externalRequests = [];

try {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10_000);
  page.on("console", message => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", error => errors.push(error.message));
  page.on("requestfailed", request => failedRequests.push(request.url()));
  page.on("request", request => {
    if (new URL(request.url()).origin !== origin) externalRequests.push(request.url());
  });
  const open = async path => {
    const response = await page.goto(baseUrl + path, { waitUntil: "domcontentloaded" });
    assert.equal(response.status(), 200);
    await page.locator(".operation").first().waitFor();
    await page.waitForLoadState("networkidle", { timeout: 10_000 });
    return response;
  };
  const document = await open("/docs");
  assert.match(document.headers()["content-security-policy"], /script-src 'self'/);
  const operationCount = await page.locator(".operation").count();
  const schemaCount = await page.locator(".schema").count();
  assert.ok(operationCount >= 20);
  assert.ok(schemaCount >= 8);
  await page.getByLabel("Find an operation").fill("/experiments");
  const filtered = await page.locator(".operation:visible").count();
  assert.ok(filtered > 0 && filtered < operationCount);
  await page.getByLabel("HTTP method").selectOption("POST");
  const postCount = await page.locator(".operation:visible").count();
  assert.ok(postCount > 0 && postCount < filtered);
  await page.locator(".operation:visible summary").first().focus();
  await page.keyboard.press("Enter");
  assert.equal(await page.locator(".operation:visible[open] .operation-body").first().isVisible(), true);
  await page.getByLabel("Find an operation").fill("unmatched-operation-example");
  assert.equal(await page.locator("#status").textContent(), "No operations match this search.");
  await page.getByLabel("Find an operation").fill("");
  await page.getByLabel("HTTP method").selectOption("");
  await page.setViewportSize({ width: 375, height: 812 });
  const mobile = await page.evaluate(() => ({
    content: document.documentElement.scrollWidth,
    viewport: innerWidth,
  }));
  assert.ok(mobile.content <= mobile.viewport);
  await open("/redoc");
  assert.equal(await page.locator(".operation").count(), operationCount);
  assert.equal((await context.request.get(baseUrl + "/openapi.json")).status(), 200);
  assert.equal((await context.request.get(baseUrl + "/docs-assets/not-found.js")).status(), 404);
  assert.equal((await context.request.get(baseUrl + "/api/v1/unknown")).status(), 404);
  assert.deepEqual(errors, []);
  assert.deepEqual(failedRequests, []);
  assert.deepEqual(externalRequests, []);
  console.log(JSON.stringify({
    status: "passed", operationCount, schemaCount, filtered, postCount, mobile,
    javascriptErrors: errors.length, failedRequests: failedRequests.length,
    externalRequests: externalRequests.length,
  }));
} finally {
  await browser.close();
}
