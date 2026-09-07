import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock("../api/client", () => ({ api: { login } }));
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("submits credentials through the opaque-cookie login API", async () => {
    const authenticated = vi.fn();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE", must_change_password: false };
    login.mockResolvedValueOnce(user);
    render(<LoginPage onAuthenticated={authenticated} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith(user.email, "long passphrase"));
    expect(authenticated).toHaveBeenCalledWith(user);
  });

  it("shows the same safe login failure surface", async () => {
    login.mockRejectedValueOnce(new Error("Invalid credentials."));
    render(<LoginPage onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email address"), { target: { value: "missing@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Invalid credentials.")).toBeInTheDocument();
  });

  it("navigates to the same-origin Google authorization start route", () => {
    const assign = vi.fn();
    render(<LoginPage onAuthenticated={vi.fn()} onGoogleAuthorizationStart={assign} />);
    const googleButton = screen.getByRole("button", { name: "Continue with Google" });
    expect(googleButton).toHaveAttribute("type", "button");
    const passwordForm = screen.getByRole("button", { name: "Sign in" }).closest("form");
    expect(passwordForm).not.toContainElement(googleButton);
    fireEvent.click(googleButton);
    expect(assign).toHaveBeenCalledWith("/api/v1/auth/google/start");
    expect(assign).toHaveBeenCalledTimes(1);
    expect(login).not.toHaveBeenCalled();
  });

  it("exposes public privacy and terms links before sign-in", () => {
    render(<LoginPage onAuthenticated={vi.fn()} />);
    expect(screen.getAllByRole("link", { name: "Privacy Policy" }).every((link) => link.getAttribute("href") === "/privacy")).toBe(true);
    expect(screen.getAllByRole("link", { name: "Terms of Service" }).every((link) => link.getAttribute("href") === "/terms")).toBe(true);
  });
});
