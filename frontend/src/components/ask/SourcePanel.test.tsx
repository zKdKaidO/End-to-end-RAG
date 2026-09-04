import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SourcePanel } from "./SourcePanel";

const citation = { source_id: "S1", chunk_id: "chunk-1", document_id: "doc-1", metadata_json: { title: "safe title" }, provenance_json: { document_id: "doc-1", page_start: 2, source_relative_path: "must-not-render" } };

describe("SourcePanel local citations", () => {
  it("uses the real local citation shape without a fabricated label or preview", () => {
    const select = vi.fn();
    render(<SourcePanel tab="evidence" onTabChange={vi.fn()} documents={[{ document_id: "doc-1", filename: "local-law.pdf", page_count: 2, chunk_count: 3 }]} selectedDocumentIds={["doc-1"]} activeCitation={citation} evidenceCitations={[citation]} onToggleDocument={vi.fn()} onSelectAll={vi.fn()} onSelectCitation={select} onOpenCitationDetail={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("S1")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(screen.getByText("Evidence preview is unavailable locally.")).toBeInTheDocument();
    expect(screen.queryByText("must-not-render")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /S1/ }));
    expect(select).toHaveBeenCalledWith(citation);
  });

  it("uses the mapped local filename when citation provenance has no safe page", () => {
    const noPageCitation = { ...citation, chunk_id: "chunk-2", source_id: "S2", provenance_json: { document_id: "doc-1" } };
    render(<SourcePanel tab="evidence" onTabChange={vi.fn()} documents={[{ document_id: "doc-1", filename: "local-law.pdf", page_count: 2, chunk_count: 3 }]} selectedDocumentIds={["doc-1"]} activeCitation={null} evidenceCitations={[noPageCitation]} onToggleDocument={vi.fn()} onSelectAll={vi.fn()} onSelectCitation={vi.fn()} onOpenCitationDetail={vi.fn()} onClose={vi.fn()} />);
    expect(screen.getByText("local-law.pdf")).toBeInTheDocument();
  });
});
