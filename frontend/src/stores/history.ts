import { defineStore } from "pinia";

import { deleteResearchTask, fetchResearchTasks } from "../services/api";
import type { ResearchTaskSummary } from "../types/research";

interface HistoryState {
  tasks: ResearchTaskSummary[];
  loading: boolean;
  deletingTaskIds: string[];
  errorMessage: string;
}

export const useHistoryStore = defineStore("history", {
  state: (): HistoryState => ({
    tasks: [],
    loading: false,
    deletingTaskIds: [],
    errorMessage: ""
  }),
  actions: {
    async loadTasks(limit = 20) {
      this.loading = true;
      this.errorMessage = "";
      try {
        this.tasks = await fetchResearchTasks(limit);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "加载历史任务失败";
      } finally {
        this.loading = false;
      }
    },
    async deleteTask(taskId: string) {
      this.errorMessage = "";
      if (this.deletingTaskIds.includes(taskId)) {
        return;
      }
      this.deletingTaskIds.push(taskId);
      try {
        await deleteResearchTask(taskId);
        this.tasks = this.tasks.filter((task) => task.id !== taskId);
      } catch (error) {
        this.errorMessage = error instanceof Error ? error.message : "删除历史任务失败";
        throw error;
      } finally {
        this.deletingTaskIds = this.deletingTaskIds.filter((id) => id !== taskId);
      }
    }
  }
});
