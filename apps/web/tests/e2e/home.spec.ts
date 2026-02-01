import { test, expect } from "@playwright/test";

test("home page displays title", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Aave Risk Monitor" })).toBeVisible();
});
