import { defineStore } from "pinia";

const AUTH_KEY = "deep-research-auth";

interface AuthState {
  apiBaseUrl: string;
  token: string;
}

function loadState(): AuthState {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (!raw) {
      return { apiBaseUrl: "http://localhost:8000", token: "change-me" };
    }
    return JSON.parse(raw) as AuthState;
  } catch {
    return { apiBaseUrl: "http://localhost:8000", token: "change-me" };
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

