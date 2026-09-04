import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const compute = vi.hoisted(() => ({ discover: vi.fn(), connect: vi.fn(), listDocuments: vi.fn(), answer: vi.fn(), query: vi.fn() }));
const platform = vi.hoisted(() => ({ documents: vi.fn(), chatSessions: vi.fn(), createChatSession: vi.fn(), chatMessages: vi.fn(), renameChatSession: vi.fn(), deleteChatSession: vi.fn(), chunk: vi.fn(), streamChatTurn: vi.fn() }));

vi.mock("../compute", () => ({ BrowserComputeClient: class { constructor() { return compute; } } }));
vi.mock("../api/client", () => ({ api: platform, streamChatTurn: platform.streamChatTurn }));

import { AskPage } from "./AskPage";

const user = { id: "user-1", email: "user@example.com", role: "USER" as const, status: "ACTIVE" as const, must_change_password: false };
const device = { deviceId: "11111111-1111-1111-1111-111111111111" };
const localA = { document_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", original_filename: "law-a.pdf", byte_size: 10, preparation_state: "INDEX_READY", index_state: "INDEX_READY", last_error_code: null, created_at: 1, updated_at: 1, page_count: 1, chunk_count: 3 };
const localB = { ...localA, document_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb", original_filename: "law-b.pdf", page_count: 2, chunk_count: 4 };
const answer = {
  request_id: "local-answer", provider: "LOCAL" as const, provider_type: "LOCAL" as const, provider_config_id: null, model_id: "qwen3.5:9b",
  result: { request_id: "local-answer", status: "COMPLETED" as const, answer_text: "Grounded [S1]", citations: [{ source_id: "S1", chunk_id: "chunk-a", document_id: localA.document_id, metadata_json: { title: "safe" }, provenance_json: { document_id: localA.document_id, page_start: 1 } }], invalid_citations: [], citation_validation: "PASS" as const, model_id: "qwen3.5:9b", prompt_version: "legal-rag-v2", finish_reason: "stop", usage: null, answerability_status: "ANSWERABLE" as const, answerability_validation: "PASS" }, hierarchy: {}, timings: {}, routing: { policy: "LOCAL_ONLY" as const, selected_provider_type: "LOCAL" as const, fallback_occurred: false, privacy_boundary: "LOCAL_DEVICE" as const },
};

function renderAsk() { return render(<MemoryRouter initialEntries={["/ask"]}><AskPage user={user} onLogout={vi.fn()} /></MemoryRouter>); }

beforeEach(() => {
  Object.values(compute).forEach((mock) => mock.mockReset());
  Object.values(platform).forEach((mock) => mock.mockReset());
  compute.connect.mockResolvedValue(device);
  compute.listDocuments.mockResolvedValue([localA, localB]);
  compute.answer.mockResolvedValue(answer);
});

describe("local-first Ask workspace", () => {
  it("loads the selected device's queryable local source catalog and selects it all", async () => {
    renderAsk();
    expect(await screen.findByRole("checkbox", { name: "Include law-a.pdf" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Include law-b.pdf" })).toBeChecked();
    expect(compute.connect).toHaveBeenCalledWith("answer");
    expect(compute.listDocuments).toHaveBeenCalledOnce();
  });

  it("submits exactly one local answer without a preliminary query and preserves all/subset scope", async () => {
    renderAsk();
    await screen.findByRole("checkbox", { name: "Include law-a.pdf" });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "All sources" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(compute.answer).toHaveBeenCalledTimes(1));
    expect(compute.answer).toHaveBeenLastCalledWith({ query_text: "All sources", document_ids: null });
    expect(compute.query).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("checkbox", { name: "Include law-b.pdf" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Only A" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    await waitFor(() => expect(compute.answer).toHaveBeenCalledTimes(2));
    expect(compute.answer).toHaveBeenLastCalledWith({ query_text: "Only A", document_ids: [localA.document_id] });
  });

  it("prevents a zero-source selection from reaching local Compute", async () => {
    renderAsk();
    await screen.findByRole("checkbox", { name: "Select All" });
    fireEvent.click(screen.getByRole("checkbox", { name: "Select All" }));
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Blocked" } });
    expect(screen.getByRole("button", { name: "Send message" })).toBeDisabled();
    expect(screen.getByText("Select a source")).toBeInTheDocument();
    expect(compute.answer).not.toHaveBeenCalled();
  });

  it("renders a pending assistant state and then the one synchronous local answer with intact citations", async () => {
    let resolveAnswer: (value: typeof answer) => void = () => undefined;
    compute.answer.mockReturnValueOnce(new Promise<typeof answer>((resolve) => { resolveAnswer = resolve; }));
    renderAsk();
    await screen.findByRole("checkbox", { name: "Include law-a.pdf" });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "PRIVATE_LOCAL_QUERY_SENTINEL" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Thinking…")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Stop generation" })).not.toBeInTheDocument();
    resolveAnswer(answer);
    expect(await screen.findByText(/Grounded/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "[S1]" })).toBeInTheDocument();
    expect(JSON.stringify(Object.values(platform).flatMap((mock) => mock.mock.calls))).not.toContain("PRIVATE_LOCAL_QUERY_SENTINEL");
    expect(platform.documents).not.toHaveBeenCalled();
    expect(platform.chatSessions).not.toHaveBeenCalled();
    expect(platform.createChatSession).not.toHaveBeenCalled();
    expect(platform.chatMessages).not.toHaveBeenCalled();
    expect(platform.renameChatSession).not.toHaveBeenCalled();
    expect(platform.deleteChatSession).not.toHaveBeenCalled();
    expect(platform.chunk).not.toHaveBeenCalled();
    expect(platform.streamChatTurn).not.toHaveBeenCalled();
  });

  it("retries only after an explicit local failure and resets browser-memory conversation with New", async () => {
    compute.answer.mockRejectedValueOnce(new Error("local unavailable")).mockResolvedValueOnce(answer);
    renderAsk();
    await screen.findByRole("checkbox", { name: "Include law-a.pdf" });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Retry local" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(compute.answer).toHaveBeenCalledTimes(2));
    expect(compute.answer.mock.calls[1][0]).toEqual({ query_text: "Retry local", document_ids: null });
    expect(platform.chatMessages).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTitle("New inquiry"));
    expect(screen.queryByText("Retry local")).not.toBeInTheDocument();
    expect(platform.createChatSession).not.toHaveBeenCalled();
  });

  it("surfaces a selected-device error without source or answer fallback", async () => {
    compute.connect.mockRejectedValueOnce(Object.assign(new Error("Select a device"), { code: "DEVICE_SELECTION_REQUIRED" }));
    renderAsk();
    expect(await screen.findByText("Select a device")).toBeInTheDocument();
    expect(compute.listDocuments).not.toHaveBeenCalled();
    expect(compute.answer).not.toHaveBeenCalled();
    expect(platform.documents).not.toHaveBeenCalled();
  });

  it("does not restore a transcript after a fresh page mount", async () => {
    const first = renderAsk();
    await screen.findByRole("checkbox", { name: "Include law-a.pdf" });
    fireEvent.change(screen.getByLabelText("Question"), { target: { value: "Ephemeral" } });
    fireEvent.click(screen.getByRole("button", { name: "Send message" }));
    expect(await screen.findByText("Ephemeral")).toBeInTheDocument();
    first.unmount();
    renderAsk();
    await screen.findByRole("checkbox", { name: "Include law-a.pdf" });
    expect(screen.queryByText("Ephemeral")).not.toBeInTheDocument();
    expect(platform.chatSessions).not.toHaveBeenCalled();
  });
});
