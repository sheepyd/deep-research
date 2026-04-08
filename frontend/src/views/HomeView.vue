<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import MarkdownIt from "markdown-it";
import { ElMessage, ElMessageBox } from "element-plus";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";
import { Github, History, Settings, Trash2 } from "lucide-vue-next";

import { fetchProviders } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useHistoryStore } from "../stores/history";
import { useResearchStore } from "../stores/research";
import { useSettingsStore } from "../stores/settings";

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

const { apiBaseUrl, token } = storeToRefs(authStore);
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

onMounted(async () => {
  await historyStore.loadTasks();

  try {
    const providers = await fetchProviders(authStore.apiBaseUrl, authStore.token);
    settingsStore.setProviders(providers);
  } catch (error) {
    researchStore.errorMessage = error instanceof Error ? error.message : "加载 provider 失败";
  }
});
</script>

<template>
  <div class="max-w-screen-lg mx-auto px-4 relative z-10">
    <header class="flex justify-between items-center my-6 max-sm:my-4 print:hidden">
      <h1 class="text-left text-xl font-semibold font-heading">
        Deep Research
      </h1>
      <div class="flex">
        <a href="https://github.com/sheepyd/deep-research.git" target="_blank" rel="noopener noreferrer">
          <el-button class="h-8 w-8 !p-1" title="开源代码" text>
            <Github class="h-5 w-5" />
          </el-button>
        </a>
        <el-button class="h-8 w-8 !p-1" text title="历史记录" @click="showHistory = true">
          <History class="h-5 w-5" />
        </el-button>
        <el-button class="h-8 w-8 !p-1" text title="设置" @click="showSettings = true">
          <Settings class="h-5 w-5" />
        </el-button>
      </div>
    </header>

    <main class="flex flex-col gap-6 items-start">
      <section class="flex flex-col gap-6 w-full">
        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume I</p>
                <h2 class="text-3xl font-heading text-foreground">研究工作台</h2>
              </div>
              <span class="px-3 py-1 bg-background border border-border rounded-full text-xs font-display uppercase tracking-widest text-accent">
                {{ status }} / {{ researchStore.currentStep || "idle" }}
              </span>
            </div>
          </template>

          <div class="flex flex-col gap-6">
            <el-input
              type="textarea"
              :rows="7"
              :model-value="query"
              placeholder="输入你的研究主题、目标、背景和输出要求..."
              @input="researchStore.setQuery(String($event))"
            />
            <div class="flex flex-wrap gap-4">
              <el-button type="primary" :loading="loadingClarify" @click="researchStore.requestClarify()">
                生成澄清问题
              </el-button>
              <el-button
                :loading="loadingTask"
                :disabled="!canStartResearch"
                @click="researchStore.startResearch()"
              >
                启动研究
              </el-button>
            </div>
          </div>
        </el-card>

        <el-card v-if="clarifyQuestions.length">
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume II</p>
                <h2 class="text-3xl font-heading text-foreground">澄清问题</h2>
              </div>
            </div>
          </template>

          <div class="flex flex-col gap-6">
            <div
              v-for="(question, index) in clarifyQuestions"
              :key="index"
              class="flex flex-col gap-2"
            >
              <p class="text-lg font-heading text-foreground">
                <span class="font-display text-accent mr-2">{{ index + 1 }}.</span> {{ question }}
              </p>
              <el-input
                type="textarea"
                :rows="3"
                :model-value="answers[index]"
                @input="researchStore.updateAnswer(index, String($event))"
              />
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

      <section class="flex flex-col gap-6 w-full">
        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume III</p>
                <h2 class="text-3xl font-heading text-foreground">执行进度</h2>
              </div>
            </div>
          </template>

          <div class="flex flex-col gap-4">
            <div
              v-for="(item, index) in progressHistory"
              :key="`${item.step}-${item.status}-${index}`"
              class="flex gap-4 items-start"
            >
              <div class="w-3 h-3 mt-1.5 rounded-full bg-accent shadow-[0_0_0_2px_rgba(201,169,98,0.2)] shrink-0" />
              <div class="flex flex-col gap-1 p-3 bg-background border border-border rounded w-full">
                <strong class="text-base font-heading text-foreground">{{ item.step }}</strong>
                <span class="text-sm font-body text-mutedForeground">
                  {{ item.role ? `${item.role} · ` : "" }}{{ item.status }}
                  <template v-if="item.attempt"> · attempt {{ item.attempt }}</template>
                </span>
                <small class="text-xs italic text-mutedForeground" v-if="item.name">{{ item.name }}</small>
                <small class="text-xs text-accent" v-if="item.compressedContext">compressed context</small>
              </div>
            </div>
          </div>
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume IV</p>
                <h2 class="text-3xl font-heading text-foreground">研究计划与推理</h2>
              </div>
            </div>
          </template>

          <div class="markdown-body" v-html="renderedPlan" />
          <div class="ornate-divider my-6"></div>
          <pre class="bg-background border border-border p-4 rounded font-mono text-sm text-mutedForeground overflow-x-auto whitespace-pre-wrap">{{ reasoningLog.join("\n\n") }}</pre>
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume V</p>
                <h2 class="text-3xl font-heading text-foreground">最终报告预览</h2>
              </div>
            </div>
          </template>

          <div class="markdown-body max-h-[500px] overflow-y-auto pr-2" v-html="renderedReport" />
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume VI</p>
                <h2 class="text-3xl font-heading text-foreground">引用来源</h2>
              </div>
            </div>
          </template>

          <div v-if="sources.length" class="flex flex-col gap-3">
            <a
              v-for="source in sources"
              :key="source.id"
              :href="source.url"
              target="_blank"
              rel="noreferrer"
              class="flex flex-col gap-1 p-3 bg-background border border-border rounded transition-colors hover:border-accent group"
            >
              <strong class="text-base font-heading text-foreground group-hover:text-accent transition-colors line-clamp-1">{{ source.title || source.url }}</strong>
              <span class="text-xs font-body text-mutedForeground break-all line-clamp-2">{{ source.url }}</span>
            </a>
          </div>
          <div v-else class="text-sm font-body italic text-mutedForeground">
            研究完成后会在这里展示引用来源。
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
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">API Key</label>
              <el-input v-model="settingsStore.llmApiKey" placeholder="请输入模型 API 密钥 (留空使用后端默认配置)" show-password @change="settingsStore.persist()" />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">API Base URL</label>
              <el-input v-model="settingsStore.llmBaseUrl" placeholder="请输入 API 基础 URL (留空使用后端默认配置)" @change="settingsStore.persist()" />
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
              <label class="text-sm font-semibold text-foreground">Search API Key</label>
              <el-input v-model="settingsStore.searchApiKey" placeholder="请输入搜索 API 密钥 (留空使用后端默认配置)" show-password @change="settingsStore.persist()" />
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">Search Base URL</label>
              <el-input v-model="settingsStore.searchBaseUrl" placeholder="请输入搜索 API 基础 URL (留空使用后端默认配置)" @change="settingsStore.persist()" />
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
              <label class="text-sm font-semibold text-foreground">Backend API Base URL</label>
              <el-input v-model="apiBaseUrl" placeholder="后端 API 基础 URL" @change="authStore.setApiBaseUrl(apiBaseUrl)" />
              <p class="text-xs text-mutedForeground">Python 后端服务的地址。</p>
            </div>
            <div class="flex flex-col gap-1">
              <label class="text-sm font-semibold text-foreground">Backend Bearer Token</label>
              <el-input v-model="token" placeholder="后端 Bearer Token" show-password @change="authStore.setToken(token)" />
              <p class="text-xs text-mutedForeground">后端 API 鉴权令牌。</p>
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
:deep(.el-dialog) {
  /* Using standard corner-flourish approach */
}
:deep(.el-drawer) {
  background-color: var(--color-backgroundAlt);
}
</style>
