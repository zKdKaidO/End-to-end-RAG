import { describe, expect, it, vi } from "vitest";
import { PlatformComputeApi } from "./platform";

describe("PlatformComputeApi", () => {
  it("uses the exact existing compute-control route, origin, and grant body", async () => {
    const request = vi.fn().mockResolvedValue(new Response(JSON.stringify({ local_access_grant: "g", expires_at: 2, device_id: "d", endpoint_generation: "e" }), { status: 200 }));
    const api = new PlatformComputeApi(request);
    await api.requestLocalSessionGrant("device id", "nonce-1");
    const [path, init] = request.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/compute/devices/device%20id/local-session-grants");
    expect(init).toMatchObject({ method: "POST", credentials: "include", body: '{"browser_nonce":"nonce-1"}' });
    expect(init.headers).toMatchObject({ Origin: window.location.origin, "Content-Type": "application/json" });
  });

  it("reads the actual device and manifest envelopes", async () => {
    const request = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ devices: [{ device_id: "d", state: "READY", protocol_version: "zkd-compute-v1", runtime_version: "1", endpoint_generation: "g", endpoint_port: 1234, capabilities: {} }] }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ manifests: [{ document_id: "x", device_id: "d", queryable: false }] }), { status: 200 }));
    const api = new PlatformComputeApi(request);
    await expect(api.listDevices()).resolves.toHaveLength(1);
    await expect(api.listLocalManifests()).resolves.toHaveLength(1);
  });

  it("sends only the allowlisted local-fetch diagnostic envelope", async () => {
    const request = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    const api = new PlatformComputeApi(request);
    await api.reportLocalFetchDiagnostic({
      operation: "answers", phase: "actual-fetch", exception_name: "TypeError",
      exception_message: "LOCAL_FETCH_NETWORK_REJECTED", host_type: "loopback",
      method: "POST", endpoint_path: "/v1/answers", local_session_present: true,
      browser_nonce_present: false, abort_signal_fired: false,
      request_timeout_configured: false, frontend_state: "AUTHENTICATED_REQUEST",
      classification: "BROWSER_NETWORK_REJECTED",
    });
    const [path, init] = request.mock.calls[0] as [string, RequestInit];
    expect(path).toBe("/api/v1/diagnostics/local-fetch");
    expect(init).toMatchObject({ method: "POST", credentials: "include" });
    expect(init.headers).toMatchObject({ Origin: window.location.origin, "Content-Type": "application/json" });
    expect(init.body).toBe('{"operation":"answers","phase":"actual-fetch","exception_name":"TypeError","exception_message":"LOCAL_FETCH_NETWORK_REJECTED","host_type":"loopback","method":"POST","endpoint_path":"/v1/answers","local_session_present":true,"browser_nonce_present":false,"abort_signal_fired":false,"request_timeout_configured":false,"frontend_state":"AUTHENTICATED_REQUEST","classification":"BROWSER_NETWORK_REJECTED"}');
  });
});
