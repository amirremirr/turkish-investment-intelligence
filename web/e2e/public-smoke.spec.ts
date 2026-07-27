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

test("mobile navigation exposes the primary routes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/", { waitUntil: "networkidle" });

  await page.getByRole("button", { name: "Open navigation" }).click();
  const nav = page.getByRole("navigation", { name: "Mobile navigation" });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "Funds" })).toBeVisible();
  await expect(nav.getByRole("link", { name: "Data status" })).toBeVisible();
});

test("screener restores shareable filters and sort from the URL", async ({ page }) => {
  await page.goto("/funds?q=ABC&minAum=500000000&sort=aum&dir=asc", {
    waitUntil: "networkidle",
  });

  await expect(page.getByRole("textbox", { name: "Search funds by code or name" })).toHaveValue("ABC");
  await expect(page.getByRole("combobox", { name: "Filter by minimum assets under management" })).toHaveValue("500000000");
  await expect(page.getByRole("columnheader", { name: /AUM/ })).toHaveAttribute("aria-sort", "ascending");
});
