import { test, expect } from "@playwright/test";

test("landing page renders", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Literature review, evidence-backed/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Get started/i })).toBeVisible();
});

test("login page has Google button", async ({ page }) => {
  await page.goto("/login");
  await expect(page.getByRole("button", { name: /Continue with Google/i })).toBeVisible();
});
