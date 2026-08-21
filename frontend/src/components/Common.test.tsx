import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CandidateTable, CitedAnswer, EmptyState, StatusBadge } from "./Common";

describe("debug rendering", () => {
  it("renders an explicit lexical empty state", () => {
    render(<CandidateTable kind="lexical" candidates={[]} onInspect={() => undefined} />);
    expect(screen.getByText("No lexical candidates.")).toBeInTheDocument();
  });

  it("renders dense rank and diagnostic preview", () => {
    render(<CandidateTable kind="dense" onInspect={() => undefined} candidates={[{ chunk_id: "12345678-0000", document_id: "abcdef00-0000", dense_rank: 1, dense_score: .88, content_preview: "Relevant evidence" }]} />);
    expect(screen.getByText("Relevant evidence")).toBeInTheDocument();
    expect(screen.getByText("0.8800")).toBeInTheDocument();
  });

  it("turns a mapped citation into an inspectable control", () => {
    const inspect = vi.fn();
    render(<CitedAnswer text="Answer [S1]" citations={[{ source_id: "S1", chunk_id: "c1", document_id: "d1", metadata_json: {}, provenance_json: {} }]} onCitation={inspect} />);
    fireEvent.click(screen.getByRole("button", { name: "[S1]" }));
    expect(inspect).toHaveBeenCalledOnce();
  });

  it("shows readable status and empty state", () => {
    render(<><StatusBadge value="INSUFFICIENT_EVIDENCE" /><EmptyState>No citations.</EmptyState></>);
    expect(screen.getByText("INSUFFICIENT EVIDENCE")).toBeInTheDocument();
    expect(screen.getByText("No citations.")).toBeInTheDocument();
  });
});
