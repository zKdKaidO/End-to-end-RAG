export const COMPUTE_PROTOCOL_VERSION = "zkd-compute-v1";

export type ComputeOperation = "documents" | "jobs" | "retrieval" | "answer";
export type CapabilityState = "READY" | "ADMITTED" | string;
export type DeviceState =
  | "OFFLINE" | "CONNECTING" | "AUTHENTICATING" | "READY" | "BUSY"
  | "DEGRADED" | "UNAVAILABLE" | "REVOKED" | "UPDATE_REQUIRED" | string;

/** Platform read model. It intentionally contains no local content. */
export interface ComputeDevice {
  device_id: string;
  friendly_label?: string | null;
  credential_epoch?: number;
  state: DeviceState;
  protocol_version: string;
  runtime_version: string;
  endpoint_generation: string | null;
  endpoint_port: number | null;
  capabilities: Record<string, CapabilityState>;
}

export interface LocalManifest {
  document_id: string;
  device_id: string;
  preparation_state: string;
  index_state: string;
  local_availability: string;
  artifact_id: string | null;
  artifact_profile_fingerprint: string | null;
  device_state: DeviceState;
  retrieval_admitted: boolean;
  artifact_compatible: boolean;
  queryable: boolean;
  generation_available: boolean;
}

export interface PlatformGrant {
  local_access_grant: string;
  expires_at: number;
  device_id: string;
  endpoint_generation: string;
}

export interface LocalSessionSnapshot {
  deviceId: string;
  endpointGeneration: string;
  endpointPort: number;
  baseUrl: string;
  expiresAt: number;
  allowedOperations: readonly ComputeOperation[];
  protocolVersion: string;
}

/** Private client state; never expose this value to UI state, storage, or logs. */
export interface LocalSession extends LocalSessionSnapshot {
  sessionId: string;
  sessionKey: string;
}

export interface LocalBootstrapResponse {
  request_id?: string;
  local_session_id: string;
  session_key: string;
  expires_at: number;
  protocol_version: string;
  endpoint_generation: string;
  allowed_operations: string[];
}

export interface ComputeClientStatus {
  selectedDeviceId: string | null;
  session: LocalSessionSnapshot | null;
}

export type JsonObject = Record<string, unknown>;
