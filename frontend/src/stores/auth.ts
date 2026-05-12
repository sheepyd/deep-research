import { defineStore } from "pinia";

import { fetchSession, loginAsGuest, loginWithPassword, logoutSession } from "../services/api";

export interface AuthState {
  authenticated: boolean;
  subject: string;
  authMode: string;
  checkingSession: boolean;
  guestEnabled: boolean;
}

function defaultState(): AuthState {
  return {
    authenticated: false,
    subject: "",
    authMode: "",
    checkingSession: true,
    guestEnabled: false
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
    applySessionState(payload: {
      authenticated: boolean;
      subject?: string | null;
      auth_mode?: string | null;
      guest_enabled?: boolean;
    }) {
      this.authenticated = payload.authenticated;
      this.subject = payload.subject ?? "";
      this.authMode = payload.auth_mode ?? "";
      if (typeof payload.guest_enabled === "boolean") {
        this.guestEnabled = payload.guest_enabled;
      }
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
    async loginAsGuest() {
      this.checkingSession = true;
      try {
        this.applySessionState(await loginAsGuest());
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
