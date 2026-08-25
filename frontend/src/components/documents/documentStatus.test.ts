import { describe, expect, it } from "vitest";
import type { DocumentPipeline } from "../../types";
import { getDocumentDisplayState, matchesDocumentFilter } from "./documentStatus";

const base: DocumentPipeline = { document_id: "d", filename: "law.pdf", mime_type: "application/pdf", file_size: 1, ingestion: { status: "COMPLETED" }, processing: { status: "COMPLETED" }, indexing: { status: "COMPLETED" }, page_count: 1, legal_unit_count: 1, chunk_count: 2, index_count: 2 };

describe("document display state", () => {
  it("centralizes ready, active, and failure action semantics", () => {
    expect(getDocumentDisplayState(base)).toMatchObject({ key: "READY", canIndex: true, indexActionLabel: "Re-index" });
    expect(getDocumentDisplayState({ ...base, indexing: { status: "RUNNING" } })).toMatchObject({ key: "INDEXING", active: true, canIndex: false });
    expect(getDocumentDisplayState({ ...base, processing: { status: "FAILED" }, chunk_count: 0, index_count: 0 })).toMatchObject({ key: "PROCESSING_FAILED", failed: true, canIndex: false });
    expect(getDocumentDisplayState({ ...base, indexing: { status: "FAILED" }, index_count: 0 })).toMatchObject({ key: "INDEXING_FAILED", canIndex: true, indexActionLabel: "Retry indexing" });
    expect(getDocumentDisplayState({ ...base, processing: { status: "NOT_STARTED" }, indexing: { status: "NOT_STARTED" }, chunk_count: 0, index_count: 0 })).toMatchObject({ key: "NOT_INDEXED", active: false, canIndex: false });
  });
  it("drives filter groups from the same mapped state", () => {
    expect(matchesDocumentFilter(base, "READY")).toBe(true);
    expect(matchesDocumentFilter({ ...base, indexing: { status: "PENDING" } }, "PROCESSING")).toBe(true);
    expect(matchesDocumentFilter({ ...base, ingestion: { status: "ERROR" } }, "FAILED")).toBe(true);
  });
});
