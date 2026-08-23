import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  documents: vi.fn(), chatSessions: vi.fn(), createChatSession: vi.fn(), chatMessages: vi.fn(),
  renameChatSession: vi.fn(), deleteChatSession: vi.fn(), chunk: vi.fn(), streamChatTurn: vi.fn(),
}));
vi.mock("../api/client", () => ({
  api: {
    documents: mocks.documents, chatSessions: mocks.chatSessions, createChatSession: mocks.createChatSession,
    chatMessages: mocks.chatMessages, renameChatSession: mocks.renameChatSession,
    deleteChatSession: mocks.deleteChatSession, chunk: mocks.chunk,
  },
  streamChatTurn: mocks.streamChatTurn,
}));
import { AskPage } from "./AskPage";

const session = { id: "10000000-0000-4000-8000-000000000001", title: "New conversation", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z", last_message_at: null, last_message_preview: null, message_count: 0 };
const result = { request_id: "r", status: "COMPLETED", answer_text: "Grounded [S1]", citations: [], invalid_citations: [], citation_validation: "PASS", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", finish_reason: "stop", usage: null, answerability_status: "ANSWERABLE", answerability_validation: "PASS" };

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset());
  mocks.documents.mockResolvedValue([]);
  mocks.chatSessions.mockResolvedValue({ data: [session], next_cursor: null });
  mocks.createChatSession.mockResolvedValue(session);
  mocks.chatMessages.mockResolvedValue({ data: [], next_before_sequence: null });
  mocks.renameChatSession.mockImplementation(async (_id, title) => ({ ...session, title }));
  mocks.deleteChatSession.mockResolvedValue(undefined);
});

describe("persistent Ask workspace", () => {
  it("creates a server session and sends a client-generated logical turn", async () => {
    mocks.chatSessions.mockResolvedValue({ data: [], next_cursor: null });
    mocks.streamChatTurn.mockImplementation(async (_session, _payload, handlers) => {
      handlers.start?.({ request_id: "r" }); handlers.delta?.("Grounded "); handlers.done?.(result);
    });
    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    await waitFor(() => expect(mocks.streamChatTurn).toHaveBeenCalledOnce());
    const [sessionId, payload] = mocks.streamChatTurn.mock.calls[0];
    expect(sessionId).toBe(session.id);
    expect(payload.query).toBe("Question?");
    expect(payload.client_turn_id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(mocks.chatMessages.mock.calls.length).toBeGreaterThan(0);
  });

  it("reloads historical answer and opens the immutable citation snapshot without a live chunk fetch", async () => {
    mocks.chatMessages.mockResolvedValue({ data: [
      { id: "u", session_id: session.id, turn_id: "t", role: "USER", sequence_no: 1, content: "Historic?", delivery_state: "COMMITTED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: null, failure_code: null, failure_detail_safe: null, citations: [] },
      { id: "a", session_id: session.id, turn_id: "t", role: "ASSISTANT", sequence_no: 2, content: "Historic answer [S1]", delivery_state: "COMPLETED", answer_status: "ANSWERABLE", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", created_at: "x", finalized_at: "x", failure_code: null, failure_detail_safe: null, citations: [{ source_id: "S1", chunk_id: "old-chunk", document_id: "old-doc", metadata_json: {}, provenance_json: { page_start: 4 }, evidence_text: "Immutable evidence", availability: "SOURCE_UNAVAILABLE" }] },
    ], next_before_sequence: null });
    render(<AskPage />);
    fireEvent.click(await screen.findByRole("button", { name: "[S1]" }));
    expect(await screen.findByText("Immutable evidence")).toBeInTheDocument();
    expect(screen.getByText(/original source is no longer available/i)).toBeInTheDocument();
    expect(mocks.chunk).not.toHaveBeenCalled();
  });

  it("preserves AbortController cancellation for persistent streams", async () => {
    mocks.streamChatTurn.mockImplementation((_session, _payload, handlers, signal) => new Promise((_resolve, reject) => {
      handlers.start?.({ request_id: "r" });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    render(<AskPage />);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Long query" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop generation" }));
    await waitFor(() => expect(mocks.chatMessages.mock.calls.length).toBeGreaterThan(1));
  });

  it("renders interrupted history distinctly and Retry creates a new logical turn id", async () => {
    mocks.chatMessages.mockResolvedValue({ data: [
      { id: "u", session_id: session.id, turn_id: "old-turn", role: "USER", sequence_no: 1, content: "Retry me", delivery_state: "COMMITTED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: null, failure_code: null, failure_detail_safe: null, citations: [] },
      { id: "a", session_id: session.id, turn_id: "old-turn", role: "ASSISTANT", sequence_no: 2, content: "", delivery_state: "FAILED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: "x", failure_code: "ORPHANED_STREAM_TIMEOUT", failure_detail_safe: "Generation was interrupted before completion.", citations: [] },
    ], next_before_sequence: null });
    mocks.streamChatTurn.mockImplementation(async (_session, _payload, handlers) => handlers.error?.({ safe_message: "safe" }));
    render(<AskPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mocks.streamChatTurn).toHaveBeenCalledOnce());
    expect(mocks.streamChatTurn.mock.calls[0][1].client_turn_id).not.toBe("old-turn");
    expect(screen.getByText("INTERRUPTED")).toBeInTheDocument();
  });

  it("renames, deletes, and keyset-loads server-authoritative history", async () => {
    mocks.chatSessions.mockResolvedValueOnce({ data: [session], next_cursor: "next" }).mockResolvedValueOnce({ data: [{ ...session, id: "older", title: "Older" }], next_cursor: null });
    mocks.chatMessages.mockResolvedValueOnce({ data: [], next_before_sequence: 10 }).mockResolvedValueOnce({ data: [], next_before_sequence: null });
    vi.spyOn(window, "prompt").mockReturnValue("Renamed");
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<AskPage />);
    fireEvent.click(await screen.findByRole("button", { name: `Rename ${session.title}` }));
    await waitFor(() => expect(mocks.renameChatSession).toHaveBeenCalledWith(session.id, "Renamed"));
    fireEvent.click(screen.getByRole("button", { name: "Older conversations" }));
    await waitFor(() => expect(mocks.chatSessions).toHaveBeenCalledWith("next"));
    fireEvent.click(screen.getByRole("button", { name: "Load older messages" }));
    await waitFor(() => expect(mocks.chatMessages).toHaveBeenCalledWith(session.id, 10));
    fireEvent.click(screen.getByRole("button", { name: "Delete Renamed" }));
    await waitFor(() => expect(mocks.deleteChatSession).toHaveBeenCalledWith(session.id));
  });
});
