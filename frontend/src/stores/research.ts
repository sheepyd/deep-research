import { defineStore } from "pinia";

import { clarifyResearch, createFollowUpResearchTask, createResearchTask, fetchResearchTask } from "../services/api";
import { openTaskStream } from "../services/sse";
import { useAuthStore } from "./auth";
import { useHistoryStore } from "./history";
import { useSettingsStore } from "./settings";
import type { EventRecord, ResearchTaskDetail, SseEvent } from "../types/research";

const TASK_KEY = "deep-research-last-task-id";

interface ProgressState {
  step: string;
  status: string;
  name?: string;
  role?: string;
  attempt?: number;
  compressedContext?: boolean;
}

interface ResearchState {
  query: string;
  lastClarifiedQuery: string;
  clarifyQuestions: string[];
  answers: string[];
  taskId: string;
  status: string;
  loadingClarify: boolean;
  loadingTask: boolean;
  eventLog: string[];
  reasoningLog: string[];
  reportPlan: string;
  finalReport: string;
  currentStep: string;
  progressHistory: ProgressState[];
  sources: ResearchTaskDetail["sources"];
  errorMessage: string;
}

function defaultState(): ResearchState {
  return {
    query: "",
    lastClarifiedQuery: "",
    clarifyQuestions: [],
    answers: [],
    taskId: localStorage.getItem(TASK_KEY) ?? "",
    status: "idle",
    loadingClarify: false,
    loadingTask: false,
    eventLog: [],
    reasoningLog: [],
    reportPlan: "",
    finalReport: "",
    currentStep: "",
    progressHistory: [],
    sources: [],
    errorMessage: ""
  };
}

export const useResearchStore = defineStore("research", {
  state: (): ResearchState => defaultState(),
  actions: {
    setQuery(value: string) {
      if (value !== this.query) {
        this.clarifyQuestions = [];
        this.answers = [];
        this.lastClarifiedQuery = "";
      }
      this.query = value;
    },
    updateAnswer(index: number, value: string) {
      this.answers[index] = value;
    },
    resetTask() {
      this.status = "idle";
      this.eventLog = [];
      this.reasoningLog = [];
      this.reportPlan = "";
      this.finalReport = "";
      this.currentStep = "";
      this.progressHistory = [];
      this.sources = [];
      this.errorMessage = "";
    },
    async requestClarify() {
      const auth = useAuthStore();
      const settings = useSettingsStore();
      this.loadingClarify = true;
      this.errorMessage = "";
      try {
        const result = await clarifyResearch(auth.apiBaseUrl, auth.token, {
          query: this.query,
          provider: settings.provider,
          thinking_model: settings.thinkingModel,
          language: settings.language
        });
        this.clarifyQuestions = result.questions;
        this.answers = result.questions.map(() => "");
        this.lastClarifiedQuery = this.query;
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "澄清问题生成失败";
      } finally {
        this.loadingClarify = false;
      }
    },
    async startResearch() {
      const auth = useAuthStore();
      const history = useHistoryStore();
      const settings = useSettingsStore();
      if (!this.clarifyQuestions.length || this.lastClarifiedQuery !== this.query) {
        this.errorMessage = "请先基于当前主题生成澄清问题，再启动研究";
        return;
      }
      this.loadingTask = true;
      this.resetTask();
      try {
        const result = await createResearchTask(auth.apiBaseUrl, auth.token, {
          query: this.query,
          questions: this.clarifyQuestions,
          answers: this.answers.filter((item) => item.trim().length > 0),
          provider: settings.provider,
          thinking_model: settings.thinkingModel,
          task_model: settings.taskModel,
          search_provider: settings.searchProvider,
          language: settings.language,
          max_results: settings.maxResults
        });
        this.taskId = result.task_id;
        this.status = result.status;
        localStorage.setItem(TASK_KEY, this.taskId);
        await history.loadTasks();
        await this.connectStream(this.taskId);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "任务启动失败";
      } finally {
        this.loadingTask = false;
      }
    },
    async startFollowUpResearch(parentTaskId: string, followUpRequest: string) {
      const auth = useAuthStore();
      const history = useHistoryStore();
      const settings = useSettingsStore();
      this.loadingTask = true;
      this.errorMessage = "";
      this.resetTask();
      try {
        const result = await createFollowUpResearchTask(auth.apiBaseUrl, auth.token, parentTaskId, {
          follow_up_request: followUpRequest,
          max_results: settings.maxResults
        });
        this.taskId = result.task_id;
        this.status = result.status;
        localStorage.setItem(TASK_KEY, this.taskId);
        await history.loadTasks();
        await this.connectStream(this.taskId);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "追加研究启动失败";
      } finally {
        this.loadingTask = false;
      }
    },
    async hydrateTask(taskId: string) {
      const auth = useAuthStore();
      const detail = await fetchResearchTask(auth.apiBaseUrl, auth.token, taskId);
      this.taskId = detail.id;
      this.status = detail.status;
      this.query = detail.query;
      this.lastClarifiedQuery = detail.query;
      this.clarifyQuestions = detail.clarify_questions;
      this.answers = detail.clarify_answers;
      this.reportPlan = "";
      this.finalReport = "";
      this.sources = detail.sources;
      this.currentStep = detail.current_step ?? "";
      this.errorMessage = detail.error_message ?? "";
      this.eventLog = [];
      this.reasoningLog = [];
      this.progressHistory = [];
      detail.events.forEach((event) => this.applyStoredEvent(event));
      if (!this.reportPlan) {
        this.reportPlan = detail.report_plan ?? "";
      }
      if (!this.finalReport) {
        this.finalReport = detail.final_report ?? "";
      }
    },
    applyStoredEvent(event: EventRecord) {
      this.applySseEvent({ event: event.event_type, data: event.payload_json });
    },
    applySseEvent(payload: SseEvent) {
      if (payload.event === "message") {
        const text = String(payload.data.text ?? "");
        this.eventLog.push(text);
        if (this.currentStep === "report-plan" && !this.finalReport) {
          this.reportPlan += text;
        } else {
          this.finalReport += text;
        }
      } else if (payload.event === "reasoning") {
        const text = String(payload.data.text ?? "");
        const role = payload.data.role ? String(payload.data.role) : "";
        this.reasoningLog.push(role ? `[${role}] ${text}` : text);
      } else if (payload.event === "progress") {
        const step = String(payload.data.step ?? "");
        const status = String(payload.data.status ?? "");
        const name = payload.data.name ? String(payload.data.name) : undefined;
        const role = payload.data.role ? String(payload.data.role) : undefined;
        const attempt =
          typeof payload.data.attempt === "number" ? payload.data.attempt : undefined;
        const compressedContext =
          typeof payload.data.compressed_context === "boolean"
            ? payload.data.compressed_context
            : undefined;
        this.currentStep = step;
        this.progressHistory.push({ step, status, name, role, attempt, compressedContext });
        if (step === "report-plan" && status === "start") {
          this.reportPlan = "";
        }
        if (step === "final-report" && status === "start") {
          this.finalReport = "";
        }
      } else if (payload.event === "error") {
        this.errorMessage = String(payload.data.message ?? "任务失败");
        this.status = "failed";
      } else if (payload.event === "done") {
        this.status = String(payload.data.status ?? "completed");
        void useHistoryStore().loadTasks();
      }
    },
    async connectStream(taskId: string) {
      const auth = useAuthStore();
      await openTaskStream(
        `${auth.apiBaseUrl}/api/v1/research/tasks/${taskId}/stream`,
        auth.token,
        (event) => {
          this.applySseEvent(event);
        }
      );
    }
  }
});
