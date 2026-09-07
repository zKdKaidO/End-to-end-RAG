import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const { me } = vi.hoisted(() => ({ me: vi.fn(() => new Promise(() => undefined)) }));
vi.mock("./api/client", () => ({ api: { me } }));

import { App } from "./App";

describe("public legal routes", () => {
  it.each([
    ["/privacy", "Privacy Policy"],
    ["/terms", "Terms of Service"],
  ])("renders %s before authentication resolves", (path, heading) => {
    render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: heading })).toBeInTheDocument();
  });
});
