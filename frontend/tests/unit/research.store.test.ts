import { beforeEach, describe, expect, it, vi } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { useResearchStore } from "../../src/stores/research";
import { useSettingsStore } from "../../src/stores/settings";
import { useHistoryStore } from "../../src/stores/history";

vi.mock("../../src/services/api", () => ({
  clarifyResearch: vi.fn(),
  createFollowUpResearchTask: vi.fn(),
  createResearchTask: vi.fn(async () => ({ task_id: "task-1", status: "queued" })),
  fetchResearchTask: vi.fn(),
  fetchResearchTasks: vi.fn(),
  deleteResearchTask: vi.fn()
}));

vi.mock("../../src/services/sse", () => ({
  openTaskStream: vi.fn(
    () =>
      new Promise<void>(() => {
        // Keep the stream open to mimic a long-running task.
      })
  )
}));

import { createResearchTask } from "../../src/services/api";
import { openTaskStream } from "../../src/services/sse";

describe("research store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
    vi.clearAllMocks();
  });

  it("applies report-plan and final-report events in order", () => {
    const store = useResearchStore();
    store.applySseEvent({ event: "progress", data: { step: "report-plan", status: "start" } });
    store.applySseEvent({ event: "message", data: { type: "text", text: "# Plan" } });
    store.applySseEvent({ event: "progress", data: { step: "final-report", status: "start" } });
    store.applySseEvent({ event: "message", data: { type: "text", text: "# Final" } });

    expect(store.reportPlan).toContain("# Plan");
    expect(store.finalReport).toContain("# Final");
  });

  it("captures failure events", () => {
    const store = useResearchStore();
    store.applySseEvent({ event: "error", data: { message: "boom" } });
    store.applySseEvent({ event: "done", data: { status: "failed" } });

    expect(store.errorMessage).toBe("boom");
    expect(store.status).toBe("failed");
  });

  it("clears clarify state when query changes", () => {
    const store = useResearchStore();
    store.query = "旧主题";
    store.clarifyQuestions = ["Q1"];
    store.answers = ["A1"];
    store.lastClarifiedQuery = "旧主题";

    store.setQuery("新主题");

    expect(store.clarifyQuestions).toEqual([]);
    expect(store.answers).toEqual([]);
    expect(store.lastClarifiedQuery).toBe("");
  });

  it("records workflow role and retry metadata from SSE events", () => {
    const store = useResearchStore();
    store.applySseEvent({
      event: "reasoning",
      data: { type: "text", text: "Supervisor dispatched tasks", role: "supervisor" }
    });
    store.applySseEvent({
      event: "progress",
      data: {
        step: "search-task",
        status: "end",
        role: "researcher",
        attempt: 2,
        compressed_context: true
      }
    });

    expect(store.reasoningLog[0]).toBe("[supervisor] Supervisor dispatched tasks");
    expect(store.progressHistory[0]).toMatchObject({
      step: "search-task",
      status: "end",
      role: "researcher",
      attempt: 2,
      compressedContext: true
    });
  });

  it("clears loadingTask after task creation without waiting for stream or history refresh", async () => {
    const settingsStore = useSettingsStore();
    const historyStore = useHistoryStore();
    const store = useResearchStore();

    settingsStore.provider = "openai";
    settingsStore.thinkingModel = "gpt-5.4-mini";
    settingsStore.taskModel = "gpt-5.4-mini";
    settingsStore.searchProvider = "searxng";
    settingsStore.language = "zh-CN";
    settingsStore.maxResults = 5;
    historyStore.loadTasks = vi.fn(
      () =>
        new Promise<void>(() => {
          // Keep history refresh pending to verify it does not block the start button spinner.
        })
    );

    store.query = "rag技术的发展情况";
    store.clarifyQuestions = ["你更关注论文、产品还是工程实践？"];
    store.answers = ["都关注"];
    store.lastClarifiedQuery = store.query;

    await store.startResearch();

    expect(createResearchTask).toHaveBeenCalledWith({
      query: "rag技术的发展情况",
      questions: ["你更关注论文、产品还是工程实践？"],
      answers: ["都关注"],
      provider: "openai",
      thinking_model: "gpt-5.4-mini",
      task_model: "gpt-5.4-mini",
      search_provider: "searxng",
      language: "zh-CN",
      max_results: 5
    });
    expect(historyStore.loadTasks).toHaveBeenCalled();
    expect(openTaskStream).toHaveBeenCalledWith(
      "/api/v1/research/tasks/task-1/stream",
      expect.any(Function),
      expect.any(AbortSignal)
    );
    expect(store.loadingTask).toBe(false);
    expect(store.taskId).toBe("task-1");
  });

  it("clears loaded task state when the active history item is deleted", () => {
    const store = useResearchStore();

    store.taskId = "task-1";
    store.query = "RAG 技术的发展情况";
    store.lastClarifiedQuery = "RAG 技术的发展情况";
    store.clarifyQuestions = ["Q1"];
    store.answers = ["A1"];
    store.status = "completed";
    localStorage.setItem("deep-research-last-task-id", "task-1");

    store.clearDeletedTask("task-1");

    expect(store.taskId).toBe("");
    expect(store.query).toBe("");
    expect(store.clarifyQuestions).toEqual([]);
    expect(localStorage.getItem("deep-research-last-task-id")).toBeNull();
  });
});
