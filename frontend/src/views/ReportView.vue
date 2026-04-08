<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import MarkdownIt from "markdown-it";
import { useRoute, useRouter } from "vue-router";

import { fetchResearchTask } from "../services/api";
import { useAuthStore } from "../stores/auth";
import { useResearchStore } from "../stores/research";
import type { ResearchTaskDetail } from "../types/research";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
});

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();
const researchStore = useResearchStore();

const task = ref<ResearchTaskDetail | null>(null);
const loading = ref(false);
const errorMessage = ref("");
const followUpRequest = ref("");
const startingFollowUp = ref(false);

const renderedReport = computed(() => md.render(task.value?.final_report || ""));
const renderedPlan = computed(() => md.render(task.value?.report_plan || ""));

function formatDate(value: string | null | undefined): string {
  if (!value) return "进行中";
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

async function loadTask(taskId: string): Promise<void> {
  loading.value = true;
  errorMessage.value = "";
  try {
    task.value = await fetchResearchTask(authStore.apiBaseUrl, authStore.token, taskId);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "加载报告失败";
  } finally {
    loading.value = false;
  }
}

async function startFollowUp(): Promise<void> {
  if (!task.value || !followUpRequest.value.trim()) return;
  startingFollowUp.value = true;
  errorMessage.value = "";
  try {
    await researchStore.startFollowUpResearch(task.value.id, followUpRequest.value.trim());
    followUpRequest.value = "";
    await router.push({ name: "home" });
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "启动追加研究失败";
  } finally {
    startingFollowUp.value = false;
  }
}

onMounted(async () => {
  await loadTask(String(route.params.taskId));
});

watch(
  () => route.params.taskId,
  async (value) => {
    if (value) {
      await loadTask(String(value));
    }
  }
);
</script>

<template>
  <div class="report-shell">
    <header class="report-header">
      <div>
        <p class="eyebrow">Final Report</p>
        <h1>{{ task?.query || "研究报告" }}</h1>
        <p class="hero-copy">独立报告页，便于单独查看最终结论、计划与引用来源。</p>
      </div>
      <div class="header-actions">
        <el-button @click="router.push({ name: 'home' })">返回工作台</el-button>
      </div>
    </header>

    <div v-if="loading" class="report-loading">正在加载报告...</div>
    <el-alert
      v-else-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
    />
    <main v-else-if="task" class="report-layout">
      <aside class="report-meta">
        <section class="meta-card">
          <p class="panel-kicker">Meta</p>
          <h2>任务信息</h2>
          <dl class="meta-list">
            <div>
              <dt>研究轮次</dt>
              <dd>Round {{ task.research_iteration }}</dd>
            </div>
            <div v-if="task.parent_task_id">
              <dt>父任务</dt>
              <dd>{{ task.parent_task_id }}</dd>
            </div>
            <div>
              <dt>状态</dt>
              <dd>{{ task.status }}</dd>
            </div>
            <div>
              <dt>当前阶段</dt>
              <dd>{{ task.current_step || "completed" }}</dd>
            </div>
            <div>
              <dt>Provider</dt>
              <dd>{{ task.provider }}</dd>
            </div>
            <div>
              <dt>Thinking</dt>
              <dd>{{ task.thinking_model }}</dd>
            </div>
            <div>
              <dt>Task Model</dt>
              <dd>{{ task.task_model }}</dd>
            </div>
            <div>
              <dt>搜索</dt>
              <dd>{{ task.search_provider }}</dd>
            </div>
            <div>
              <dt>创建时间</dt>
              <dd>{{ formatDate(task.created_at) }}</dd>
            </div>
            <div>
              <dt>完成时间</dt>
              <dd>{{ formatDate(task.completed_at) }}</dd>
            </div>
          </dl>
        </section>

        <section class="meta-card">
          <p class="panel-kicker">Clarify</p>
          <h2>澄清记录</h2>
          <div v-if="task.clarify_questions.length" class="qa-list">
            <article
              v-for="(question, index) in task.clarify_questions"
              :key="`${question}-${index}`"
              class="qa-item"
            >
              <strong>{{ question }}</strong>
              <p>{{ task.clarify_answers[index] || "未填写回答" }}</p>
            </article>
          </div>
          <div v-else class="empty-state">没有保存澄清记录。</div>
        </section>

        <section class="meta-card">
          <p class="panel-kicker">Follow-up</p>
          <h2>多轮 Re-Research</h2>
          <p v-if="task.follow_up_request" class="helper-copy">
            本轮追加指令：{{ task.follow_up_request }}
          </p>
          <el-input
            v-model="followUpRequest"
            type="textarea"
            :rows="4"
            placeholder="输入新的研究方向、补充问题或想继续深挖的点"
          />
          <el-button
            type="primary"
            :loading="startingFollowUp"
            :disabled="!followUpRequest.trim()"
            @click="startFollowUp"
          >
            发起下一轮研究
          </el-button>
        </section>

        <section class="meta-card">
          <p class="panel-kicker">Sources</p>
          <h2>引用来源</h2>
          <div v-if="task.sources.length" class="source-list">
            <a
              v-for="source in task.sources"
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
          <div v-else class="empty-state">暂无来源数据。</div>
        </section>
      </aside>

      <section class="report-content">
        <article class="report-card">
          <p class="panel-kicker">Output</p>
          <h2>最终报告</h2>
          <div class="markdown-body report-document" v-html="renderedReport" />
        </article>

        <article class="report-card">
          <p class="panel-kicker">Plan</p>
          <h2>研究方案</h2>
          <div class="markdown-body" v-html="renderedPlan" />
        </article>
      </section>
    </main>
  </div>
</template>
