<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";

import { useAuthStore } from "./stores/auth";

const authStore = useAuthStore();
const password = ref("");
const loginError = ref("");

async function signIn(): Promise<void> {
  loginError.value = "";
  try {
    await authStore.login(password.value);
    password.value = "";
  } catch (error) {
    loginError.value = error instanceof Error ? error.message : "登录失败";
  }
}

function handleUnauthorized(): void {
  authStore.applyAnonymousState();
  ElMessage.error("登录已失效，请重新登录。");
}

onMounted(async () => {
  window.addEventListener("deep-research:unauthorized", handleUnauthorized);
  try {
    await authStore.restoreSession();
  } catch (error) {
    loginError.value = error instanceof Error ? error.message : "会话检查失败";
    authStore.applyAnonymousState();
    authStore.checkingSession = false;
  }
});

onBeforeUnmount(() => {
  window.removeEventListener("deep-research:unauthorized", handleUnauthorized);
});
</script>

<template>
  <div
    v-if="authStore.checkingSession"
    class="min-h-screen flex items-center justify-center px-6 text-center text-mutedForeground"
  >
    正在验证登录状态...
  </div>
  <div v-else-if="!authStore.authenticated" class="min-h-screen flex items-center justify-center px-6">
    <div class="w-full max-w-md ornate-frame bg-backgroundAlt border border-border p-8 flex flex-col gap-6">
      <div class="flex flex-col gap-2">
        <p class="text-xs font-display uppercase tracking-[0.25em] text-accent">Secure Access</p>
        <h1 class="text-3xl font-heading text-foreground">Deep Research</h1>
        <p class="text-sm text-mutedForeground">
          这个实例现在使用服务端会话认证。输入部署时配置的管理密码继续。
        </p>
      </div>
      <el-alert
        v-if="loginError"
        :title="loginError"
        type="error"
        :closable="false"
        show-icon
      />
      <el-input
        v-model="password"
        type="password"
        show-password
        placeholder="管理密码"
        @keyup.enter="signIn"
      />
      <el-button type="primary" class="w-full" :loading="authStore.checkingSession" @click="signIn">
        登录
      </el-button>
    </div>
  </div>
  <router-view v-else />
</template>
