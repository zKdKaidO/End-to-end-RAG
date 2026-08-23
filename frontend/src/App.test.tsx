import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api/client", () => ({ api: {
  me: vi.fn().mockResolvedValue({ id: "user-1", email: "admin@example.com", role: "ADMIN", status: "ACTIVE", must_change_password: false }),
  logout: vi.fn().mockResolvedValue(undefined),
  health: vi.fn().mockResolvedValue({ status: "ok", service: "api" }),
  status: vi.fn().mockResolvedValue({ api: "available", provider: "available", model_id: "qwen3.5:9b" }),
  documents: vi.fn().mockResolvedValue([]),
  evaluationSummary: vi.fn(),
  evaluationCases: vi.fn().mockResolvedValue([]),
  evaluationComparison: vi.fn(),
} }));
import { App } from "./App";
import { api } from "./api/client";

describe("application routes", () => {
  beforeEach(() => {
    vi.mocked(api.me).mockResolvedValue({ id: "user-1", email: "admin@example.com", role: "ADMIN", status: "ACTIVE", must_change_password: false });
    vi.mocked(api.status).mockResolvedValue({ api: "available", provider: "available", model_id: "qwen3.5:9b" });
  });

  it("renders the product shell and Ask route", async () => {
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Ask the corpus" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("qwen3.5:9b")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Debug" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Evaluation" })).toBeInTheDocument();
  });

  it("renders the Documents route without changing backend semantics", async () => {
    render(<MemoryRouter initialEntries={["/documents"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Documents" })).toBeInTheDocument();
    expect(await screen.findByText(/No documents are stored/)).toBeInTheDocument();
  });

  it("keeps internal navigation unavailable to a USER", async () => {
    vi.mocked(api.me).mockResolvedValueOnce({ id: "user-2", email: "user@example.com", role: "USER", status: "ACTIVE", must_change_password: false });
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Ask the corpus" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Debug" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Evaluation" })).not.toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });
});
