import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { login } = vi.hoisted(() => ({ login: vi.fn() }));
vi.mock("../api/client", () => ({ api: { login } }));
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("submits credentials through the opaque-cookie login API", async () => {
    const authenticated = vi.fn();
    const user = { id: "user-1", email: "alice@example.com", role: "USER", status: "ACTIVE", must_change_password: false };
    login.mockResolvedValueOnce(user);
    render(<LoginPage onAuthenticated={authenticated} />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: user.email } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "long passphrase" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith(user.email, "long passphrase"));
    expect(authenticated).toHaveBeenCalledWith(user);
  });

  it("shows the same safe login failure surface", async () => {
    login.mockRejectedValueOnce(new Error("Invalid credentials."));
    render(<LoginPage onAuthenticated={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "missing@example.com" } });
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "wrong password" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Invalid credentials.")).toBeInTheDocument();
  });
});
