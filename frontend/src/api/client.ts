import type {
  ChunkDetail,
  DebugTrace,
  DocumentPipeline,
  EvaluationCase,
  EvaluationComparison,
  EvaluationSummary,
  GenerationResult,
  ChatMessage,
  ChatSession,
  AuthUser,
} from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId?: string) {
    super(message);
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "include", ...init });
  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("legal-rag:unauthorized"));
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = typeof payload.detail === "string" ? payload.detail : payload.detail?.message ?? message;
    } catch {
      // Preserve the safe status-only fallback.
    }
    throw new ApiError(message, response.status, requestId);
  }
  return response.json() as Promise<T>;
}

async function apiFetchVoid(path: string, init?: RequestInit): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, { credentials: "include", ...init });
  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event("legal-rag:unauthorized"));
    throw new ApiError(`Request failed (${response.status})`, response.status, response.headers.get("X-Request-ID") ?? undefined);
  }
}

export const api = {
  me: () => apiFetch<AuthUser>("/api/v1/auth/me"),
  login: (email: string, password: string) => apiFetch<AuthUser>("/api/v1/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }),
  }),
  logout: () => apiFetchVoid("/api/v1/auth/logout", { method: "POST" }),
  health: () => apiFetch<{ status: string; service: string }>("/health"),
  status: () => apiFetch<{ api: string; provider: string; model_id: string }>("/internal/debug/status"),
  documents: () => apiFetch<DocumentPipeline[]>("/documents"),
  document: (id: string) => apiFetch<DocumentPipeline>(`/api/v1/documents/${id}`),
  chunk: (id: string) => apiFetch<ChunkDetail>(`/api/v1/chunks/${id}`),
  debug: (payload: { query_text: string; document_ids?: string[] | null; evaluation_case_id?: string | null }) =>
    apiFetch<DebugTrace>("/internal/debug/rag", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  evaluationSummary: (datasetId?: string) => apiFetch<EvaluationSummary>(`/internal/evaluation/summary${datasetQuery(datasetId)}`),
  evaluationCases: (datasetId?: string) => apiFetch<EvaluationCase[]>(`/internal/evaluation/cases${datasetQuery(datasetId)}`),
  evaluationCase: (id: string, datasetId?: string) => apiFetch<{ dataset_case: Record<string, unknown>; measured_case: Record<string, unknown> }>(`/internal/evaluation/cases/${id}${datasetQuery(datasetId)}`),
  evaluationComparison: () => apiFetch<EvaluationComparison>("/internal/evaluation/comparison"),
  rerunCase: (id: string, datasetId?: string) => apiFetch<DebugTrace>(`/internal/evaluation/cases/${id}/rerun${datasetQuery(datasetId)}`, { method: "POST" }),
  upload: async (file: File, access: "private" | "global" = "private") => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ document: { id: string; filename: string; status: string } }>(`/documents?access=${access}`, { method: "POST", body: form });
  },
  deleteDocument: (id: string) => apiFetch<Record<string, unknown>>(`/documents/${id}`, { method: "DELETE" }),
  indexDocument: (id: string) => apiFetch<Record<string, unknown>>(`/documents/${id}/index`, { method: "POST" }),
  createChatSession: (title?: string) => apiFetch<ChatSession>("/api/v1/chat/sessions", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(title ? { title } : {}),
  }),
  chatSessions: (cursor?: string) => apiFetch<{ data: ChatSession[]; next_cursor: string | null }>(`/api/v1/chat/sessions${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`),
  chatSession: (id: string) => apiFetch<ChatSession>(`/api/v1/chat/sessions/${id}`),
  renameChatSession: (id: string, title: string) => apiFetch<ChatSession>(`/api/v1/chat/sessions/${id}`, {
    method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title }),
  }),
  deleteChatSession: (id: string) => apiFetchVoid(`/api/v1/chat/sessions/${id}`, { method: "DELETE" }),
  chatMessages: async (id: string, beforeSequence?: number) => {
    const page = await apiFetch<{ data: RawChatMessage[]; next_before_sequence: number | null }>(
      `/api/v1/chat/sessions/${id}/messages${beforeSequence ? `?before_sequence=${beforeSequence}` : ""}`,
    );
    return { ...page, data: page.data.map(normalizeChatMessage) };
  },
};

interface RawChatMessage extends Omit<ChatMessage, "citations"> {
  citations: Array<Record<string, unknown>>;
}

function normalizeChatMessage(message: RawChatMessage): ChatMessage {
  return {
    ...message,
    citations: message.citations.map((raw) => ({
      source_id: String(raw.citation_label),
      chunk_id: raw.original_chunk_id ? String(raw.original_chunk_id) : "",
      document_id: raw.original_document_id ? String(raw.original_document_id) : "",
      metadata_json: (raw.metadata_json ?? {}) as Record<string, unknown>,
      provenance_json: (raw.provenance_json ?? {}) as Record<string, unknown>,
      snapshot_id: String(raw.id),
      citation_order: Number(raw.citation_order),
      original_legal_unit_id: raw.original_legal_unit_id ? String(raw.original_legal_unit_id) : null,
      document_title: raw.document_title ? String(raw.document_title) : null,
      document_filename: raw.document_filename ? String(raw.document_filename) : null,
      document_sha256: raw.document_sha256 ? String(raw.document_sha256) : null,
      chunk_content_sha256: String(raw.chunk_content_sha256),
      page_start: raw.page_start == null ? null : Number(raw.page_start),
      page_end: raw.page_end == null ? null : Number(raw.page_end),
      article: raw.article ? String(raw.article) : null,
      clause: raw.clause ? String(raw.clause) : null,
      point: raw.point ? String(raw.point) : null,
      evidence_text: String(raw.evidence_text),
      availability: raw.availability as "CURRENT_EQUIVALENT" | "SOURCE_UPDATED" | "SOURCE_UNAVAILABLE",
      current_document_id: raw.current_document_id ? String(raw.current_document_id) : null,
      current_chunk_id: raw.current_chunk_id ? String(raw.current_chunk_id) : null,
    })),
  };
}

function datasetQuery(datasetId?: string) {
  return datasetId ? `?dataset_id=${encodeURIComponent(datasetId)}` : "";
}

export interface SseHandlers {
  start?: (data: Record<string, unknown>) => void;
  delta?: (text: string) => void;
  done?: (result: GenerationResult) => void;
  error?: (data: Record<string, unknown>) => void;
}

export function parseSseBlock(block: string): { event: string; data: unknown } | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.replace(/\r/g, "").split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
  }
  if (!data.length) return null;
  return { event, data: JSON.parse(data.join("\n")) };
}

export async function streamAnswer(
  payload: { query_text: string; document_ids?: string[] | null },
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/answer/stream`, {
    credentials: "include",
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
    if (response.status === 401) window.dispatchEvent(new Event("legal-rag:unauthorized"));
    throw new ApiError(`Stream request failed (${response.status})`, response.status, response.headers.get("X-Request-ID") ?? undefined);
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const parsed = parseSseBlock(block);
      if (!parsed) continue;
      const data = parsed.data as Record<string, unknown>;
      if (parsed.event === "start") handlers.start?.(data);
      else if (parsed.event === "delta") handlers.delta?.(String(data.text ?? ""));
      else if (parsed.event === "done") handlers.done?.(data as unknown as GenerationResult);
      else if (parsed.event === "error") handlers.error?.(data);
    }
    if (done) break;
  }
}

export async function streamChatTurn(
  sessionId: string,
  payload: { client_turn_id: string; query: string; document_ids?: string[] | null },
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  return streamSse(`/api/v1/chat/sessions/${sessionId}/turns/stream`, payload, handlers, signal);
}

async function streamSse(
  path: string,
  payload: Record<string, unknown>,
  handlers: SseHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST", credentials: "include", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload), signal,
  });
  if (!response.ok || !response.body) {
    if (response.status === 401) window.dispatchEvent(new Event("legal-rag:unauthorized"));
    let message = `Stream request failed (${response.status})`;
    try { const body = await response.json(); message = body.detail?.message ?? message; } catch { /* safe fallback */ }
    throw new ApiError(message, response.status, response.headers.get("X-Request-ID") ?? undefined);
  }
  await consumeSse(response, handlers);
}

async function consumeSse(response: Response, handlers: SseHandlers) {
  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, "\n");
    let boundary: number;
    while ((boundary = buffer.indexOf("\n\n")) >= 0) {
      const parsed = parseSseBlock(buffer.slice(0, boundary));
      buffer = buffer.slice(boundary + 2);
      if (!parsed) continue;
      const data = parsed.data as Record<string, unknown>;
      if (parsed.event === "start") handlers.start?.(data);
      else if (parsed.event === "delta") handlers.delta?.(String(data.text ?? ""));
      else if (parsed.event === "done") handlers.done?.(data as unknown as GenerationResult);
      else if (parsed.event === "error") handlers.error?.(data);
    }
    if (done) break;
  }
}
