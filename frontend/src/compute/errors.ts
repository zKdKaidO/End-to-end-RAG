export type BrowserComputeErrorCode =
  | "NO_DEVICE"
  | "DEVICE_SELECTION_REQUIRED"
  | "DEVICE_OFFLINE"
  | "DEVICE_BUSY"
  | "DEVICE_REVOKED"
  | "UPDATE_REQUIRED"
  | "NOT_PAIRED"
  | "CAPABILITY_UNAVAILABLE"
  | "PROTOCOL_VERSION_UNSUPPORTED"
  | "ENDPOINT_GENERATION_UNAVAILABLE"
  | "LOOPBACK_ENDPOINT_UNAVAILABLE"
  | "SESSION_REQUIRED"
  | "SESSION_EXPIRED"
  | "SESSION_INVALID"
  | "ENDPOINT_CHANGED"
  | "OPERATION_NOT_ALLOWED"
  | "LOCAL_COMPUTE_UNAVAILABLE"
  | "PLATFORM_UNAVAILABLE"
  | "CLOCK_SKEW"
  | "AUTH_FAILED"
  | "PROTOCOL_MISMATCH"
  | "REQUEST_FAILED"
  | "INVALID_LOCAL_RESPONSE"
  | "INVALID_REQUEST_PATH";

export class BrowserComputeError extends Error {
  constructor(
    public readonly code: BrowserComputeErrorCode,
    message?: string,
    public readonly status?: number,
    public readonly requestId?: string,
  ) {
    super(message ?? code);
    this.name = "BrowserComputeError";
  }
}

export function isSessionInvalidatingCode(code?: string): boolean {
  return ["SESSION_EXPIRED", "SESSION_BINDING_INVALID", "ENDPOINT_GENERATION_MISMATCH", "AUTH_REQUIRED", "AUTH_INVALID", "CLOCK_SKEW"].includes(code ?? "");
}

export function isDeviceInvalidatingCode(code?: string): boolean {
  return ["NOT_PAIRED", "DEVICE_REVOKED", "UPDATE_REQUIRED"].includes(code ?? "");
}
