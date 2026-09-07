import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PublicLegalPage } from "./PublicLegalPage";

function renderPage(kind: "privacy" | "terms") {
  return render(<MemoryRouter><PublicLegalPage kind={kind} /></MemoryRouter>);
}

describe("PublicLegalPage", () => {
  it("accurately describes Google authentication and local-first privacy boundaries", () => {
    renderPage("privacy");
    expect(screen.getByRole("heading", { name: "Privacy Policy" })).toBeInTheDocument();
    expect(screen.getByText(/does not request Gmail, Drive, Calendar, Contacts/i)).toBeInTheDocument();
    expect(screen.getByText(/does not persist Google access tokens, refresh tokens, ID tokens, or OAuth authorization codes/i)).toBeInTheDocument();
    expect(screen.getByText(/remain in local ZKD Compute/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy and support contact" })).toHaveAttribute("href", "mailto:phamnhatnamthsg@gmail.com");
  });

  it("renders concise public terms with privacy and support links", () => {
    renderPage("terms");
    expect(screen.getByRole("heading", { name: "Terms of Service" })).toBeInTheDocument();
    expect(screen.getByText(/not legal, financial, medical, or other professional advice/i)).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Privacy Policy" }).every((link) => link.getAttribute("href") === "/privacy")).toBe(true);
  });
});
