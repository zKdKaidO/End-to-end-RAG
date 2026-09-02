import { describe, expect, it, vi } from "vitest";
import { BrowserComputeClient } from "./client";
import { BrowserComputeError } from "./errors";
import type { ComputeDevice, PlatformGrant } from "./types";

const device: ComputeDevice = {
  device_id: "11111111-1111-1111-1111-111111111111", state: "READY", protocol_version: "zkd-compute-v1", runtime_version: "1.0.0",
  endpoint_generation: "endpoint-a", endpoint_port: 48123,
  capabilities: { documents: "READY", jobs: "READY", retrieval: "READY", answer: "READY" },
};

function response(payload: unknown, status = 200): Response { return new Response(JSON.stringify(payload), { status, headers: { "Content-Type": "application/json" } }); }

function fixture(devices: ComputeDevice[] = [device]) {
  const platform = {
    listDevices: vi.fn().mockResolvedValue(devices),
    listLocalManifests: vi.fn().mockResolvedValue([]),
    requestLocalSessionGrant: vi.fn().mockResolvedValue({ local_access_grant: "grant", expires_at: 1800000000, device_id: device.device_id, endpoint_generation: "endpoint-a" } satisfies PlatformGrant),
  };
  const localFetch = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/v1/sessions")) return response({ local_session_id: "session-a", session_key: "secret-a", expires_at: 1800000000, protocol_version: "zkd-compute-v1", endpoint_generation: "endpoint-a", allowed_operations: ["documents", "jobs", "retrieval", "answer"] });
    return response({ request_id: "r1", route: url, method: init?.method });
  });
  return { platform, localFetch };
}

describe("BrowserComputeClient", () => {
  it("uses the control plane only to bootstrap and then signs a local request", async () => {
    const { platform, localFetch } = fixture();
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000, nonceFactory: () => "nonce-1" });
    await client.discover();
    await client.query({ query_text: "doanh nghiệp" });
    expect(platform.requestLocalSessionGrant).toHaveBeenCalledTimes(1);
    expect(localFetch).toHaveBeenCalledTimes(2);
    const [, request] = localFetch.mock.calls[1] as [string, RequestInit];
    expect(request.headers).toMatchObject({ Origin: window.location.origin, "X-ZKD-Local-Session": "session-a", "X-ZKD-Timestamp": "1700000000", "X-ZKD-Nonce": "nonce-1", "X-ZKD-Protocol-Version": "zkd-compute-v1" });
    expect(request.body).toBeInstanceOf(ArrayBuffer);
    expect(client.status().session).toEqual(expect.objectContaining({ deviceId: device.device_id, endpointGeneration: "endpoint-a" }));
    expect(JSON.stringify(client.status())).not.toContain("secret-a");
  });

  it("does not silently choose between multiple usable devices", async () => {
    const second = { ...device, device_id: "22222222-2222-2222-2222-222222222222", endpoint_port: 48124 };
    const { platform, localFetch } = fixture([device, second]);
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch });
    await client.discover();
    await expect(client.query({ query_text: "x" })).rejects.toMatchObject({ code: "DEVICE_SELECTION_REQUIRED" });
  });

  it("invalidates a local session after endpoint generation changes", async () => {
    const { platform, localFetch } = fixture();
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    await client.query({ query_text: "x" });
    platform.listDevices.mockResolvedValue([{ ...device, endpoint_generation: "endpoint-b" }]);
    await client.discover();
    expect(client.status().session).toBeNull();
  });

  it("fails closed on a local session-expiry error", async () => {
    const { platform, localFetch } = fixture();
    localFetch.mockImplementation(async (input: RequestInfo | URL) => String(input).endsWith("/v1/sessions")
      ? response({ local_session_id: "session-a", session_key: "secret-a", expires_at: 1800000000, protocol_version: "zkd-compute-v1", endpoint_generation: "endpoint-a", allowed_operations: ["retrieval"] })
      : response({ request_id: "r", error: { code: "SESSION_EXPIRED", message: "expired" } }, 401));
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    await expect(client.query({ query_text: "x" })).rejects.toBeInstanceOf(BrowserComputeError);
    expect(client.status().session).toBeNull();
  });

  it("deduplicates concurrent bootstrap and continues locally when platform is unavailable", async () => {
    const { platform, localFetch } = fixture();
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    await Promise.all([client.runtime(), client.capabilities()]);
    expect(platform.requestLocalSessionGrant).toHaveBeenCalledTimes(1);
    platform.listDevices.mockRejectedValue(new Error("outage"));
    await expect(client.runtime()).resolves.toMatchObject({ method: "GET" });
    expect(platform.listDevices).toHaveBeenCalledTimes(1);
  });

  it("does not share session material across a new client instance", async () => {
    const { platform, localFetch } = fixture();
    const first = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    await first.runtime();
    const second = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    expect(second.status().session).toBeNull();
    first.logout();
    expect(first.status()).toEqual({ selectedDeviceId: null, session: null });
  });

  it("rejects a permitted session operation mismatch before contacting local compute", async () => {
    const { platform, localFetch } = fixture();
    localFetch.mockImplementation(async (input: RequestInfo | URL) => String(input).endsWith("/v1/sessions")
      ? response({ local_session_id: "session-a", session_key: "secret-a", expires_at: 1800000000, protocol_version: "zkd-compute-v1", endpoint_generation: "endpoint-a", allowed_operations: ["retrieval"] })
      : response({}));
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000 });
    await client.query({ query_text: "x" });
    await expect(client.answer({ query_text: "x" })).rejects.toMatchObject({ code: "OPERATION_NOT_ALLOWED" });
    expect(localFetch).toHaveBeenCalledTimes(2);
  });

  it("uses fresh authenticated nonces and sends upload bytes without a content transformation", async () => {
    const { platform, localFetch } = fixture();
    let counter = 0;
    const client = new BrowserComputeClient({ platform: platform as never, localFetch: localFetch as typeof fetch, clock: () => 1700000000, nonceFactory: () => `nonce-${++counter}` });
    await client.runtime();
    await client.uploadSource("22222222-2222-2222-2222-222222222222", new Uint8Array([0x25, 0x50, 0x44, 0x46]), "source.pdf");
    const runtimeRequest = localFetch.mock.calls[1][1] as RequestInit;
    const uploadRequest = localFetch.mock.calls[2][1] as RequestInit;
    expect((runtimeRequest.headers as Record<string, string>)["X-ZKD-Nonce"]).not.toBe((uploadRequest.headers as Record<string, string>)["X-ZKD-Nonce"]);
    expect(Array.from(new Uint8Array(uploadRequest.body as ArrayBuffer))).toEqual([0x25, 0x50, 0x44, 0x46]);
  });
});
