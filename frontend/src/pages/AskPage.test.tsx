import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { streamAnswer } = vi.hoisted(() => ({ streamAnswer: vi.fn() }));
vi.mock("../api/client", () => ({
  api: { documents: vi.fn().mockResolvedValue([]), chunk: vi.fn() },
  streamAnswer,
}));
import { AskPage } from "./AskPage";

describe("AskPage", () => {
  it("renders authoritative insufficient-evidence completion", async () => {
    streamAnswer.mockImplementation(async (_payload, handlers) => {
      handlers.start?.({ request_id: "r" });
      handlers.done?.({ request_id: "r", status: "INSUFFICIENT_EVIDENCE", answer_text: "Evidence is insufficient.", citations: [], invalid_citations: [], citation_validation: "PASS", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", finish_reason: null, usage: null, answerability_status: "INSUFFICIENT_EVIDENCE", answerability_validation: "PASS" });
    });
    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Unknown fact?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(screen.getAllByText("INSUFFICIENT EVIDENCE").length).toBeGreaterThan(0));
    expect(screen.getByText("Evidence is insufficient.")).toBeInTheDocument();
  });

  it("offers cancellation while a stream is active", async () => {
    streamAnswer.mockImplementation((_payload, handlers, signal) => new Promise((_resolve, reject) => {
      handlers.start?.({ request_id: "r" });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Long query" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    const stop = await screen.findByRole("button", { name: "Stop generation" });
    fireEvent.click(stop);
    await waitFor(() => expect(screen.getByText("cancelled")).toBeInTheDocument());
  });
});
