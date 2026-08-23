import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { documents, documentDetail } = vi.hoisted(() => ({ documents: vi.fn(), documentDetail: vi.fn() }));
vi.mock("../api/client", () => ({ api: { documents, document: documentDetail, upload: vi.fn() } }));
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
  beforeEach(() => {
    documents.mockReset().mockResolvedValue([stored]);
    documentDetail.mockReset().mockResolvedValue(stored);
  });

  it("searches the corpus list and exposes pipeline summary", async () => {
    render(<DocumentsPage />);
    await waitFor(() => expect(screen.getByText("sample_legal.pdf")).toBeInTheDocument());
    expect(screen.getByText("8", { selector: ".metric strong" })).toBeInTheDocument();
    expect(screen.getByText("PRIVATE + GLOBAL")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "missing" } });
    expect(screen.getByText("No documents match this search.")).toBeInTheDocument();
  });

  it("opens an accessible document lineage drawer", async () => {
    render(<DocumentsPage />);
    fireEvent.click(await screen.findByRole("button", { name: /sample_legal\.pdf/ }));
    expect(await screen.findByRole("dialog", { name: "sample_legal.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Document ID")).toBeInTheDocument();
    fireEvent.keyDown(document.body, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});
