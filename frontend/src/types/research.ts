export interface ClarifyRequest {
  query: string;
  provider: string;
  thinking_model: string;
  language: string;
}

export interface ResearchTaskCreateRequest {
  query: string;
  questions: string[];
  answers: string[];
  parent_task_id?: string | null;
  research_iteration?: number;
  follow_up_request?: string | null;
  provider: string;
  thinking_model: string;
  task_model: string;
  search_provider: string;
  language: string;
  max_results: number;
}

export interface ResearchTaskFollowUpRequest {
  follow_up_request: string;
  max_results?: number | null;
}

export interface ResearchTaskSummary {
  id: string;
  parent_task_id: string | null;
  research_iteration: number;
  status: string;
  query: string;
  follow_up_request: string | null;
  provider: string;
  thinking_model: string;
  task_model: string;
  search_provider: string;
  language: string;
  current_step: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
}

export interface SourceRecord {
  id: number;
  source_type: string;
  title: string | null;
  url: string;
  content: string;
  meta_json: Record<string, unknown>;
}

export interface EventRecord {
  id: number;
  sequence: number;
  event_type: string;
  step: string | null;
  payload_json: Record<string, unknown>;
  created_at: string;
}

export interface ResearchTaskDetail {
  id: string;
  parent_task_id: string | null;
  research_iteration: number;
  status: string;
  query: string;
  clarify_questions: string[];
  clarify_answers: string[];
  clarified_brief: string | null;
  follow_up_request: string | null;
  provider: string;
  thinking_model: string;
  task_model: string;
  search_provider: string;
  language: string;
  max_results: number;
  current_step: string | null;
  report_plan: string | null;
  final_report: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string | null;
  completed_at: string | null;
  sources: SourceRecord[];
  events: EventRecord[];
}

export interface ProviderCatalog {
  llm_providers: Record<string, { label: string; models: string[] }>;
  search_providers: Record<string, { label: string }>;
}

export interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}
