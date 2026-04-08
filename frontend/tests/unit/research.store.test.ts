import { beforeEach, describe, expect, it } from "vitest";
import { createPinia, setActivePinia } from "pinia";

import { useResearchStore } from "../../src/stores/research";

describe("research store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    localStorage.clear();
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
});
