import { test, expect } from "@playwright/test";

test("starts a mocked research workflow", async ({ page }) => {
  await page.route("**/api/v1/research/tasks?limit=20", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([])
    });
  });

  await page.route("**/api/v1/providers", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        llm_providers: {
          openai: {
            label: "OpenAI",
            models: ["gpt-5.4-mini"]
          }
        },
        search_providers: {
          searxng: {
            label: "SearxNG"
          }
        }
      })
    });
  });

  await page.route("**/api/v1/research/clarify", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ questions: ["你更关注市场还是技术？"] })
    });
  });

  await page.route("**/api/v1/research/tasks", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ task_id: "task-1", status: "queued" })
    });
  });

  await page.route("**/api/v1/research/tasks/task-1/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        "event: infor",
        'data: {"name":"deep-research","version":"0.1.0","task_id":"task-1"}',
        "",
        "event: progress",
        'data: {"step":"clarify-questions","status":"start"}',
        "",
        "event: progress",
        'data: {"step":"clarify-questions","status":"end","data":{"questions":["你更关注市场还是技术？"],"answers":[""]}}',
        "",
        "event: progress",
        'data: {"step":"report-plan","status":"start"}',
        "",
        "event: message",
        'data: {"type":"text","text":"# Plan"}',
        "",
        "event: progress",
        'data: {"step":"final-report","status":"start"}',
        "",
        "event: message",
        'data: {"type":"text","text":"# Final Report"}',
        "",
        "event: done",
        'data: {"task_id":"task-1","status":"completed"}',
        ""
      ].join("\n")
    });
  });

  await page.goto("/");
  await page.getByPlaceholder("输入你的研究主题、目标、背景和输出要求").fill("研究 AI Agent 市场");
  await expect(page.getByRole("button", { name: "启动研究" })).toBeDisabled();
  await page.getByRole("button", { name: "生成澄清问题" }).click();
  await expect(page.getByText("你更关注市场还是技术？")).toBeVisible();
  await expect(page.getByRole("button", { name: "启动研究" })).toBeEnabled();
  await page.getByRole("button", { name: "启动研究" }).click();
  await expect(page.getByText("Final Report")).toBeVisible();
  await expect(page.getByRole("button", { name: "查看独立报告" })).toBeVisible();
});
