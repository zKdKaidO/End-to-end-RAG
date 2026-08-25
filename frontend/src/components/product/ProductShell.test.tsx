import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProductShell } from "./ProductShell";

const user = { id: "u", email: "user@example.com", role: "USER" as const, status: "ACTIVE" as const, must_change_password: false };

function renderShell() {
  return render(<MemoryRouter initialEntries={["/ask"]}><ProductShell sidebar={{ user, onLogout: vi.fn() }}><div>Content</div></ProductShell></MemoryRouter>);
}

describe("ProductShell", () => {
  afterEach(() => vi.useRealTimers());
  it("starts expanded, collapses after pointer leave, and expands for hover or focus", () => {
    vi.useFakeTimers();
    renderShell();
    const navigation = screen.getByRole("complementary", { name: "Product navigation" });
    expect(navigation).toHaveAttribute("data-expanded", "true");
    fireEvent.mouseLeave(navigation.parentElement!);
    act(() => vi.advanceTimersByTime(300));
    expect(navigation).toHaveAttribute("data-expanded", "false");
    fireEvent.mouseEnter(navigation.parentElement!);
    expect(navigation).toHaveAttribute("data-expanded", "true");
    fireEvent.mouseLeave(navigation.parentElement!);
    act(() => vi.advanceTimersByTime(300));
    fireEvent.focus(screen.getByRole("link", { name: "Search" }));
    expect(navigation).toHaveAttribute("data-expanded", "true");
  });

  it("opens the narrow navigation drawer and closes it with Escape", () => {
    renderShell();
    const trigger = screen.getByRole("button", { name: "Open navigation" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getAllByRole("complementary", { name: "Product navigation" })).toHaveLength(2);
    fireEvent.keyDown(window.document, { key: "Escape" });
    expect(screen.getAllByRole("complementary", { name: "Product navigation" })).toHaveLength(1);
    expect(trigger).toHaveFocus();
  });
});
