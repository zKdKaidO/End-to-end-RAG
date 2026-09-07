import { BrowserComputeClient } from "./client";

/*
 * A local session is deliberately memory-only, but it must survive SPA route
 * changes. Recreating the client for /ask and /documents forced an otherwise
 * healthy local Compute through a new control-plane grant on every navigation.
 * Bind the singleton to the signed-in product user and discard it at logout or
 * before another user can use this browser tab.
 */
let client: BrowserComputeClient | null = null;
let ownerUserId: string | null = null;

export function browserComputeClient(userId: string): BrowserComputeClient {
  if (client && ownerUserId === userId) return client;

  client?.logout();
  client = new BrowserComputeClient();
  ownerUserId = userId;
  return client;
}

export function clearBrowserComputeClient(): void {
  client?.logout();
  client = null;
  ownerUserId = null;
}
