import { expect, test } from "@playwright/test";

const routes = ["/", "/funds", "/market", "/research", "/status", "/stocks"];

for (const route of routes) {
  test(`public route ${route} renders without a server error`, async ({ page }) => {
    const response = await page.goto(route, { waitUntil: "networkidle" });
    expect(response?.status(), `${route} response`).toBeLessThan(500);
    await expect(page.locator("main")).toBeVisible();
    await expect(page.locator("body")).not.toContainText("Application error");
  });
}
