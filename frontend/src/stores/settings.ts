import { defineStore } from "pinia";

import type { ProviderCatalog } from "../types/research";

const SETTINGS_KEY = "deep-research-settings";

export interface SettingsState {
  provider: string;
  thinkingModel: string;
  taskModel: string;
  llmApiKey: string;
  llmBaseUrl: string;
  searchProvider: string;
  searchApiKey: string;
  searchBaseUrl: string;
  language: string;
  maxResults: number;
  providers: ProviderCatalog;
}

function defaultCatalog(): ProviderCatalog {
  return {
    llm_providers: {
      openai: { label: "OpenAI", models: ["gpt-5.4-mini", "gpt-5.4", "gpt-5"] }
    },
    search_providers: {
      tavily: { label: "Tavily" },
      searxng: { label: "SearxNG" }
    }
  };
}

function loadState(): SettingsState {
  try {
    const raw = localStorage.getItem(SETTINGS_KEY);
    if (raw) {
      return { ...defaultState(), ...JSON.parse(raw) } as SettingsState;
    }
  } catch {
    return defaultState();
  }
  return defaultState();
}

function defaultState(): SettingsState {
  const providers = defaultCatalog();
  return {
    provider: "openai",
    thinkingModel: providers.llm_providers.openai.models[0],
    taskModel: providers.llm_providers.openai.models[0],
    llmApiKey: "",
    llmBaseUrl: "",
    searchProvider: "tavily",
    searchApiKey: "",
    searchBaseUrl: "",
    language: "zh-CN",
    maxResults: 5,
    providers
  };
}

export const useSettingsStore = defineStore("settings", {
  state: (): SettingsState => loadState(),
  getters: {
    llmOptions: (state) => state.providers.llm_providers[state.provider]?.models ?? [],
    searchOptions: (state) => Object.entries(state.providers.search_providers)
  },
  actions: {
    persist() {
      localStorage.setItem(
        SETTINGS_KEY,
        JSON.stringify({
          provider: this.provider,
          thinkingModel: this.thinkingModel,
          taskModel: this.taskModel,
          llmApiKey: this.llmApiKey,
          llmBaseUrl: this.llmBaseUrl,
          searchProvider: this.searchProvider,
          searchApiKey: this.searchApiKey,
          searchBaseUrl: this.searchBaseUrl,
          language: this.language,
          maxResults: this.maxResults
        })
      );
    },
    setProvider(provider: string) {
      this.provider = provider;
      const models = this.providers.llm_providers[provider]?.models ?? [];
      this.thinkingModel = models[0] ?? "";
      this.taskModel = models[0] ?? "";
      this.persist();
    },
    setProviders(payload: ProviderCatalog) {
      this.providers = payload;
      if (!payload.llm_providers[this.provider]) {
        this.provider = Object.keys(payload.llm_providers)[0];
      }
      const models = payload.llm_providers[this.provider]?.models ?? [];
      if (!models.includes(this.thinkingModel)) {
        this.thinkingModel = models[0] ?? "";
      }
      if (!models.includes(this.taskModel)) {
        this.taskModel = models[0] ?? "";
      }
      if (!payload.search_providers[this.searchProvider]) {
        this.searchProvider = Object.keys(payload.search_providers)[0] ?? "";
      }
      this.persist();
    }
  }
});
