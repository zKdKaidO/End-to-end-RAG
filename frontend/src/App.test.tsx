import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./api/client", () => ({ api: {
  me: vi.fn().mockResolvedValue({ id: "user-1", email: "admin@example.com", role: "ADMIN", status: "ACTIVE", must_change_password: false }),
  logout: vi.fn().mockResolvedValue(undefined),
  health: vi.fn().mockResolvedValue({ status: "ok", service: "api" }),
  status: vi.fn().mockResolvedValue({ api: "available", provider: "available", model_id: "qwen3.5:9b" }),
  documents: vi.fn().mockResolvedValue([]),
  chatSessions: vi.fn().mockResolvedValue({ data: [], next_cursor: null }),
  chatMessages: vi.fn().mockResolvedValue({ data: [], next_before_sequence: null }),
  createChatSession: vi.fn(),
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
    vi.mocked(api.logout).mockResolvedValue(undefined);
  });

  it("keeps the authenticated workspace behind the auth loading state", () => {
    vi.mocked(api.me).mockImplementationOnce(() => new Promise(() => undefined));
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(screen.getByText("Loading secure workspace…")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "New Inquiry" })).not.toBeInTheDocument();
  });

  it("routes an unauthenticated Ask request to sign in", async () => {
    vi.mocked(api.me).mockRejectedValueOnce(new Error("Unauthorized"));
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("renders the Ask-specific shell without the global sidebar", async () => {
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "New Inquiry" })).toBeInTheDocument();
    expect(screen.getByRole("complementary", { name: "Product navigation" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Product areas" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary navigation" })).not.toBeInTheDocument();
    expect(screen.getAllByText("Lexicon AI").length).toBeGreaterThan(0);
  });

  it("keeps sign out accessible from the Ask-specific shell", async () => {
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(api.logout).toHaveBeenCalledOnce());
  });

  it("renders the Documents route without changing backend semantics", async () => {
    render(<MemoryRouter initialEntries={["/documents"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Documents" })).toBeInTheDocument();
    expect(await screen.findByText(/No documents are stored/)).toBeInTheDocument();
  });

  it.each(["/ask/", "/documents/"])("uses the product shell for trailing-slash route %s", async (path) => {
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
    expect(await screen.findByRole("complementary", { name: "Product navigation" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Primary navigation" })).not.toBeInTheDocument();
  });

  it("keeps internal navigation unavailable to a USER", async () => {
    vi.mocked(api.me).mockResolvedValueOnce({ id: "user-2", email: "user@example.com", role: "USER", status: "ACTIVE", must_change_password: false });
    render(<MemoryRouter initialEntries={["/ask"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "New Inquiry" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Debug" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Evaluation" })).not.toBeInTheDocument();
    expect(screen.getByText("user@example.com")).toBeInTheDocument();
  });

  it("retains the legacy shell on a directly loaded authorized internal route", async () => {
    render(<MemoryRouter initialEntries={["/debug"]}><App /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Pipeline Debug" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    expect(screen.queryByRole("complementary", { name: "Product navigation" })).not.toBeInTheDocument();
  });
});
