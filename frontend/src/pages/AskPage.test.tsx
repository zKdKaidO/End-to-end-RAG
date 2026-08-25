import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
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
const user = { id: "user-1", email: "user@example.com", role: "USER" as const, status: "ACTIVE" as const, must_change_password: false };
const result = { request_id: "r", status: "COMPLETED", answer_text: "Grounded [S1]", citations: [], invalid_citations: [], citation_validation: "PASS", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", finish_reason: "stop", usage: null, answerability_status: "ANSWERABLE", answerability_validation: "PASS" };
const indexedA = { document_id: "doc-a", filename: "law-a.pdf", mime_type: "application/pdf", file_size: 10, ingestion: { status: "COMPLETED" }, processing: { status: "COMPLETED" }, indexing: { status: "COMPLETED" }, page_count: 1, legal_unit_count: 1, chunk_count: 3, index_count: 3 };
const indexedB = { ...indexedA, document_id: "doc-b", filename: "law-b.pdf", chunk_count: 2, index_count: 2 };
const notIndexed = { ...indexedA, document_id: "doc-c", filename: "draft.pdf", indexing: { status: "PENDING" }, chunk_count: 0, index_count: 0 };

function renderAsk() {
  return render(<MemoryRouter initialEntries={["/ask"]}><AskPage user={user} onLogout={vi.fn()} /></MemoryRouter>);
}

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
  it("renders existing sessions, selects one, and creates a New Inquiry", async () => {
    const second = { ...session, id: "10000000-0000-4000-8000-000000000002", title: "Second inquiry" };
    mocks.chatSessions.mockResolvedValue({ data: [session, second], next_cursor: null });
    renderAsk();
    fireEvent.click(await screen.findByRole("button", { name: "Second inquiry" }));
    await waitFor(() => expect(mocks.chatMessages).toHaveBeenCalledWith(second.id));
    fireEvent.click(screen.getByRole("button", { name: "New Inquiry" }));
    await waitFor(() => expect(mocks.createChatSession).toHaveBeenCalledOnce());
  });

  it("creates a server session and sends a client-generated logical turn", async () => {
    mocks.chatSessions.mockResolvedValue({ data: [], next_cursor: null });
    mocks.streamChatTurn.mockImplementation(async (_session, _payload, handlers) => {
      handlers.start?.({ request_id: "r" }); handlers.delta?.("Grounded "); handlers.done?.(result);
    });
    renderAsk();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question?" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(mocks.streamChatTurn).toHaveBeenCalledOnce());
    const [sessionId, payload] = mocks.streamChatTurn.mock.calls[0];
    expect(sessionId).toBe(session.id);
    expect(payload.query).toBe("Question?");
    expect(payload.client_turn_id).toMatch(/^[0-9a-f-]{36}$/i);
    expect(payload.document_ids).toBeNull();
    expect(mocks.chatMessages.mock.calls.length).toBeGreaterThan(0);
  });

  it("selects every indexed document by default and excludes non-indexed documents", async () => {
    mocks.documents.mockResolvedValue([indexedA, indexedB, notIndexed]);
    renderAsk();
    expect(await screen.findByRole("checkbox", { name: "Include law-a.pdf" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Include law-b.pdf" })).toBeChecked();
    expect(screen.queryByRole("checkbox", { name: "Include draft.pdf" })).not.toBeInTheDocument();
  });

  it("sends null for all documents and exact document_ids for a subset", async () => {
    mocks.documents.mockResolvedValue([indexedA, indexedB]);
    mocks.streamChatTurn.mockImplementation(async (_session, _payload, handlers) => { handlers.start?.({ request_id: "r" }); handlers.done?.(result); });
    renderAsk();
    const secondDocument = await screen.findByRole("checkbox", { name: "Include law-b.pdf" });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "All documents" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(mocks.streamChatTurn).toHaveBeenCalledTimes(1));
    expect(mocks.streamChatTurn.mock.calls[0][1].document_ids).toBeNull();

    await waitFor(() => expect(screen.getByLabelText("Question")).toHaveValue(""));
    fireEvent.click(secondDocument);
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Subset" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    await waitFor(() => expect(mocks.streamChatTurn).toHaveBeenCalledTimes(2));
    expect(mocks.streamChatTurn.mock.calls[1][1].document_ids).toEqual(["doc-a"]);
  });

  it("disables submission for an empty indexed scope and Select All restores it", async () => {
    mocks.documents.mockResolvedValue([indexedA, indexedB]);
    renderAsk();
    fireEvent.click(await screen.findByRole("checkbox", { name: "Select All" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Question" } });
    expect(screen.getByRole("button", { name: "Submit" })).toBeDisabled();
    expect(screen.getByText("Select at least one source.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select All" }));
    expect(screen.getByRole("checkbox", { name: "Include law-a.pdf" })).toBeChecked();
    expect(screen.getByRole("button", { name: "Submit" })).toBeEnabled();
  });

  it("reloads historical answer, selects its evidence, and opens the immutable snapshot on demand", async () => {
    mocks.chatMessages.mockResolvedValue({ data: [
      { id: "u", session_id: session.id, turn_id: "t", role: "USER", sequence_no: 1, content: "Historic?", delivery_state: "COMMITTED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: null, failure_code: null, failure_detail_safe: null, citations: [] },
      { id: "a", session_id: session.id, turn_id: "t", role: "ASSISTANT", sequence_no: 2, content: "Historic answer [S1]", delivery_state: "COMPLETED", answer_status: "ANSWERABLE", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", created_at: "x", finalized_at: "x", failure_code: null, failure_detail_safe: null, citations: [{ source_id: "S1", chunk_id: "old-chunk", document_id: "old-doc", metadata_json: {}, provenance_json: { page_start: 4 }, evidence_text: "Immutable evidence", availability: "SOURCE_UNAVAILABLE" }] },
    ], next_before_sequence: null });
    renderAsk();
    expect(await screen.findByText("Historic?")).toBeInTheDocument();
    expect(screen.getByText(/Historic answer/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "[S1]" }));
    expect(screen.getByRole("tab", { name: "evidence" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Immutable evidence")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open evidence detail" }));
    const dialog = await screen.findByRole("dialog", { name: "S1" });
    expect(within(dialog).getByText("Immutable evidence")).toBeInTheDocument();
    expect(within(dialog).getByText(/original source is no longer available/i)).toBeInTheDocument();
    expect(mocks.chunk).not.toHaveBeenCalled();
  });

  it("wires Active Scope, Add Scope, and source counts to the correct panel modes", async () => {
    mocks.documents.mockResolvedValue([indexedA]);
    mocks.chatMessages.mockResolvedValue({ data: [{ id: "a", session_id: session.id, turn_id: "t", role: "ASSISTANT", sequence_no: 1, content: "Answer [S1]", delivery_state: "COMPLETED", answer_status: "ANSWERABLE", model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", created_at: "x", finalized_at: "x", failure_code: null, failure_detail_safe: null, citations: [{ source_id: "S1", chunk_id: "c", document_id: "doc-a", metadata_json: {}, provenance_json: {}, evidence_text: "Evidence" }] }], next_before_sequence: null });
    renderAsk();
    expect(await screen.findByText(/Answer/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /Active Scope/ }));
    expect(screen.getByRole("tab", { name: "scope" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "1 source" }));
    expect(screen.getByRole("tab", { name: "evidence" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("button", { name: "Add Scope" }));
    expect(screen.getByRole("tab", { name: "scope" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("snapshot sources")).not.toBeInTheDocument();
  });

  it("preserves AbortController cancellation for persistent streams", async () => {
    mocks.streamChatTurn.mockImplementation((_session, _payload, handlers, signal) => new Promise((_resolve, reject) => {
      handlers.start?.({ request_id: "r" });
      signal.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
    }));
    renderAsk();
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Long query" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    fireEvent.click(await screen.findByRole("button", { name: "Stop generation" }));
    await waitFor(() => expect(mocks.chatMessages.mock.calls.length).toBeGreaterThan(1));
  });

  it("renders interrupted history distinctly and Retry creates a new logical turn id", async () => {
    mocks.chatMessages.mockResolvedValue({ data: [
      { id: "u", session_id: session.id, turn_id: "old-turn", role: "USER", sequence_no: 1, content: "Retry me", delivery_state: "COMMITTED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: null, failure_code: null, failure_detail_safe: null, citations: [] },
      { id: "a", session_id: session.id, turn_id: "old-turn", role: "ASSISTANT", sequence_no: 2, content: "", delivery_state: "FAILED", answer_status: null, model_id: null, prompt_version: null, created_at: "x", finalized_at: "x", failure_code: "ORPHANED_STREAM_TIMEOUT", failure_detail_safe: "Generation was interrupted before completion.", citations: [] },
    ], next_before_sequence: null });
    mocks.streamChatTurn.mockImplementation(async (_session, _payload, handlers) => handlers.error?.({ safe_message: "safe" }));
    renderAsk();
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
    renderAsk();
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
