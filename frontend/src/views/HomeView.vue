<script setup lang="ts">
import { computed, onMounted } from "vue";
import MarkdownIt from "markdown-it";
import { storeToRefs } from "pinia";
import { useRouter } from "vue-router";

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
const { tasks, loading: loadingHistory } = storeToRefs(historyStore);
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

onMounted(async () => {
  await historyStore.loadTasks();

  try {
    const providers = await fetchProviders(authStore.apiBaseUrl, authStore.token);
    settingsStore.setProviders(providers);
  } catch (error) {
    researchStore.errorMessage = error instanceof Error ? error.message : "加载 provider 失败";
  }

  if (researchStore.taskId) {
    try {
      await openTaskInWorkspace(researchStore.taskId);
    } catch (error) {
      researchStore.errorMessage = error instanceof Error ? error.message : "恢复任务失败";
    }
  }
});
</script>

<template>
  <div class="shell-frame">
    <header class="app-header">
      <div class="brand-block">
        <p class="eyebrow">Deep Research</p>
        <h1>Research Console</h1>
        <p class="hero-copy">
          参考原版项目的信息架构，保留工作台、历史和报告分离的使用方式。
        </p>
      </div>
      <div class="header-actions">
        <div class="status-pill">
          <span>Current Task</span>
          <strong>{{ currentTaskLabel }}</strong>
          <small>{{ status || "idle" }}</small>
        </div>
        <el-button
          v-if="canOpenReport"
          type="primary"
          plain
          @click="openReport(taskId)"
        >
          打开独立报告页
        </el-button>
      </div>
    </header>

    <section class="settings-ribbon">
      <div class="settings-grid">
        <el-input
          v-model="apiBaseUrl"
          placeholder="API Base URL"
          @change="authStore.setApiBaseUrl(apiBaseUrl)"
        />
        <el-input
          v-model="token"
          placeholder="Bearer Token"
          show-password
          @change="authStore.setToken(token)"
        />
        <el-select
          :model-value="settingsStore.provider"
          @change="settingsStore.setProvider(String($event))"
        >
          <el-option
            v-for="(provider, key) in settingsStore.providers.llm_providers"
            :key="key"
            :label="provider.label"
            :value="key"
          />
        </el-select>
        <el-select v-model="settingsStore.thinkingModel" @change="settingsStore.persist()">
          <el-option
            v-for="model in settingsStore.llmOptions"
            :key="model"
            :label="model"
            :value="model"
          />
        </el-select>
        <el-select v-model="settingsStore.taskModel" @change="settingsStore.persist()">
          <el-option
            v-for="model in settingsStore.llmOptions"
            :key="model"
            :label="model"
            :value="model"
          />
        </el-select>
        <el-select v-model="settingsStore.searchProvider" @change="settingsStore.persist()">
          <el-option
            v-for="[key, provider] in settingsStore.searchOptions"
            :key="key"
            :label="provider.label"
            :value="key"
          />
        </el-select>
        <el-select v-model="settingsStore.language" @change="settingsStore.persist()">
          <el-option label="简体中文" value="zh-CN" />
          <el-option label="English" value="en-US" />
        </el-select>
        <el-input-number
          v-model="settingsStore.maxResults"
          :min="1"
          :max="10"
          @change="settingsStore.persist()"
        />
      </div>
    </section>

    <main class="console-layout">
      <aside class="history-panel">
        <div class="panel-header">
          <div>
            <p class="panel-kicker">History</p>
            <h2>研究历史</h2>
          </div>
          <el-button text @click="historyStore.loadTasks()">刷新</el-button>
        </div>

        <div v-if="loadingHistory" class="empty-state">正在加载历史任务...</div>
        <div v-else-if="!tasks.length" class="empty-state">还没有可展示的研究记录。</div>
        <div v-else class="history-list">
          <article
            v-for="item in tasks"
            :key="item.id"
            class="history-card"
            :class="{ active: item.id === taskId }"
          >
            <button class="history-main" @click="openTaskInWorkspace(item.id)">
              <strong>
                {{ item.query }}
                <template v-if="item.research_iteration > 1"> · Round {{ item.research_iteration }}</template>
              </strong>
              <span>{{ item.status }} · {{ taskStageLabel(item.current_step) }}</span>
              <small v-if="item.follow_up_request">{{ item.follow_up_request }}</small>
              <small>{{ formatDate(item.completed_at || item.created_at) }}</small>
            </button>
            <div class="history-actions">
              <el-button size="small" @click="openTaskInWorkspace(item.id)">载入</el-button>
              <el-button
                size="small"
                type="primary"
                plain
                @click="openReport(item.id)"
              >
                报告
              </el-button>
            </div>
          </article>
        </div>
      </aside>

      <section class="workspace-stack">
        <el-card class="glass-card composer-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Topic</p>
                <h2>研究工作台</h2>
              </div>
              <span class="task-badge">{{ status }} / {{ researchStore.currentStep || "idle" }}</span>
            </div>
          </template>

          <el-input
            type="textarea"
            :rows="7"
            :model-value="query"
            placeholder="输入你的研究主题、目标、背景和输出要求"
            @input="researchStore.setQuery(String($event))"
          />
          <div class="action-row">
            <el-button type="primary" :loading="loadingClarify" @click="researchStore.requestClarify()">
              生成澄清问题
            </el-button>
            <el-button
              type="success"
              :loading="loadingTask"
              :disabled="!canStartResearch"
              @click="researchStore.startResearch()"
            >
              启动研究
            </el-button>
            <el-button
              v-if="canOpenReport"
              type="info"
              plain
              @click="openReport(taskId)"
            >
              查看独立报告
            </el-button>
          </div>
          <p class="helper-copy">
            当前版本要求先完成澄清问题，再能正式启动研究。修改主题后需要重新生成一次澄清问题。
          </p>
        </el-card>

        <el-card v-if="clarifyQuestions.length" class="glass-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Clarify</p>
                <h2>澄清问题</h2>
              </div>
            </div>
          </template>

          <div
            v-for="(question, index) in clarifyQuestions"
            :key="question"
            class="question-block"
          >
            <p class="question-title">{{ index + 1 }}. {{ question }}</p>
            <el-input
              type="textarea"
              :rows="3"
              :model-value="answers[index]"
              @input="researchStore.updateAnswer(index, String($event))"
            />
          </div>
        </el-card>

        <el-alert
          v-if="errorMessage"
          :title="errorMessage"
          type="error"
          show-icon
          :closable="false"
        />
      </section>

      <section class="insight-stack">
        <el-card class="glass-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Progress</p>
                <h2>执行进度</h2>
              </div>
            </div>
          </template>

          <div class="timeline-list">
            <div
              v-for="(item, index) in progressHistory"
              :key="`${item.step}-${item.status}-${index}`"
              class="timeline-item"
            >
              <div class="timeline-dot" />
              <div class="timeline-content">
                <strong>{{ item.step }}</strong>
                <span>
                  {{ item.role ? `${item.role} · ` : "" }}{{ item.status }}
                  <template v-if="item.attempt"> · attempt {{ item.attempt }}</template>
                </span>
                <small v-if="item.name">{{ item.name }}</small>
                <small v-if="item.compressedContext">compressed context</small>
              </div>
            </div>
          </div>
        </el-card>

        <el-card class="glass-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Plan</p>
                <h2>研究计划与推理</h2>
              </div>
            </div>
          </template>

          <div class="markdown-body" v-html="renderedPlan" />
          <el-divider />
          <pre class="reasoning-box">{{ reasoningLog.join("\n\n") }}</pre>
        </el-card>

        <el-card class="glass-card report-preview-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Report</p>
                <h2>最终报告预览</h2>
              </div>
            </div>
          </template>

          <div class="report-preview" v-html="renderedReport" />
        </el-card>

        <el-card class="glass-card">
          <template #header>
            <div class="card-headline">
              <div>
                <p class="panel-kicker">Sources</p>
                <h2>引用来源</h2>
              </div>
            </div>
          </template>

          <div v-if="sources.length" class="source-list">
            <a
              v-for="source in sources"
              :key="source.id"
              :href="source.url"
              target="_blank"
              rel="noreferrer"
              class="source-link-card"
            >
              <strong>{{ source.title || source.url }}</strong>
              <span>{{ source.url }}</span>
            </a>
          </div>
          <div v-else class="empty-state">研究完成后会在这里展示引用来源。</div>
        </el-card>
      </section>
    </main>
  </div>
</template>
