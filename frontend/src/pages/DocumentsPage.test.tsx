import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { documents, documentDetail, indexDocument, deleteDocument } = vi.hoisted(() => ({ documents: vi.fn(), documentDetail: vi.fn(), indexDocument: vi.fn(), deleteDocument: vi.fn() }));
vi.mock("../api/client", () => ({ api: { documents, document: documentDetail, upload: vi.fn(), indexDocument, deleteDocument } }));
import { DocumentsPage } from "./DocumentsPage";

const stored = {
  document_id: "11111111-1111-1111-1111-111111111111",
  filename: "sample_legal.pdf",
  mime_type: "application/pdf",
  file_size: 2048,
  created_at: "2026-08-20T12:00:00Z",
  ingestion: { status: "COMPLETED", current_stage: null },
  processing: { status: "COMPLETED", current_stage: null },
  indexing: { status: "COMPLETED", current_stage: null },
  page_count: 4,
  legal_unit_count: 6,
  chunk_count: 8,
  index_count: 8,
  access_origin: "PRIVATE + GLOBAL",
  chunks: [],
};

describe("DocumentsPage", () => {
  afterEach(() => vi.useRealTimers());
  beforeEach(() => {
    documents.mockReset().mockResolvedValue([stored]);
    documentDetail.mockReset().mockResolvedValue(stored);
    indexDocument.mockReset().mockResolvedValue({});
    deleteDocument.mockReset().mockResolvedValue({});
  });

  const renderDocuments = () => render(<MemoryRouter initialEntries={["/documents"]}><DocumentsPage /></MemoryRouter>);

  it("searches the corpus list and exposes pipeline summary", async () => {
    renderDocuments();
    await waitFor(() => expect(screen.getByText("sample_legal.pdf")).toBeInTheDocument());
    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText(/PRIVATE \+ GLOBAL/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "missing" } });
    expect(screen.getByText("No documents match this search or filter.")).toBeInTheDocument();
  });

  it("opens an accessible document lineage drawer", async () => {
    renderDocuments();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect sample_legal.pdf" }));
    expect(await screen.findByRole("dialog", { name: "sample_legal.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Document ID")).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("uses the real re-index action and confirms private access removal", async () => {
    renderDocuments();
    fireEvent.click(await screen.findByRole("button", { name: "Re-index sample_legal.pdf" }));
    await waitFor(() => expect(indexDocument).toHaveBeenCalledWith(stored.document_id));
    fireEvent.click(screen.getByRole("button", { name: "Remove sample_legal.pdf" }));
    expect(screen.getByRole("dialog", { name: /Remove “sample_legal\.pdf”/ })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(deleteDocument).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Remove sample_legal.pdf" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(deleteDocument).toHaveBeenCalledWith(stored.document_id));
  });

  it("polls only while a pipeline is active and stops after terminal refresh", async () => {
    vi.useFakeTimers();
    const active = { ...stored, indexing: { status: "RUNNING", current_stage: "EMBED" }, index_count: 0 };
    documents.mockReset().mockResolvedValueOnce([active]).mockResolvedValueOnce([stored]);
    renderDocuments();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(documents).toHaveBeenCalledTimes(1);
    await act(async () => { vi.advanceTimersByTime(4_000); await Promise.resolve(); await Promise.resolve(); });
    expect(documents).toHaveBeenCalledTimes(2);
    await act(async () => { vi.advanceTimersByTime(12_000); await Promise.resolve(); });
    expect(documents).toHaveBeenCalledTimes(2);
  });
});
