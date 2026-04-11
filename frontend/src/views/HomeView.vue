<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import MarkdownIt from "markdown-it";
import { ElMessage, ElMessageBox } from "element-plus";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { Github, History, LogOut, Settings, Trash2 } from "lucide-vue-next";

import { fetchProviders } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useHistoryStore } from "../stores/history";
import { useResearchStore } from "../stores/research";
import { useSettingsStore } from "../stores/settings";
import WorkflowProgress from "../components/WorkflowProgress.vue";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
});

const router = useRouter();
const authStore = useAuthStore();
const historyStore = useHistoryStore();
const researchStore = useResearchStore();
const settingsStore = useSettingsStore();

const { tasks, loading: loadingHistory, deletingTaskIds } = storeToRefs(historyStore);
const {
  query,
  clarifyQuestions,
  answers,
  loadingClarify,
  loadingTask,
  taskId,
  status,
  reportPlan,
  finalReport,
  progressHistory,
  reasoningLog,
  errorMessage,
  sources
} = storeToRefs(researchStore);

const renderedReport = computed(() => md.render(finalReport.value || ""));
const renderedPlan = computed(() => md.render(reportPlan.value || ""));
const currentTaskLabel = computed(() => taskId.value || "尚未启动");
const canOpenReport = computed(() => Boolean(taskId.value && (finalReport.value || status.value !== "idle")));
const canStartResearch = computed(
  () => Boolean(query.value.trim() && clarifyQuestions.value.length && researchStore.lastClarifiedQuery === query.value)
);

const activeStage = computed(() => {
  if (taskId.value) {
    if (status.value === "completed" || status.value === "failed") return "done";
    return "progress";
  }
  if (clarifyQuestions.value.length > 0) return "clarify";
  return "workbench";
});

watch(
  () => status.value,
  (newStatus) => {
    if (newStatus === "completed" && taskId.value) {
      router.push({ name: "report", params: { taskId: taskId.value } });
    }
  }
);

const showHistory = ref(false);
const showSettings = ref(false);

function formatDate(value: string | null): string {
  if (!value) return "进行中";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function taskStageLabel(step: string | null): string {
  if (!step) return "queued";
  return step;
}

async function openTaskInWorkspace(id: string): Promise<void> {
  await researchStore.hydrateTask(id);
  if (!["completed", "failed"].includes(researchStore.status)) {
    void researchStore.connectStream(id);
  }
  showHistory.value = false;
  if (researchStore.status === "completed") {
    router.push({ name: "report", params: { taskId: id } });
  }
}

function openReport(id: string): void {
  void router.push({ name: "report", params: { taskId: id } });
}

async function deleteTaskFromHistory(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm("删除后将无法恢复；如果任务仍在运行，会先取消再删除。", "删除历史任务", {
      type: "warning",
      confirmButtonText: "删除",
      cancelButtonText: "取消"
    });
  } catch {
    return;
  }

  try {
    await historyStore.deleteTask(id);
    researchStore.clearDeletedTask(id);
    if (router.currentRoute.value.name === "report" && String(router.currentRoute.value.params.taskId) === id) {
      await router.push({ name: "home" });
    }
    ElMessage.success("历史任务已删除");
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "删除历史任务失败");
  }
}

async function signOut(): Promise<void> {
  try {
    await authStore.logout();
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : "退出登录失败");
  }
}

onMounted(async () => {
  await historyStore.loadTasks();

  try {
    const providers = await fetchProviders();
    settingsStore.setProviders(providers);
  } catch (error) {
    researchStore.errorMessage = error instanceof Error ? error.message : "加载 provider 失败";
  }
});
</script>

<template>
  <div class="max-w-screen-lg mx-auto px-4 relative z-10 pb-16">
    <header class="flex justify-between items-center my-6 max-sm:my-4 print:hidden">
      <h1 class="text-left text-xl font-semibold font-heading text-foreground">
        Deep Research
      </h1>
      <div class="flex">
        <a href="https://github.com/sheepyd/deep-research.git" target="_blank" rel="noopener noreferrer">
          <el-button class="h-8 w-8 !p-1 text-foreground" title="开源代码" text>
            <Github class="h-5 w-5" />
          </el-button>
        </a>
        <el-button class="h-8 w-8 !p-1 text-foreground" text title="历史记录" @click="showHistory = true">
          <History class="h-5 w-5" />
        </el-button>
        <el-button class="h-8 w-8 !p-1 text-foreground" text title="设置" @click="showSettings = true">
          <Settings class="h-5 w-5" />
        </el-button>
        <el-button class="h-8 w-8 !p-1 text-foreground" text title="退出登录" @click="signOut">
          <LogOut class="h-5 w-5" />
        </el-button>
      </div>
    </header>

    <main class="flex flex-col gap-6 items-start w-full">
      <!-- Stage: Workbench -->
      <section v-if="activeStage === 'workbench'" class="flex flex-col gap-6 w-full fade-in">
        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume I</p>
                <h2 class="text-3xl font-heading text-foreground drop-cap">研究工作台</h2>
              </div>
            </div>
          </template>

          <div class="flex flex-col gap-6">
            <p class="text-sm font-body text-mutedForeground">
              开启一项新的深度研究，系统将通过智能分析拆解您的目标，提供详尽的报告与论证。
            </p>
            <el-input
              type="textarea"
              :rows="7"
              :model-value="query"
              placeholder="输入你的研究主题、目标、背景和输出要求..."
              @input="researchStore.setQuery(String($event))"
              class="bg-backgroundAlt border-border"
            />
            <div class="flex justify-end">
              <el-button 
                class="min-w-[140px]" 
                :loading="loadingClarify" 
                @click="researchStore.requestClarify()"
                :disabled="!query.trim()"
              >
                <span class="engraved-text">生成澄清问题</span>
              </el-button>
            </div>
          </div>
        </el-card>

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
          class="bg-accentSecondary/10 border border-accentSecondary text-foreground"
        />
      </section>

      <!-- Stage: Clarify -->
      <section v-if="activeStage === 'clarify'" class="flex flex-col gap-6 w-full fade-in">
        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume II</p>
                <h2 class="text-3xl font-heading text-foreground">澄清问题</h2>
              </div>
              <el-button @click="researchStore.clarifyQuestions = []" text size="small">
                返回修改主题
              </el-button>
            </div>
          </template>

          <div class="flex flex-col gap-6">
            <div class="p-4 bg-backgroundAlt border border-border rounded opacity-80">
              <p class="text-xs font-display uppercase tracking-widest text-mutedForeground mb-1">原始主题</p>
              <p class="text-base font-body text-foreground">{{ query }}</p>
            </div>
            
            <div class="ornate-divider my-2 w-full"></div>
            
            <div
              v-for="(question, index) in clarifyQuestions"
              :key="index"
              class="flex flex-col gap-3"
            >
              <p class="text-lg font-heading text-foreground">
                <span class="font-display text-accent mr-2">{{ index + 1 }}.</span> {{ question }}
              </p>
              <el-input
                type="textarea"
                :rows="3"
                :model-value="answers[index]"
                placeholder="您的回答将指导研究的方向..."
                @input="researchStore.updateAnswer(index, String($event))"
              />
            </div>
            
            <div class="flex justify-end pt-4 border-t border-border mt-2">
              <el-button
                class="min-w-[140px] bg-[linear-gradient(180deg,#D4B872_0%,#C9A962_50%,#B8953F_100%)] text-[#1C1714] border-none hover:brightness-110 shadow-[inset_0_1px_0_rgba(255,255,255,0.2),inset_0_-1px_0_rgba(0,0,0,0.2),0_2px_8px_rgba(0,0,0,0.3)] transition-all"
                :loading="loadingTask"
                :disabled="!canStartResearch"
                @click="researchStore.startResearch()"
              >
                <span class="font-display uppercase tracking-[0.15em] text-xs font-bold text-shadow-[1px_1px_1px_rgba(0,0,0,0.4),-1px_-1px_1px_rgba(255,255,255,0.1)]">启动深度研究</span>
              </el-button>
            </div>
          </div>
        </el-card>

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
          class="bg-accentSecondary/10 border border-accentSecondary text-foreground"
        />
      </section>

      <!-- Stage: Progress & Reasoning (Volume III & IV) -->
      <section v-if="activeStage === 'progress' || activeStage === 'done'" class="flex flex-col gap-6 w-full fade-in">
        <WorkflowProgress />

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
          class="bg-accentSecondary/10 border border-accentSecondary text-foreground"
        />

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume IV</p>
                <h2 class="text-3xl font-heading text-foreground">研究计划与推理</h2>
              </div>
              <span class="px-3 py-1 bg-background border border-border rounded-full text-xs font-display uppercase tracking-widest text-accent">
                {{ status }} / {{ researchStore.currentStep || "idle" }}
              </span>
            </div>
          </template>

          <div class="flex flex-col gap-6">
            <div>
              <h3 class="text-lg font-heading text-foreground mb-4 border-b border-border pb-2">研究计划</h3>
              <div v-if="renderedPlan" class="markdown-body text-sm" v-html="renderedPlan" />
              <div v-else class="italic text-mutedForeground text-sm p-4 bg-backgroundAlt rounded border border-border">正在制定研究计划，请稍候...</div>
            </div>

            <div class="ornate-divider my-2 w-full"></div>

            <details class="group bg-background border border-border rounded" :open="!renderedPlan">
              <summary class="p-3 cursor-pointer font-heading text-foreground hover:text-accent transition-colors flex justify-between items-center bg-backgroundAlt border-b border-transparent group-open:border-border">
                <span class="font-medium text-base">详细执行记录与推理</span>
                <span class="text-xs font-body text-mutedForeground opacity-70">点击展开/折叠</span>
              </summary>
              <div class="p-4 bg-background">
                <pre v-if="reasoningLog.length || progressHistory.length" class="font-mono text-xs text-mutedForeground overflow-x-auto whitespace-pre-wrap max-h-96 overflow-y-auto leading-relaxed scrollbar-thin">{{ reasoningLog.join("\n\n") }}</pre>
                <div v-else class="italic text-mutedForeground text-sm text-center">暂无执行记录...</div>
              </div>
            </details>
          </div>
        </el-card>
      </section>
    </main>

    <!-- Settings Dialog -->
    <el-dialog v-model="showSettings" title="设置" width="800px" class="bg-backgroundAlt border border-border">
      <el-tabs class="w-full">
        <el-tab-pane label="模型设置">
          <div class="grid grid-cols-1 gap-4">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">AI Provider</label>
              <el-select :model-value="settingsStore.provider" @change="settingsStore.setProvider(String($event))">
                <el-option v-for="(provider, key) in settingsStore.providers.llm_providers" :key="key" :label="provider.label" :value="key" />
              </el-select>
              <p class="text-xs text-mutedForeground">AI 服务提供商。</p>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div class="flex flex-col gap-1">
                <label class="text-sm font-semibold text-foreground">Thinking Model</label>
                <el-select v-model="settingsStore.thinkingModel" @change="settingsStore.persist()">
                  <el-option v-for="model in settingsStore.llmOptions" :key="model" :label="model" :value="model" />
                </el-select>
                <p class="text-xs text-mutedForeground">深度研究使用的核心模型，建议选择擅长思考的模型。</p>
              </div>
              <div class="flex flex-col gap-1">
                <label class="text-sm font-semibold text-foreground">Task Model</label>
                <el-select v-model="settingsStore.taskModel" @change="settingsStore.persist()">
                  <el-option v-for="model in settingsStore.llmOptions" :key="model" :label="model" :value="model" />
                </el-select>
                <p class="text-xs text-mutedForeground">负责辅助任务的模型，建议选择输出效率高的模型。</p>
              </div>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="搜索参数">
          <div class="grid grid-cols-1 gap-4">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">Search Provider</label>
              <el-select v-model="settingsStore.searchProvider" @change="settingsStore.persist()">
                <el-option v-for="[key, provider] in settingsStore.searchOptions" :key="key" :label="provider.label" :value="key" />
              </el-select>
              <p class="text-xs text-mutedForeground">搜索服务提供商。</p>
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">Max Results</label>
              <el-input-number v-model="settingsStore.maxResults" :min="1" :max="10" @change="settingsStore.persist()" class="w-full" />
              <p class="text-xs text-mutedForeground">单次搜索的最大结果数量。</p>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="系统设置">
          <div class="grid grid-cols-1 gap-4">
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">语言</label>
              <el-select v-model="settingsStore.language" @change="settingsStore.persist()">
                <el-option label="简体中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
              <p class="text-xs text-mutedForeground">提示词和报告生成的首选语言。</p>
            </div>
            <div class="flex flex-col gap-1 mt-4 pt-4 border-t border-border">
              <label class="text-sm font-semibold text-foreground">安全说明</label>
              <p class="text-sm text-mutedForeground">
                模型密钥、搜索密钥、网关地址和登录态都由服务端管理，不再保存在浏览器本地。
              </p>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>

    <!-- History Drawer -->
    <el-drawer v-model="showHistory" title="研究历史" size="400px" direction="rtl" class="bg-backgroundAlt border-l border-border">
      <div v-if="loadingHistory" class="p-6 text-mutedForeground italic text-center">
        正在加载历史任务...
      </div>
      <div v-else-if="!tasks.length" class="p-6 text-mutedForeground italic text-center">
        还没有可展示的研究记录。
      </div>
      <div v-else class="flex flex-col gap-4 p-4">
        <article
          v-for="item in tasks"
          :key="item.id"
          class="p-4 rounded border transition-all duration-300 cursor-pointer hover:border-accent hover:shadow-[0_8px_24px_rgba(0,0,0,0.3)] flex flex-col gap-3"
          :class="item.id === taskId ? 'bg-background border-accent' : 'bg-backgroundAlt border-border'"
          @click="openTaskInWorkspace(item.id)"
        >
          <div class="flex flex-col gap-1 text-left">
            <strong class="text-lg font-heading text-foreground leading-tight">
              {{ item.query }}
              <template v-if="item.research_iteration > 1"> · Round {{ item.research_iteration }}</template>
            </strong>
            <span class="text-sm font-body text-mutedForeground">{{ item.status }} · {{ taskStageLabel(item.current_step) }}</span>
            <small class="text-sm italic text-mutedForeground" v-if="item.follow_up_request">{{ item.follow_up_request }}</small>
            <small class="text-xs font-display uppercase tracking-widest text-accent/70 mt-2">{{ formatDate(item.completed_at || item.created_at) }}</small>
          </div>
          <div class="flex gap-2 mt-2">
            <el-button size="small" @click.stop="openTaskInWorkspace(item.id)">载入</el-button>
            <el-button size="small" type="primary" @click.stop="openReport(item.id)">报告</el-button>
            <el-button
              size="small"
              type="danger"
              :loading="deletingTaskIds.includes(item.id)"
              @click.stop="deleteTaskFromHistory(item.id)"
            >
              <Trash2 class="h-4 w-4" />
            </el-button>
          </div>
        </article>
      </div>
    </el-drawer>
  </div>
</template>

<style scoped>
:deep(.el-drawer__header) {
  color: var(--color-foreground);
  font-family: var(--font-heading);
  font-size: 1.5rem;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 1rem;
  margin-bottom: 0;
}
:deep(.el-dialog__title) {
  color: var(--color-foreground);
  font-family: var(--font-heading);
  font-size: 1.5rem;
}
:deep(.el-dialog__header) {
  border-bottom: 1px solid var(--color-border);
  margin-right: 0;
}
:deep(.el-drawer) {
  background-color: var(--color-backgroundAlt);
}
.fade-in {
  animation: fadeIn 0.5s ease-out;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}
.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: var(--color-backgroundAlt);
  border-radius: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 4px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: var(--color-mutedForeground);
}
</style>

