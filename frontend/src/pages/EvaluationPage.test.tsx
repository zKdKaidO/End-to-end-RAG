import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api/client", () => ({ api: {
  evaluationSummary: vi.fn().mockResolvedValue({ report_id: "r", dataset_sha256: "abc", aggregate: { case_count: 32, answerable_count: 27, unanswerable_count: 5, retrieval: { hit_at_10: .92, mrr: .88 }, context: { expected_evidence_retention: 1 }, generation: { citation_structural_validity_rate: 1 }, unanswerable: { correct_abstention_rate: 1 }, failure_counts: { PASS: 28, RETRIEVAL_MISS: 2 } }, known_limitations: ["Limited corpus"] }),
  evaluationCases: vi.fn().mockResolvedValue([{ case_id: "c1", category: "DIRECT_FACT", question: "Q?", answerable: true, retrieval_result: "FOUND", context_result: "RETAINED", generation_result: "COMPLETED", diagnosis: "PASS" }]),
  evaluationComparison: vi.fn().mockResolvedValue({ before: { retrieval: { hit_at_1: .8, hit_at_10: .9, mrr: .8 }, generation: {}, unanswerable: {} }, after: { retrieval: { hit_at_1: .8, hit_at_10: .9, mrr: .8 }, generation: {}, unanswerable: {} }, delta: {}, known_limitations: [] }),
} }));
import { api } from "../api/client";
import { EvaluationPage } from "./EvaluationPage";

describe("EvaluationPage", () => {
  it("renders stored metrics, failure filtering data, cases, and limitations", async () => {
    render(<EvaluationPage />);
    await waitFor(() => expect(screen.getByText("92.00%")).toBeInTheDocument());
    expect(screen.getByText("RETRIEVAL MISS")).toBeInTheDocument();
    expect(screen.getByText("c1")).toBeInTheDocument();
    expect(screen.getByText("Limited corpus")).toBeInTheDocument();
    expect(screen.getByText("Before / after")).toBeInTheDocument();
  });

  it("loads immutable Evaluation V2 artifacts through the dataset selector", async () => {
    render(<EvaluationPage />);
    await waitFor(() => expect(api.evaluationSummary).toHaveBeenCalledWith("legal_eval_v1"));
    fireEvent.change(screen.getByLabelText("Evaluation dataset"), { target: { value: "legal_eval_v2" } });
    await waitFor(() => expect(api.evaluationSummary).toHaveBeenCalledWith("legal_eval_v2"));
    expect(api.evaluationCases).toHaveBeenCalledWith("legal_eval_v2");
  });
});
