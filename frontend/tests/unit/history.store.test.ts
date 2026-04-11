import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { useHistoryStore } from "../../src/stores/history";

vi.mock("../../src/services/api", () => ({
  fetchResearchTasks: vi.fn(),
  deleteResearchTask: vi.fn(async () => ({ deleted: true }))
}));

import { deleteResearchTask } from "../../src/services/api";

describe("history store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("removes a deleted task from history", async () => {
    const store = useHistoryStore();

    store.tasks = [
      {
        id: "task-1",
        parent_task_id: null,
        research_iteration: 1,
        status: "completed",
        query: "topic",
        follow_up_request: null,
        provider: "openai",
        thinking_model: "gpt-5.4-mini",
        task_model: "gpt-5.4-mini",
        search_provider: "tavily",
        language: "zh-CN",
        current_step: "completed",
        created_at: "2026-04-01T00:00:00Z",
        updated_at: "2026-04-01T00:00:00Z",
        completed_at: "2026-04-01T00:00:00Z"
      }
    ];

    await store.deleteTask("task-1");

    expect(deleteResearchTask).toHaveBeenCalledWith("task-1");
    expect(store.tasks).toEqual([]);
    expect(store.deletingTaskIds).toEqual([]);
  });
});
