<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import MarkdownIt from "markdown-it";
import { useRoute, useRouter } from "vue-router";

import { fetchResearchTask } from "../services/api";
import { useResearchStore } from "../stores/research";
import type { ResearchTaskDetail } from "../types/research";

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true
});

const route = useRoute();
const router = useRouter();
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
    task.value = await fetchResearchTask(taskId);
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
  <div class="max-w-7xl mx-auto px-4 py-16 md:px-8 relative z-10">
    <header class="flex flex-col md:flex-row justify-between items-start gap-8 mb-16 ornate-frame p-8 bg-backgroundAlt border border-border">
      <div class="flex flex-col gap-2 max-w-2xl">
        <p class="text-xs font-display uppercase tracking-[0.25em] text-accent">Volume I</p>
        <h1 class="text-5xl md:text-6xl font-heading leading-[1.1] tracking-tight text-foreground drop-cap">
          {{ task?.query || "研究报告" }}
        </h1>
        <div class="ornate-divider w-full max-w-md my-4"></div>
        <p class="text-lg font-body text-mutedForeground leading-relaxed">
          独立报告页，便于单独查看最终结论、计划与引用来源。
          A comprehensive artifact of scholarly investigation.
        </p>
      </div>
      <div class="flex flex-col gap-4 min-w-[200px]">
        <el-button @click="router.push({ name: 'home' })" class="w-full">
          <span class="engraved-text">返回工作台</span>
        </el-button>
      </div>
    </header>

    <div v-if="loading" class="p-8 bg-backgroundAlt border border-border text-mutedForeground italic rounded text-center text-lg">正在加载报告...</div>
    <el-alert
      v-else-if="errorMessage"
      :title="errorMessage"
      type="error"
      show-icon
      :closable="false"
      class="bg-accentSecondary/10 border border-accentSecondary text-foreground mb-8"
    />
    <main v-else-if="task" class="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-8 items-start">
      <aside class="flex flex-col gap-8 sticky top-8">
        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume II</p>
                <h2 class="text-2xl font-heading text-foreground">任务信息</h2>
              </div>
            </div>
          </template>
          <dl class="flex flex-col gap-3">
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">研究轮次</dt>
              <dd class="text-base font-heading text-foreground">Round {{ task.research_iteration }}</dd>
            </div>
            <div v-if="task.parent_task_id" class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">父任务</dt>
              <dd class="text-sm font-body text-foreground break-all">{{ task.parent_task_id }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">状态</dt>
              <dd class="text-base font-heading text-foreground">{{ task.status }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">当前阶段</dt>
              <dd class="text-base font-heading text-foreground">{{ task.current_step || "completed" }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">Provider</dt>
              <dd class="text-base font-heading text-foreground">{{ task.provider }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">Thinking Model</dt>
              <dd class="text-sm font-body text-foreground break-all">{{ task.thinking_model }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">Task Model</dt>
              <dd class="text-sm font-body text-foreground break-all">{{ task.task_model }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">Search Provider</dt>
              <dd class="text-base font-heading text-foreground">{{ task.search_provider }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-3 border-b border-border">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">创建时间</dt>
              <dd class="text-sm font-body text-foreground">{{ formatDate(task.created_at) }}</dd>
            </div>
            <div class="flex flex-col gap-1 pb-1">
              <dt class="text-xs font-display uppercase tracking-widest text-mutedForeground">完成时间</dt>
              <dd class="text-sm font-body text-foreground">{{ formatDate(task.completed_at) }}</dd>
            </div>
          </dl>
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume III</p>
                <h2 class="text-2xl font-heading text-foreground">澄清记录</h2>
              </div>
            </div>
          </template>
          <div v-if="task.clarify_questions.length" class="flex flex-col gap-4">
            <article
              v-for="(question, index) in task.clarify_questions"
              :key="`${question}-${index}`"
              class="p-4 bg-background border border-border rounded"
            >
              <strong class="text-base font-heading text-foreground block mb-2">{{ question }}</strong>
              <p class="text-sm font-body text-mutedForeground">{{ task.clarify_answers[index] || "未填写回答" }}</p>
            </article>
          </div>
          <div v-else class="text-sm font-body italic text-mutedForeground">没有保存澄清记录。</div>
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume IV</p>
                <h2 class="text-2xl font-heading text-foreground">多轮 Re-Research</h2>
              </div>
            </div>
          </template>
          <div class="flex flex-col gap-4">
            <p v-if="task.follow_up_request" class="text-sm font-body italic text-accent">
              本轮追加指令：{{ task.follow_up_request }}
            </p>
            <el-input
              v-model="followUpRequest"
              type="textarea"
              :rows="4"
              placeholder="输入新的研究方向、补充问题或想继续深挖的点..."
            />
            <el-button
              type="primary"
              :loading="startingFollowUp"
              :disabled="!followUpRequest.trim()"
              @click="startFollowUp"
              class="w-full"
            >
              发起下一轮研究
            </el-button>
          </div>
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume V</p>
                <h2 class="text-2xl font-heading text-foreground">引用来源</h2>
              </div>
            </div>
          </template>
          <div v-if="task.sources.length" class="flex flex-col gap-3">
            <a
              v-for="source in task.sources"
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
          <div v-else class="text-sm font-body italic text-mutedForeground">暂无来源数据。</div>
        </el-card>
      </aside>

      <section class="flex flex-col gap-8">
        <el-card class="min-h-[500px]">
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume VI</p>
                <h2 class="text-3xl font-heading text-foreground">最终报告</h2>
              </div>
            </div>
          </template>
          <div class="markdown-body p-4 md:p-8" v-html="renderedReport" />
        </el-card>

        <el-card>
          <template #header>
            <div class="flex justify-between items-start">
              <div>
                <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume VII</p>
                <h2 class="text-3xl font-heading text-foreground">研究方案</h2>
              </div>
            </div>
          </template>
          <div class="markdown-body p-4 md:p-8" v-html="renderedPlan" />
        </el-card>
      </section>
    </main>
  </div>
</template>
