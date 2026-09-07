import { apiUrl } from "../api/client";
import { BrowserComputeError } from "./errors";
import type { ComputeDevice, LocalManifest, PlatformGrant } from "./types";

export type PlatformFetch = typeof fetch;

/**
 * Deliberately metadata-only telemetry for a browser request that never
 * reached localhost. All fields are closed enums or booleans; no request
 * payload, grant, nonce, session, or native exception text is accepted.
 */
export interface LocalFetchDiagnostic {
  operation: "answers";
  phase: "actual-fetch" | "abort";
  exception_name: "TypeError" | "AbortError" | "NetworkError" | "NotAllowedError" | "UnknownError";
  exception_message: "LOCAL_FETCH_ABORTED" | "LOCAL_FETCH_BODY_OR_HEADER_REJECTED" | "LOCAL_FETCH_NETWORK_REJECTED" | "LOCAL_FETCH_NOT_ALLOWED" | "LOCAL_FETCH_OTHER_REJECTION";
  host_type: "loopback";
  method: "POST";
  endpoint_path: "/v1/answers";
  local_session_present: boolean;
  browser_nonce_present: boolean;
  abort_signal_fired: boolean;
  request_timeout_configured: boolean;
  frontend_state: "AUTHENTICATED_REQUEST";
  classification: "FETCH_ABORTED" | "BODY_INIT_INVALID" | "BROWSER_NETWORK_REJECTED" | "ORIGIN_POLICY_REJECTED" | "OTHER_BROWSER_FETCH_FAILURE";
}

export interface LocalTransportProbeDiagnostic {
  operation: "transport_probe";
  probe_id: "P1" | "P2" | "P3";
  success: boolean;
  exception_name: "None" | "TypeError" | "AbortError" | "NetworkError" | "NotAllowedError" | "UnknownError";
  classification: "PROBE_SUCCEEDED" | "FETCH_ABORTED" | "BODY_INIT_INVALID" | "BROWSER_NETWORK_REJECTED" | "ORIGIN_POLICY_REJECTED" | "OTHER_BROWSER_FETCH_FAILURE";
}

export interface AnswerRequestPreparationDiagnostic {
  operation: "answer_request_preparation";
  body_type: "ArrayBuffer" | "NONE" | "OTHER";
  body_byte_length: number;
  body_detached: boolean;
  request_construction: "SUCCEEDED" | "FAILED";
  exception_name: "None" | "TypeError" | "AbortError" | "NetworkError" | "NotAllowedError" | "UnknownError";
  classification: "REQUEST_CONSTRUCTION_SUCCEEDED" | "REQUEST_CONSTRUCTION_FAILED";
  header_validity: {
    origin: boolean;
    "content-type": boolean;
    "x-zkd-local-session": boolean;
    "x-zkd-timestamp": boolean;
    "x-zkd-nonce": boolean;
    "x-zkd-mac": boolean;
    "x-zkd-protocol-version": boolean;
  };
}

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

  async reportLocalFetchDiagnostic(diagnostic: LocalFetchDiagnostic): Promise<void> {
    await this.reportDiagnostic(diagnostic);
  }

  async reportLocalTransportProbeDiagnostic(diagnostic: LocalTransportProbeDiagnostic): Promise<void> {
    await this.reportDiagnostic(diagnostic);
  }

  async reportAnswerRequestPreparation(diagnostic: AnswerRequestPreparationDiagnostic): Promise<void> {
    await this.reportDiagnostic(diagnostic);
  }

  private async reportDiagnostic(
    diagnostic: LocalFetchDiagnostic | LocalTransportProbeDiagnostic | AnswerRequestPreparationDiagnostic,
  ): Promise<void> {
    const response = await this.request(apiUrl("/api/v1/diagnostics/local-fetch"), {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Origin: window.location.origin },
      body: JSON.stringify(diagnostic),
    });

    if (!response.ok) {
      throw new BrowserComputeError("PLATFORM_UNAVAILABLE", "Local transport diagnostics could not be recorded.", response.status);
    }
  }
}
