import type {
  ClarifyRequest,
  ProviderCatalog,
  ResearchTaskCreateRequest,
  ResearchTaskFollowUpRequest,
  ResearchTaskSummary,
  ResearchTaskDetail
} from "../types/research";

async function request<T>(baseUrl: string, token: string, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {})
    }
  });
  if (!response.ok) {
    let errorMessage = `Request failed: ${response.status}`;
    try {
      const errorData = await response.json();
      if (errorData.detail) {
        errorMessage = typeof errorData.detail === 'string' ? errorData.detail : JSON.stringify(errorData.detail);
      } else if (errorData.message) {
        errorMessage = errorData.message;
      }
    } catch {
      // ignore
    }
    throw new Error(errorMessage);
  }
  return response.json() as Promise<T>;
}

export function fetchProviders(baseUrl: string, token: string): Promise<ProviderCatalog> {
  return request(baseUrl, token, "/api/v1/providers");
}

export function clarifyResearch(
  baseUrl: string,
  token: string,
  payload: ClarifyRequest
): Promise<{ questions: string[] }> {
  return request(baseUrl, token, "/api/v1/research/clarify", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createResearchTask(
  baseUrl: string,
  token: string,
  payload: ResearchTaskCreateRequest
): Promise<{ task_id: string; status: string }> {
  return request(baseUrl, token, "/api/v1/research/tasks", {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function createFollowUpResearchTask(
  baseUrl: string,
  token: string,
  taskId: string,
  payload: ResearchTaskFollowUpRequest
): Promise<{ task_id: string; status: string }> {
  return request(baseUrl, token, `/api/v1/research/tasks/${taskId}/follow-up`, {
    method: "POST",
    body: JSON.stringify(payload)
  });
}

export function fetchResearchTask(
  baseUrl: string,
  token: string,
  taskId: string
): Promise<ResearchTaskDetail> {
  return request(baseUrl, token, `/api/v1/research/tasks/${taskId}`);
}

export function fetchResearchTasks(
  baseUrl: string,
  token: string,
  limit = 20
): Promise<ResearchTaskSummary[]> {
  return request(baseUrl, token, `/api/v1/research/tasks?limit=${limit}`);
}

export function deleteResearchTask(
  baseUrl: string,
  token: string,
  taskId: string
): Promise<{ deleted: boolean }> {
  return request(baseUrl, token, `/api/v1/research/tasks/${taskId}`, {
    method: "DELETE"
  });
}
