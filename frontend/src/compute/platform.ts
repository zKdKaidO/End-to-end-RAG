import { apiUrl } from "../api/client";
import { BrowserComputeError } from "./errors";
import type { ComputeDevice, LocalManifest, PlatformGrant } from "./types";

export type PlatformFetch = typeof fetch;

async function parseResponse<T>(response: Response, fallbackCode: "PLATFORM_UNAVAILABLE" | "INVALID_LOCAL_RESPONSE"): Promise<T> {
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = undefined; }
  if (!response.ok) {
    const detail = (payload as { detail?: { error_code?: string; message?: string } | string } | undefined)?.detail;
    const message = typeof detail === "string" ? detail : detail?.message;
    throw new BrowserComputeError(response.status === 401 || response.status === 403 ? "AUTH_FAILED" : fallbackCode, message ?? `Request failed (${response.status})`, response.status, response.headers.get("X-Request-ID") ?? undefined);
  }
  if (payload === undefined) throw new BrowserComputeError(fallbackCode, "Expected a JSON response.", response.status);
  return payload as T;
}

/** Authenticated control-plane calls only; no document/RAG content is sent here. */
export class PlatformComputeApi {
  constructor(private readonly request: PlatformFetch = fetch) {}

  async listDevices(): Promise<ComputeDevice[]> {
    const response = await this.request(apiUrl("/api/v1/compute/devices"), { credentials: "include" });
    return (await parseResponse<{ devices: ComputeDevice[] }>(response, "PLATFORM_UNAVAILABLE")).devices;
  }

  async listLocalManifests(): Promise<LocalManifest[]> {
    const response = await this.request(apiUrl("/api/v1/compute/local-manifests"), { credentials: "include" });
    return (await parseResponse<{ manifests: LocalManifest[] }>(response, "PLATFORM_UNAVAILABLE")).manifests;
  }

  async requestLocalSessionGrant(deviceId: string, browserNonce: string): Promise<PlatformGrant> {
    const response = await this.request(apiUrl(`/api/v1/compute/devices/${encodeURIComponent(deviceId)}/local-session-grants`), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Origin: window.location.origin },
      body: JSON.stringify({ browser_nonce: browserNonce }),
    });
    return parseResponse<PlatformGrant>(response, "PLATFORM_UNAVAILABLE");
  }
}
