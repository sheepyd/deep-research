<script setup lang="ts">
import { computed } from 'vue';
import { useResearchStore } from '../stores/research';
import { CheckCircle2, Circle, LoaderCircle } from 'lucide-vue-next';

const store = useResearchStore();

const steps = computed(() => {
  // Determine if collection is completed. It's completed if final report is starting or task is completed.
  const collectionCompleted = store.progressHistory.some(h => h.step === 'final-report' && h.status === 'start') || store.finalReport.length > 0 || store.status === 'completed';
  const planCompleted = store.reportPlan.trim().length > 0;
  
  const rawSteps = [
    {
      id: 'topic',
      label: '主题构思',
      completed: store.query.trim().length > 0,
      description: '输入研究主题'
    },
    {
      id: 'questions',
      label: '澄清问题',
      completed: store.clarifyQuestions.length > 0,
      description: '生成并回答澄清问题'
    },
    {
      id: 'plan',
      label: '研究计划',
      completed: planCompleted,
      description: '制定搜索和研究策略'
    },
    {
      id: 'collection',
      label: '资料收集',
      completed: collectionCompleted,
      description: '执行深度搜索和内容萃取'
    },
    {
      id: 'report',
      label: '最终报告',
      completed: store.finalReport.trim().length > 0 || store.status === 'completed',
      description: '撰写并生成研究报告'
    }
  ];

  const activeIndex = rawSteps.findIndex(s => !s.completed);
  return rawSteps.map((step, idx) => ({
    ...step,
    state: step.completed || activeIndex === -1 ? 'completed' : idx === activeIndex ? 'active' : 'pending'
  }));
});

const progress = computed(() => {
  const completedStages = steps.value.filter(s => s.completed).length;
  return Math.round((completedStages / steps.value.length) * 100);
});

const completedStages = computed(() => steps.value.filter(s => s.completed).length);
</script>

<template>
  <section class="p-6 border rounded border-border bg-backgroundAlt w-full">
    <div class="flex gap-2 items-center justify-between max-sm:flex-col max-sm:items-start mb-6">
      <div>
        <p class="text-[10px] font-display uppercase tracking-[0.3em] text-accent mb-1">Volume III</p>
        <h3 class="font-heading text-2xl text-foreground">
          执行进度
        </h3>
      </div>
      <span class="text-sm font-body text-mutedForeground mt-2 max-sm:mt-0">
        进度: {{ progress }}% ({{ completedStages }} / {{ steps.length }})
      </span>
    </div>
    
    <div class="h-2 rounded-full bg-muted overflow-hidden mb-6 border border-border/50">
      <div 
        class="h-full rounded-full bg-[linear-gradient(90deg,#D4B872_0%,#C9A962_50%,#B8953F_100%)] transition-all duration-500 ease-out shadow-[0_0_10px_rgba(201,169,98,0.5)]"
        :style="{ width: `${progress}%` }"
      ></div>
    </div>
    
    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      <div 
        v-for="step in steps" 
        :key="step.id"
        class="rounded border px-4 py-3 flex flex-col gap-2 transition-colors duration-300"
        :class="{
          'border-accent bg-background shadow-[0_4px_12px_rgba(201,169,98,0.1)]': step.state === 'completed',
          'border-accent bg-backgroundAlt ring-1 ring-accent ring-opacity-50': step.state === 'active',
          'border-border bg-background/50 opacity-70': step.state === 'pending'
        }"
      >
        <div class="flex items-center gap-2">
          <CheckCircle2 v-if="step.state === 'completed'" class="h-5 w-5 text-accent" />
          <LoaderCircle v-else-if="step.state === 'active'" class="h-5 w-5 text-accent animate-spin" />
          <Circle v-else class="h-5 w-5 text-mutedForeground" />
          <p class="text-sm font-heading font-medium text-foreground truncate">{{ step.label }}</p>
        </div>
        <p class="text-xs font-body text-mutedForeground">
          <template v-if="step.state === 'completed'">已完成</template>
          <template v-else-if="step.state === 'active'">进行中</template>
          <template v-else>等待中</template>
          <span class="opacity-70 ml-1">· {{ step.description }}</span>
        </p>
      </div>
    </div>
  </section>
</template>
