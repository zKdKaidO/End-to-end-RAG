import { beforeEach, describe, expect, it, vi } from "vitest";

const clients = vi.hoisted(() => [] as Array<{ logout: ReturnType<typeof vi.fn> }>);

vi.mock("./client", () => ({
  BrowserComputeClient: class {
    logout = vi.fn();
    constructor() { clients.push(this); }
  },
}));

import { browserComputeClient, clearBrowserComputeClient } from "./shared";

describe("browser Compute session lifecycle", () => {
  beforeEach(() => {
    clearBrowserComputeClient();
    clients.length = 0;
  });

  it("keeps one memory-only client across SPA routes for the same user", () => {
    const first = browserComputeClient("user-a");
    const second = browserComputeClient("user-a");

    expect(second).toBe(first);
    expect(clients).toHaveLength(1);
  });

  it("clears the client before another user or logout can reuse it", () => {
    const first = browserComputeClient("user-a") as unknown as { logout: ReturnType<typeof vi.fn> };
    const second = browserComputeClient("user-b");

    expect(first.logout).toHaveBeenCalledOnce();
    expect(second).not.toBe(first);
    clearBrowserComputeClient();
    expect((second as unknown as { logout: ReturnType<typeof vi.fn> }).logout).toHaveBeenCalledOnce();
  });
});
