import { defineStore } from "pinia";

import { clarifyResearch, createFollowUpResearchTask, createResearchTask, fetchResearchTask } from "../services/api";
import { openTaskStream } from "../services/sse";
import { useAuthStore } from "./auth";
import { useHistoryStore } from "./history";
import { useSettingsStore } from "./settings";
import type { EventRecord, ResearchTaskDetail, SseEvent } from "../types/research";

const TASK_KEY = "deep-research-last-task-id";
let activeStreamController: AbortController | null = null;

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
    taskId: "",
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
        this.errorMessage = "";
      }
      this.query = value;
    },
    updateAnswer(index: number, value: string) {
      this.answers[index] = value;
    },
    clearDeletedTask(taskId: string) {
      if (this.taskId !== taskId) {
        return;
      }
      this.resetTask();
      this.taskId = "";
      this.query = "";
      this.lastClarifiedQuery = "";
      this.clarifyQuestions = [];
      this.answers = [];
      localStorage.removeItem(TASK_KEY);
    },
    resetTask() {
      activeStreamController?.abort();
      activeStreamController = null;
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
          llm_api_key: settings.llmApiKey || undefined,
          llm_base_url: settings.llmBaseUrl || undefined,
          language: settings.language
        });
        this.clarifyQuestions = result.questions;
        if (this.clarifyQuestions.length === 0) {
          this.errorMessage = "模型未能生成澄清问题，请检查模型配置或稍后重试。";
        }
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
          llm_api_key: settings.llmApiKey || undefined,
          llm_base_url: settings.llmBaseUrl || undefined,
          search_provider: settings.searchProvider,
          search_api_key: settings.searchApiKey || undefined,
          search_base_url: settings.searchBaseUrl || undefined,
          language: settings.language,
          max_results: settings.maxResults
        });
        this.taskId = result.task_id;
        this.status = result.status;
        localStorage.setItem(TASK_KEY, this.taskId);
        void history.loadTasks();
        void this.connectStream(this.taskId);
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
        void history.loadTasks();
        void this.connectStream(this.taskId);
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
      activeStreamController?.abort();
      const controller = new AbortController();
      activeStreamController = controller;
      try {
        await openTaskStream(
          `${auth.apiBaseUrl}/api/v1/research/tasks/${taskId}/stream`,
          auth.token,
          (event) => {
            this.applySseEvent(event);
          },
          controller.signal
        );
      } catch (error) {
        if (!(error instanceof DOMException && error.name === "AbortError")) {
          this.errorMessage = error instanceof Error ? error.message : "任务流连接失败";
          this.status = "failed";
        }
      } finally {
        if (activeStreamController === controller) {
          activeStreamController = null;
        }
      }
    }
  }
});
