import { defineStore } from "pinia";

const AUTH_KEY = "deep-research-auth";

interface AuthState {
  apiBaseUrl: string;
  token: string;
}

function defaultApiBaseUrl(): string {
  if (typeof window !== "undefined" && window.location?.origin) {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

function loadState(): AuthState {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) {
      return { apiBaseUrl: defaultApiBaseUrl(), token: "change-me" };
    }
    return JSON.parse(raw) as AuthState;
  } catch {
    return { apiBaseUrl: defaultApiBaseUrl(), token: "change-me" };
  }
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => loadState(),
  actions: {
    setApiBaseUrl(value: string) {
      this.apiBaseUrl = value;
      localStorage.setItem(AUTH_KEY, JSON.stringify({ apiBaseUrl: this.apiBaseUrl, token: this.token }));
    },
    setToken(value: string) {
      this.token = value;
      localStorage.setItem(AUTH_KEY, JSON.stringify({ apiBaseUrl: this.apiBaseUrl, token: this.token }));
    }
  }
});
