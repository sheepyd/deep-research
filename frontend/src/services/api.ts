import type {
  ClarifyRequest,
  ProviderCatalog,
  ResearchTaskCreateRequest,
  ResearchTaskDetail,
  ResearchTaskFollowUpRequest,
  ResearchTaskSummary
} from "../types/research";

export interface SessionState {
  authenticated: boolean;
  subject?: string | null;
  auth_mode?: string | null;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers
  });

  if (!response.ok) {
    let errorMessage = `Request failed: ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === "string" ? errorData.detail : JSON.stringify(errorData.detail);
      } else if (errorData.message) {
        errorMessage = errorData.message;
      }
    } catch {
      // ignore
    }
    if (response.status === 401 && !path.startsWith("/api/v1/auth") && typeof window !== "undefined") {
      window.dispatchEvent(new Event("deep-research:unauthorized"));
    }
    throw new ApiError(errorMessage, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function fetchSession(): Promise<SessionState> {
  return request("/api/v1/auth/session");
}

export function loginWithPassword(password: string): Promise<SessionState> {
  return request("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify({ password })
  });
}

export function logoutSession(): Promise<SessionState> {
  return request("/api/v1/auth/logout", {
    method: "POST"
  });
}

export function fetchProviders(): Promise<ProviderCatalog> {
  return request("/api/v1/providers");
}

export function clarifyResearch(payload: ClarifyRequest): Promise<{ questions: string[] }> {
  return request("/api/v1/research/clarify", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createResearchTask(payload: ResearchTaskCreateRequest): Promise<{ task_id: string; status: string }> {
  return request("/api/v1/research/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createFollowUpResearchTask(
  taskId: string,
  payload: ResearchTaskFollowUpRequest
): Promise<{ task_id: string; status: string }> {
  return request(`/api/v1/research/tasks/${taskId}/follow-up`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchResearchTask(taskId: string): Promise<ResearchTaskDetail> {
  return request(`/api/v1/research/tasks/${taskId}`);
}

export function fetchResearchTasks(limit = 20): Promise<ResearchTaskSummary[]> {
  return request(`/api/v1/research/tasks?limit=${limit}`);
}

export function deleteResearchTask(taskId: string): Promise<{ deleted: boolean }> {
  return request(`/api/v1/research/tasks/${taskId}`, {
    method: "DELETE"
  });
}
