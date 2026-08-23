import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { debug } = vi.hoisted(() => ({ debug: vi.fn() }));
vi.mock("../api/client", () => ({
  api: {
    documents: vi.fn().mockResolvedValue([]),
    evaluationCases: vi.fn().mockResolvedValue([]),
    debug,
    chunk: vi.fn(),
  },
}));
import { api } from "../api/client";
import { DebugPage } from "./DebugPage";

const trace = {
  request_id: "r1", query_text: "test query", document_ids: [],
  retrieval: { dense_candidates: [], lexical_candidates: [], final_candidates: [], dense_candidate_count: 0, lexical_candidate_count: 0, overlap_count: 0, lexical_mode: "NO_LEXICAL_MATCH", score_semantics: "diagnostic", timings_ms: {} },
  context: { candidate_count: 0, duplicate_count: 0, selected_count: 0, dropped_count: 0, context_token_count: 0, context_budget_tokens: 4096, budget_utilization_percent: 0, budget_exhausted: false, stop_reason: "NONE", selected_evidence: [] },
  generation: { status: "INSUFFICIENT_EVIDENCE", answerability_status: "INSUFFICIENT_EVIDENCE", answerability_validation: "PASS", answer_text: "No evidence", citations: [], invalid_citations: [], citation_validation: "PASS", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", finish_reason: null, usage: null, prompt_token_count: 0, context_token_count: 0, generation_ms: 1, time_to_first_token_ms: null },
  timings_ms: { total_ms: 2 }, expected: null, diagnosis: null,
};

describe("DebugPage", () => {
  beforeEach(() => debug.mockResolvedValue(trace));
  it("renders all frozen pipeline stages and avoids ad-hoc correctness claims", async () => {
    render(<DebugPage />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "test query" } });
    fireEvent.click(screen.getByRole("button", { name: "Run Debug" }));
    await waitFor(() => expect(screen.getByText("Request trace")).toBeInTheDocument());
    expect(screen.getByText("Dense candidates")).toBeInTheDocument();
    expect(screen.getByText("No lexical candidates.")).toBeInTheDocument();
    expect(screen.getByText("Context")).toBeInTheDocument();
    expect(screen.getByText("Generation")).toBeInTheDocument();
    expect(screen.getByText("NO GROUND TRUTH")).toBeInTheDocument();
    expect(screen.queryByText("CORRECT")).not.toBeInTheDocument();
  });

  it("explains the intentional debug gate when the backend returns 404", async () => {
    const gated = Object.assign(new Error("Debug endpoints are disabled"), { status: 404 });
    vi.mocked(api.documents).mockRejectedValueOnce(gated);
    render(<DebugPage />);
    await waitFor(() => expect(screen.getByText("Internal diagnostics are disabled by the backend environment contract.")).toBeInTheDocument());
  });
});
