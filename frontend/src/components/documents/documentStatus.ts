import type { DocumentPipeline, PipelineStage } from "../../types";

export type DocumentDisplayStateKey = "READY" | "PROCESSING" | "INDEXING" | "INGESTION_FAILED" | "PROCESSING_FAILED" | "INDEXING_FAILED" | "NOT_INDEXED";
export type DocumentFilter = "ALL" | "READY" | "PROCESSING" | "FAILED";

export interface DocumentDisplayState {
  key: DocumentDisplayStateKey;
  label: string;
  active: boolean;
  failed: boolean;
  canIndex: boolean;
  indexActionLabel: "Retry indexing" | "Re-index" | "Index document" | null;
}

const ACTIVE = new Set(["PENDING", "QUEUED", "RUNNING", "PROCESSING", "UPLOADING", "STARTED", "IN_PROGRESS", "RECEIVED", "EXTRACTING", "CHUNKING", "INDEXING"]);
const COMPLETED = new Set(["COMPLETED", "COMPLETE", "SUCCEEDED", "SUCCESS"]);

function status(stage: PipelineStage) { return stage.status.trim().toUpperCase(); }
function isFailed(stage: PipelineStage) { const value = status(stage); return value === "ERROR" || value.startsWith("FAILED"); }
function isActive(stage: PipelineStage) { return ACTIVE.has(status(stage)); }
function isComplete(stage: PipelineStage) { return COMPLETED.has(status(stage)); }

export function getDocumentDisplayState(document: DocumentPipeline): DocumentDisplayState {
  const chunksAvailable = document.chunk_count > 0;
  if (isFailed(document.ingestion)) return state("INGESTION_FAILED", "Ingestion failed", false, true, false, null);
  if (isActive(document.ingestion)) return state("PROCESSING", "Ingesting", true, false, false, null);
  if (isFailed(document.processing)) return state("PROCESSING_FAILED", "Processing failed", false, true, false, null);
  if (isActive(document.processing)) return state("PROCESSING", "Processing", true, false, false, null);
  if (isFailed(document.indexing)) return state("INDEXING_FAILED", "Indexing failed", false, true, chunksAvailable, chunksAvailable ? "Retry indexing" : null);
  if (isActive(document.indexing)) return state("INDEXING", "Indexing", true, false, false, null);
  if (document.index_count > 0 && isComplete(document.indexing)) return state("READY", "Ready", false, false, chunksAvailable, chunksAvailable ? "Re-index" : null);
  return state("NOT_INDEXED", "Not indexed", false, false, chunksAvailable, chunksAvailable ? "Index document" : null);
}

function state(key: DocumentDisplayStateKey, label: string, active: boolean, failed: boolean, canIndex: boolean, indexActionLabel: DocumentDisplayState["indexActionLabel"]): DocumentDisplayState {
  return { key, label, active, failed, canIndex, indexActionLabel };
}

export function matchesDocumentFilter(document: DocumentPipeline, filter: DocumentFilter) {
  const display = getDocumentDisplayState(document);
  if (filter === "ALL") return true;
  if (filter === "READY") return display.key === "READY";
  if (filter === "FAILED") return display.failed;
  return display.active;
}

export function documentStatusClasses(state: DocumentDisplayState) {
  if (state.key === "READY") return "bg-emerald-50 text-emerald-700 ring-emerald-200";
  if (state.failed) return "bg-red-50 text-red-700 ring-red-200";
  if (state.active) return "bg-amber-50 text-amber-700 ring-amber-200";
  return "bg-slate-100 text-slate-600 ring-slate-200";
}
