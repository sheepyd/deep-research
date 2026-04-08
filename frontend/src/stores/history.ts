import { defineStore } from "pinia";

import { fetchResearchTasks } from "../services/api";
import type { ResearchTaskSummary } from "../types/research";
import { useAuthStore } from "./auth";

interface HistoryState {
  tasks: ResearchTaskSummary[];
  loading: boolean;
  errorMessage: string;
}

export const useHistoryStore = defineStore("history", {
  state: (): HistoryState => ({
    tasks: [],
    loading: false,
    errorMessage: ""
  }),
  actions: {
    async loadTasks(limit = 20) {
      const auth = useAuthStore();
      this.loading = true;
      this.errorMessage = "";
      try {
        this.tasks = await fetchResearchTasks(auth.apiBaseUrl, auth.token, limit);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "加载历史任务失败";
      } finally {
        this.loading = false;
      }
    }
  }
});
