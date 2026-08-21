import type {
  ChunkDetail,
  DebugTrace,
  DocumentPipeline,
  EvaluationCase,
  EvaluationComparison,
  EvaluationSummary,
  GenerationResult,
} from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

export class ApiError extends Error {
  constructor(message: string, public status: number, public requestId?: string) {
    super(message);
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const requestId = response.headers.get("X-Request-ID") ?? undefined;
  if (!response.ok) {
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

export const api = {
  status: () => apiFetch<{ api: string; provider: string; model_id: string }>("/internal/debug/status"),
  documents: () => apiFetch<DocumentPipeline[]>("/internal/debug/documents"),
  document: (id: string) => apiFetch<DocumentPipeline>(`/internal/debug/documents/${id}`),
  chunk: (id: string) => apiFetch<ChunkDetail>(`/internal/debug/chunks/${id}`),
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
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return apiFetch<{ document: { id: string; filename: string; status: string } }>("/documents", { method: "POST", body: form });
  },
};

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
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal,
  });
  if (!response.ok || !response.body) {
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
