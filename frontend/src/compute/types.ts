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

/** Authoritative metadata from the selected local Compute catalog, never a cloud manifest. */
export interface LocalComputeDocument {
  document_id: string;
  original_filename: string;
  byte_size: number;
  preparation_state: "ACCEPTED" | "PROCESSING" | "CHUNKING" | "VALIDATING" | "PREPARED_NOT_INDEXED" | "INDEXING" | "INDEX_READY" | "FAILED" | string;
  index_state: "NOT_READY" | "NOT_INDEXED" | "INDEXING" | "INDEX_READY" | string;
  last_error_code: string | null;
  created_at: number;
  updated_at: number;
  page_count: number;
  chunk_count: number;
}

export interface ComputeClientStatus {
  selectedDeviceId: string | null;
  session: LocalSessionSnapshot | null;
}

export type JsonObject = Record<string, unknown>;

/**
 * Browser-facing request for the authenticated local retrieval route. Omit
 * `document_ids` (or pass null) for all queryable documents on the selected
 * device. An empty array is deliberately not a valid product scope: the local
 * runtime treats it as all documents, which would turn a zero-selection UI
 * state into an unintended broad query.
 */
export interface LocalQueryRequest {
  query_text: string;
  document_ids?: readonly string[] | null;
}

export interface LocalRetrievedCandidate {
  chunk_id: string;
  document_id: string;
  artifact_id: string;
  legal_unit_id: string | null;
  content_text: string;
  metadata_json: JsonObject;
  provenance_json: JsonObject;
  dense_score: number | null;
  dense_rank: number | null;
  lexical_score: number | null;
  lexical_rank: number | null;
  fusion_score: number;
  retrieval_final_rank: number;
  final_rank: number;
  context_candidate_order: number;
  candidate_origin: string;
  hierarchy_relation: string | null;
  hierarchy_depth: number;
  anchor_chunk_id: string | null;
  anchor_legal_unit_id: string | null;
  anchor_retrieval_final_rank: number | null;
  hierarchy_anchor_references: string[];
}

export interface LocalQueryResponse {
  request_id: string;
  results: LocalRetrievedCandidate[];
  hierarchy: JsonObject;
}

export type LocalGenerationRoutingPolicy =
  | "LOCAL_ONLY"
  | "USER_CLOUD_ONLY"
  | "PREFER_LOCAL"
  | "PREFER_USER_CLOUD";

/** The local route accepts only a preconfigured provider identity, never a credential or endpoint. */
export interface LocalAnswerRequest extends LocalQueryRequest {
  routing_policy?: LocalGenerationRoutingPolicy;
  provider_config_id?: string;
  allow_user_cloud_fallback?: boolean;
  allow_local_fallback?: boolean;
}

export interface LocalCitation {
  source_id: string;
  chunk_id: string;
  document_id: string;
  metadata_json: JsonObject;
  provenance_json: JsonObject;
}

export interface LocalGenerationUsage {
  input_tokens: number | null;
  output_tokens: number | null;
  total_tokens: number | null;
}

export interface LocalGenerationResult {
  request_id: string;
  status: "COMPLETED" | "COMPLETED_WITH_WARNINGS" | "INSUFFICIENT_EVIDENCE";
  answer_text: string;
  citations: LocalCitation[];
  invalid_citations: string[];
  citation_validation: "PASS" | "INVALID_REFERENCES" | "MISSING_CITATIONS";
  model_id: string;
  prompt_version: string;
  finish_reason: string | null;
  usage: LocalGenerationUsage | null;
  answerability_status: "ANSWERABLE" | "INSUFFICIENT_EVIDENCE" | null;
  answerability_validation: string;
}

export interface LocalAnswerResponse {
  request_id: string;
  provider: "LOCAL" | "USER_CLOUD";
  provider_type: "LOCAL" | "USER_CLOUD";
  provider_config_id: string | null;
  model_id: string;
  result: LocalGenerationResult;
  hierarchy: JsonObject;
  timings: Record<string, number | null>;
  routing: {
    policy: LocalGenerationRoutingPolicy;
    selected_provider_type: "LOCAL" | "USER_CLOUD";
    provider_config_id?: string | null;
    fallback_occurred: boolean;
    privacy_boundary: "LOCAL_DEVICE" | "USER_CLOUD_EXTERNAL";
  };
}
