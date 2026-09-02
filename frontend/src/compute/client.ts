import { binaryBodyBytes, canonicalTranscript, createBrowserNonce, exactArrayBuffer, hmacSha256Hex, serializeJsonOnce, sha256Hex } from "./crypto";
import { BrowserComputeError, isDeviceInvalidatingCode, isSessionInvalidatingCode } from "./errors";
import { PlatformComputeApi, type PlatformFetch } from "./platform";
import { COMPUTE_PROTOCOL_VERSION, type ComputeClientStatus, type ComputeDevice, type ComputeOperation, type JsonObject, type LocalAnswerRequest, type LocalAnswerResponse, type LocalBootstrapResponse, type LocalComputeDocument, type LocalQueryRequest, type LocalQueryResponse, type LocalSession, type LocalSessionSnapshot, type PlatformGrant } from "./types";

export interface BrowserComputeClientOptions {
  platform?: PlatformComputeApi;
  localFetch?: typeof fetch;
  origin?: string;
  clock?: () => number;
  nonceFactory?: () => string;
}

type RequestBody = Uint8Array | undefined;

function isAdmitted(device: ComputeDevice, operation: ComputeOperation): boolean {
  return device.capabilities?.[operation] === "READY" || device.capabilities?.[operation] === "ADMITTED";
}

function localBaseUrl(device: ComputeDevice, operation: ComputeOperation): string {
  if (device.state === "REVOKED") throw new BrowserComputeError("DEVICE_REVOKED");
  if (device.state === "UPDATE_REQUIRED") throw new BrowserComputeError("UPDATE_REQUIRED");
  if (device.state === "BUSY") throw new BrowserComputeError("DEVICE_BUSY");
  if (device.state !== "READY") throw new BrowserComputeError("DEVICE_OFFLINE");
  if (device.protocol_version !== COMPUTE_PROTOCOL_VERSION || !device.runtime_version) throw new BrowserComputeError("PROTOCOL_VERSION_UNSUPPORTED");
  if (!device.endpoint_generation) throw new BrowserComputeError("ENDPOINT_GENERATION_UNAVAILABLE");
  if (!Number.isInteger(device.endpoint_port) || !device.endpoint_port || device.endpoint_port < 1 || device.endpoint_port > 65535) {
    throw new BrowserComputeError("LOOPBACK_ENDPOINT_UNAVAILABLE");
  }
  if (!isAdmitted(device, operation)) throw new BrowserComputeError("CAPABILITY_UNAVAILABLE");
  return `http://127.0.0.1:${device.endpoint_port}`;
}

function toSnapshot(session: LocalSession): LocalSessionSnapshot {
  return {
    deviceId: session.deviceId,
    endpointGeneration: session.endpointGeneration,
    endpointPort: session.endpointPort,
    baseUrl: session.baseUrl,
    expiresAt: session.expiresAt,
    allowedOperations: session.allowedOperations,
    protocolVersion: session.protocolVersion,
  };
}

function operationFromPath(path: string): ComputeOperation {
  if (path === "/v1/runtime" || path === "/v1/capabilities" || /^\/v1\/jobs\/[^/]+(?::cancel)?$/.test(path)) return "jobs";
  if (path === "/v1/queries") return "retrieval";
  if (path === "/v1/answers") return "answer";
  return "documents";
}

function localAskBody(payload: LocalQueryRequest | LocalAnswerRequest): Uint8Array {
  if (typeof payload.query_text !== "string" || !payload.query_text.trim()) {
    throw new BrowserComputeError("INVALID_REQUEST", "A non-empty query is required.");
  }
  if (Array.isArray(payload.document_ids) && payload.document_ids.length === 0) {
    throw new BrowserComputeError("EMPTY_DOCUMENT_SCOPE", "Select at least one local document or use all local documents.");
  }
  return serializeJsonOnce({
    ...payload,
    ...(Array.isArray(payload.document_ids) ? { document_ids: [...payload.document_ids] } : {}),
  });
}

async function parseLocalResponse<T>(response: Response): Promise<T> {
  let payload: unknown;
  try { payload = await response.json(); } catch { payload = undefined; }
  if (!response.ok) {
    const source = payload as { error?: { code?: string; message?: string }; request_id?: string } | undefined;
    const remoteCode = source?.error?.code;
    if (remoteCode === "CLOCK_SKEW") throw new BrowserComputeError("CLOCK_SKEW", source?.error?.message, response.status, source?.request_id);
    if (isSessionInvalidatingCode(remoteCode)) throw new BrowserComputeError(remoteCode === "SESSION_EXPIRED" ? "SESSION_EXPIRED" : "SESSION_INVALID", source?.error?.message, response.status, source?.request_id);
    if (remoteCode === "UPDATE_REQUIRED") throw new BrowserComputeError("UPDATE_REQUIRED", source?.error?.message, response.status, source?.request_id);
    if (remoteCode === "NOT_PAIRED" || remoteCode === "DEVICE_REVOKED") throw new BrowserComputeError("NOT_PAIRED", source?.error?.message, response.status, source?.request_id);
    if (remoteCode === "OPERATION_NOT_ALLOWED") throw new BrowserComputeError("OPERATION_NOT_ALLOWED", source?.error?.message, response.status, source?.request_id);
    throw new BrowserComputeError("REQUEST_FAILED", source?.error?.message ?? `Local request failed (${response.status})`, response.status, source?.request_id);
  }
  if (payload === undefined) throw new BrowserComputeError("INVALID_LOCAL_RESPONSE", "Expected a JSON local response.", response.status);
  return payload as T;
}

/**
 * Non-visual production browser integration. All session material remains in this
 * object only; consumers receive a redacted snapshot and cannot read its key.
 */
export class BrowserComputeClient {
  private readonly platform: PlatformComputeApi;
  private readonly localFetch: typeof fetch;
  private readonly origin: string;
  private readonly clock: () => number;
  private readonly nonceFactory: () => string;
  private devices = new Map<string, ComputeDevice>();
  private selectedDeviceId: string | null = null;
  private session: LocalSession | null = null;
  private bootstrapInFlight: Promise<LocalSession> | null = null;

  constructor(options: BrowserComputeClientOptions = {}) {
    if (options.origin && options.origin !== window.location.origin) throw new BrowserComputeError("AUTH_FAILED", "Compute requests must use the browser application origin.");
    this.origin = window.location.origin;
    this.platform = options.platform ?? new PlatformComputeApi(fetch as PlatformFetch);
    this.localFetch = options.localFetch ?? fetch;
    this.clock = options.clock ?? (() => Date.now() / 1000);
    this.nonceFactory = options.nonceFactory ?? createBrowserNonce;
  }

  status(): ComputeClientStatus {
    return { selectedDeviceId: this.selectedDeviceId, session: this.session ? toSnapshot(this.session) : null };
  }

  clearSession(): void { this.session = null; }
  /** For future application logout. Nothing is persisted, so this is complete cleanup. */
  logout(): void { this.session = null; this.selectedDeviceId = null; this.devices.clear(); }
  disconnect(): void { this.clearSession(); }
  async connect(operation: ComputeOperation = "jobs", deviceId?: string): Promise<LocalSessionSnapshot> {
    await this.selectDevice(operation, deviceId);
    return toSnapshot(await this.ensureSession(operation, deviceId));
  }

  async discover(): Promise<ComputeDevice[]> {
    const discovered = await this.platform.listDevices();
    this.devices = new Map(discovered.map((device) => [device.device_id, device]));
    if (this.session) {
      const current = this.devices.get(this.session.deviceId);
      if (!current || current.state === "REVOKED" || current.state === "UPDATE_REQUIRED" || current.endpoint_generation !== this.session.endpointGeneration) this.clearSession();
    }
    return discovered;
  }

  async localManifests() { return this.platform.listLocalManifests(); }

  async selectDevice(operation: ComputeOperation, deviceId?: string): Promise<ComputeDevice> {
    if (!this.devices.size) await this.discover();
    if (deviceId) {
      const requested = this.devices.get(deviceId);
      if (!requested) throw new BrowserComputeError("NO_DEVICE", "Selected compute device was not found.");
      localBaseUrl(requested, operation);
      if (this.selectedDeviceId && this.selectedDeviceId !== requested.device_id) this.clearSession();
      this.selectedDeviceId = requested.device_id;
      return requested;
    }
    if (this.selectedDeviceId) {
      const selected = this.devices.get(this.selectedDeviceId);
      if (selected) {
        localBaseUrl(selected, operation);
        return selected;
      }
    }
    const available = Array.from(this.devices.values()).filter((candidate) => {
      try { localBaseUrl(candidate, operation); return true; } catch { return false; }
    });
    if (!available.length) {
      if (Array.from(this.devices.values()).some((device) => device.state === "REVOKED")) throw new BrowserComputeError("DEVICE_REVOKED");
      throw new BrowserComputeError(this.devices.size ? "DEVICE_OFFLINE" : "NO_DEVICE");
    }
    if (available.length > 1) throw new BrowserComputeError("DEVICE_SELECTION_REQUIRED");
    this.selectedDeviceId = available[0].device_id;
    return available[0];
  }

  private sessionIsUsable(operation: ComputeOperation): boolean {
    return Boolean(this.session && this.session.expiresAt > Math.floor(this.clock()) && this.session.allowedOperations.includes(operation));
  }

  async ensureSession(operation: ComputeOperation, deviceId?: string): Promise<LocalSession> {
    if (this.sessionIsUsable(operation) && (!deviceId || this.session?.deviceId === deviceId)) return this.session as LocalSession;
    if (this.session && this.session.expiresAt <= Math.floor(this.clock())) this.clearSession();
    if (this.session && (!deviceId || this.session.deviceId === deviceId) && !this.session.allowedOperations.includes(operation)) {
      throw new BrowserComputeError("OPERATION_NOT_ALLOWED");
    }
    if (this.bootstrapInFlight) return this.bootstrapInFlight;
    this.bootstrapInFlight = this.bootstrap(operation, deviceId).finally(() => { this.bootstrapInFlight = null; });
    return this.bootstrapInFlight;
  }

  private async bootstrap(operation: ComputeOperation, deviceId?: string): Promise<LocalSession> {
    const device = await this.selectDevice(operation, deviceId);
    const baseUrl = localBaseUrl(device, operation);
    const browserNonce = this.nonceFactory();
    let grant: PlatformGrant;
    try { grant = await this.platform.requestLocalSessionGrant(device.device_id, browserNonce); }
    catch (error) { throw error instanceof BrowserComputeError ? error : new BrowserComputeError("PLATFORM_UNAVAILABLE"); }
    if (grant.device_id !== device.device_id || grant.endpoint_generation !== device.endpoint_generation) {
      this.clearSession();
      throw new BrowserComputeError("SESSION_INVALID", "Platform grant does not match the selected device endpoint.");
    }
    let response: Response;
    try {
      response = await this.localFetch(`${baseUrl}/v1/sessions`, {
        method: "POST",
        headers: { Origin: this.origin, "X-ZKD-Local-Grant": grant.local_access_grant, "X-ZKD-Browser-Nonce": browserNonce },
      });
    } catch { throw new BrowserComputeError("LOCAL_COMPUTE_UNAVAILABLE"); }
    const bootstrapped = await parseLocalResponse<LocalBootstrapResponse>(response);
    if (bootstrapped.protocol_version !== COMPUTE_PROTOCOL_VERSION || bootstrapped.endpoint_generation !== device.endpoint_generation) {
      this.clearSession();
      throw new BrowserComputeError("SESSION_INVALID", "Local session response does not match the selected endpoint.");
    }
    const allowed = bootstrapped.allowed_operations.filter((value): value is ComputeOperation => ["documents", "jobs", "retrieval", "answer"].includes(value));
    if (!allowed.includes(operation)) throw new BrowserComputeError("OPERATION_NOT_ALLOWED");
    const session: LocalSession = { deviceId: device.device_id, endpointGeneration: device.endpoint_generation!, endpointPort: device.endpoint_port!, baseUrl, sessionId: bootstrapped.local_session_id, sessionKey: bootstrapped.session_key, expiresAt: bootstrapped.expires_at, allowedOperations: allowed, protocolVersion: bootstrapped.protocol_version };
    this.session = session;
    return session;
  }

  private async localRequest<T>(method: string, path: string, body: RequestBody, headers: Record<string, string> = {}): Promise<T> {
    const operation = operationFromPath(path);
    const session = await this.ensureSession(operation);
    if (!this.sessionIsUsable(operation)) { this.clearSession(); throw new BrowserComputeError("SESSION_EXPIRED"); }
    const rawBody = body ?? new Uint8Array();
    const timestamp = String(Math.floor(this.clock()));
    const nonce = this.nonceFactory();
    let mac: string;
    try { mac = await hmacSha256Hex(session.sessionKey, canonicalTranscript(method, path, timestamp, nonce, await sha256Hex(rawBody))); }
    catch (error) { if ((error as Error).message === "INVALID_REQUEST_PATH") throw new BrowserComputeError("INVALID_REQUEST_PATH"); throw error; }
    let response: Response;
    try {
      response = await this.localFetch(`${session.baseUrl}${path}`, { method, headers: { Origin: this.origin, "X-ZKD-Local-Session": session.sessionId, "X-ZKD-Timestamp": timestamp, "X-ZKD-Nonce": nonce, "X-ZKD-MAC": mac, "X-ZKD-Protocol-Version": session.protocolVersion, ...headers }, body: rawBody.length ? exactArrayBuffer(rawBody) : undefined });
    } catch { throw new BrowserComputeError("LOCAL_COMPUTE_UNAVAILABLE"); }
    try { return await parseLocalResponse<T>(response); }
    catch (error) {
      if (error instanceof BrowserComputeError && (isSessionInvalidatingCode(error.code) || isDeviceInvalidatingCode(error.code))) this.clearSession();
      throw error;
    }
  }

  async runtime() { return this.localRequest<JsonObject>("GET", "/v1/runtime", undefined); }
  async capabilities() { return this.localRequest<JsonObject>("GET", "/v1/capabilities", undefined); }
  async uploadSource(documentId: string, file: Blob | ArrayBuffer | Uint8Array, filename: string) { return this.localRequest<JsonObject>("PUT", `/v1/documents/${encodeURIComponent(documentId)}/source`, await binaryBodyBytes(file), { "Content-Type": "application/pdf", "X-ZKD-Filename": filename }); }
  async listDocuments(): Promise<LocalComputeDocument[]> { return (await this.localRequest<{ documents: LocalComputeDocument[] }>("GET", "/v1/documents", undefined)).documents; }
  async prepareDocument(documentId: string) { return this.localRequest<JsonObject>("POST", `/v1/documents/${encodeURIComponent(documentId)}/prepare`, undefined); }
  async documentState(documentId: string) { return this.localRequest<JsonObject>("GET", `/v1/documents/${encodeURIComponent(documentId)}`, undefined); }
  async deleteDocument(documentId: string) { return this.localRequest<JsonObject>("DELETE", `/v1/documents/${encodeURIComponent(documentId)}`, undefined); }
  async indexDocument(documentId: string) { return this.localRequest<JsonObject>("POST", `/v1/documents/${encodeURIComponent(documentId)}/index`, undefined); }
  async jobState(jobId: string) { return this.localRequest<JsonObject>("GET", `/v1/jobs/${encodeURIComponent(jobId)}`, undefined); }
  async cancelJob(jobId: string) { return this.localRequest<JsonObject>("POST", `/v1/jobs/${encodeURIComponent(jobId)}:cancel`, undefined); }
  async query(payload: LocalQueryRequest): Promise<LocalQueryResponse> { return this.localRequest<LocalQueryResponse>("POST", "/v1/queries", localAskBody(payload), { "Content-Type": "application/json" }); }
  async answer(payload: LocalAnswerRequest): Promise<LocalAnswerResponse> { return this.localRequest<LocalAnswerResponse>("POST", "/v1/answers", localAskBody(payload), { "Content-Type": "application/json" }); }
}
