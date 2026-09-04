import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { compute, platformApi } = vi.hoisted(() => ({
  compute: {
    discover: vi.fn(),
    connect: vi.fn(),
    listDocuments: vi.fn(),
    uploadSource: vi.fn(),
    prepareDocument: vi.fn(),
    indexDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
  platformApi: {
    documents: vi.fn(),
    document: vi.fn(),
    upload: vi.fn(),
    indexDocument: vi.fn(),
    deleteDocument: vi.fn(),
  },
}));

vi.mock("../compute", () => ({ BrowserComputeClient: class { constructor() { return compute; } } }));
vi.mock("../api/client", () => ({ api: platformApi }));

import { DocumentsPage } from "./DocumentsPage";

const ready = {
  document_id: "11111111-1111-1111-1111-111111111111",
  original_filename: "sample_legal.pdf",
  byte_size: 2048,
  preparation_state: "INDEX_READY",
  index_state: "INDEX_READY",
  last_error_code: null,
  created_at: 1_787_529_600,
  updated_at: 1_787_529_600,
  page_count: 4,
  chunk_count: 8,
};

const prepared = {
  ...ready,
  document_id: "22222222-2222-2222-2222-222222222222",
  original_filename: "prepared.pdf",
  preparation_state: "PREPARED_NOT_INDEXED",
  index_state: "NOT_INDEXED",
  chunk_count: 3,
};

const failed = {
  ...ready,
  document_id: "33333333-3333-3333-3333-333333333333",
  original_filename: "failed.pdf",
  preparation_state: "FAILED",
  index_state: "NOT_READY",
  last_error_code: "PREPARE_FAILED",
  chunk_count: 0,
};

function renderDocuments() {
  return render(<MemoryRouter initialEntries={["/documents"]}><DocumentsPage /></MemoryRouter>);
}

function expectNoPlatformContentCalls() {
  expect(platformApi.documents).not.toHaveBeenCalled();
  expect(platformApi.document).not.toHaveBeenCalled();
  expect(platformApi.upload).not.toHaveBeenCalled();
  expect(platformApi.indexDocument).not.toHaveBeenCalled();
  expect(platformApi.deleteDocument).not.toHaveBeenCalled();
}

describe("DocumentsPage local-first behavior", () => {
  beforeEach(() => {
    Object.values(compute).forEach((method) => method.mockReset());
    Object.values(platformApi).forEach((method) => method.mockReset());
    compute.discover.mockResolvedValue([]);
    compute.connect.mockResolvedValue({});
    compute.listDocuments.mockResolvedValue([ready, prepared]);
    compute.uploadSource.mockResolvedValue({});
    compute.prepareDocument.mockResolvedValue({});
    compute.indexDocument.mockResolvedValue({});
    compute.deleteDocument.mockResolvedValue({});
    vi.stubGlobal("crypto", { ...globalThis.crypto, randomUUID: vi.fn(() => "44444444-4444-4444-4444-444444444444") });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("loads the selected device's local catalog and derives metrics, search, and filter from it", async () => {
    renderDocuments();
    await waitFor(() => expect(screen.getByText("sample_legal.pdf")).toBeInTheDocument());
    expect(compute.discover).toHaveBeenCalledTimes(1);
    expect(compute.connect).toHaveBeenCalledWith("documents");
    expect(compute.listDocuments).toHaveBeenCalledTimes(1);
    expect(screen.getByText("11")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search documents"), { target: { value: "prepared" } });
    expect(screen.queryByText("sample_legal.pdf")).not.toBeInTheDocument();
    expect(screen.getByText("prepared.pdf")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Filter documents"), { target: { value: "READY" } });
    expect(screen.getByText("No documents match this search or filter.")).toBeInTheDocument();
    expectNoPlatformContentCalls();
  });

  it("uploads PDF bytes only through Compute, then prepares the generated local document identity", async () => {
    renderDocuments();
    await screen.findByText("sample_legal.pdf");
    const file = new File([new Uint8Array([37, 80, 68, 70])], "local.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("Upload PDF"), { target: { files: [file] } });
    await waitFor(() => expect(compute.uploadSource).toHaveBeenCalledWith("44444444-4444-4444-4444-444444444444", file, "local.pdf"));
    expect(compute.prepareDocument).toHaveBeenCalledWith("44444444-4444-4444-4444-444444444444");
    expectNoPlatformContentCalls();
  });

  it("uses local index and delete actions, with failed documents retained and only deletable", async () => {
    compute.listDocuments.mockResolvedValue([prepared, failed]);
    renderDocuments();
    await screen.findByText("prepared.pdf");
    fireEvent.click(screen.getByRole("button", { name: "Index document prepared.pdf" }));
    await waitFor(() => expect(compute.indexDocument).toHaveBeenCalledWith(prepared.document_id));
    expect(screen.queryByRole("button", { name: "Index document failed.pdf" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete failed.pdf" }));
    expect(screen.getByRole("alertdialog", { name: /Remove document/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(compute.deleteDocument).toHaveBeenCalledWith(failed.document_id));
    expectNoPlatformContentCalls();
  });

  it("opens a local metadata-only drawer without requesting platform document content", async () => {
    renderDocuments();
    fireEvent.click(await screen.findByRole("button", { name: "Inspect sample_legal.pdf" }));
    expect(await screen.findByRole("dialog", { name: "sample_legal.pdf" })).toBeInTheDocument();
    expect(screen.getByText("Local document metadata does not expose chunk content.")).toBeInTheDocument();
    expectNoPlatformContentCalls();
  });

  it("refreshes through discovery and the local catalog only", async () => {
    renderDocuments();
    await screen.findByText("sample_legal.pdf");
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(compute.listDocuments).toHaveBeenCalledTimes(2));
    expect(compute.discover).toHaveBeenCalledTimes(2);
    expectNoPlatformContentCalls();
  });

  it("polls active local lifecycle work and stops after the next idle catalog refresh", async () => {
    vi.useFakeTimers();
    const active = { ...ready, preparation_state: "PROCESSING", index_state: "NOT_READY" };
    compute.listDocuments.mockResolvedValueOnce([active]).mockResolvedValueOnce([ready]);
    renderDocuments();
    await act(async () => { await Promise.resolve(); await Promise.resolve(); });
    expect(compute.listDocuments).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(4_000); });
    expect(compute.listDocuments).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(12_000); });
    expect(compute.listDocuments).toHaveBeenCalledTimes(2);
    expectNoPlatformContentCalls();
  });

  it("disables local mutations when Compute becomes unavailable without a platform fallback", async () => {
    renderDocuments();
    await screen.findByText("sample_legal.pdf");
    compute.connect.mockRejectedValueOnce(new Error("DEVICE_OFFLINE"));
    fireEvent.click(screen.getByRole("button", { name: /Refresh/ }));
    await waitFor(() => expect(screen.getByText(/Document action failed/i)).toBeInTheDocument());
    expect(screen.getByLabelText("Upload PDF")).toBeDisabled();
    expect(screen.getByRole("button", { name: "Re-index sample_legal.pdf" })).toBeDisabled();
    expect(compute.indexDocument).not.toHaveBeenCalled();
    expect(compute.deleteDocument).not.toHaveBeenCalled();
    expectNoPlatformContentCalls();
  });

  it("surfaces the multiple-device selection requirement without choosing a device or falling back", async () => {
    compute.connect.mockRejectedValueOnce(new Error("DEVICE_SELECTION_REQUIRED"));
    renderDocuments();
    await waitFor(() => expect(screen.getByText(/Document action failed/i)).toBeInTheDocument());
    expect(compute.listDocuments).not.toHaveBeenCalled();
    expectNoPlatformContentCalls();
  });
});
