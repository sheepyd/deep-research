import { defineStore } from "pinia";

import { fetchSession, loginWithPassword, logoutSession } from "../services/api";

export interface AuthState {
  authenticated: boolean;
  subject: string;
  authMode: string;
  checkingSession: boolean;
}

function defaultState(): AuthState {
  return {
    authenticated: false,
    subject: "",
    authMode: "",
    checkingSession: true
  };
}

export const useAuthStore = defineStore("auth", {
  state: (): AuthState => defaultState(),
  actions: {
    applyAnonymousState() {
      this.authenticated = false;
      this.subject = "";
      this.authMode = "";
    },
    applySessionState(payload: { authenticated: boolean; subject?: string | null; auth_mode?: string | null }) {
      this.authenticated = payload.authenticated;
      this.subject = payload.subject ?? "";
      this.authMode = payload.auth_mode ?? "";
    },
    async restoreSession() {
      this.checkingSession = true;
      try {
        this.applySessionState(await fetchSession());
      } finally {
        this.checkingSession = false;
      }
    },
    async login(password: string) {
      this.checkingSession = true;
      try {
        this.applySessionState(await loginWithPassword(password));
      } finally {
        this.checkingSession = false;
      }
    },
    async logout() {
      this.checkingSession = true;
      try {
        this.applySessionState(await logoutSession());
      } finally {
        this.checkingSession = false;
      }
    }
  }
});
